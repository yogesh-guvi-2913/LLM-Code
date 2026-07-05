package main

import (
	"io"
	"net/http"
	"path"
	"strings"

	"github.com/guvi-geek/flash/internal/store"
)

// The playground is the candidate IDE: a Monaco editor that reads/writes the live
// sandbox's files, plus the existing preview + terminal + submit. Everything here
// is the CANDIDATE plane — authorized by the per-session token in `?token=`, never
// an org key (the candidate has only their token). File ops route through the
// Provisioner, so they work the same in local and cluster mode.

// candidateSession resolves and authorizes a session by its token (query param).
func (s *server) candidateSession(w http.ResponseWriter, r *http.Request) (*store.Session, bool) {
	sess, err := s.store.GetSession(r.Context(), r.PathValue("id"))
	if err != nil {
		httpErr(w, http.StatusNotFound, "session not found")
		return nil, false
	}
	token := r.URL.Query().Get("token")
	if token == "" || token != sess.SessionToken {
		httpErr(w, http.StatusUnauthorized, "invalid token")
		return nil, false
	}
	if sess.Status != "ACTIVE" {
		httpErr(w, http.StatusConflict, "session not active")
		return nil, false
	}
	return sess, true
}

// safeRel confines a candidate-supplied path to a relative path under the work dir
// (no leading slash, no `..` escape). path.Clean on a rooted copy collapses any
// traversal; we then strip the root.
func safeRel(p string) (string, bool) {
	if p == "" {
		return "", false
	}
	clean := path.Clean("/" + strings.TrimPrefix(p, "/"))
	rel := strings.TrimPrefix(clean, "/")
	if rel == "" || rel == "." {
		return "", false
	}
	return rel, true
}

// playInfo returns the live URLs + template kind the IDE needs to render, given the
// session token (so a candidate who only has ?session&token can bootstrap).
func (s *server) playInfo(w http.ResponseWriter, r *http.Request) {
	sess, ok := s.candidateSession(w, r)
	if !ok {
		return
	}
	out := map[string]any{
		"session_id":   sess.ID,
		"candidate_id": sess.CandidateID,
		"question_id":  sess.QuestionID,
		"status":       sess.Status,
		"kind":         "api",
		"app_url":      "", // API templates: candidates curl from the terminal
	}
	if t, ok := s.reg.get(sess.QuestionID); ok {
		out["kind"] = t.Kind
		out["title"] = t.Title
		if t.Kind == "frontend" {
			out["preview_url"] = s.previewURL(sess.ID, sess.SessionToken)
		}
	}
	out["terminal_page"] = "/terminal?session=" + sess.ID + "&token=" + sess.SessionToken
	writeJSON(w, http.StatusOK, out)
}

// files lists the candidate's editable files.
func (s *server) files(w http.ResponseWriter, r *http.Request) {
	sess, ok := s.candidateSession(w, r)
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

// readFile returns one file's contents (text).
func (s *server) readFile(w http.ResponseWriter, r *http.Request) {
	sess, ok := s.candidateSession(w, r)
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
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	_, _ = w.Write(b)
}

// writeFile saves an edited file back into the live sandbox. For frontend templates
// the dev server's HMR picks it up and the preview updates immediately.
func (s *server) writeFile(w http.ResponseWriter, r *http.Request) {
	sess, ok := s.candidateSession(w, r)
	if !ok {
		return
	}
	rel, ok := safeRel(r.URL.Query().Get("path"))
	if !ok {
		httpErr(w, http.StatusBadRequest, "bad path")
		return
	}
	body, err := io.ReadAll(io.LimitReader(r.Body, 4<<20))
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

// result returns the latest submission's score for the session (the IDE polls this
// after submitting). Unlike the file ops it must work once the session is no longer
// ACTIVE — submitting destroys the sandbox — so it checks only the token.
func (s *server) result(w http.ResponseWriter, r *http.Request) {
	sess, err := s.store.GetSession(r.Context(), r.PathValue("id"))
	if err != nil {
		httpErr(w, http.StatusNotFound, "session not found")
		return
	}
	if tok := r.URL.Query().Get("token"); tok == "" || tok != sess.SessionToken {
		httpErr(w, http.StatusUnauthorized, "invalid token")
		return
	}
	status, score, maxScore, has, err := s.store.LatestSubmission(r.Context(), sess.ID)
	if err != nil {
		httpErr(w, http.StatusInternalServerError, "result query failed")
		return
	}
	if !has {
		writeJSON(w, http.StatusOK, map[string]any{"submitted": false})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"submitted": true, "status": status, "score": score, "max_score": maxScore,
	})
}
