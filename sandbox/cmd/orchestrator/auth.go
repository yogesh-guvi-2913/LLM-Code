package main

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"net/http"
	"strings"
	"sync"

	"golang.org/x/time/rate"

	"github.com/guvi-geek/flash/internal/pool"
	"github.com/guvi-geek/flash/internal/store"
)

// Auth has two distinct credential types that must never be conflated:
//
//   - Org API key (`flash_…`): the OPERATOR credential. It identifies an org, gates
//     the control plane (create/destroy sandboxes, manage templates, read the
//     dashboard), and carries that org's concurrency cap. Sent as `Authorization:
//     Bearer flash_…` on /v1/* operator routes.
//   - Session token (`tok_…`): the CANDIDATE credential, scoped to ONE session.
//     It authorizes that session's submit, terminal, and preview — nothing else.
//     Unchanged from v1; handled where those routes already check it.
//
// This file implements the operator side: minting, hashing, lookup middleware,
// per-org rate limiting, and the concurrency cap.

const apiKeyPrefix = "flash_"

type orgCtxKey struct{}
type keyIDCtxKey struct{}

// authn holds auth config + the in-process per-org rate limiters. Single-node:
// the limiters live here; Phase 3 moves them behind Redis for a multi-node fleet.
type authn struct {
	enabled bool
	rps     float64
	burst   int

	mu       sync.Mutex
	limiters map[string]*rate.Limiter
}

func newAuthn(enabled bool, rps float64, burst int) *authn {
	return &authn{enabled: enabled, rps: rps, burst: burst, limiters: map[string]*rate.Limiter{}}
}

func (a *authn) limiter(orgID string) *rate.Limiter {
	a.mu.Lock()
	defer a.mu.Unlock()
	l, ok := a.limiters[orgID]
	if !ok {
		l = rate.NewLimiter(rate.Limit(a.rps), a.burst)
		a.limiters[orgID] = l
	}
	return l
}

// hashKey is the at-rest representation of a raw API key. SHA-256 is the right
// choice for a 256-bit random token (constant-time compared on lookup).
func hashKey(raw string) string {
	sum := sha256.Sum256([]byte(raw))
	return hex.EncodeToString(sum[:])
}

// mintKey returns a fresh raw key (`flash_<32 hex>`) and its display prefix.
func mintKey() (raw, prefix string) {
	b := make([]byte, 16)
	_, _ = rand.Read(b)
	raw = apiKeyPrefix + hex.EncodeToString(b)
	return raw, raw[:len(apiKeyPrefix)+6]
}

// bootstrapAuth guarantees a usable operator credential exists on boot:
//   - always ensure a "default" org;
//   - if BOOTSTRAP_API_KEY is set, register it (idempotent) so dashboards/CI have
//     a known key;
//   - else, if auth is enabled and no keys exist yet, mint one and log it ONCE.
func (s *server) bootstrapAuth(ctx context.Context, concurrency int) {
	if err := s.store.EnsureOrg(ctx, "default", "Default", concurrency); err != nil {
		s.log.Error("bootstrap: ensure org", "err", err)
		return
	}
	if raw := env("BOOTSTRAP_API_KEY", ""); raw != "" {
		_ = s.store.UpsertAPIKey(ctx, pool.NewID("key"), "default", "bootstrap", hashKey(raw), keyPrefix(raw))
		s.log.Info("bootstrap api key registered from env", "prefix", keyPrefix(raw))
		return
	}
	if !s.auth.enabled {
		return
	}
	n, err := s.store.CountAPIKeys(ctx)
	if err != nil {
		s.log.Error("bootstrap: count keys", "err", err)
		return
	}
	if n == 0 {
		raw, prefix := mintKey()
		if err := s.store.UpsertAPIKey(ctx, pool.NewID("key"), "default", "auto", hashKey(raw), prefix); err != nil {
			s.log.Error("bootstrap: mint key", "err", err)
			return
		}
		// Printed once, at WARN so it stands out — there is no way to recover the
		// raw key later (only its hash is stored).
		s.log.Warn("AUTH ENABLED — first API key minted, SAVE IT (shown once)", "api_key", raw)
	}
}

// requireOrg authenticates an operator request by its Bearer API key, enforces the
// per-org rate limit, and stashes the org in the request context. When auth is
// disabled it injects a synthetic "default" org so downstream concurrency limiting
// still has an identity to count against.
func (s *server) requireOrg(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !s.auth.enabled {
			next(w, r.WithContext(context.WithValue(r.Context(), orgCtxKey{},
				store.Org{ID: "default", Name: "Default", ConcurrencyLimit: s.defaultConcurrency})))
			return
		}
		raw := bearer(r)
		if raw == "" || !strings.HasPrefix(raw, apiKeyPrefix) {
			httpErr(w, http.StatusUnauthorized, "missing or malformed API key")
			return
		}
		org, keyID, ok, err := s.store.LookupAPIKey(r.Context(), hashKey(raw))
		if err != nil {
			httpErr(w, http.StatusInternalServerError, "auth lookup failed")
			return
		}
		if !ok {
			httpErr(w, http.StatusUnauthorized, "invalid API key")
			return
		}
		if !s.auth.limiter(org.ID).Allow() {
			httpErr(w, http.StatusTooManyRequests, "rate limit exceeded")
			return
		}
		go func() { _ = s.store.TouchAPIKey(context.Background(), keyID) }()
		ctx := context.WithValue(r.Context(), orgCtxKey{}, org)
		ctx = context.WithValue(ctx, keyIDCtxKey{}, keyID)
		next(w, r.WithContext(ctx))
	}
}

// orgFrom returns the authenticated org placed by requireOrg.
func orgFrom(ctx context.Context) (store.Org, bool) {
	o, ok := ctx.Value(orgCtxKey{}).(store.Org)
	return o, ok
}

// bearer extracts a raw Bearer token, with a constant-time guard against the
// literal "Bearer " never matching an empty token.
func bearer(r *http.Request) string {
	h := r.Header.Get("Authorization")
	const p = "Bearer "
	if len(h) <= len(p) || subtle.ConstantTimeCompare([]byte(h[:len(p)]), []byte(p)) != 1 {
		return ""
	}
	return strings.TrimSpace(h[len(p):])
}

func keyPrefix(raw string) string {
	if len(raw) >= len(apiKeyPrefix)+6 {
		return raw[:len(apiKeyPrefix)+6]
	}
	return raw
}
