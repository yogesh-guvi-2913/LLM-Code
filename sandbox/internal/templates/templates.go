// Package templates is the shared template domain — the image + pool config +
// display metadata for each question. It lives in internal/ (not in the
// orchestrator's package main) because BOTH the control plane and every node-agent
// need it: the control plane to list/validate, the nodes to know what to warm.
package templates

import (
	"os"
	"regexp"
	"time"

	"github.com/guvi-geek/flash/internal/pool"
)

// Template is a question's image + pool config + display metadata.
type Template struct {
	ID          string  `json:"id"`
	Slug        string  `json:"slug"`
	Title       string  `json:"title"`
	Language    string  `json:"language"`
	Description string  `json:"description"`
	Image       string  `json:"image"`
	MinWarm     int     `json:"min_warm"`
	VCPU        float64 `json:"vcpu"`
	MemoryMB    int     `json:"memory_mb"`
	PidsLimit   int     `json:"pids_limit"`
	// Kind is "api" (curl the app port directly) or "frontend" (browser preview
	// via the reverse proxy). The dashboard renders previews only for frontends.
	Kind   string `json:"kind"`
	DevCmd string `json:"dev_cmd,omitempty"`
}

// IDPattern constrains user-supplied template ids to safe, url/label-friendly
// tokens (they end up in container labels and subdomains).
var IDPattern = regexp.MustCompile(`^[a-z0-9][a-z0-9-]{0,31}$`)

// Default is the static v1 template set, seeded into the registry on boot.
func Default() []Template {
	return []Template{
		{
			ID: "q1", Slug: "express-todo", Title: "Express Todo API", Language: "Node.js",
			Description: "Implement POST /todos and GET /todos/:id on an Express REST API.",
			Image:       env("Q1_IMAGE", "flash-sandbox:q1-express-api-v1"),
			MinWarm:     3, VCPU: 0.5, MemoryMB: 512, PidsLimit: 150, Kind: "api", DevCmd: "node server.js",
		},
		{
			ID: "q2", Slug: "flask-todo", Title: "Flask Todo API", Language: "Python",
			Description: "Implement POST /todos and GET /todos/<id> on a Flask REST API.",
			Image:       env("Q2_IMAGE", "flash-sandbox:q2-flask-api-v1"),
			MinWarm:     2, VCPU: 0.5, MemoryMB: 512, PidsLimit: 150, Kind: "api", DevCmd: "python server.py",
		},
		{
			ID: "q3", Slug: "react-todo", Title: "React Todo App", Language: "React/Vite",
			Description: "Build an interactive Todo list in React — add, list, and toggle todos.",
			Image:       env("Q3_IMAGE", "flash-sandbox:q3-react-vite-v1"),
			// Frontend dev servers (Vite) are heavier and slower to boot, so a
			// smaller warm pool with more memory headroom.
			MinWarm: 2, VCPU: 1.0, MemoryMB: 768, PidsLimit: 200, Kind: "frontend",
			// vite.config.cjs is loaded in-memory (no temp file), so plain vite
			// boots fine under the read-only /app rootfs.
			DevCmd: "npx vite --host 0.0.0.0 --port 3000",
		},
	}
}

// Config derives the pool + image config for one template. previewPort is handed to
// frontend templates as HMR_CLIENT_PORT so Vite's HMR WebSocket targets the
// orchestrator's reverse proxy.
func Config(t Template, runtime, previewPort string) pool.QuestionConfig {
	mem := int64(t.MemoryMB)
	if mem == 0 {
		mem = 512
	}
	pids := int64(t.PidsLimit)
	if pids == 0 {
		pids = 150
	}
	vcpu := t.VCPU
	if vcpu == 0 {
		vcpu = 0.5
	}
	var extraEnv []string
	if t.Kind == "frontend" {
		extraEnv = []string{"HMR_CLIENT_PORT=" + previewPort}
	}
	return pool.QuestionConfig{
		Image:       t.Image,
		MinWarm:     t.MinWarm,
		AppPort:     3000,
		ToolboxPort: 49983,
		MemoryMB:    mem,
		CPUQuota:    int64(vcpu * 100000),
		PidsLimit:   pids,
		TimeLimit:   90 * time.Minute,
		Runtime:     runtime,
		DevCmd:      t.DevCmd,
		ExtraEnv:    extraEnv,
	}
}

func env(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}
