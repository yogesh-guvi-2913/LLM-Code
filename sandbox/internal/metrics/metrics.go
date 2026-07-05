// Package metrics is the orchestrator's Prometheus surface. It exists to make the
// cost claim falsifiable: every number behind "cheaper than a managed provider" —
// warm depth, claim latency, live density (real memory per sandbox) — is a
// measured series here, not a slide. Scrape /metrics, or read the derived
// $/sandbox-hr from /v1/usage.
package metrics

import (
	"net/http"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

// Metrics holds the collectors and their private registry. One per process.
type Metrics struct {
	reg *prometheus.Registry

	claimsTotal   *prometheus.CounterVec   // by question + warm|cold path
	claimDuration *prometheus.HistogramVec // claim latency, by question
	warm          *prometheus.GaugeVec     // warm depth, by question
	active        *prometheus.GaugeVec     // active sessions, by question
	sandboxMem    prometheus.Gauge         // total RSS across live sandboxes (bytes)
	sandboxCount  prometheus.Gauge         // live sandbox containers (warm + active)
	memPerSandbox prometheus.Gauge         // derived: mean RSS per sandbox (bytes)
	warmTarget    prometheus.Gauge         // planner's total desired warm depth (all templates)
	requiredNodes prometheus.Gauge         // derived: nodes needed for the warm target — the ASG signal
}

// New builds the collectors and registers them on a private registry (no global
// state, so tests and multiple instances don't collide).
func New() *Metrics {
	m := &Metrics{reg: prometheus.NewRegistry()}

	m.claimsTotal = prometheus.NewCounterVec(prometheus.CounterOpts{
		Name: "flash_claims_total",
		Help: "Sandbox claims, partitioned by template and whether the warm pool was hit.",
	}, []string{"question", "path"})

	m.claimDuration = prometheus.NewHistogramVec(prometheus.HistogramOpts{
		Name: "flash_claim_duration_seconds",
		Help: "Time to hand a candidate a usable sandbox.",
		// Warm hits are sub-second; cold spins are seconds. Cover both.
		Buckets: []float64{0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 30},
	}, []string{"question"})

	m.warm = prometheus.NewGaugeVec(prometheus.GaugeOpts{
		Name: "flash_warm_containers",
		Help: "Idle containers ready to claim, by template.",
	}, []string{"question"})

	m.active = prometheus.NewGaugeVec(prometheus.GaugeOpts{
		Name: "flash_active_sessions",
		Help: "Claimed (live) sandboxes, by template.",
	}, []string{"question"})

	m.sandboxMem = prometheus.NewGauge(prometheus.GaugeOpts{
		Name: "flash_sandbox_mem_bytes",
		Help: "Total resident memory across all live sandbox containers.",
	})
	m.sandboxCount = prometheus.NewGauge(prometheus.GaugeOpts{
		Name: "flash_sandbox_containers",
		Help: "Live sandbox containers (warm + active).",
	})
	m.memPerSandbox = prometheus.NewGauge(prometheus.GaugeOpts{
		Name: "flash_sandbox_mem_bytes_per_container",
		Help: "Mean resident memory per live sandbox — the density input to $/sandbox-hr.",
	})
	m.warmTarget = prometheus.NewGauge(prometheus.GaugeOpts{
		Name: "flash_warm_target_total",
		Help: "Planner's desired warm depth across all templates (baseline + booked windows).",
	})
	m.requiredNodes = prometheus.NewGauge(prometheus.GaugeOpts{
		Name: "flash_required_nodes",
		Help: "Nodes needed to hold the warm target at the configured density — the ASG target-tracking signal.",
	})

	m.reg.MustRegister(m.claimsTotal, m.claimDuration, m.warm, m.active,
		m.sandboxMem, m.sandboxCount, m.memPerSandbox, m.warmTarget, m.requiredNodes)
	return m
}

// Handler is the /metrics endpoint.
func (m *Metrics) Handler() http.Handler {
	return promhttp.HandlerFor(m.reg, promhttp.HandlerOpts{})
}

// ObserveClaim records one claim: its latency and whether it took the cold path.
func (m *Metrics) ObserveClaim(question string, cold bool, seconds float64) {
	path := "warm"
	if cold {
		path = "cold"
	}
	m.claimsTotal.WithLabelValues(question, path).Inc()
	m.claimDuration.WithLabelValues(question).Observe(seconds)
}

// SetWarm publishes the per-template warm depth (called by the sampler).
func (m *Metrics) SetWarm(byQuestion map[string]int) {
	m.warm.Reset()
	for q, n := range byQuestion {
		m.warm.WithLabelValues(q).Set(float64(n))
	}
}

// SetActive publishes the per-template active count (called by the sampler).
func (m *Metrics) SetActive(byQuestion map[string]int) {
	m.active.Reset()
	for q, n := range byQuestion {
		m.active.WithLabelValues(q).Set(float64(n))
	}
}

// SetCapacityTargets publishes what the planner wants: the total warm depth across
// templates and the node count that satisfies it at the configured density. The
// node count is the metric an ASG target-tracking policy scales on, so booking a
// window raises the fleet size ahead of T (the L3 tier) without any imperative call.
func (m *Metrics) SetCapacityTargets(warmTarget, requiredNodes int) {
	m.warmTarget.Set(float64(warmTarget))
	m.requiredNodes.Set(float64(requiredNodes))
}

// SetDensity publishes measured live density: total RSS and container count, plus
// the derived mean — the single most important input to the cost number.
func (m *Metrics) SetDensity(totalMemBytes int64, containers int) {
	m.sandboxMem.Set(float64(totalMemBytes))
	m.sandboxCount.Set(float64(containers))
	if containers > 0 {
		m.memPerSandbox.Set(float64(totalMemBytes) / float64(containers))
	} else {
		m.memPerSandbox.Set(0)
	}
}
