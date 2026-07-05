// Package flash is the official Go SDK for the Flash sandbox engine — a
// self-hosted sandbox platform: claim an isolated sandbox from a warm pool in
// under 2 seconds, run commands in it, read and write its files, open its
// live preview, and destroy it.
//
// Quick start:
//
//	client, err := flash.New() // FLASH_API_KEY + FLASH_BASE_URL from env
//	sbx, err := client.Sandboxes.Create(ctx, flash.CreateSandboxOpts{Template: "q1"})
//	defer sbx.Kill(ctx)
//	res, err := sbx.Run(ctx, "node -e 'console.log(40+2)'")
//	fmt.Print(res.Stdout) // "42\n"
//
// The SDK is dependency-free (stdlib only) and every call is context-aware.
package flash

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"
)

const (
	defaultBaseURL = "http://127.0.0.1:8090"
	envAPIKey      = "FLASH_API_KEY"
	envBaseURL     = "FLASH_BASE_URL"
)

// Client is the entry point. Construct with New; zero value is not usable.
type Client struct {
	baseURL string
	apiKey  string
	http    *http.Client

	// Sandboxes creates and controls sandboxes (the core surface).
	Sandboxes *SandboxService
	// Templates lists and registers sandbox templates.
	Templates *TemplateService
	// APIKeys manages the org's API keys.
	APIKeys *APIKeyService
	// Assessments is the assessment layer on top of sandboxes:
	// candidate sessions with submit → automated scoring.
	Assessments *AssessmentService
}

// Option configures a Client.
type Option func(*Client)

// WithAPIKey sets the org API key (`flash_…`). Overrides FLASH_API_KEY.
func WithAPIKey(key string) Option { return func(c *Client) { c.apiKey = key } }

// WithBaseURL points the client at an orchestrator. Overrides FLASH_BASE_URL.
func WithBaseURL(u string) Option { return func(c *Client) { c.baseURL = strings.TrimRight(u, "/") } }

// WithHTTPClient swaps the underlying *http.Client (custom TLS, proxies, tracing).
func WithHTTPClient(h *http.Client) Option { return func(c *Client) { c.http = h } }

// New builds a Client. The API key and base URL default from FLASH_API_KEY /
// FLASH_BASE_URL; an explicit Option wins. An empty API key is allowed only
// for orchestrators running with AUTH_ENABLED=false.
func New(opts ...Option) (*Client, error) {
	c := &Client{
		baseURL: strings.TrimRight(envOr(envBaseURL, defaultBaseURL), "/"),
		apiKey:  os.Getenv(envAPIKey),
		http:    &http.Client{Timeout: 620 * time.Second},
	}
	for _, o := range opts {
		o(c)
	}
	if c.baseURL == "" {
		return nil, fmt.Errorf("flash: base URL required (set %s or WithBaseURL)", envBaseURL)
	}
	c.Sandboxes = &SandboxService{c: c}
	c.Templates = &TemplateService{c: c}
	c.APIKeys = &APIKeyService{c: c}
	c.Assessments = &AssessmentService{c: c}
	return c, nil
}

// APIError is a non-2xx response from the orchestrator.
type APIError struct {
	StatusCode int
	Message    string
}

func (e *APIError) Error() string {
	return fmt.Sprintf("flash: API error %d: %s", e.StatusCode, e.Message)
}

// IsNotFound reports whether err is a 404 APIError.
func IsNotFound(err error) bool {
	var ae *APIError
	return asAPIErr(err, &ae) && ae.StatusCode == http.StatusNotFound
}

func asAPIErr(err error, target **APIError) bool {
	for err != nil {
		if ae, ok := err.(*APIError); ok {
			*target = ae
			return true
		}
		u, ok := err.(interface{ Unwrap() error })
		if !ok {
			return false
		}
		err = u.Unwrap()
	}
	return false
}

// do performs a JSON request. body (if non-nil) is marshalled; out (if non-nil)
// receives the decoded response.
func (c *Client) do(ctx context.Context, method, path string, body, out any) error {
	var rd io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			return fmt.Errorf("flash: marshal request: %w", err)
		}
		rd = bytes.NewReader(b)
	}
	resp, err := c.raw(ctx, method, path, "application/json", rd)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if out == nil {
		_, _ = io.Copy(io.Discard, resp.Body)
		return nil
	}
	if err := json.NewDecoder(resp.Body).Decode(out); err != nil {
		return fmt.Errorf("flash: decode response: %w", err)
	}
	return nil
}

// raw performs a request and returns the response with a 2xx status; non-2xx is
// consumed and returned as *APIError. Caller closes the body on success.
func (c *Client) raw(ctx context.Context, method, path, contentType string, body io.Reader) (*http.Response, error) {
	req, err := http.NewRequestWithContext(ctx, method, c.baseURL+path, body)
	if err != nil {
		return nil, fmt.Errorf("flash: build request: %w", err)
	}
	if body != nil && contentType != "" {
		req.Header.Set("Content-Type", contentType)
	}
	if c.apiKey != "" {
		req.Header.Set("Authorization", "Bearer "+c.apiKey)
	}
	resp, err := c.http.Do(req)
	if err != nil {
		return nil, fmt.Errorf("flash: %s %s: %w", method, path, err)
	}
	if resp.StatusCode >= 300 {
		defer resp.Body.Close()
		b, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		msg := strings.TrimSpace(string(b))
		var je struct {
			Error string `json:"error"`
		}
		if json.Unmarshal(b, &je) == nil && je.Error != "" {
			msg = je.Error
		}
		return nil, &APIError{StatusCode: resp.StatusCode, Message: msg}
	}
	return resp, nil
}

func decodeJSON(r io.Reader, out any) error {
	if err := json.NewDecoder(r).Decode(out); err != nil {
		return fmt.Errorf("flash: decode response: %w", err)
	}
	return nil
}

func envOr(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}
