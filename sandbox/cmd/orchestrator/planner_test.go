package main

import (
	"testing"
	"time"

	"github.com/guvi-geek/flash/internal/store"
)

func TestWindowPhase(t *testing.T) {
	now := time.Date(2026, 6, 30, 10, 0, 0, 0, time.UTC)
	base := store.Window{
		StartsAt:    now.Add(30 * time.Minute),
		EndsAt:      now.Add(90 * time.Minute),
		LeadMinutes: 10,
	}
	canceled := now.Add(-time.Minute)

	cases := []struct {
		name string
		w    store.Window
		want string
	}{
		{"before lead", base, "scheduled"},
		{"inside lead", withTimes(base, now.Add(5*time.Minute), now.Add(65*time.Minute)), "prewarming"},
		{"running", withTimes(base, now.Add(-10*time.Minute), now.Add(50*time.Minute)), "active"},
		{"ended", withTimes(base, now.Add(-2*time.Hour), now.Add(-time.Hour)), "done"},
		{"canceled wins", store.Window{StartsAt: now.Add(time.Hour), EndsAt: now.Add(2 * time.Hour), CanceledAt: &canceled}, "canceled"},
	}
	for _, c := range cases {
		if got := windowPhase(c.w, now); got != c.want {
			t.Errorf("%s: phase = %q, want %q", c.name, got, c.want)
		}
	}
}

func withTimes(w store.Window, start, end time.Time) store.Window {
	w.StartsAt, w.EndsAt = start, end
	return w
}
