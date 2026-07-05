package flash

import (
	"bytes"
	"context"
	"io"
	"net/http"
)

// TemplateService lists and registers sandbox templates.
type TemplateService struct{ c *Client }

// Template is a sandbox image + its pool/resource config.
type Template struct {
	ID          string  `json:"id"`
	Slug        string  `json:"slug,omitempty"`
	Title       string  `json:"title,omitempty"`
	Language    string  `json:"language,omitempty"`
	Description string  `json:"description,omitempty"`
	Image       string  `json:"image"`
	MinWarm     int     `json:"min_warm"`
	VCPU        float64 `json:"vcpu,omitempty"`
	MemoryMB    int     `json:"memory_mb,omitempty"`
	PidsLimit   int     `json:"pids_limit,omitempty"`
	// Kind is "api" or "frontend" (frontend templates get a browser preview).
	Kind   string `json:"kind"`
	DevCmd string `json:"dev_cmd,omitempty"`
	// Warm is the live warm-pool depth (list only).
	Warm int `json:"warm,omitempty"`
}

// List returns all registered templates with their live warm depth.
func (s *TemplateService) List(ctx context.Context) ([]Template, error) {
	var out []Template
	err := s.c.do(ctx, http.MethodGet, "/v1/templates", nil, &out)
	return out, err
}

// Create registers a new template at runtime; the orchestrator validates the
// image exists and starts warming the pool immediately.
func (s *TemplateService) Create(ctx context.Context, t Template) (*Template, error) {
	var created Template
	if err := s.c.do(ctx, http.MethodPost, "/v1/templates", t, &created); err != nil {
		return nil, err
	}
	return &created, nil
}

// Scale sets a template's warm-pool floor at runtime (the pre-warm knob).
func (s *TemplateService) Scale(ctx context.Context, id string, minWarm int) error {
	return s.c.do(ctx, http.MethodPost, "/v1/templates/"+id+"/min_warm",
		map[string]int{"min_warm": minWarm}, nil)
}

// bytesReader adapts a []byte for the raw request path without pulling extra deps
// into sandbox.go's imports.
func bytesReader(b []byte) io.Reader { return bytes.NewReader(b) }
