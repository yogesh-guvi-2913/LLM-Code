package main

import (
	"context"
	"encoding/json"
	"net/http"
	"time"

	"github.com/guvi-geek/flash/internal/pool"
	"github.com/guvi-geek/flash/internal/store"
)

// createWindow books a pre-warm window for a template (operator plane). The
// planner picks it up on its next tick; we also nudge a reconcile immediately so
// a window that opens now takes effect within a second instead of up to 15.
func (s *server) createWindow(w http.ResponseWriter, r *http.Request) {
	var req struct {
		QuestionID  string `json:"question_id"`
		Label       string `json:"label"`
		Seats       int    `json:"seats"`
		LeadMinutes *int   `json:"lead_minutes"`
		StartsAt    string `json:"starts_at"`
		EndsAt      string `json:"ends_at"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		httpErr(w, http.StatusBadRequest, "bad json")
		return
	}
	if _, ok := s.reg.get(req.QuestionID); !ok {
		httpErr(w, http.StatusNotFound, "unknown question")
		return
	}
	if req.Seats < 1 || req.Seats > 200 {
		httpErr(w, http.StatusBadRequest, "seats out of range (1-200)")
		return
	}
	startsAt, err := time.Parse(time.RFC3339, req.StartsAt)
	if err != nil {
		httpErr(w, http.StatusBadRequest, "starts_at must be RFC3339")
		return
	}
	endsAt, err := time.Parse(time.RFC3339, req.EndsAt)
	if err != nil {
		httpErr(w, http.StatusBadRequest, "ends_at must be RFC3339")
		return
	}
	if !endsAt.After(startsAt) {
		httpErr(w, http.StatusBadRequest, "ends_at must be after starts_at")
		return
	}
	lead := 5
	if req.LeadMinutes != nil {
		lead = *req.LeadMinutes
	}
	if lead < 0 || lead > 120 {
		httpErr(w, http.StatusBadRequest, "lead_minutes out of range (0-120)")
		return
	}

	org, _ := orgFrom(r.Context())
	win := store.Window{
		ID: pool.NewID("win"), OrgID: org.ID, QuestionID: req.QuestionID, Label: req.Label,
		Seats: req.Seats, LeadMinutes: lead, StartsAt: startsAt, EndsAt: endsAt,
	}
	if err := s.store.CreateWindow(r.Context(), win); err != nil {
		s.log.Error("create window failed", "err", err)
		httpErr(w, http.StatusInternalServerError, "persist failed")
		return
	}
	if s.planner != nil {
		go s.planner.reconcile(context.Background())
	}
	writeJSON(w, http.StatusCreated, windowView(win, time.Now()))
}

// listWindows returns booked windows (live by default, ?all=true for history),
// each annotated with its current phase, plus the planner's live desired-warm map
// so the operator can see scheduled scaling acting in real time.
func (s *server) listWindows(w http.ResponseWriter, r *http.Request) {
	includeEnded := r.URL.Query().Get("all") == "true"
	ws, err := s.store.ListWindows(r.Context(), includeEnded)
	if err != nil {
		httpErr(w, http.StatusInternalServerError, "list windows failed")
		return
	}
	now := time.Now()
	out := make([]map[string]any, 0, len(ws))
	for _, win := range ws {
		out = append(out, windowView(win, now))
	}
	desired, _ := s.store.DesiredWarmByQuestion(r.Context())
	if desired == nil {
		desired = map[string]int{}
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"windows":          out,
		"desired_warm_now": desired,
	})
}

func (s *server) cancelWindow(w http.ResponseWriter, r *http.Request) {
	org, _ := orgFrom(r.Context())
	ok, err := s.store.CancelWindow(r.Context(), r.PathValue("id"), org.ID)
	if err != nil {
		httpErr(w, http.StatusInternalServerError, "cancel failed")
		return
	}
	if !ok {
		httpErr(w, http.StatusNotFound, "window not found")
		return
	}
	if s.planner != nil {
		go s.planner.reconcile(context.Background())
	}
	w.WriteHeader(http.StatusNoContent)
}

func windowView(win store.Window, now time.Time) map[string]any {
	return map[string]any{
		"id":           win.ID,
		"question_id":  win.QuestionID,
		"label":        win.Label,
		"seats":        win.Seats,
		"lead_minutes": win.LeadMinutes,
		"starts_at":    win.StartsAt.UTC().Format(time.RFC3339),
		"ends_at":      win.EndsAt.UTC().Format(time.RFC3339),
		"phase":        windowPhase(win, now),
	}
}
