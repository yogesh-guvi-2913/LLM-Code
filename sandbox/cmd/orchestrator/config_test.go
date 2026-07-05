package main

import "testing"

// TestLoadConfigValid checks a sane env produces a valid, fully-populated config.
func TestLoadConfigValid(t *testing.T) {
	t.Setenv("DATABASE_URL", "postgres://localhost:5432/flash?sslmode=disable")
	t.Setenv("LISTEN_ADDR", ":8090")
	t.Setenv("SANDBOX_RUNTIME", "runsc")
	t.Setenv("AUTH_RATE_RPS", "20")
	t.Setenv("LOG_LEVEL", "debug")

	cfg, err := loadConfig()
	if err != nil {
		t.Fatalf("expected valid config, got %v", err)
	}
	if cfg.Addr != ":8090" {
		t.Errorf("addr = %q", cfg.Addr)
	}
	if cfg.PreviewPort != "8090" {
		t.Errorf("preview port derived wrong: %q", cfg.PreviewPort)
	}
	if cfg.Runtime != "runsc" {
		t.Errorf("runtime = %q", cfg.Runtime)
	}
}

// TestLoadConfigRejects asserts each invalid value fails fast at load.
func TestLoadConfigRejects(t *testing.T) {
	cases := []struct {
		name string
		env  map[string]string
	}{
		{"bad addr", map[string]string{"LISTEN_ADDR": "not-an-addr:::"}},
		{"bad runtime", map[string]string{"SANDBOX_RUNTIME": "kata"}},
		{"bad log level", map[string]string{"LOG_LEVEL": "trace"}},
		{"zero rate", map[string]string{"AUTH_RATE_RPS": "0"}},
		{"zero burst", map[string]string{"AUTH_RATE_BURST": "0"}},
		{"zero ram", map[string]string{"COST_NODE_RAM_GB": "0"}},
		{"bad bootstrap key", map[string]string{"AUTH_ENABLED": "true", "BOOTSTRAP_API_KEY": "nope_123"}},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			// Baseline valid env, then override with the one bad value.
			t.Setenv("DATABASE_URL", "postgres://localhost/flash")
			t.Setenv("LISTEN_ADDR", ":8090")
			t.Setenv("AUTH_RATE_RPS", "20")
			t.Setenv("AUTH_RATE_BURST", "40")
			t.Setenv("COST_NODE_RAM_GB", "32")
			t.Setenv("LOG_LEVEL", "info")
			t.Setenv("SANDBOX_RUNTIME", "")
			t.Setenv("AUTH_ENABLED", "false")
			t.Setenv("BOOTSTRAP_API_KEY", "")
			for k, v := range c.env {
				t.Setenv(k, v)
			}
			if _, err := loadConfig(); err == nil {
				t.Fatalf("expected %s to be rejected, got nil", c.name)
			}
		})
	}
}
