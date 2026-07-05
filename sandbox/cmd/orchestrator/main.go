// Command orchestrator is the single v1 control-plane binary. It merges what the
// production spec splits across API + SQS consumer + scorer: an HTTP API for
// sessions, the in-process warm pool, the background maintenance loops, and the
// scoring path. No SQS, no Redis — direct and synchronous, which is the right
// shape for a single node.
package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"sync/atomic"
	"syscall"
	"time"

	"github.com/guvi-geek/flash/internal/cluster"
	"github.com/guvi-geek/flash/internal/dashboard"
	dk "github.com/guvi-geek/flash/internal/docker"
	"github.com/guvi-geek/flash/internal/metrics"
	"github.com/guvi-geek/flash/internal/pool"
	"github.com/guvi-geek/flash/internal/store"
)

type server struct {
	log                *slog.Logger
	prov               Provisioner // local (in-process pool) or cluster (node-agents)
	pool               *pool.Manager
	store              *store.Store
	docker             *dk.Client
	metrics            *metrics.Metrics
	cost               costModel // node $/hr + RAM, for the derived $/sandbox-hr
	auth               *authn    // operator API-key auth + per-org rate limiting
	defaultConcurrency int       // per-org concurrent-sandbox cap
	cfg                map[string]pool.QuestionConfig
	reg                *registry // runtime-mutable templates + pool/scorer config
	planner            *planner  // scheduled scaling: booked windows → warm floor
	previewDomain      string    // host suffix for the preview vhost, e.g. "preview.localhost"
	previewPort        string    // external port the browser reaches the proxy on
	jobs               *jobGroup // detached background work (async scoring) for drain
	ready              atomic.Bool
}

// templateByID returns the registered template for a question id.
func (s *server) templateByID(id string) (Template, bool) {
	return s.reg.get(id)
}

// previewURL builds the candidate-facing browser-preview URL for a frontend
// session. The token is the left-most host label so the preview authenticates
// inside a cross-origin iframe without cookies (see preview.go). Empty for API
// templates (they are curled on app_url directly).
func (s *server) previewURL(sessionID, token string) string {
	host := token + "." + sessionID + "." + s.previewDomain
	if s.previewPort != "" && s.previewPort != "80" {
		host += ":" + s.previewPort
	}
	return "http://" + host + "/"
}

func main() {
	bootLog := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))

	cfg, err := loadConfig()
	if err != nil {
		bootLog.Error("config", "err", err)
		os.Exit(2)
	}
	log := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: logLevel(cfg.LogLevel)}))

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	st, err := store.New(ctx, cfg.DSN)
	if err != nil {
		log.Error("store", "err", err)
		os.Exit(1)
	}
	defer st.Close()

	reg := newRegistry(defaultTemplates(), cfg.Runtime, cfg.PreviewPort)
	if cfg.Runtime != "" {
		log.Info("using sandbox runtime", "runtime", cfg.Runtime)
	}

	concurrency := cfg.Concurrency
	clusterMode := cfg.ClusterMode
	s := &server{log: log, store: st, reg: reg,
		metrics: metrics.New(), cost: costModel{NodeUSDPerHour: cfg.NodeUSDPerHour, NodeRAMGB: cfg.NodeRAMGB},
		auth:               newAuthn(cfg.AuthEnabled, cfg.RateRPS, cfg.RateBurst),
		defaultConcurrency: concurrency, jobs: &jobGroup{},
		previewDomain: cfg.PreviewDomain, previewPort: cfg.PreviewPort}

	// Provisioner: where sandboxes run. Cluster mode schedules across node-agents
	// over Redis (the control plane needs no Docker); local mode runs an in-process
	// pool (the v1 single-node path, unchanged).
	if clusterMode {
		creg, err := cluster.New(cfg.RedisURL, 5*time.Second)
		if err != nil {
			log.Error("redis", "err", err)
			os.Exit(1)
		}
		if err := creg.Ping(ctx); err != nil {
			log.Error("redis ping", "err", err)
			os.Exit(1)
		}
		defer creg.Close()
		s.prov = &clusterProvisioner{reg: creg, tmpl: reg, store: st,
			http: &http.Client{Timeout: 60 * time.Second}, log: log}
		log.Info("CLUSTER mode — scheduling sandboxes across node-agents via Redis")
	} else {
		d, err := dk.New()
		if err != nil {
			log.Error("docker", "err", err)
			os.Exit(1)
		}
		defer d.Close()
		qcfg := map[string]pool.QuestionConfig{}
		for _, id := range reg.ids() {
			c, _ := reg.config(id)
			qcfg[id] = c
		}
		pm := pool.New(log, d, cfg.Network, qcfg)
		s.pool, s.docker = pm, d
		s.prov = &localProvisioner{pool: pm, docker: d, reg: reg, store: st, log: log}
		log.Info("LOCAL mode — in-process warm pool (single node)")
	}

	s.bootstrapAuth(ctx, concurrency)
	if cfg.AuthEnabled {
		log.Info("operator auth enabled", "per_org_concurrency", concurrency)
	} else {
		log.Warn("operator auth DISABLED — /v1 control plane is open (set AUTH_ENABLED=true)")
	}

	// Reconcile from the durable truth on boot (local: Docker+Postgres re-adopt;
	// cluster: confirm the live fleet). Then warm (local) — in cluster mode the
	// node-agents warm themselves.
	s.prov.Reconcile(ctx)
	if !clusterMode {
		for _, q := range reg.ids() {
			log.Info("warming pool", "question", q)
			s.pool.Replenish(ctx, q)
		}
	}
	// Reconcile + initial warm done: we can serve claims now. /readyz flips to 200,
	// so a load balancer (or the ASG health check) only sends traffic from here.
	s.ready.Store(true)

	go s.runMaintainLoop(ctx)
	go s.runTimeoutLoop(ctx)
	go s.runSampleLoop(ctx)

	// Scheduled scaling: reconcile booked assessment windows → warm floor, and
	// publish the required-nodes signal an ASG scales on.
	s.planner = newPlanner(s, cfg.SandboxPerNode)
	go s.planner.run(ctx)

	mux := http.NewServeMux()
	// Operator control plane — requires an org API key (requireOrg).
	mux.HandleFunc("POST /v1/sessions", s.requireOrg(s.createSession))
	mux.HandleFunc("DELETE /v1/sessions/{id}", s.requireOrg(s.destroySession))
	mux.HandleFunc("GET /v1/sessions/{id}", s.requireOrg(s.getSession)) // returns session_token: operator-only
	mux.HandleFunc("GET /v1/sessions", s.requireOrg(s.listSessions))
	// Generic sandbox API — the SDK-facing surface. All org-key.
	mux.HandleFunc("POST /v1/sandboxes", s.requireOrg(s.createSandbox))
	mux.HandleFunc("GET /v1/sandboxes", s.requireOrg(s.listSandboxes))
	mux.HandleFunc("GET /v1/sandboxes/{id}", s.requireOrg(s.getSandbox))
	mux.HandleFunc("DELETE /v1/sandboxes/{id}", s.requireOrg(s.killSandbox))
	mux.HandleFunc("POST /v1/sandboxes/{id}/timeout", s.requireOrg(s.setSandboxTimeout))
	mux.HandleFunc("POST /v1/sandboxes/{id}/exec", s.requireOrg(s.execSandbox))
	mux.HandleFunc("GET /v1/sandboxes/{id}/files", s.requireOrg(s.sandboxFiles))
	mux.HandleFunc("GET /v1/sandboxes/{id}/files/content", s.requireOrg(s.sandboxReadFile))
	mux.HandleFunc("PUT /v1/sandboxes/{id}/files/content", s.requireOrg(s.sandboxWriteFile))
	mux.HandleFunc("DELETE /v1/sandboxes/{id}/files/content", s.requireOrg(s.sandboxDeleteFile))
	// API-key lifecycle — named keys, shown once, revocable.
	mux.HandleFunc("POST /v1/api-keys", s.requireOrg(s.createAPIKey))
	mux.HandleFunc("GET /v1/api-keys", s.requireOrg(s.listAPIKeys))
	mux.HandleFunc("DELETE /v1/api-keys/{id}", s.requireOrg(s.revokeAPIKey))
	mux.HandleFunc("GET /v1/templates", s.requireOrg(s.listTemplates))
	mux.HandleFunc("POST /v1/templates", s.requireOrg(s.createTemplate))
	mux.HandleFunc("POST /v1/templates/{id}/min_warm", s.requireOrg(s.scaleTemplate))
	mux.HandleFunc("GET /v1/windows", s.requireOrg(s.listWindows))
	mux.HandleFunc("POST /v1/windows", s.requireOrg(s.createWindow))
	mux.HandleFunc("DELETE /v1/windows/{id}", s.requireOrg(s.cancelWindow))
	mux.HandleFunc("GET /v1/stats", s.requireOrg(s.stats))
	mux.HandleFunc("GET /v1/usage", s.requireOrg(s.usage))
	mux.HandleFunc("GET /v1/nodes", s.requireOrg(s.nodes))
	// Candidate plane — scoped by the per-session token, not an org key.
	mux.HandleFunc("POST /v1/sessions/{id}/submit", s.submitSession)
	mux.HandleFunc("GET /v1/sessions/{id}/terminal", s.terminal)
	mux.HandleFunc("GET /v1/sessions/{id}/play", s.playInfo)
	mux.HandleFunc("GET /v1/sessions/{id}/files", s.files)
	mux.HandleFunc("GET /v1/sessions/{id}/file", s.readFile)
	mux.HandleFunc("PUT /v1/sessions/{id}/file", s.writeFile)
	mux.HandleFunc("GET /v1/sessions/{id}/result", s.result)
	mux.HandleFunc("GET /terminal", s.terminalPage)
	// Internal/infra — no org context needed.
	mux.Handle("GET /metrics", s.metrics.Handler())
	// Liveness: the process is up and serving. Readiness: it has finished reconcile
	// + initial warm and is still accepting (flips to 503 the moment we start
	// draining on SIGTERM, so the LB stops routing before the listener closes).
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, r *http.Request) { _, _ = w.Write([]byte("ok")) })
	mux.HandleFunc("GET /readyz", func(w http.ResponseWriter, r *http.Request) {
		if !s.ready.Load() {
			httpErr(w, http.StatusServiceUnavailable, "not ready")
			return
		}
		_, _ = w.Write([]byte("ready"))
	})

	// Native dashboard — the static-exported Next.js app embedded in this binary,
	// served on everything the API doesn't claim. Same origin as the API, so the
	// dashboard needs zero configuration. Unknown /v1/* paths stay JSON 404s.
	if dashboard.Available() {
		dash := dashboard.Handler()
		mux.HandleFunc("GET /", func(w http.ResponseWriter, r *http.Request) {
			if strings.HasPrefix(r.URL.Path, "/v1/") {
				httpErr(w, http.StatusNotFound, "not found")
				return
			}
			dash.ServeHTTP(w, r)
		})
		log.Info("native dashboard enabled", "path", "/")
	} else {
		log.Warn("no dashboard assets embedded — run scripts/build-dashboard.sh and rebuild")
	}

	// Split the listener by vhost: `<id>.preview.<domain>` is the candidate's
	// live app preview (reverse-proxied, its own auth), everything else is the
	// JSON API. One port, two planes.
	api := withCORS(mux)
	root := s.withRequestLog(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if s.isPreviewHost(r.Host) {
			s.preview(w, r)
			return
		}
		api.ServeHTTP(w, r)
	}))

	srv := &http.Server{Addr: cfg.Addr, Handler: root}
	log.Info("preview vhost enabled", "pattern", "*."+cfg.PreviewDomain+portColon(cfg.Addr))
	go func() {
		log.Info("orchestrator listening", "addr", cfg.Addr)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Error("http", "err", err)
			stop()
		}
	}()

	<-ctx.Done()
	// Graceful drain: fail readiness first (LB stops sending new work), then stop
	// accepting and let in-flight HTTP handlers finish, then wait for detached
	// background jobs (async scoring) so no submission is left un-scored.
	s.ready.Store(false)
	log.Info("shutting down — draining")
	shutCtx, cancel := context.WithTimeout(context.Background(), 25*time.Second)
	defer cancel()
	if err := srv.Shutdown(shutCtx); err != nil {
		log.Warn("http shutdown timed out", "err", err)
	}
	if s.jobs.wait(20 * time.Second) {
		log.Info("background jobs drained")
	} else {
		log.Warn("background jobs did not drain in time")
	}
	log.Info("shutdown complete")
}

// logLevel maps a config string to an slog level.
func logLevel(s string) slog.Level {
	switch s {
	case "debug":
		return slog.LevelDebug
	case "warn":
		return slog.LevelWarn
	case "error":
		return slog.LevelError
	default:
		return slog.LevelInfo
	}
}

// --- HTTP handlers ---

func (s *server) createSession(w http.ResponseWriter, r *http.Request) {
	var req struct {
		CandidateID  string `json:"candidate_id"`
		QuestionID   string `json:"question_id"`
		AssessmentID string `json:"assessment_id"`
		TimeLimitMin int    `json:"time_limit_minutes"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		httpErr(w, http.StatusBadRequest, "bad json")
		return
	}
	if req.CandidateID == "" || req.QuestionID == "" {
		httpErr(w, http.StatusBadRequest, "candidate_id and question_id required")
		return
	}

	org, _ := orgFrom(r.Context())
	// Concurrency cap — also a cost guardrail: an org can't exceed its live-sandbox
	// budget. Counted from the durable ledger so it survives restarts.
	if org.ConcurrencyLimit > 0 {
		n, err := s.store.ActiveCountByOrg(r.Context(), org.ID)
		if err == nil && n >= org.ConcurrencyLimit {
			httpErr(w, http.StatusTooManyRequests,
				fmt.Sprintf("concurrency limit reached (%d active)", org.ConcurrencyLimit))
			return
		}
	}

	sessionID := pool.NewID("sess")
	token := pool.NewID("tok")
	qcfg, _ := s.reg.config(req.QuestionID)
	ttl := qcfg.TimeLimit
	if req.TimeLimitMin > 0 {
		ttl = time.Duration(req.TimeLimitMin) * time.Minute
	}

	claimStart := time.Now()
	pl, err := s.prov.Claim(r.Context(), req.QuestionID, req.CandidateID, sessionID, token)
	if errors.Is(err, pool.ErrUnknownQuestion) {
		httpErr(w, http.StatusNotFound, "unknown question")
		return
	}
	if err != nil {
		s.log.Error("claim failed", "err", err)
		httpErr(w, http.StatusServiceUnavailable, "could not provision sandbox")
		return
	}
	s.metrics.ObserveClaim(req.QuestionID, pl.Cold, time.Since(claimStart).Seconds())

	expires := time.Now().Add(ttl)
	if err := s.store.CreateSession(r.Context(), store.Session{
		ID: sessionID, CandidateID: req.CandidateID, QuestionID: req.QuestionID,
		AssessmentID: req.AssessmentID, OrgID: org.ID, ContainerID: pl.ContainerID, HostPort: pl.HostApp,
		NodeID: pl.Node, NodeAddr: pl.NodeAddr, NodeHost: pl.Host, HostToolbox: pl.HostToolbox,
		Status: "ACTIVE", SessionToken: token, ExpiresAt: expires,
	}); err != nil {
		s.prov.Release(r.Context(), pl)
		s.log.Error("persist session failed", "err", err)
		httpErr(w, http.StatusInternalServerError, "persist failed")
		return
	}

	resp := map[string]any{
		"session_id":    sessionID,
		"session_token": token,
		"app_url":       fmt.Sprintf("http://%s:%d", pl.Host, pl.HostApp),
		"terminal_url":  fmt.Sprintf("http://%s:%d/ws/terminal", pl.Host, pl.HostToolbox),
		"expires_at":    expires.UTC().Format(time.RFC3339),
	}
	// Frontend templates get an authenticated browser preview through the proxy.
	if t, ok := s.templateByID(req.QuestionID); ok && t.Kind == "frontend" {
		resp["preview_url"] = s.previewURL(sessionID, token)
	}
	writeJSON(w, http.StatusCreated, resp)
}

// getSession returns one session plus the live URLs the dashboard needs to
// embed it (app, terminal WS, browser preview). URLs are only populated while
// the session is ACTIVE — once destroyed there is nothing to connect to.
func (s *server) getSession(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	sess, err := s.store.GetSession(r.Context(), id)
	if err != nil {
		httpErr(w, http.StatusNotFound, "session not found")
		return
	}
	out := map[string]any{
		"session_id":   sess.ID,
		"candidate_id": sess.CandidateID,
		"question_id":  sess.QuestionID,
		"status":       sess.Status,
		"expires_at":   sess.ExpiresAt.UTC().Format(time.RFC3339),
	}
	if sess.Status == "ACTIVE" {
		out["session_token"] = sess.SessionToken
		out["app_url"] = fmt.Sprintf("http://%s:%d", sess.NodeHost, sess.HostPort)
		if sess.HostToolbox > 0 {
			out["terminal_url"] = fmt.Sprintf("http://%s:%d/ws/terminal", sess.NodeHost, sess.HostToolbox)
			// The embeddable xterm page, served by the orchestrator itself.
			out["terminal_page"] = fmt.Sprintf("/terminal?session=%s&token=%s", sess.ID, sess.SessionToken)
		}
		if t, ok := s.reg.get(sess.QuestionID); ok && t.Kind == "frontend" {
			out["preview_url"] = s.previewURL(sess.ID, sess.SessionToken)
		}
	}
	writeJSON(w, http.StatusOK, out)
}

// placementOf rebuilds the routing Placement from a persisted session, so
// release / snapshot / score reach the node that owns the sandbox.
func placementOf(sess *store.Session) Placement {
	return Placement{
		Node: sess.NodeID, NodeAddr: sess.NodeAddr, Host: sess.NodeHost,
		ContainerID: sess.ContainerID, HostApp: sess.HostPort, HostToolbox: sess.HostToolbox,
	}
}

func (s *server) destroySession(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	sess, err := s.store.GetSession(r.Context(), id)
	if err != nil {
		httpErr(w, http.StatusNotFound, "session not found")
		return
	}
	s.prov.Release(r.Context(), placementOf(sess))
	_ = s.store.MarkDestroyed(r.Context(), id)
	w.WriteHeader(http.StatusNoContent)
}

func (s *server) submitSession(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	sess, err := s.store.GetSession(r.Context(), id)
	if err != nil {
		httpErr(w, http.StatusNotFound, "session not found")
		return
	}
	if !s.authOK(r, sess.SessionToken) {
		httpErr(w, http.StatusUnauthorized, "invalid token")
		return
	}
	if sess.Status != "ACTIVE" {
		httpErr(w, http.StatusConflict, "session not active")
		return
	}

	// Snapshot before destroying the container (routes to the owning node).
	pl := placementOf(sess)
	srcTar, err := s.prov.Snapshot(r.Context(), pl)
	if err != nil {
		s.log.Error("snapshot failed", "err", err)
		httpErr(w, http.StatusInternalServerError, "snapshot failed")
		return
	}

	subID := pool.NewID("sub")
	_ = s.store.MarkSubmitted(r.Context(), id)
	if err := s.store.CreateSubmission(r.Context(), subID, id, sess.QuestionID); err != nil {
		s.log.Error("create submission failed", "err", err)
	}

	// Candidate loses live access immediately.
	s.prov.Release(r.Context(), pl)
	_ = s.store.MarkDestroyed(r.Context(), id)

	// Score asynchronously — keep the request fast. Tracked so a SIGTERM mid-score
	// still writes the result before the process exits.
	s.jobs.run(func() { s.score(context.Background(), subID, sess.QuestionID, srcTar, pl) })

	writeJSON(w, http.StatusAccepted, map[string]any{"submission_id": subID, "status": "scoring"})
}

func (s *server) stats(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{"warm": s.prov.WarmCount(r.Context())})
}

// nodes is the Fleet view: one synthetic node in local mode, every live node-agent
// in cluster mode.
func (s *server) nodes(w http.ResponseWriter, r *http.Request) {
	ns, err := s.prov.Nodes(r.Context())
	if err != nil {
		httpErr(w, http.StatusInternalServerError, "node list failed")
		return
	}
	if ns == nil {
		ns = []NodeView{}
	}
	writeJSON(w, http.StatusOK, ns)
}

// --- scoring ---

type scoreOutput struct {
	Score       int               `json:"score"`
	MaxScore    int               `json:"max_score"`
	TestResults []json.RawMessage `json:"test_results"`
}

func (s *server) score(ctx context.Context, subID, questionID string, srcTar []byte, pl Placement) {
	out, err := s.prov.Score(ctx, pl, questionID, srcTar)
	if err != nil {
		s.log.Error("scoring run failed", "submission", subID, "err", err)
		_ = s.store.WriteScore(ctx, subID, "error", 0, 0, nil)
		return
	}
	jsonLine := lastJSONLine(out)
	var parsed scoreOutput
	if err := json.Unmarshal(jsonLine, &parsed); err != nil {
		s.log.Error("invalid scorer output", "submission", subID, "raw", string(out))
		_ = s.store.WriteScore(ctx, subID, "invalid_output", 0, 0, nil)
		return
	}
	if err := s.store.WriteScore(ctx, subID, "scored", parsed.Score, parsed.MaxScore, jsonLine); err != nil {
		s.log.Error("write score failed", "submission", subID, "err", err)
		return
	}
	s.log.Info("submission.scored", "submission", subID, "score", parsed.Score, "max", parsed.MaxScore)
}

// scaleTemplate sets a template's warm depth at runtime — the knob scheduled
// scaling drives (raise before a booked window, lower after). In local mode it
// updates the in-process floor; in cluster mode it fans the new floor out to every
// node-agent. Either way an immediate replenish fills toward it.
func (s *server) scaleTemplate(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	var req struct {
		MinWarm *int `json:"min_warm"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.MinWarm == nil {
		httpErr(w, http.StatusBadRequest, "min_warm (int) required")
		return
	}
	if *req.MinWarm < 0 || *req.MinWarm > 200 {
		httpErr(w, http.StatusBadRequest, "min_warm out of range (0-200)")
		return
	}
	if !s.prov.SetMinWarm(r.Context(), id, *req.MinWarm) {
		httpErr(w, http.StatusNotFound, "unknown template")
		return
	}
	s.reg.setMinWarm(id, *req.MinWarm) // keep the listing in sync
	// A manual scale sets the template's baseline — the floor the planner restores
	// after a window, and the level it adds window seats on top of.
	if s.planner != nil {
		s.planner.setBaseline(id, *req.MinWarm)
	}
	writeJSON(w, http.StatusOK, map[string]any{"template": id, "min_warm": *req.MinWarm})
}

// --- background loops ---

func (s *server) runMaintainLoop(ctx context.Context) {
	t := time.NewTicker(30 * time.Second)
	defer t.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-t.C:
			s.prov.Maintain(ctx)
		}
	}
}

func (s *server) runTimeoutLoop(ctx context.Context) {
	t := time.NewTicker(30 * time.Second)
	defer t.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-t.C:
			ids, err := s.store.ExpiredActive(ctx)
			if err != nil {
				s.log.Error("expired query", "err", err)
				continue
			}
			for _, id := range ids {
				s.autoSubmit(ctx, id)
			}
		}
	}
}

// autoSubmit is the supervisor-side timeout: it is the source of truth, never
// the container. Snapshots, scores, and destroys an expired session.
func (s *server) autoSubmit(ctx context.Context, sessionID string) {
	sess, err := s.store.GetSession(ctx, sessionID)
	if err != nil || sess.Status != "ACTIVE" {
		return
	}
	s.log.Info("session.timed_out", "session", sessionID)
	pl := placementOf(sess)
	srcTar, err := s.prov.Snapshot(ctx, pl)
	subID := pool.NewID("sub")
	_ = s.store.SetStatus(ctx, sessionID, "TIMED_OUT")
	_ = s.store.CreateSubmission(ctx, subID, sessionID, sess.QuestionID)
	s.prov.Release(ctx, pl)
	_ = s.store.MarkDestroyed(ctx, sessionID)
	if err == nil {
		s.jobs.run(func() { s.score(context.Background(), subID, sess.QuestionID, srcTar, pl) })
	} else {
		_ = s.store.WriteScore(ctx, subID, "no_snapshot", 0, 0, nil)
	}
}

// --- helpers ---

func (s *server) authOK(r *http.Request, token string) bool {
	h := r.Header.Get("Authorization")
	return strings.TrimPrefix(h, "Bearer ") == token && token != ""
}

// short truncates a container id for logs.
func short(id string) string {
	if len(id) > 12 {
		return id[:12]
	}
	return id
}

func lastJSONLine(b []byte) []byte {
	lines := strings.Split(strings.TrimSpace(string(b)), "\n")
	for i := len(lines) - 1; i >= 0; i-- {
		l := strings.TrimSpace(lines[i])
		if strings.HasPrefix(l, "{") && strings.HasSuffix(l, "}") {
			return []byte(l)
		}
	}
	return b
}

// portOf extracts the port from a listen address like ":8090" or "0.0.0.0:8090".
func portOf(addr string) string {
	if i := strings.LastIndex(addr, ":"); i >= 0 {
		return addr[i+1:]
	}
	return addr
}

// portColon renders ":<port>" for display when the port is non-standard.
func portColon(addr string) string {
	p := portOf(addr)
	if p == "" || p == "80" {
		return ""
	}
	return ":" + p
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

func httpErr(w http.ResponseWriter, code int, msg string) {
	writeJSON(w, code, map[string]string{"error": msg})
}

func writeJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(v)
}
