// Command node-agent is the per-box sandbox runner. It owns the local Docker
// socket and a warm pool, exposes a small HTTP API the control plane calls to
// claim / release / snapshot / score sandboxes, and heartbeats its capacity to
// Redis so the scheduler can place work on it.
//
// This is the split that turns Flash's ~one-box ceiling into "add boxes": the
// control plane no longer touches Docker directly; it picks a node from the
// registry and forwards the claim here. Many node-agents → many boxes → the
// concurrency unlock.
//
//	control plane ──HTTP──> node-agent ──Docker──> sandboxes
//	         (schedules)          (this binary)      (warm/active)
//	              └────────── Redis registry ──────────┘  (capacity + liveness)
package main

import (
	"context"
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"sync/atomic"
	"syscall"
	"time"

	"github.com/guvi-geek/flash/internal/cluster"
	dk "github.com/guvi-geek/flash/internal/docker"
	"github.com/guvi-geek/flash/internal/pool"
	"github.com/guvi-geek/flash/internal/templates"
)

type agent struct {
	log      *slog.Logger
	pool     *pool.Manager
	docker   *dk.Client
	reg      *cluster.Registry
	cfgs     map[string]pool.QuestionConfig
	images   map[string]string // questionID -> scorer image
	nodeID   string
	nodeMB   int64 // advertised memory budget for this node
	host     string
	addr     string // base URL the control plane reaches this agent on
	draining atomic.Bool
}

// activeTotal sums live sandboxes on this node.
func (a *agent) activeTotal() int {
	n := 0
	for _, c := range a.pool.ActiveCount() {
		n += c
	}
	return n
}

func main() {
	log := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))

	nodeID := env("NODE_ID", "node-1")
	listen := env("NODE_LISTEN", ":9001")
	host := env("NODE_HOST", "127.0.0.1")                  // host the published sandbox ports are reachable on
	advAddr := env("NODE_ADDR", "http://127.0.0.1"+listen) // how the control plane reaches THIS agent
	redisURL := env("REDIS_URL", "redis://127.0.0.1:6380/0")
	network := env("SANDBOX_NET", "sandbox-net")
	runtime := env("SANDBOX_RUNTIME", "")
	previewPort := env("PREVIEW_PORT", "8090")
	nodeMB := int64(envInt("NODE_MEM_MB", 4096))
	portLo := envInt("NODE_PORT_LO", 20000)
	portHi := envInt("NODE_PORT_HI", 29000)
	drainTimeout := time.Duration(envInt("NODE_DRAIN_TIMEOUT_SEC", 120)) * time.Second

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	d, err := dk.New()
	if err != nil {
		log.Error("docker", "err", err)
		os.Exit(1)
	}
	defer d.Close()

	reg, err := cluster.New(redisURL, 5*time.Second)
	if err != nil {
		log.Error("redis", "err", err)
		os.Exit(1)
	}
	if err := reg.Ping(ctx); err != nil {
		log.Error("redis ping", "err", err)
		os.Exit(1)
	}
	defer reg.Close()

	// Seed pool configs from the shared template set.
	cfgs := map[string]pool.QuestionConfig{}
	images := map[string]string{}
	for _, t := range templates.Default() {
		cfgs[t.ID] = templates.Config(t, runtime, previewPort)
		images[t.ID] = t.Image
	}
	pm := pool.New(log, d, network, cfgs)
	pm.SetNode(nodeID)
	pm.SetPortRange(portLo, portHi)

	a := &agent{
		log: log, pool: pm, docker: d, reg: reg, cfgs: cfgs, images: images,
		nodeID: nodeID, nodeMB: nodeMB, host: host, addr: advAddr,
	}

	// Clean slate: reap only THIS node's leftover containers (shared-daemon safe).
	a.reapOwn(ctx)

	for q := range cfgs {
		pm.Replenish(ctx, q)
	}

	go a.heartbeatLoop(ctx)
	go a.maintenanceLoop(ctx)

	mux := http.NewServeMux()
	mux.HandleFunc("POST /claim", a.claim)
	mux.HandleFunc("DELETE /sandbox/{id}", a.release)
	mux.HandleFunc("POST /sandbox/{id}/snapshot", a.snapshot)
	mux.HandleFunc("GET /sandbox/{id}/files", a.files)
	mux.HandleFunc("GET /sandbox/{id}/file", a.readFile)
	mux.HandleFunc("PUT /sandbox/{id}/file", a.writeFile)
	mux.HandleFunc("DELETE /sandbox/{id}/file", a.deleteFile)
	mux.HandleFunc("POST /sandbox/{id}/exec", a.exec)
	mux.HandleFunc("POST /score", a.score)
	mux.HandleFunc("POST /scale", a.scale)
	mux.HandleFunc("GET /stats", a.stats)
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, r *http.Request) { _, _ = w.Write([]byte("ok")) })
	// Readiness flips to 503 the instant we start draining, so the ALB/ASG health
	// check pulls this node out of rotation while it finishes its active sessions.
	mux.HandleFunc("GET /readyz", func(w http.ResponseWriter, r *http.Request) {
		if a.draining.Load() {
			http.Error(w, "draining", http.StatusServiceUnavailable)
			return
		}
		_, _ = w.Write([]byte("ready"))
	})

	srv := &http.Server{Addr: listen, Handler: mux}
	go func() {
		log.Info("node-agent listening", "node", nodeID, "addr", listen, "advertise", advAddr, "host", host)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Error("http", "err", err)
			stop()
		}
	}()

	<-ctx.Done()
	// Graceful scale-in (ASG lifecycle hook → SIGTERM): stop taking new work and
	// pull out of rotation, but keep serving so this node's ACTIVE sessions finish
	// (their candidates can still save / submit / be snapshotted). Only once they
	// drain — or the bound elapses — do we stop the listener and exit, letting the
	// ASG terminate the instance.
	a.draining.Store(true)
	dctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	_ = reg.Deregister(dctx, nodeID) // scheduler stops placing work here
	cancel()
	log.Info("node-agent draining", "node", nodeID, "active", a.activeTotal(), "timeout", drainTimeout)

	deadline := time.Now().Add(drainTimeout)
	for a.activeTotal() > 0 && time.Now().Before(deadline) {
		time.Sleep(2 * time.Second)
	}
	if n := a.activeTotal(); n > 0 {
		log.Warn("drain timeout — exiting with active sessions still live", "node", nodeID, "active", n)
	} else {
		log.Info("node drained — no active sessions", "node", nodeID)
	}
	sctx, scancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer scancel()
	_ = srv.Shutdown(sctx)
	log.Info("node-agent stopped", "node", nodeID)
}

// --- HTTP handlers ---

func (a *agent) claim(w http.ResponseWriter, r *http.Request) {
	if a.draining.Load() {
		http.Error(w, "node draining", http.StatusServiceUnavailable)
		return
	}
	var req struct {
		QuestionID, CandidateID, SessionID, Token string
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "bad json", http.StatusBadRequest)
		return
	}
	res, err := a.pool.Claim(r.Context(), req.QuestionID, req.CandidateID, req.SessionID, req.Token)
	if err != nil {
		a.log.Error("claim failed", "question", req.QuestionID, "err", err)
		http.Error(w, err.Error(), http.StatusServiceUnavailable)
		return
	}
	go a.heartbeat(context.Background()) // publish reduced capacity promptly
	writeJSON(w, http.StatusOK, map[string]any{
		"node_id": a.nodeID, "host": a.host,
		"container_id": res.ContainerID, "host_app": res.HostApp,
		"host_toolbox": res.HostToolbox, "cold": res.Cold,
	})
}

func (a *agent) release(w http.ResponseWriter, r *http.Request) {
	a.pool.Release(r.PathValue("id"))
	go a.heartbeat(context.Background())
	w.WriteHeader(http.StatusNoContent)
}

func (a *agent) snapshot(w http.ResponseWriter, r *http.Request) {
	tar, err := a.pool.Snapshot(r.Context(), r.PathValue("id"))
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/octet-stream")
	_, _ = w.Write(tar)
}

// score runs the one-shot, network-isolated scorer for a submission tar on this
// node (it already has the image). Body is the /app/src tar; query ?question=….
func (a *agent) score(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query().Get("question")
	img, ok := a.images[q]
	if !ok {
		http.Error(w, "unknown question", http.StatusNotFound)
		return
	}
	src, err := io.ReadAll(io.LimitReader(r.Body, 32<<20))
	if err != nil {
		http.Error(w, "read body", http.StatusBadRequest)
		return
	}
	out, err := a.docker.RunScorer(r.Context(), img, src,
		[]string{"sh", "/harness/run-tests.sh"}, 512, 256, 120*time.Second)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/octet-stream")
	_, _ = w.Write(out)
}

// files/readFile/writeFile back the playground. Paths are sanitized at the control
// plane before they reach here; the exec passes them as positional args anyway.
func (a *agent) files(w http.ResponseWriter, r *http.Request) {
	list, err := a.docker.ListCandidateFiles(r.Context(), r.PathValue("id"))
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"files": list})
}

func (a *agent) readFile(w http.ResponseWriter, r *http.Request) {
	b, err := a.docker.ReadCandidateFile(r.Context(), r.PathValue("id"), r.URL.Query().Get("path"))
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/octet-stream")
	_, _ = w.Write(b)
}

func (a *agent) writeFile(w http.ResponseWriter, r *http.Request) {
	body, err := io.ReadAll(io.LimitReader(r.Body, 4<<20))
	if err != nil {
		http.Error(w, "read body", http.StatusBadRequest)
		return
	}
	if err := a.docker.WriteCandidateFile(r.Context(), r.PathValue("id"), r.URL.Query().Get("path"), body); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

func (a *agent) deleteFile(w http.ResponseWriter, r *http.Request) {
	if err := a.docker.DeleteCandidateFile(r.Context(), r.PathValue("id"), r.URL.Query().Get("path")); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

// exec runs a command in a live sandbox and returns stdout/stderr/exit code —
// the node-side half of the SDK's Exec. A non-zero exit is a 200 with the code.
func (a *agent) exec(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Cmd []string `json:"cmd"`
		Cwd string   `json:"cwd"`
		Env []string `json:"env"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil || len(req.Cmd) == 0 {
		http.Error(w, "cmd (argv) required", http.StatusBadRequest)
		return
	}
	res, err := a.docker.ExecRun(r.Context(), r.PathValue("id"), req.Cmd, req.Cwd, req.Env)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"stdout": string(res.Stdout), "stderr": string(res.Stderr), "exit_code": res.ExitCode,
	})
}

func (a *agent) scale(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Question string `json:"question"`
		MinWarm  int    `json:"min_warm"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "bad json", http.StatusBadRequest)
		return
	}
	if !a.pool.SetMinWarm(req.Question, req.MinWarm) {
		http.Error(w, "unknown question", http.StatusNotFound)
		return
	}
	go a.pool.Replenish(context.Background(), req.Question)
	writeJSON(w, http.StatusOK, map[string]any{"question": req.Question, "min_warm": req.MinWarm})
}

func (a *agent) stats(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{
		"node_id": a.nodeID, "warm": a.pool.WarmCount(), "active": a.pool.ActiveCount(),
		"mem_total_mb": a.nodeMB, "mem_free_mb": a.freeMB(),
	})
}

// --- background ---

func (a *agent) freeMB() int64 {
	return max(a.nodeMB-a.pool.ReservedMB(), 0)
}

func (a *agent) heartbeat(ctx context.Context) {
	active := 0
	for _, n := range a.pool.ActiveCount() {
		active += n
	}
	n := cluster.Node{
		ID: a.nodeID, Addr: a.addr, Host: a.host,
		MemTotalMB: a.nodeMB, MemFreeMB: a.freeMB(), ActiveN: active,
	}
	if err := a.reg.Heartbeat(ctx, n, a.pool.WarmCount()); err != nil {
		a.log.Error("heartbeat failed", "err", err)
	}
}

func (a *agent) heartbeatLoop(ctx context.Context) {
	a.heartbeat(ctx) // advertise immediately on boot
	t := time.NewTicker(5 * time.Second)
	defer t.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-t.C:
			a.heartbeat(ctx)
		}
	}
}

func (a *agent) maintenanceLoop(ctx context.Context) {
	t := time.NewTicker(30 * time.Second)
	defer t.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-t.C:
			a.pool.HealthSweep(ctx)
			for q := range a.cfgs {
				a.pool.Replenish(ctx, q)
			}
		}
	}
}

// reapOwn removes only this node's leftover sandboxes on boot — never another
// agent's, even when they share one Docker daemon in the local simulation.
func (a *agent) reapOwn(ctx context.Context) {
	list, err := a.docker.ListSandboxes(ctx)
	if err != nil {
		a.log.Warn("reap: list", "err", err)
		return
	}
	n := 0
	for _, sb := range list {
		if sb.Node == a.nodeID {
			if a.docker.Remove(ctx, sb.ID) == nil {
				n++
			}
		}
	}
	if n > 0 {
		a.log.Info("reaped own leftover sandboxes", "count", n)
	}
}

// --- helpers ---

func writeJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(v)
}

func env(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}

func envInt(k string, def int) int {
	if v := os.Getenv(k); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
	}
	return def
}
