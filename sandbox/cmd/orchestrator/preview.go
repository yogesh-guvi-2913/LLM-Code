package main

import (
	"net"
	"net/http"
	"net/http/httputil"
	"net/url"
	"strconv"
	"strings"
	"time"
)

// Preview reverse proxy.
//
// Frontend templates (e.g. q3 React/Vite) run a live dev server the candidate
// needs to SEE in a browser, not just curl. We expose it through a single
// entrypoint on the orchestrator using wildcard subdomains — exactly the spec's
// Caddy + wildcard-DNS shape, but with zero DNS setup: browsers resolve any
// `*.localhost` name to loopback per RFC 6761, so a preview hostname reaches the
// orchestrator directly.
//
//	browser ──HTTP/WS──> orchestrator :8090 ──reverse proxy──> container :3000
//	  <token>.<id>.preview.localhost       host-port for that session's dev server
//
// Vite keeps base="/" and its HMR WebSocket rides the same origin, so the proxy
// tunnels the Upgrade verbatim (httputil.ReverseProxy handles that). No per-
// session Vite restart, no path rewriting.
//
// Auth: the session token is encoded as the LEFT-MOST label of the preview host
// (`<token>.<id>.preview.localhost`). This is deliberate — the dashboard embeds
// the preview in an <iframe>, which is a *third-party* context relative to the
// dashboard origin. A cookie won't work there (SameSite=Lax is dropped in cross-
// site iframes, and SameSite=None requires HTTPS, which local dev lacks). By
// putting the token in the origin host, EVERY request the iframe makes — the
// document, Vite's root-absolute assets (/@vite/client, /src/...), and the HMR
// WebSocket — carries the token in the Host header automatically, with no cookie
// and no per-request token in asset URLs.

// previewHost reports whether a request targets the preview domain and, if so,
// returns the session id and token encoded as `<token>.<id>.preview.<domain>`.
func (s *server) previewHost(host string) (id, token string, ok bool) {
	host, _, _ = strings.Cut(host, ":") // strip port
	suffix := "." + s.previewDomain
	if !strings.HasSuffix(host, suffix) {
		return "", "", false
	}
	prefix := strings.TrimSuffix(host, suffix)
	// prefix is "<token>.<id>" — exactly two dot-separated labels.
	token, id, found := strings.Cut(prefix, ".")
	if !found || token == "" || id == "" || strings.Contains(id, ".") {
		return "", "", false
	}
	return id, token, true
}

// isPreviewHost is the cheap vhost discriminator used by the top-level router;
// it only checks the domain suffix, not the token.
func (s *server) isPreviewHost(host string) bool {
	host, _, _ = strings.Cut(host, ":")
	return strings.HasSuffix(host, "."+s.previewDomain)
}

// preview proxies a request on `<token>.<id>.preview.<domain>` to that session's
// live dev server. It is mounted as the top-level handler for the preview vhost.
func (s *server) preview(w http.ResponseWriter, r *http.Request) {
	id, token, ok := s.previewHost(r.Host)
	if !ok {
		httpErr(w, http.StatusBadRequest, "not a preview host")
		return
	}

	sess, err := s.store.GetSession(r.Context(), id)
	if err != nil {
		http.Error(w, "session not found", http.StatusNotFound)
		return
	}
	if sess.Status != "ACTIVE" {
		http.Error(w, "session not active", http.StatusGone)
		return
	}
	if sess.SessionToken == "" || token != sess.SessionToken {
		http.Error(w, "invalid preview token", http.StatusUnauthorized)
		return
	}

	// Route to the node that owns this session's sandbox (the durable session row
	// carries the node host + app port — works in both local and cluster mode, and
	// survives a control-plane restart).
	if sess.HostPort == 0 {
		http.Error(w, "sandbox not reachable", http.StatusBadGateway)
		return
	}
	target := &url.URL{Scheme: "http", Host: net.JoinHostPort(sess.NodeHost, strconv.Itoa(sess.HostPort))}
	proxy := httputil.NewSingleHostReverseProxy(target)
	proxy.FlushInterval = 100 * time.Millisecond // stream dev-server output
	proxy.ErrorHandler = func(w http.ResponseWriter, _ *http.Request, _ error) {
		http.Error(w, "preview upstream unavailable", http.StatusBadGateway)
	}
	proxy.ServeHTTP(w, r)
}
