package main

import (
	"context"
	"encoding/json"
	"net/http"
	"strings"

	"github.com/guvi-geek/flash/internal/store"
	"github.com/guvi-geek/flash/internal/templates"
)

// Template and the default set now live in internal/templates (shared with the
// node-agent). This alias keeps the orchestrator's many `Template` references
// working unqualified.
type Template = templates.Template

func defaultTemplates() []Template { return templates.Default() }

// listTemplates returns templates enriched with live warm-pool depth.
func (s *server) listTemplates(w http.ResponseWriter, r *http.Request) {
	// Through the Provisioner (not s.pool, which is nil in cluster mode).
	warm := s.prov.WarmCount(r.Context())
	type row struct {
		Template
		Warm int `json:"warm"`
	}
	tmpls := s.reg.list()
	out := make([]row, 0, len(tmpls))
	for _, t := range tmpls {
		out = append(out, row{Template: t, Warm: warm[t.ID]})
	}
	writeJSON(w, http.StatusOK, out)
}

// createTemplate registers a new template at runtime and starts warming it.
// This is the dashboard's "Create Template" path (the spec's recruiter-publish
// flow, minus CodeBuild — the image must already exist in the Docker daemon).
func (s *server) createTemplate(w http.ResponseWriter, r *http.Request) {
	var t Template
	if err := json.NewDecoder(r.Body).Decode(&t); err != nil {
		httpErr(w, http.StatusBadRequest, "bad json")
		return
	}
	t.ID = strings.TrimSpace(t.ID)
	t.Image = strings.TrimSpace(t.Image)
	if t.ID == "" || t.Image == "" {
		httpErr(w, http.StatusBadRequest, "id and image are required")
		return
	}
	if !templates.IDPattern.MatchString(t.ID) {
		httpErr(w, http.StatusBadRequest, "id must be lowercase alphanumeric/dash, 1-32 chars")
		return
	}
	if t.Kind != "frontend" {
		t.Kind = "api"
	}
	if t.DevCmd == "" {
		httpErr(w, http.StatusBadRequest, "dev_cmd is required (e.g. 'node server.js')")
		return
	}
	if t.MinWarm < 0 || t.MinWarm > 10 {
		httpErr(w, http.StatusBadRequest, "min_warm must be 0-10")
		return
	}
	if t.Title == "" {
		t.Title = t.ID
	}

	// Runtime template registration needs the local Docker daemon (image check +
	// in-process pool). In cluster mode templates are seeded per node-agent; live
	// registration there needs a fan-out path that doesn't exist yet — say so
	// instead of nil-panicking.
	if s.pool == nil || s.docker == nil {
		httpErr(w, http.StatusNotImplemented, "runtime template registration is not available in cluster mode")
		return
	}

	// The image must be present locally — surface a clear error rather than a
	// pool that silently never warms.
	if !s.docker.ImageExists(r.Context(), t.Image) {
		httpErr(w, http.StatusUnprocessableEntity, "image not found in docker daemon: "+t.Image)
		return
	}

	if err := s.reg.Add(t); err != nil {
		httpErr(w, http.StatusConflict, err.Error())
		return
	}
	cfg, _ := s.reg.config(t.ID)
	s.pool.Register(t.ID, cfg)
	s.log.Info("template.registered", "id", t.ID, "image", t.Image, "kind", t.Kind)

	// Warm in the background so the request returns immediately.
	go s.pool.Replenish(context.Background(), t.ID)

	writeJSON(w, http.StatusCreated, t)
}

// listSessions returns recent sessions (with joined score) for the dashboard.
func (s *server) listSessions(w http.ResponseWriter, r *http.Request) {
	rows, err := s.store.ListSessions(r.Context(), 100)
	if err != nil {
		httpErr(w, http.StatusInternalServerError, "list failed")
		return
	}
	if rows == nil {
		rows = []store.SessionRow{} // serialize as [] not null
	}
	writeJSON(w, http.StatusOK, rows)
}

// withCORS allows the separately-served dashboard to read the API from any origin.
func withCORS(h http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Authorization, Content-Type")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		h.ServeHTTP(w, r)
	})
}
