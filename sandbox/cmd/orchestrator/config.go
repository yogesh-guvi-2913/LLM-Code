package main

import (
	"fmt"
	"net"
	"os"
	"strings"
)

// Config is the orchestrator's validated runtime configuration. Loading it fails
// fast (before any side effects) on a bad value, so a misconfigured deploy dies at
// boot with a clear message instead of misbehaving under load.
type Config struct {
	DSN            string
	Network        string
	Addr           string
	Runtime        string // "" | "runsc" (gVisor)
	PreviewDomain  string
	PreviewPort    string
	AuthEnabled    bool
	BootstrapKey   string
	Concurrency    int
	RateRPS        float64
	RateBurst      int
	ClusterMode    bool
	RedisURL       string
	NodeUSDPerHour float64
	NodeRAMGB      float64
	SandboxPerNode int // sandboxes one node holds — the required-nodes/ASG signal divisor
	LogLevel       string
}

func loadConfig() (Config, error) {
	c := Config{
		DSN:            env("DATABASE_URL", "postgres://localhost:5432/flash?sslmode=disable"),
		Network:        env("SANDBOX_NET", "sandbox-net"),
		Addr:           env("LISTEN_ADDR", ":8080"),
		Runtime:        env("SANDBOX_RUNTIME", ""),
		PreviewDomain:  env("PREVIEW_DOMAIN", "preview.localhost"),
		AuthEnabled:    env("AUTH_ENABLED", "true") == "true",
		BootstrapKey:   os.Getenv("BOOTSTRAP_API_KEY"),
		Concurrency:    envInt("ORG_CONCURRENCY_LIMIT", 20),
		RateRPS:        envFloat("AUTH_RATE_RPS", 20),
		RateBurst:      envInt("AUTH_RATE_BURST", 40),
		ClusterMode:    env("CLUSTER_MODE", "false") == "true",
		RedisURL:       env("REDIS_URL", "redis://127.0.0.1:6379/0"),
		NodeUSDPerHour: envFloat("COST_NODE_USD_PER_HR", 0.37),
		NodeRAMGB:      envFloat("COST_NODE_RAM_GB", 32),
		SandboxPerNode: envInt("SANDBOXES_PER_NODE", 40),
		LogLevel:       env("LOG_LEVEL", "info"),
	}
	c.PreviewPort = env("PREVIEW_PORT", portOf(c.Addr))

	var errs []string
	if c.DSN == "" {
		errs = append(errs, "DATABASE_URL is required")
	}
	if _, _, err := net.SplitHostPort(normalizeAddr(c.Addr)); err != nil {
		errs = append(errs, fmt.Sprintf("LISTEN_ADDR %q is not a host:port (%v)", c.Addr, err))
	}
	if c.Runtime != "" && c.Runtime != "runsc" {
		errs = append(errs, fmt.Sprintf("SANDBOX_RUNTIME %q must be empty or \"runsc\"", c.Runtime))
	}
	if c.Concurrency < 0 {
		errs = append(errs, "ORG_CONCURRENCY_LIMIT must be >= 0")
	}
	if c.RateRPS <= 0 {
		errs = append(errs, "AUTH_RATE_RPS must be > 0")
	}
	if c.RateBurst <= 0 {
		errs = append(errs, "AUTH_RATE_BURST must be > 0")
	}
	if c.NodeRAMGB <= 0 {
		errs = append(errs, "COST_NODE_RAM_GB must be > 0")
	}
	if c.NodeUSDPerHour < 0 {
		errs = append(errs, "COST_NODE_USD_PER_HR must be >= 0")
	}
	if c.SandboxPerNode < 1 {
		errs = append(errs, "SANDBOXES_PER_NODE must be >= 1")
	}
	if c.PreviewDomain == "" {
		errs = append(errs, "PREVIEW_DOMAIN is required")
	}
	switch c.LogLevel {
	case "debug", "info", "warn", "error":
	default:
		errs = append(errs, fmt.Sprintf("LOG_LEVEL %q must be debug|info|warn|error", c.LogLevel))
	}
	if c.AuthEnabled && c.BootstrapKey != "" && !strings.HasPrefix(c.BootstrapKey, apiKeyPrefix) {
		errs = append(errs, "BOOTSTRAP_API_KEY must start with \""+apiKeyPrefix+"\"")
	}
	if len(errs) > 0 {
		return Config{}, fmt.Errorf("invalid configuration:\n  - %s", strings.Join(errs, "\n  - "))
	}
	return c, nil
}

// normalizeAddr makes a bare ":8080" splittable by net.SplitHostPort.
func normalizeAddr(a string) string {
	if strings.HasPrefix(a, ":") {
		return "0.0.0.0" + a
	}
	return a
}
