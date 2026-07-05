package main

import (
	"encoding/json"
	"net/http"

	"github.com/guvi-geek/flash/internal/pool"
	"github.com/guvi-geek/flash/internal/store"
)

// API-key lifecycle: named keys an org creates, lists, and revokes from the
// dashboard or the SDK — the credential-management surface a sandbox-as-a-service
// product needs before keys go to real users. The raw key is returned exactly
// once at creation (only its SHA-256 is stored); the list shows name + display
// prefix + last use, never the key.

// createAPIKey mints a new named key for the calling org.
func (s *server) createAPIKey(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Name string `json:"name"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.Name == "" {
		httpErr(w, http.StatusBadRequest, "name required")
		return
	}
	if len(req.Name) > 100 {
		httpErr(w, http.StatusBadRequest, "name too long (max 100)")
		return
	}
	org, _ := orgFrom(r.Context())
	raw, prefix := mintKey()
	id := pool.NewID("key")
	if err := s.store.UpsertAPIKey(r.Context(), id, org.ID, req.Name, hashKey(raw), prefix); err != nil {
		s.log.Error("create api key", "err", err)
		httpErr(w, http.StatusInternalServerError, "create key failed")
		return
	}
	writeJSON(w, http.StatusCreated, map[string]any{
		"id":     id,
		"name":   req.Name,
		"prefix": prefix,
		// Shown exactly once — only the hash is stored.
		"key": raw,
	})
}

// listAPIKeys returns the org's live keys (name, prefix, created, last used).
func (s *server) listAPIKeys(w http.ResponseWriter, r *http.Request) {
	org, _ := orgFrom(r.Context())
	keys, err := s.store.ListAPIKeys(r.Context(), org.ID)
	if err != nil {
		httpErr(w, http.StatusInternalServerError, "list keys failed")
		return
	}
	if keys == nil {
		keys = []store.APIKey{}
	}
	writeJSON(w, http.StatusOK, map[string]any{"keys": keys})
}

// revokeAPIKey revokes a key immediately. Revoking the key that authenticated
// THIS request is refused (409) — it would lock the caller out mid-flight;
// create a replacement key first, switch to it, then revoke the old one.
func (s *server) revokeAPIKey(w http.ResponseWriter, r *http.Request) {
	org, _ := orgFrom(r.Context())
	id := r.PathValue("id")
	if callerKey, _ := r.Context().Value(keyIDCtxKey{}).(string); callerKey != "" && callerKey == id {
		httpErr(w, http.StatusConflict, "cannot revoke the key used for this request — create a new key first")
		return
	}
	ok, err := s.store.RevokeAPIKey(r.Context(), id, org.ID)
	if err != nil {
		httpErr(w, http.StatusInternalServerError, "revoke failed")
		return
	}
	if !ok {
		httpErr(w, http.StatusNotFound, "key not found")
		return
	}
	w.WriteHeader(http.StatusNoContent)
}
