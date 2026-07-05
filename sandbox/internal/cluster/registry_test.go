package cluster

import (
	"context"
	"os"
	"testing"
	"time"
)

// These tests run against a REAL Redis (no mock). Set REDIS_URL to enable them,
// e.g. REDIS_URL=redis://127.0.0.1:6380/9 go test ./internal/cluster/.
func testRegistry(t *testing.T) *Registry {
	url := os.Getenv("REDIS_URL")
	if url == "" {
		t.Skip("REDIS_URL not set; skipping real-Redis registry test")
	}
	r, err := New(url, time.Second)
	if err != nil {
		t.Fatalf("connect: %v", err)
	}
	ctx := context.Background()
	if err := r.Ping(ctx); err != nil {
		t.Fatalf("ping: %v", err)
	}
	// Clean the test keyspace.
	ids, _ := r.LiveNodes(ctx)
	for _, n := range ids {
		_ = r.Deregister(ctx, n.ID)
	}
	return r
}

func TestSchedulerPrefersWarmThenFreeMem(t *testing.T) {
	r := testRegistry(t)
	ctx := context.Background()
	defer func() {
		_ = r.Deregister(ctx, "n1")
		_ = r.Deregister(ctx, "n2")
		_ = r.Deregister(ctx, "n3")
		_ = r.Close()
	}()

	// n1: lots of free mem, no warm. n2: less free mem, but a warm q1. n3: most free.
	if err := r.Heartbeat(ctx, Node{ID: "n1", Addr: "http://n1", Host: "n1", MemFreeMB: 4000}, nil); err != nil {
		t.Fatal(err)
	}
	if err := r.Heartbeat(ctx, Node{ID: "n2", Addr: "http://n2", Host: "n2", MemFreeMB: 1000}, map[string]int{"q1": 2}); err != nil {
		t.Fatal(err)
	}
	if err := r.Heartbeat(ctx, Node{ID: "n3", Addr: "http://n3", Host: "n3", MemFreeMB: 8000}, nil); err != nil {
		t.Fatal(err)
	}

	// q1: must pick n2 (it has a warm container) even though n3 has more free mem.
	got, err := r.PickNode(ctx, "q1", 512)
	if err != nil {
		t.Fatal(err)
	}
	if got.ID != "n2" {
		t.Fatalf("q1 should pick warm node n2, got %s", got.ID)
	}

	// q2: nobody is warm → pick the emptiest box (n3, most free mem).
	got, err = r.PickNode(ctx, "q2", 512)
	if err != nil {
		t.Fatal(err)
	}
	if got.ID != "n3" {
		t.Fatalf("q2 should bin-pack onto emptiest n3, got %s", got.ID)
	}

	// A claim larger than any node's free mem → no node.
	if _, err := r.PickNode(ctx, "q2", 99999); err != ErrNoNode {
		t.Fatalf("oversized claim should yield ErrNoNode, got %v", err)
	}
}

func TestLivenessExpiry(t *testing.T) {
	r := testRegistry(t)
	ctx := context.Background()
	// Short heartbeat so the TTL (heartbeat * slop) expires within the test.
	r.heartbeat = 300 * time.Millisecond
	defer func() { _ = r.Deregister(ctx, "ephemeral"); _ = r.Close() }()

	if err := r.Heartbeat(ctx, Node{ID: "ephemeral", Addr: "x", Host: "x", MemFreeMB: 1000}, nil); err != nil {
		t.Fatal(err)
	}
	nodes, _ := r.LiveNodes(ctx)
	if !containsNode(nodes, "ephemeral") {
		t.Fatal("node should be live right after heartbeat")
	}
	// Stop heartbeating; after TTL it must drop out.
	time.Sleep(r.heartbeat*nodeTTLslop + 400*time.Millisecond)
	nodes, _ = r.LiveNodes(ctx)
	if containsNode(nodes, "ephemeral") {
		t.Fatal("node should have expired after missing heartbeats")
	}
}

func containsNode(ns []Node, id string) bool {
	for _, n := range ns {
		if n.ID == id {
			return true
		}
	}
	return false
}
