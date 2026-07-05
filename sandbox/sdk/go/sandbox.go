package flash

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"
)

// SandboxService creates, lists, and connects to sandboxes.
type SandboxService struct{ c *Client }

// Sandbox is a live (or past) isolated environment. Obtain one via
// Sandboxes.Create, Sandboxes.Connect, or Sandboxes.List; then use its methods
// to run commands and manage files. Fields are a snapshot from the last API
// call that produced it.
type Sandbox struct {
	ID         string            `json:"sandbox_id"`
	TemplateID string            `json:"template_id"`
	State      string            `json:"state"` // "running" | "submitted" | "timed_out" | "destroyed"
	CreatedAt  time.Time         `json:"created_at"`
	ExpiresAt  time.Time         `json:"expires_at"`
	Metadata   map[string]string `json:"metadata"`

	// AppURL is the sandbox's dev server (http://host:port), reachable while
	// running. For frontend templates prefer PreviewURL in a browser.
	AppURL string `json:"app_url"`
	// PreviewURL is the authenticated browser preview (frontend templates only).
	PreviewURL string `json:"preview_url"`
	// TerminalURL is the raw PTY WebSocket; TerminalPage is an embeddable
	// xterm.js page served by the orchestrator.
	TerminalURL  string `json:"terminal_url"`
	TerminalPage string `json:"terminal_page"`
	// Token is the per-sandbox credential for the candidate plane (terminal,
	// preview, submit). Keep it server-side; hand it only to the end user of
	// THIS sandbox.
	Token string `json:"token"`

	c *Client
}

// CreateSandboxOpts configures Sandboxes.Create.
type CreateSandboxOpts struct {
	// Template is the template id to boot from (required), e.g. "q1".
	Template string
	// Timeout is how long the sandbox lives before auto-teardown. Zero means
	// the template's default. Extend later with SetTimeout.
	Timeout time.Duration
	// Metadata is attached to the sandbox and returned on get/list.
	Metadata map[string]string
}

// Create claims a sandbox — warm-pool hit in well under 2s, cold boot otherwise.
func (s *SandboxService) Create(ctx context.Context, opts CreateSandboxOpts) (*Sandbox, error) {
	if opts.Template == "" {
		return nil, fmt.Errorf("flash: CreateSandboxOpts.Template required")
	}
	req := map[string]any{"template_id": opts.Template}
	if opts.Timeout > 0 {
		req["timeout_seconds"] = int(opts.Timeout / time.Second)
	}
	if len(opts.Metadata) > 0 {
		req["metadata"] = opts.Metadata
	}
	var sbx Sandbox
	if err := s.c.do(ctx, http.MethodPost, "/v1/sandboxes", req, &sbx); err != nil {
		return nil, err
	}
	sbx.c = s.c
	return &sbx, nil
}

// Connect attaches to an existing sandbox by id.
func (s *SandboxService) Connect(ctx context.Context, id string) (*Sandbox, error) {
	var sbx Sandbox
	if err := s.c.do(ctx, http.MethodGet, "/v1/sandboxes/"+url.PathEscape(id), nil, &sbx); err != nil {
		return nil, err
	}
	sbx.c = s.c
	return &sbx, nil
}

// List returns the org's sandboxes, newest first. runningOnly narrows to live ones.
func (s *SandboxService) List(ctx context.Context, runningOnly bool) ([]*Sandbox, error) {
	path := "/v1/sandboxes"
	if runningOnly {
		path += "?state=running"
	}
	var out struct {
		Sandboxes []*Sandbox `json:"sandboxes"`
	}
	if err := s.c.do(ctx, http.MethodGet, path, nil, &out); err != nil {
		return nil, err
	}
	for _, sbx := range out.Sandboxes {
		sbx.c = s.c
	}
	return out.Sandboxes, nil
}

// Refresh re-fetches the sandbox's state from the orchestrator in place.
func (sb *Sandbox) Refresh(ctx context.Context) error {
	fresh, err := sb.c.Sandboxes.Connect(ctx, sb.ID)
	if err != nil {
		return err
	}
	c := sb.c
	*sb = *fresh
	sb.c = c
	return nil
}

// Kill destroys the sandbox immediately. Idempotent.
func (sb *Sandbox) Kill(ctx context.Context) error {
	return sb.c.do(ctx, http.MethodDelete, "/v1/sandboxes/"+url.PathEscape(sb.ID), nil, nil)
}

// SetTimeout resets the sandbox's lifetime to now+d (keep-alive).
func (sb *Sandbox) SetTimeout(ctx context.Context, d time.Duration) error {
	var out struct {
		ExpiresAt time.Time `json:"expires_at"`
	}
	err := sb.c.do(ctx, http.MethodPost, "/v1/sandboxes/"+url.PathEscape(sb.ID)+"/timeout",
		map[string]any{"timeout_seconds": int(d / time.Second)}, &out)
	if err == nil {
		sb.ExpiresAt = out.ExpiresAt
	}
	return err
}

// ExecResult is one command's outcome. A non-zero ExitCode is a normal result,
// not a Go error — transport failures and timeouts are errors.
type ExecResult struct {
	Stdout   string `json:"stdout"`
	Stderr   string `json:"stderr"`
	ExitCode int    `json:"exit_code"`
	Duration time.Duration
}

// ExecOpts tunes a command run.
type ExecOpts struct {
	// Cwd is relative to the sandbox work dir (default: the work dir itself).
	Cwd string
	// Env adds KEY=VALUE pairs for this command only.
	Env map[string]string
	// Timeout bounds the command (server default 60s, max 5m).
	Timeout time.Duration
}

// Run executes a shell command line (via `sh -c`) in the sandbox.
func (sb *Sandbox) Run(ctx context.Context, command string, opts ...ExecOpts) (*ExecResult, error) {
	return sb.exec(ctx, map[string]any{"command": command}, opts...)
}

// Exec executes an argv directly (no shell interpretation).
func (sb *Sandbox) Exec(ctx context.Context, argv []string, opts ...ExecOpts) (*ExecResult, error) {
	return sb.exec(ctx, map[string]any{"cmd": argv}, opts...)
}

func (sb *Sandbox) exec(ctx context.Context, req map[string]any, opts ...ExecOpts) (*ExecResult, error) {
	if len(opts) > 0 {
		o := opts[0]
		if o.Cwd != "" {
			req["cwd"] = o.Cwd
		}
		if len(o.Env) > 0 {
			req["env"] = o.Env
		}
		if o.Timeout > 0 {
			req["timeout_seconds"] = int(o.Timeout / time.Second)
		}
	}
	var out struct {
		Stdout     string `json:"stdout"`
		Stderr     string `json:"stderr"`
		ExitCode   int    `json:"exit_code"`
		DurationMS int64  `json:"duration_ms"`
	}
	if err := sb.c.do(ctx, http.MethodPost, "/v1/sandboxes/"+url.PathEscape(sb.ID)+"/exec", req, &out); err != nil {
		return nil, err
	}
	return &ExecResult{
		Stdout: out.Stdout, Stderr: out.Stderr, ExitCode: out.ExitCode,
		Duration: time.Duration(out.DurationMS) * time.Millisecond,
	}, nil
}

// Files accesses the sandbox filesystem (the writable work dir).
func (sb *Sandbox) Files() *FileService { return &FileService{sb: sb} }

// FileService reads and writes files inside one sandbox's work dir. All paths
// are relative to the work dir; traversal outside it is rejected server-side.
type FileService struct{ sb *Sandbox }

// List returns every file under the work dir, as relative paths.
func (f *FileService) List(ctx context.Context) ([]string, error) {
	var out struct {
		Files []string `json:"files"`
	}
	err := f.sb.c.do(ctx, http.MethodGet, "/v1/sandboxes/"+url.PathEscape(f.sb.ID)+"/files", nil, &out)
	return out.Files, err
}

// Read returns a file's contents.
func (f *FileService) Read(ctx context.Context, path string) ([]byte, error) {
	resp, err := f.sb.c.raw(ctx, http.MethodGet,
		"/v1/sandboxes/"+url.PathEscape(f.sb.ID)+"/files/content?path="+url.QueryEscape(path), "", nil)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	return io.ReadAll(resp.Body)
}

// Write creates or replaces a file (parent directories are created).
func (f *FileService) Write(ctx context.Context, path string, content []byte) error {
	resp, err := f.sb.c.raw(ctx, http.MethodPut,
		"/v1/sandboxes/"+url.PathEscape(f.sb.ID)+"/files/content?path="+url.QueryEscape(path),
		"application/octet-stream", bytesReader(content))
	if err != nil {
		return err
	}
	resp.Body.Close()
	return nil
}

// Delete removes a file or directory.
func (f *FileService) Delete(ctx context.Context, path string) error {
	return f.sb.c.do(ctx, http.MethodDelete,
		"/v1/sandboxes/"+url.PathEscape(f.sb.ID)+"/files/content?path="+url.QueryEscape(path), nil, nil)
}
