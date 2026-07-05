package main

import (
	"context"
	"log/slog"
	"net/http"
	"sync"
	"time"

	"github.com/guvi-geek/flash/internal/pool"
)

type ctxKey int

const (
	ctxRequestID ctxKey = iota
	ctxLogger
)

// withRequestLog assigns/propagates a request id, logs one structured line per
// request (method, path, status, bytes, duration, request_id), and exposes a
// request-scoped logger via context so handlers correlate their logs. The id is
// echoed back in X-Request-ID so a caller (and the dashboard) can quote it.
func (s *server) withRequestLog(h http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		rid := r.Header.Get("X-Request-ID")
		if rid == "" {
			rid = pool.NewID("req")
		}
		w.Header().Set("X-Request-ID", rid)
		lg := s.log.With("request_id", rid)
		ctx := context.WithValue(r.Context(), ctxRequestID, rid)
		ctx = context.WithValue(ctx, ctxLogger, lg)

		sw := &statusWriter{ResponseWriter: w, status: 200}
		start := time.Now()
		h.ServeHTTP(sw, r.WithContext(ctx))

		// Health/metrics probes are noisy and uninteresting — log them at debug.
		level := slog.LevelInfo
		switch {
		case sw.status >= 500:
			level = slog.LevelError
		case r.URL.Path == "/healthz" || r.URL.Path == "/readyz" || r.URL.Path == "/metrics":
			level = slog.LevelDebug
		}
		lg.Log(r.Context(), level, "http.request",
			"method", r.Method, "path", r.URL.Path, "status", sw.status,
			"bytes", sw.bytes, "dur_ms", time.Since(start).Milliseconds(),
			"remote", clientIP(r))
	})
}

// reqLog returns the request-scoped logger (falls back to the base logger).
func (s *server) reqLog(ctx context.Context) *slog.Logger {
	if lg, ok := ctx.Value(ctxLogger).(*slog.Logger); ok {
		return lg
	}
	return s.log
}

type statusWriter struct {
	http.ResponseWriter
	status int
	bytes  int
}

func (w *statusWriter) WriteHeader(code int) {
	w.status = code
	w.ResponseWriter.WriteHeader(code)
}

func (w *statusWriter) Write(b []byte) (int, error) {
	n, err := w.ResponseWriter.Write(b)
	w.bytes += n
	return n, err
}

// Flush/hijack passthroughs keep SSE/WebSocket-style handlers working through the
// wrapper (the terminal proxy hijacks the connection).
func (w *statusWriter) Flush() {
	if f, ok := w.ResponseWriter.(http.Flusher); ok {
		f.Flush()
	}
}

func clientIP(r *http.Request) string {
	if xff := r.Header.Get("X-Forwarded-For"); xff != "" {
		return xff
	}
	return r.RemoteAddr
}

// jobs tracks detached background work (async scoring) so graceful shutdown can
// wait for it to finish — "persist nothing-in-limbo": a submission that is mid-
// score when SIGTERM arrives still gets its result written before we exit.
type jobGroup struct{ wg sync.WaitGroup }

func (j *jobGroup) run(fn func()) { j.wg.Go(fn) }

// wait blocks until all jobs finish or the timeout elapses; returns true if drained.
func (j *jobGroup) wait(d time.Duration) bool {
	done := make(chan struct{})
	go func() { j.wg.Wait(); close(done) }()
	select {
	case <-done:
		return true
	case <-time.After(d):
		return false
	}
}
