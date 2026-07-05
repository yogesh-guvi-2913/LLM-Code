package main

import (
	"context"
	"math"
	"net/http"
	"os"
	"strconv"
	"time"
)

// costModel turns measured density into a dollar figure. The two inputs are the
// node you actually rent (its hourly price and usable RAM); everything else
// (sandboxes per node, $/sandbox-hr) is derived from the live working-set the
// sampler measures — so the cost claim is computed from reality, not a guess.
//
// Defaults are a c7g.4xlarge (16 vCPU / 32 GB Graviton) at a ~1-yr Savings Plan
// rate. Override per deploy with COST_NODE_USD_PER_HR / COST_NODE_RAM_GB.
type costModel struct {
	NodeUSDPerHour float64
	NodeRAMGB      float64
}

// runSampleLoop publishes the live gauges Prometheus scrapes: warm depth, active
// count, and — the one that matters for cost — real resident memory per sandbox,
// read from `docker stats` on every live container. 15s is frequent enough to
// track a window filling without hammering the daemon.
func (s *server) runSampleLoop(ctx context.Context) {
	t := time.NewTicker(15 * time.Second)
	defer t.Stop()
	s.sampleOnce(ctx) // publish immediately so /metrics isn't empty on first scrape
	for {
		select {
		case <-ctx.Done():
			return
		case <-t.C:
			s.sampleOnce(ctx)
		}
	}
}

func (s *server) sampleOnce(ctx context.Context) {
	s.metrics.SetWarm(s.prov.WarmCount(ctx))
	s.metrics.SetActive(s.prov.ActiveCount(ctx))
	total, counted := s.prov.LiveMem(ctx)
	s.metrics.SetDensity(total, counted)
}

// usage is the cost-proof endpoint. It reports billed sandbox-hours from the
// session ledger and the MEASURED live density, then derives sandboxes-per-node
// and $/sandbox-hour from the node cost model. This is the number to hold up
// against a managed-provider invoice.
func (s *server) usage(w http.ResponseWriter, r *http.Request) {
	rows, err := s.store.UsageSummary(r.Context())
	if err != nil {
		httpErr(w, http.StatusInternalServerError, "usage query failed")
		return
	}

	var totalSeconds float64
	var totalSessions, activeNow int
	byQ := make([]map[string]any, 0, len(rows))
	for _, u := range rows {
		totalSeconds += u.SandboxSeconds
		totalSessions += u.Sessions
		activeNow += u.ActiveNow
		byQ = append(byQ, map[string]any{
			"question_id":   u.QuestionID,
			"sessions":      u.Sessions,
			"active_now":    u.ActiveNow,
			"sandbox_hours": round2(u.SandboxSeconds / 3600),
		})
	}

	// Two density bounds, because one number here would be dishonest:
	//
	//   conservative — node RAM / the CONFIGURED memory reservation per sandbox.
	//     This is the OOM-safe floor: it assumes every sandbox could use its full
	//     limit at once (a busy candidate editing + rebuilding + running tests).
	//     This is the number to quote.
	//
	//   overcommit-ceiling — node RAM / the MEASURED resident memory right now.
	//     Idle/warm sandboxes use a fraction of their limit, so this is how dense
	//     you *could* pack — but only safely if real load stays near what's
	//     measured. It is an upper bound to VALIDATE under assessment load, never
	//     a number to bill against blind.
	usableGB := s.cost.NodeRAMGB * 0.85 // reserve ~15% for OS + node-agent

	// Configured reservation across live containers, weighted by the live mix.
	var configuredTotalMB float64
	var liveCount int
	for q, n := range s.prov.WarmCount(r.Context()) {
		if cfg, ok := s.reg.config(q); ok {
			configuredTotalMB += float64(n) * float64(cfg.MemoryMB)
			liveCount += n
		}
	}
	for q, n := range s.prov.ActiveCount(r.Context()) {
		if cfg, ok := s.reg.config(q); ok {
			configuredTotalMB += float64(n) * float64(cfg.MemoryMB)
			liveCount += n
		}
	}
	configuredPerMB := 512.0
	if liveCount > 0 {
		configuredPerMB = configuredTotalMB / float64(liveCount)
	}

	// Measured resident memory across live containers (local: real docker-stats;
	// cluster: committed memory aggregated from node heartbeats).
	memTotal, counted := s.prov.LiveMem(r.Context())
	measuredPerMB := 0.0
	if counted > 0 {
		measuredPerMB = float64(memTotal) / float64(counted) / (1 << 20)
	}

	perNode := func(perMB float64) int {
		if perMB <= 0 {
			return 0
		}
		return int(math.Floor(usableGB * 1024 / perMB))
	}
	usdPer := func(n int) float64 {
		if n <= 0 {
			return 0
		}
		return s.cost.NodeUSDPerHour / float64(n)
	}
	conservativeN := perNode(configuredPerMB)
	overcommitN := perNode(measuredPerMB)

	writeJSON(w, http.StatusOK, map[string]any{
		"billed": map[string]any{
			"sessions":      totalSessions,
			"active_now":    activeNow,
			"sandbox_hours": round2(totalSeconds / 3600),
			"by_question":   byQ,
		},
		"measured_density": map[string]any{
			"live_containers":               counted,
			"measured_mem_per_sandbox_mb":   round2(measuredPerMB),
			"configured_mem_per_sandbox_mb": round2(configuredPerMB),
			"total_measured_mem_gb":         round2(float64(memTotal) / (1 << 30)),
			"basis":                         "measured value reflects CURRENT load; sample under real assessment activity before trusting the overcommit ceiling",
		},
		"cost_model": map[string]any{
			"node_usd_per_hour": s.cost.NodeUSDPerHour,
			"node_ram_gb":       s.cost.NodeRAMGB,
			"usable_ram_gb":     round2(usableGB),
			// Headline: safe, no-overcommit.
			"conservative_sandboxes_per_node": conservativeN,
			"conservative_usd_per_sandbox_hr": round4(usdPer(conservativeN)),
			// Ceiling: validate under load before relying on it.
			"overcommit_ceiling_sandboxes_per_node": overcommitN,
			"overcommit_ceiling_usd_per_sandbox_hr": round4(usdPer(overcommitN)),
			"note":                                  "quote the conservative figure; overcommit ceiling is an upper bound to validate under real load. Spot pricing cuts node_usd_per_hour ~2-3x further.",
		},
	})
}

func round2(f float64) float64 { return math.Round(f*100) / 100 }
func round4(f float64) float64 { return math.Round(f*10000) / 10000 }

func envFloat(k string, def float64) float64 {
	if v := os.Getenv(k); v != "" {
		if f, err := strconv.ParseFloat(v, 64); err == nil {
			return f
		}
	}
	return def
}
