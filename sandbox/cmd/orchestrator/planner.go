package main

import (
	"context"
	"log/slog"
	"sync"
	"time"

	"github.com/guvi-geek/flash/internal/metrics"
	"github.com/guvi-geek/flash/internal/store"
)

// planner drives scheduled scaling: it reconciles each template's warm floor
// (min_warm) against the union of booked assessment windows. Ahead of a window's
// start (by its lead time) it raises the floor to cover the seat burst; after the
// window ends it restores the template's baseline.
//
// It is deliberately stateless w.r.t. the schedule — every reconcile recomputes
// the desired floor from Postgres — so a control-plane restart resumes cleanly.
// The only in-memory state is the per-template baseline (the floor absent any
// window), which is seeded from the registry at boot and updated whenever an
// operator manually scales a template (so manual scaling becomes the new baseline
// that windows add on top of, not something the planner fights).
type planner struct {
	prov    Provisioner
	reg     *registry
	store   *store.Store
	log     *slog.Logger
	metrics *metrics.Metrics
	perNode int // sandboxes one node holds, for the required-nodes signal

	mu       sync.Mutex
	baseline map[string]int
}

func newPlanner(s *server, perNode int) *planner {
	if perNode < 1 {
		perNode = 1
	}
	p := &planner{
		prov: s.prov, reg: s.reg, store: s.store, log: s.log, metrics: s.metrics,
		perNode:  perNode,
		baseline: map[string]int{},
	}
	for _, id := range s.reg.ids() {
		if c, ok := s.reg.config(id); ok {
			p.baseline[id] = c.MinWarm
		}
	}
	return p
}

// setBaseline records the floor a template should hold absent any window. Called
// when an operator manually scales a template, so the planner treats that as the
// new baseline rather than reverting it.
func (p *planner) setBaseline(id string, n int) {
	p.mu.Lock()
	p.baseline[id] = n
	p.mu.Unlock()
}

// baselineFor returns the recorded baseline for a template, lazily capturing the
// current configured floor the first time we see an id (e.g. a template added at
// runtime). Capturing on first sight is safe because a brand-new template has no
// window yet, so its current floor IS its baseline.
func (p *planner) baselineFor(id string) int {
	p.mu.Lock()
	defer p.mu.Unlock()
	if n, ok := p.baseline[id]; ok {
		return n
	}
	n := 0
	if c, ok := p.reg.config(id); ok {
		n = c.MinWarm
	}
	p.baseline[id] = n
	return n
}

func (p *planner) run(ctx context.Context) {
	p.reconcile(ctx) // apply any already-open window immediately on boot
	t := time.NewTicker(15 * time.Second)
	defer t.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-t.C:
			p.reconcile(ctx)
		}
	}
}

// reconcile computes the desired warm floor for every template (max of its
// baseline and any active window's seats) and applies the delta through the
// provisioner. Idempotent: when desired == current it does nothing, so it is
// cheap to run often and safe to call ad-hoc after a window is booked/canceled.
func (p *planner) reconcile(ctx context.Context) {
	desired, err := p.store.DesiredWarmByQuestion(ctx)
	if err != nil {
		p.log.Error("planner: desired warm query failed", "err", err)
		return
	}
	totalTarget := 0
	for _, id := range p.reg.ids() {
		base := p.baselineFor(id)
		target := base
		if seats, ok := desired[id]; ok && seats > target {
			target = seats
		}
		totalTarget += target
		cur := base
		if c, ok := p.reg.config(id); ok {
			cur = c.MinWarm
		}
		if target == cur {
			continue
		}
		if p.prov.SetMinWarm(ctx, id, target) {
			p.reg.setMinWarm(id, target)
			p.log.Info("planner.scaled", "question", id,
				"from", cur, "to", target, "baseline", base, "window_seats", desired[id])
		} else {
			p.log.Warn("planner: set min_warm failed", "question", id, "target", target)
		}
	}
	// Publish the autoscaling signal: nodes needed to hold the warm target at the
	// configured density. An ASG target-tracking policy scales the fleet on this,
	// so a booked window grows node count ahead of T (L3) — no imperative API call.
	requiredNodes := max((totalTarget+p.perNode-1)/p.perNode, 1)
	if p.metrics != nil {
		p.metrics.SetCapacityTargets(totalTarget, requiredNodes)
	}
	// Warn about windows pointing at unknown templates — they can never be served.
	known := map[string]bool{}
	for _, id := range p.reg.ids() {
		known[id] = true
	}
	for q := range desired {
		if !known[q] {
			p.log.Warn("planner: window references unknown template", "question", q)
		}
	}
}

// windowPhase derives a display phase from a window's timestamps relative to now.
func windowPhase(w store.Window, now time.Time) string {
	if w.CanceledAt != nil {
		return "canceled"
	}
	if !now.Before(w.EndsAt) {
		return "done"
	}
	leadStart := w.StartsAt.Add(-time.Duration(w.LeadMinutes) * time.Minute)
	if now.Before(leadStart) {
		return "scheduled"
	}
	if now.Before(w.StartsAt) {
		return "prewarming"
	}
	return "active"
}
