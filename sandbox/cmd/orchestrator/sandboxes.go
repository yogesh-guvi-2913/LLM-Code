package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/guvi-geek/flash/internal/pool"
	"github.com/guvi-geek/flash/internal/store"
)

// The /v1/sandboxes API is the generic, SDK-facing surface: create a sandbox
// from a template, run commands in it, read/write its
// files, reach its preview, kill it. It is the OPERATOR plane end to end (every
// route requires an org API key); the session-token candidate plane stays what
// it was. Under the hood a sandbox IS a session — same pool, same ledger, same
// reconcile/routing — with the assessment framing (candidate, submit→score)
// optional on top.

const (
	execDefaultTimeout = 60 * time.Second
	execMaxTimeout     = 300 * time.Second
	sandboxMaxTimeout  = 24 * time.Hour
)

// sandboxView renders a session in the SDK vocabulary. URLs are populated only
// while the sandbox is running.
func (s *server) sandboxView(sess *store.Session) map[string]any {
	out := map[string]any{
		"sandbox_id":  sess.ID,
		"template_id": sess.QuestionID,
		"state":       sandboxState(sess.Status),
		"created_at":  sess.CreatedAt.UTC().Format(time.RFC3339),
		"expires_at":  sess.ExpiresAt.UTC().Format(time.RFC3339),
		"metadata":    json.RawMessage(orEmptyJSON(sess.Metadata)),
	}
	if sess.Status == "ACTIVE" {
		out["app_url"] = fmt.Sprintf("http://%s:%d", sess.NodeHost, sess.HostPort)
		out["token"] = sess.SessionToken
		if sess.HostToolbox > 0 {
			out["terminal_url"] = fmt.Sprintf("http://%s:%d/ws/terminal", sess.NodeHost, sess.HostToolbox)
			out["terminal_page"] = fmt.Sprintf("/terminal?session=%s&token=%s", sess.ID, sess.SessionToken)
		}
		if t, ok := s.reg.get(sess.QuestionID); ok && t.Kind == "frontend" {
			out["preview_url"] = s.previewURL(sess.ID, sess.SessionToken)
		}
	}
	return out
}

// sandboxState maps the session ledger's status to the SDK's state vocabulary.
func sandboxState(status string) string {
	switch status {
	case "ACTIVE":
		return "running"
	case "SUBMITTED":
		return "submitted"
	case "TIMED_OUT":
		return "timed_out"
	default:
		return "destroyed"
	}
}

func orEmptyJSON(b []byte) []byte {
	if len(b) == 0 {
		return []byte("{}")
	}
	return b
}

// orgSandbox resolves a sandbox by id and enforces org ownership — an org key
// can only touch its own sandboxes. 404 (not 403) for another org's sandbox so
// ids aren't probeable.
func (s *server) orgSandbox(w http.ResponseWriter, r *http.Request) (*store.Session, bool) {
	org, _ := orgFrom(r.Context())
	sess, err := s.store.GetSession(r.Context(), r.PathValue("id"))
	if err != nil || sess.OrgID != org.ID {
		httpErr(w, http.StatusNotFound, "sandbox not found")
		return nil, false
	}
	return sess, true
}

// runningSandbox is orgSandbox + the sandbox must still be live (exec/files
// need a container to talk to).
func (s *server) runningSandbox(w http.ResponseWriter, r *http.Request) (*store.Session, bool) {
	sess, ok := s.orgSandbox(w, r)
	if !ok {
		return nil, false
	}
	if sess.Status != "ACTIVE" {
		httpErr(w, http.StatusConflict, "sandbox not running")
		return nil, false
	}
	return sess, true
}

// createSandbox claims a warm sandbox from a template — the SDK's `Create`.
func (s *server) createSandbox(w http.ResponseWriter, r *http.Request) {
	var req struct {
		TemplateID     string            `json:"template_id"`
		TimeoutSeconds int               `json:"timeout_seconds"`
		Metadata       map[string]string `json:"metadata"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		httpErr(w, http.StatusBadRequest, "bad json")
		return
	}
	if req.TemplateID == "" {
		httpErr(w, http.StatusBadRequest, "template_id required")
		return
	}
	if req.TimeoutSeconds < 0 || time.Duration(req.TimeoutSeconds)*time.Second > sandboxMaxTimeout {
		httpErr(w, http.StatusBadRequest, "timeout_seconds out of range")
		return
	}

	org, _ := orgFrom(r.Context())
	if org.ConcurrencyLimit > 0 {
		n, err := s.store.ActiveCountByOrg(r.Context(), org.ID)
		if err == nil && n >= org.ConcurrencyLimit {
			httpErr(w, http.StatusTooManyRequests,
				fmt.Sprintf("concurrency limit reached (%d active)", org.ConcurrencyLimit))
			return
		}
	}

	qcfg, ok := s.reg.config(req.TemplateID)
	if !ok {
		httpErr(w, http.StatusNotFound, "unknown template")
		return
	}
	ttl := qcfg.TimeLimit
	if req.TimeoutSeconds > 0 {
		ttl = time.Duration(req.TimeoutSeconds) * time.Second
	}
	meta, _ := json.Marshal(req.Metadata)

	sandboxID := pool.NewID("sbx")
	token := pool.NewID("tok")
	claimStart := time.Now()
	pl, err := s.prov.Claim(r.Context(), req.TemplateID, "sdk", sandboxID, token)
	if errors.Is(err, pool.ErrUnknownQuestion) {
		httpErr(w, http.StatusNotFound, "unknown template")
		return
	}
	if err != nil {
		s.log.Error("sandbox claim failed", "err", err)
		httpErr(w, http.StatusServiceUnavailable, "could not provision sandbox")
		return
	}
	s.metrics.ObserveClaim(req.TemplateID, pl.Cold, time.Since(claimStart).Seconds())

	now := time.Now()
	sess := store.Session{
		ID: sandboxID, CandidateID: "sdk", QuestionID: req.TemplateID,
		OrgID: org.ID, ContainerID: pl.ContainerID, HostPort: pl.HostApp,
		NodeID: pl.Node, NodeAddr: pl.NodeAddr, NodeHost: pl.Host, HostToolbox: pl.HostToolbox,
		Status: "ACTIVE", SessionToken: token, Metadata: meta, ExpiresAt: now.Add(ttl),
	}
	if err := s.store.CreateSession(r.Context(), sess); err != nil {
		s.prov.Release(r.Context(), pl)
		s.log.Error("persist sandbox failed", "err", err)
		httpErr(w, http.StatusInternalServerError, "persist failed")
		return
	}
	sess.CreatedAt = now
	writeJSON(w, http.StatusCreated, s.sandboxView(&sess))
}

// listSandboxes returns the org's sandboxes, newest first. ?state=running
// filters to live ones (the SDK's default list).
func (s *server) listSandboxes(w http.ResponseWriter, r *http.Request) {
	org, _ := orgFrom(r.Context())
	status := ""
	if st := r.URL.Query().Get("state"); st == "running" {
		status = "ACTIVE"
	}
	sessions, err := s.store.SessionsByOrg(r.Context(), org.ID, status, 200)
	if err != nil {
		httpErr(w, http.StatusInternalServerError, "list failed")
		return
	}
	out := make([]map[string]any, 0, len(sessions))
	for i := range sessions {
		out = append(out, s.sandboxView(&sessions[i]))
	}
	writeJSON(w, http.StatusOK, map[string]any{"sandboxes": out})
}

func (s *server) getSandbox(w http.ResponseWriter, r *http.Request) {
	sess, ok := s.orgSandbox(w, r)
	if !ok {
		return
	}
	writeJSON(w, http.StatusOK, s.sandboxView(sess))
}

// killSandbox destroys a sandbox immediately — the SDK's `Kill`. Idempotent:
// killing an already-dead sandbox is a 204.
func (s *server) killSandbox(w http.ResponseWriter, r *http.Request) {
	sess, ok := s.orgSandbox(w, r)
	if !ok {
		return
	}
	if sess.Status == "ACTIVE" {
		s.prov.Release(r.Context(), placementOf(sess))
		_ = s.store.MarkDestroyed(r.Context(), sess.ID)
	}
	w.WriteHeader(http.StatusNoContent)
}

// setSandboxTimeout moves the expiry to now+timeout_seconds — the SDK's
// `SetTimeout` keep-alive.
func (s *server) setSandboxTimeout(w http.ResponseWriter, r *http.Request) {
	sess, ok := s.runningSandbox(w, r)
	if !ok {
		return
	}
	var req struct {
		TimeoutSeconds int `json:"timeout_seconds"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.TimeoutSeconds <= 0 ||
		time.Duration(req.TimeoutSeconds)*time.Second > sandboxMaxTimeout {
		httpErr(w, http.StatusBadRequest, "timeout_seconds (1..86400) required")
		return
	}
	expires := time.Now().Add(time.Duration(req.TimeoutSeconds) * time.Second)
	if ok, err := s.store.ExtendSession(r.Context(), sess.ID, expires); err != nil || !ok {
		httpErr(w, http.StatusConflict, "could not extend sandbox")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"sandbox_id": sess.ID, "expires_at": expires.UTC().Format(time.RFC3339),
	})
}

// execSandbox runs one command in the sandbox and returns stdout/stderr/exit
// code — the SDK's `Exec`/`RunCode` primitive. Accepts argv (`cmd`) or a shell
// string (`command`, run via sh -c). A non-zero exit is a 200 with the code;
// only transport/timeout failures are HTTP errors.
func (s *server) execSandbox(w http.ResponseWriter, r *http.Request) {
	sess, ok := s.runningSandbox(w, r)
	if !ok {
		return
	}
	var req struct {
		Cmd            []string          `json:"cmd"`
		Command        string            `json:"command"`
		Cwd            string            `json:"cwd"`
		Env            map[string]string `json:"env"`
		TimeoutSeconds int               `json:"timeout_seconds"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		httpErr(w, http.StatusBadRequest, "bad json")
		return
	}
	argv := req.Cmd
	if len(argv) == 0 && req.Command != "" {
		argv = []string{"sh", "-c", req.Command}
	}
	if len(argv) == 0 {
		httpErr(w, http.StatusBadRequest, "cmd (argv) or command (shell string) required")
		return
	}
	var cwd string
	if req.Cwd != "" {
		rel, ok := safeRel(req.Cwd)
		if !ok {
			httpErr(w, http.StatusBadRequest, "bad cwd")
			return
		}
		cwd = "/app/src/" + rel
	}
	env := make([]string, 0, len(req.Env))
	for k, v := range req.Env {
		env = append(env, k+"="+v)
	}
	timeout := execDefaultTimeout
	if req.TimeoutSeconds > 0 {
		timeout = min(time.Duration(req.TimeoutSeconds)*time.Second, execMaxTimeout)
	}
	ctx, cancel := context.WithTimeout(r.Context(), timeout)
	defer cancel()

	start := time.Now()
	res, err := s.prov.Exec(ctx, placementOf(sess), ExecRequest{Cmd: argv, Cwd: cwd, Env: env})
	if err != nil {
		if ctx.Err() != nil {
			httpErr(w, http.StatusRequestTimeout, "command timed out")
			return
		}
		httpErr(w, http.StatusBadGateway, "exec failed: "+err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"stdout":      res.Stdout,
		"stderr":      res.Stderr,
		"exit_code":   res.ExitCode,
		"duration_ms": time.Since(start).Milliseconds(),
	})
}

// --- files (operator/SDK plane; the candidate-plane copies live in playground.go) ---

func (s *server) sandboxFiles(w http.ResponseWriter, r *http.Request) {
	sess, ok := s.runningSandbox(w, r)
	if !ok {
		return
	}
	list, err := s.prov.Files(r.Context(), placementOf(sess))
	if err != nil {
		httpErr(w, http.StatusBadGateway, "list files failed: "+err.Error())
		return
	}
	if list == nil {
		list = []string{}
	}
	writeJSON(w, http.StatusOK, map[string]any{"files": list})
}

func (s *server) sandboxReadFile(w http.ResponseWriter, r *http.Request) {
	sess, ok := s.runningSandbox(w, r)
	if !ok {
		return
	}
	rel, ok := safeRel(r.URL.Query().Get("path"))
	if !ok {
		httpErr(w, http.StatusBadRequest, "bad path")
		return
	}
	b, err := s.prov.ReadFile(r.Context(), placementOf(sess), rel)
	if err != nil {
		httpErr(w, http.StatusBadGateway, "read failed: "+err.Error())
		return
	}
	w.Header().Set("Content-Type", "application/octet-stream")
	_, _ = w.Write(b)
}

func (s *server) sandboxWriteFile(w http.ResponseWriter, r *http.Request) {
	sess, ok := s.runningSandbox(w, r)
	if !ok {
		return
	}
	rel, ok := safeRel(r.URL.Query().Get("path"))
	if !ok {
		httpErr(w, http.StatusBadRequest, "bad path")
		return
	}
	body, err := io.ReadAll(io.LimitReader(r.Body, 8<<20))
	if err != nil {
		httpErr(w, http.StatusBadRequest, "read body")
		return
	}
	if err := s.prov.WriteFile(r.Context(), placementOf(sess), rel, body); err != nil {
		httpErr(w, http.StatusBadGateway, "write failed: "+err.Error())
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

func (s *server) sandboxDeleteFile(w http.ResponseWriter, r *http.Request) {
	sess, ok := s.runningSandbox(w, r)
	if !ok {
		return
	}
	rel, ok := safeRel(r.URL.Query().Get("path"))
	if !ok {
		httpErr(w, http.StatusBadRequest, "bad path")
		return
	}
	if err := s.prov.DeleteFile(r.Context(), placementOf(sess), rel); err != nil {
		httpErr(w, http.StatusBadGateway, "delete failed: "+err.Error())
		return
	}
	w.WriteHeader(http.StatusNoContent)
}
