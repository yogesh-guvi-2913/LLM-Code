package main

import (
	"fmt"
	"sync"

	"github.com/guvi-geek/flash/internal/pool"
	"github.com/guvi-geek/flash/internal/templates"
)

// registry is the runtime-mutable set of templates. v1 seeds it from the static
// defaults; the dashboard can register more via POST /v1/templates (the spec's
// "recruiter publishes a question" path, minus CodeBuild). It is the single
// source of truth for templates, their pool configs, and their scorer images,
// guarded by one RWMutex so concurrent reads (list/claim/score) stay cheap.
type registry struct {
	mu          sync.RWMutex
	order       []string                       // preserves display order
	templates   map[string]Template            // id -> template
	cfg         map[string]pool.QuestionConfig // id -> pool config
	scorerImage map[string]string              // id -> scorer image
	runtime     string                         // sandbox runtime ("" | "runsc")
	previewPort string                         // external port for HMR
}

func newRegistry(tmpls []Template, runtime, previewPort string) *registry {
	r := &registry{
		templates:   map[string]Template{},
		cfg:         map[string]pool.QuestionConfig{},
		scorerImage: map[string]string{},
		runtime:     runtime,
		previewPort: previewPort,
	}
	for _, t := range tmpls {
		r.put(t)
	}
	return r
}

// put inserts/updates a template and its derived config. Caller-internal; not
// locked (used during construction and under Add's lock).
func (r *registry) put(t Template) {
	if _, exists := r.templates[t.ID]; !exists {
		r.order = append(r.order, t.ID)
	}
	r.templates[t.ID] = t
	r.cfg[t.ID] = templates.Config(t, r.runtime, r.previewPort)
	r.scorerImage[t.ID] = t.Image
}

// Add registers a new template at runtime. Returns an error if the id collides.
func (r *registry) Add(t Template) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	if _, exists := r.templates[t.ID]; exists {
		return fmt.Errorf("template %q already exists", t.ID)
	}
	r.put(t)
	return nil
}

// setMinWarm updates a template's warm-depth floor in both the derived pool config
// and the displayed Template, so /v1/templates reflects a scheduled scale. No-op
// for an unknown id (the pool is the authority on whether the scale applied).
func (r *registry) setMinWarm(id string, n int) {
	r.mu.Lock()
	defer r.mu.Unlock()
	if c, ok := r.cfg[id]; ok {
		c.MinWarm = n
		r.cfg[id] = c
	}
	if t, ok := r.templates[id]; ok {
		t.MinWarm = n
		r.templates[id] = t
	}
}

func (r *registry) get(id string) (Template, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	t, ok := r.templates[id]
	return t, ok
}

func (r *registry) config(id string) (pool.QuestionConfig, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	c, ok := r.cfg[id]
	return c, ok
}

func (r *registry) scorer(id string) string {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return r.scorerImage[id]
}

// ids returns the template ids in display order (snapshot copy, safe to range).
func (r *registry) ids() []string {
	r.mu.RLock()
	defer r.mu.RUnlock()
	out := make([]string, len(r.order))
	copy(out, r.order)
	return out
}

// list returns the templates in display order (snapshot copy).
func (r *registry) list() []Template {
	r.mu.RLock()
	defer r.mu.RUnlock()
	out := make([]Template, 0, len(r.order))
	for _, id := range r.order {
		out = append(out, r.templates[id])
	}
	return out
}
