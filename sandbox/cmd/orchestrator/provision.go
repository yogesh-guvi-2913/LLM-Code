package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"

	"github.com/guvi-geek/flash/internal/cluster"
	dk "github.com/guvi-geek/flash/internal/docker"
	"github.com/guvi-geek/flash/internal/pool"
	"github.com/guvi-geek/flash/internal/store"
)

// Scorer resource limits. The frontend vitest harness spawns a worker pool +
// esbuild, so it needs many more than a handful of pids — 50 starves it ("no test
// report produced" → a wrong 0). These cover the heaviest (vitest) suite; the
// lighter single-process API scorers use the same headroom harmlessly.
const (
	scorerMemMB int64 = 512
	scorerPids  int64 = 256
)

// Placement is where a claimed sandbox physically lives. In single-node mode the
// node fields are empty/local; in cluster mode they identify the owning node-agent
// so release / snapshot / score route back to it and the preview / terminal proxies
// know which host:port to reach. It is persisted on the session (durable routing).
type Placement struct {
	Node        string // node id ("" = local)
	NodeAddr    string // node-agent base URL ("" = local)
	Host        string // host the published sandbox ports are reachable on
	ContainerID string
	HostApp     int
	HostToolbox int
	Cold        bool
}

// NodeView is the dashboard-facing snapshot of a sandbox runner. In local mode it
// is a single synthetic node ("local"); in cluster mode, one per live node-agent.
type NodeView struct {
	ID         string         `json:"id"`
	Host       string         `json:"host"`
	Addr       string         `json:"addr"`
	Mode       string         `json:"mode"` // "local" | "cluster"
	MemTotalMB int64          `json:"mem_total_mb"`
	MemFreeMB  int64          `json:"mem_free_mb"`
	Active     int            `json:"active"`
	Warm       map[string]int `json:"warm"`
	LastSeen   int64          `json:"last_seen_unix"`
}

// ExecRequest is a command to run inside a live sandbox. Cmd is argv (never a
// shell string — callers wanting a shell pass ["sh","-c",…] explicitly). Cwd
// defaults to the sandbox work dir; Env entries are KEY=VALUE.
type ExecRequest struct {
	Cmd []string `json:"cmd"`
	Cwd string   `json:"cwd,omitempty"`
	Env []string `json:"env,omitempty"`
}

// ExecResult carries both output streams and the real exit code back to the SDK.
type ExecResult struct {
	Stdout   string `json:"stdout"`
	Stderr   string `json:"stderr"`
	ExitCode int    `json:"exit_code"`
}

// Provisioner is the seam between the control plane and where sandboxes actually
// run. localProvisioner runs them in-process (single node, the v1 path, unchanged
// behaviour). clusterProvisioner schedules them across node-agents over Redis +
// HTTP — the same control-plane code, now horizontally scalable.
type Provisioner interface {
	Claim(ctx context.Context, question, candidate, sessionID, token string) (Placement, error)
	Release(ctx context.Context, pl Placement)
	Snapshot(ctx context.Context, pl Placement) ([]byte, error)
	Score(ctx context.Context, pl Placement, question string, srcTar []byte) ([]byte, error)
	SetMinWarm(ctx context.Context, question string, n int) bool
	// Playground file ops on a live sandbox (rel is a sanitized relative path).
	Files(ctx context.Context, pl Placement) ([]string, error)
	ReadFile(ctx context.Context, pl Placement, rel string) ([]byte, error)
	WriteFile(ctx context.Context, pl Placement, rel string, content []byte) error
	DeleteFile(ctx context.Context, pl Placement, rel string) error
	// Exec runs a command in a live sandbox and returns both streams + exit code
	// (the SDK contract: a non-zero exit is a result, not an error).
	Exec(ctx context.Context, pl Placement, req ExecRequest) (ExecResult, error)
	WarmCount(ctx context.Context) map[string]int
	ActiveCount(ctx context.Context) map[string]int
	LiveMem(ctx context.Context) (totalBytes int64, count int)
	Nodes(ctx context.Context) ([]NodeView, error) // fleet view for the dashboard
	Maintain(ctx context.Context)                  // periodic replenish + health sweep
	Reconcile(ctx context.Context)                 // rebuild routing/pool from durable truth on boot
}

// ---------------- local (single-node) ----------------

type localProvisioner struct {
	pool   *pool.Manager
	docker *dk.Client
	reg    *registry
	store  *store.Store
	log    interface {
		Warn(string, ...any)
		Info(string, ...any)
	}
}

func (p *localProvisioner) Claim(ctx context.Context, q, cand, sid, tok string) (Placement, error) {
	res, err := p.pool.Claim(ctx, q, cand, sid, tok)
	if err != nil {
		return Placement{}, err
	}
	return Placement{
		Host: "127.0.0.1", ContainerID: res.ContainerID,
		HostApp: res.HostApp, HostToolbox: res.HostToolbox, Cold: res.Cold,
	}, nil
}

func (p *localProvisioner) Release(_ context.Context, pl Placement) { p.pool.Release(pl.ContainerID) }

func (p *localProvisioner) Snapshot(ctx context.Context, pl Placement) ([]byte, error) {
	return p.pool.Snapshot(ctx, pl.ContainerID)
}

func (p *localProvisioner) Score(ctx context.Context, _ Placement, question string, srcTar []byte) ([]byte, error) {
	return p.docker.RunScorer(ctx, p.reg.scorer(question), srcTar,
		[]string{"sh", "/harness/run-tests.sh"}, scorerMemMB, scorerPids, 120*time.Second)
}

func (p *localProvisioner) SetMinWarm(ctx context.Context, q string, n int) bool {
	if !p.pool.SetMinWarm(q, n) {
		return false
	}
	go p.pool.Replenish(context.Background(), q)
	return true
}

func (p *localProvisioner) Files(ctx context.Context, pl Placement) ([]string, error) {
	return p.docker.ListCandidateFiles(ctx, pl.ContainerID)
}
func (p *localProvisioner) ReadFile(ctx context.Context, pl Placement, rel string) ([]byte, error) {
	return p.docker.ReadCandidateFile(ctx, pl.ContainerID, rel)
}
func (p *localProvisioner) WriteFile(ctx context.Context, pl Placement, rel string, content []byte) error {
	return p.docker.WriteCandidateFile(ctx, pl.ContainerID, rel, content)
}
func (p *localProvisioner) DeleteFile(ctx context.Context, pl Placement, rel string) error {
	return p.docker.DeleteCandidateFile(ctx, pl.ContainerID, rel)
}

func (p *localProvisioner) Exec(ctx context.Context, pl Placement, req ExecRequest) (ExecResult, error) {
	res, err := p.docker.ExecRun(ctx, pl.ContainerID, req.Cmd, req.Cwd, req.Env)
	if err != nil {
		return ExecResult{}, err
	}
	return ExecResult{Stdout: string(res.Stdout), Stderr: string(res.Stderr), ExitCode: res.ExitCode}, nil
}

func (p *localProvisioner) WarmCount(context.Context) map[string]int   { return p.pool.WarmCount() }
func (p *localProvisioner) ActiveCount(context.Context) map[string]int { return p.pool.ActiveCount() }

func (p *localProvisioner) LiveMem(ctx context.Context) (int64, int) {
	var total int64
	var n int
	for _, id := range p.pool.LiveContainerIDs() {
		if mem, err := p.docker.ContainerMem(ctx, id); err == nil {
			total += mem
			n++
		}
	}
	return total, n
}

// Nodes presents the single local box as one node, so the dashboard's Fleet view
// works identically in local and cluster mode.
func (p *localProvisioner) Nodes(ctx context.Context) ([]NodeView, error) {
	warm := p.pool.WarmCount()
	active := 0
	for _, n := range p.pool.ActiveCount() {
		active += n
	}
	return []NodeView{{
		ID: "local", Host: "127.0.0.1", Addr: "in-process", Mode: "local",
		MemTotalMB: 0, MemFreeMB: 0, Active: active, Warm: warm,
		LastSeen: 0, // n/a for the in-process node
	}}, nil
}

func (p *localProvisioner) Maintain(ctx context.Context) {
	p.pool.HealthSweep(ctx)
	for _, q := range p.reg.ids() {
		p.pool.Replenish(ctx, q)
	}
}

// Reconcile rebuilds the in-process pool from Docker + Postgres after a restart so
// live sessions survive (see Phase 1). Unchanged logic, now behind the interface.
func (p *localProvisioner) Reconcile(ctx context.Context) {
	live, err := p.docker.ListSandboxes(ctx)
	if err != nil {
		p.log.Warn("reconcile: list sandboxes failed, skipping", "err", err)
		return
	}
	actives, err := p.store.ActiveSessions(ctx)
	if err != nil {
		p.log.Warn("reconcile: active sessions query failed, skipping", "err", err)
		return
	}
	byContainer := make(map[string]store.Session, len(actives))
	for _, ss := range actives {
		if ss.ContainerID != "" {
			byContainer[ss.ContainerID] = ss
		}
	}
	seen := map[string]bool{}
	var adoptedActive, adoptedWarm, reaped int
	for _, sb := range live {
		cfg, ok := p.reg.config(sb.Question)
		if !ok {
			_ = p.docker.Remove(ctx, sb.ID)
			reaped++
			continue
		}
		hostApp := sb.Ports[cfg.AppPort]
		hostTB := sb.Ports[cfg.ToolboxPort]
		if sess, claimed := byContainer[sb.ID]; claimed {
			seen[sb.ID] = true
			if !sb.Running || hostApp == 0 || hostTB == 0 {
				p.log.Warn("reconcile: active container unusable, destroying session",
					"session", sess.ID, "container", short(sb.ID), "running", sb.Running)
				_ = p.docker.Remove(ctx, sb.ID)
				_ = p.store.MarkDestroyed(ctx, sess.ID)
				reaped++
				continue
			}
			p.pool.AdoptActive(sb.Question, sb.ID, hostApp, hostTB)
			adoptedActive++
			continue
		}
		if sb.Running && hostApp != 0 && hostTB != 0 && p.pool.AdoptWarm(sb.Question, sb.ID, hostApp, hostTB) {
			adoptedWarm++
		} else {
			_ = p.docker.Remove(ctx, sb.ID)
			reaped++
		}
	}
	for cid, sess := range byContainer {
		if !seen[cid] {
			p.log.Warn("reconcile: active session has no live container, marking destroyed", "session", sess.ID)
			_ = p.store.MarkDestroyed(ctx, sess.ID)
		}
	}
	p.log.Info("reconciled", "adopted_active", adoptedActive, "adopted_warm", adoptedWarm, "reaped", reaped)
}

// ---------------- cluster (multi-node) ----------------

type clusterProvisioner struct {
	reg   *cluster.Registry
	tmpl  *registry // template configs (mem per question, scorer image)
	store *store.Store
	http  *http.Client
	log   interface {
		Warn(string, ...any)
		Info(string, ...any)
		Error(string, ...any)
	}
}

func (p *clusterProvisioner) needMB(question string) int64 {
	if cfg, ok := p.tmpl.config(question); ok {
		return cfg.MemoryMB
	}
	return 512
}

func (p *clusterProvisioner) Claim(ctx context.Context, q, cand, sid, tok string) (Placement, error) {
	if _, ok := p.tmpl.config(q); !ok {
		return Placement{}, pool.ErrUnknownQuestion
	}
	node, err := p.reg.PickNode(ctx, q, p.needMB(q))
	if err != nil {
		return Placement{}, fmt.Errorf("schedule: %w", err)
	}
	body, _ := json.Marshal(map[string]string{
		"QuestionID": q, "CandidateID": cand, "SessionID": sid, "Token": tok,
	})
	var out struct {
		NodeID      string `json:"node_id"`
		Host        string `json:"host"`
		ContainerID string `json:"container_id"`
		HostApp     int    `json:"host_app"`
		HostToolbox int    `json:"host_toolbox"`
		Cold        bool   `json:"cold"`
	}
	if err := p.call(ctx, http.MethodPost, node.Addr+"/claim", bytes.NewReader(body), &out); err != nil {
		return Placement{}, fmt.Errorf("node %s claim: %w", node.ID, err)
	}
	return Placement{
		Node: out.NodeID, NodeAddr: node.Addr, Host: out.Host, ContainerID: out.ContainerID,
		HostApp: out.HostApp, HostToolbox: out.HostToolbox, Cold: out.Cold,
	}, nil
}

func (p *clusterProvisioner) Release(ctx context.Context, pl Placement) {
	if pl.NodeAddr == "" || pl.ContainerID == "" {
		return
	}
	_ = p.call(ctx, http.MethodDelete, pl.NodeAddr+"/sandbox/"+pl.ContainerID, nil, nil)
}

func (p *clusterProvisioner) Snapshot(ctx context.Context, pl Placement) ([]byte, error) {
	return p.raw(ctx, http.MethodPost, pl.NodeAddr+"/sandbox/"+pl.ContainerID+"/snapshot", nil)
}

func (p *clusterProvisioner) Score(ctx context.Context, pl Placement, question string, srcTar []byte) ([]byte, error) {
	return p.raw(ctx, http.MethodPost, pl.NodeAddr+"/score?question="+question, bytes.NewReader(srcTar))
}

// SetMinWarm fans the new warm floor out to every live node — the fleet-wide knob
// scheduled scaling drives. Returns true if at least one node accepted it.
func (p *clusterProvisioner) SetMinWarm(ctx context.Context, q string, n int) bool {
	nodes, err := p.reg.LiveNodes(ctx)
	if err != nil {
		return false
	}
	body, _ := json.Marshal(map[string]any{"question": q, "min_warm": n})
	ok := false
	for _, nd := range nodes {
		if err := p.call(ctx, http.MethodPost, nd.Addr+"/scale", bytes.NewReader(body), nil); err == nil {
			ok = true
		}
	}
	return ok
}

func (p *clusterProvisioner) Files(ctx context.Context, pl Placement) ([]string, error) {
	var out struct {
		Files []string `json:"files"`
	}
	err := p.call(ctx, http.MethodGet, pl.NodeAddr+"/sandbox/"+pl.ContainerID+"/files", nil, &out)
	return out.Files, err
}
func (p *clusterProvisioner) ReadFile(ctx context.Context, pl Placement, rel string) ([]byte, error) {
	return p.raw(ctx, http.MethodGet, pl.NodeAddr+"/sandbox/"+pl.ContainerID+"/file?path="+url.QueryEscape(rel), nil)
}
func (p *clusterProvisioner) WriteFile(ctx context.Context, pl Placement, rel string, content []byte) error {
	_, err := p.raw(ctx, http.MethodPut, pl.NodeAddr+"/sandbox/"+pl.ContainerID+"/file?path="+url.QueryEscape(rel), bytes.NewReader(content))
	return err
}
func (p *clusterProvisioner) DeleteFile(ctx context.Context, pl Placement, rel string) error {
	_, err := p.raw(ctx, http.MethodDelete, pl.NodeAddr+"/sandbox/"+pl.ContainerID+"/file?path="+url.QueryEscape(rel), nil)
	return err
}

func (p *clusterProvisioner) Exec(ctx context.Context, pl Placement, req ExecRequest) (ExecResult, error) {
	body, _ := json.Marshal(req)
	var out ExecResult
	err := p.call(ctx, http.MethodPost, pl.NodeAddr+"/sandbox/"+pl.ContainerID+"/exec", bytes.NewReader(body), &out)
	return out, err
}

func (p *clusterProvisioner) WarmCount(ctx context.Context) map[string]int {
	w, err := p.reg.TotalWarm(ctx)
	if err != nil {
		return map[string]int{}
	}
	return w
}

// ActiveCount comes from the durable session ledger (the registry tracks only a
// per-node total, not per-question).
func (p *clusterProvisioner) ActiveCount(ctx context.Context) map[string]int {
	m, err := p.store.ActiveCountsByQuestion(ctx)
	if err != nil {
		return map[string]int{}
	}
	return m
}

// LiveMem in cluster mode reports the fleet's COMMITTED memory (reserved = total −
// free) and live container count from the registry; per-container measured RSS is a
// per-node concern (each node-agent could expose it). Count = active + warm.
func (p *clusterProvisioner) LiveMem(ctx context.Context) (int64, int) {
	nodes, err := p.reg.LiveNodes(ctx)
	if err != nil {
		return 0, 0
	}
	var reservedMB int64
	var count int
	warm, _ := p.reg.TotalWarm(ctx)
	for _, n := range nodes {
		reservedMB += n.MemTotalMB - n.MemFreeMB
		count += n.ActiveN
	}
	for _, c := range warm {
		count += c
	}
	return reservedMB * (1 << 20), count
}

// Nodes lists every live node-agent with its capacity + per-node warm depth.
func (p *clusterProvisioner) Nodes(ctx context.Context) ([]NodeView, error) {
	nodes, err := p.reg.LiveNodes(ctx)
	if err != nil {
		return nil, err
	}
	out := make([]NodeView, 0, len(nodes))
	for _, n := range nodes {
		warm, _ := p.reg.NodeWarmAll(ctx, n.ID)
		out = append(out, NodeView{
			ID: n.ID, Host: n.Host, Addr: n.Addr, Mode: "cluster",
			MemTotalMB: n.MemTotalMB, MemFreeMB: n.MemFreeMB,
			Active: n.ActiveN, Warm: warm, LastSeen: n.LastSeen,
		})
	}
	return out, nil
}

// Maintain is a no-op for the control plane: each node-agent runs its own health
// sweep + replenish loop locally.
func (p *clusterProvisioner) Maintain(context.Context) {}

// Reconcile in cluster mode is light: the durable session→node routing already
// lives in Postgres, and node-agents own their own container truth. We just log the
// live fleet so a restarted control plane is observably back in business.
func (p *clusterProvisioner) Reconcile(ctx context.Context) {
	nodes, err := p.reg.LiveNodes(ctx)
	if err != nil {
		p.log.Warn("cluster reconcile: list nodes failed", "err", err)
		return
	}
	p.log.Info("cluster reconcile", "live_nodes", len(nodes))
}

// call does a JSON request, decoding into out (if non-nil) and surfacing non-2xx.
func (p *clusterProvisioner) call(ctx context.Context, method, url string, body io.Reader, out any) error {
	req, err := http.NewRequestWithContext(ctx, method, url, body)
	if err != nil {
		return err
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	resp, err := p.http.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		b, _ := io.ReadAll(io.LimitReader(resp.Body, 2048))
		return fmt.Errorf("%s -> %d: %s", url, resp.StatusCode, bytes.TrimSpace(b))
	}
	if out != nil {
		return json.NewDecoder(resp.Body).Decode(out)
	}
	return nil
}

// raw does a request and returns the raw response body (snapshot tar / scorer out).
func (p *clusterProvisioner) raw(ctx context.Context, method, url string, body io.Reader) ([]byte, error) {
	req, err := http.NewRequestWithContext(ctx, method, url, body)
	if err != nil {
		return nil, err
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/octet-stream")
	}
	resp, err := p.http.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		b, _ := io.ReadAll(io.LimitReader(resp.Body, 2048))
		return nil, fmt.Errorf("%s -> %d: %s", url, resp.StatusCode, bytes.TrimSpace(b))
	}
	return io.ReadAll(resp.Body)
}
