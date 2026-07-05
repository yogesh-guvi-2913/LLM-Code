// Package cluster is the shared state that makes Flash multi-node: a Redis-backed
// registry of sandbox nodes plus the scheduler that places a claim on one of them.
//
// Why Redis here (when v1 deliberately avoided it): with a SECOND node, one control
// plane can no longer inspect another node's Docker to know its warm depth or
// liveness. That cross-node truth has to live somewhere both can reach. Node
// liveness is ephemeral (a node that stops heartbeating is gone), which is exactly
// what Redis key TTLs model — so this is Redis earning its keep, not ceremony.
//
// Keys:
//
//	flash:node:<id>            HASH  {addr, mem_total_mb, mem_free_mb, ...}  (TTL = liveness)
//	flash:node:<id>:warm       HASH  question -> warm count                 (TTL with the node)
//	flash:nodes                SET   of live node ids (members expire via the node key TTL sweep)
package cluster

import (
	"context"
	"errors"
	"fmt"
	"sort"
	"strconv"
	"time"

	"github.com/redis/go-redis/v9"
)

const (
	keyPrefix   = "flash:"
	nodesSet    = keyPrefix + "nodes"
	nodeTTLslop = 3 // node key TTL = heartbeat interval * this, so a missed beat or two is tolerated
)

// Node is a sandbox runner advertised to the registry.
type Node struct {
	ID         string `json:"id"`
	Addr       string `json:"addr"` // base URL the control plane reaches the node-agent on
	Host       string `json:"host"` // host the node's published sandbox ports are reachable on
	MemTotalMB int64  `json:"mem_total_mb"`
	MemFreeMB  int64  `json:"mem_free_mb"`
	ActiveN    int    `json:"active"`
	LastSeen   int64  `json:"last_seen_unix"`
}

// Registry is a thin typed wrapper over Redis for the node registry.
type Registry struct {
	rdb       *redis.Client
	heartbeat time.Duration
}

// New connects to Redis (redisURL like "redis://127.0.0.1:6380/0").
func New(redisURL string, heartbeat time.Duration) (*Registry, error) {
	opt, err := redis.ParseURL(redisURL)
	if err != nil {
		return nil, fmt.Errorf("parse redis url: %w", err)
	}
	rdb := redis.NewClient(opt)
	return &Registry{rdb: rdb, heartbeat: heartbeat}, nil
}

// Ping verifies connectivity (called on boot so a bad REDIS_URL fails fast).
func (r *Registry) Ping(ctx context.Context) error { return r.rdb.Ping(ctx).Err() }

func (r *Registry) Close() error { return r.rdb.Close() }

func nodeKey(id string) string     { return fmt.Sprintf("%snode:%s", keyPrefix, id) }
func nodeWarmKey(id string) string { return fmt.Sprintf("%snode:%s:warm", keyPrefix, id) }

// Heartbeat publishes a node's current capacity and refreshes its liveness TTL. A
// node calls this every `heartbeat`; if it stops, the keys expire and the node
// drops out of scheduling automatically.
func (r *Registry) Heartbeat(ctx context.Context, n Node, warm map[string]int) error {
	ttl := r.heartbeat * nodeTTLslop
	now := time.Now().Unix()
	pipe := r.rdb.TxPipeline()
	pipe.HSet(ctx, nodeKey(n.ID), map[string]any{
		"id": n.ID, "addr": n.Addr, "host": n.Host,
		"mem_total_mb": n.MemTotalMB, "mem_free_mb": n.MemFreeMB,
		"active": n.ActiveN, "last_seen_unix": now,
	})
	pipe.Expire(ctx, nodeKey(n.ID), ttl)
	if len(warm) > 0 {
		m := make(map[string]any, len(warm))
		for q, c := range warm {
			m[q] = c
		}
		pipe.Del(ctx, nodeWarmKey(n.ID)) // replace wholesale so stale templates don't linger
		pipe.HSet(ctx, nodeWarmKey(n.ID), m)
		pipe.Expire(ctx, nodeWarmKey(n.ID), ttl)
	} else {
		pipe.Del(ctx, nodeWarmKey(n.ID))
	}
	pipe.SAdd(ctx, nodesSet, n.ID)
	_, err := pipe.Exec(ctx)
	return err
}

// Deregister removes a node immediately (graceful shutdown / drain).
func (r *Registry) Deregister(ctx context.Context, id string) error {
	pipe := r.rdb.TxPipeline()
	pipe.Del(ctx, nodeKey(id), nodeWarmKey(id))
	pipe.SRem(ctx, nodesSet, id)
	_, err := pipe.Exec(ctx)
	return err
}

// LiveNodes returns the nodes that still have a non-expired key, pruning dead ids
// from the index set as it goes (lazy cleanup of nodes that died without
// deregistering).
func (r *Registry) LiveNodes(ctx context.Context) ([]Node, error) {
	ids, err := r.rdb.SMembers(ctx, nodesSet).Result()
	if err != nil {
		return nil, err
	}
	var out []Node
	var dead []string
	for _, id := range ids {
		h, err := r.rdb.HGetAll(ctx, nodeKey(id)).Result()
		if err != nil {
			return nil, err
		}
		if len(h) == 0 {
			dead = append(dead, id)
			continue
		}
		out = append(out, Node{
			ID: h["id"], Addr: h["addr"], Host: h["host"],
			MemTotalMB: atoi64(h["mem_total_mb"]), MemFreeMB: atoi64(h["mem_free_mb"]),
			ActiveN: int(atoi64(h["active"])), LastSeen: atoi64(h["last_seen_unix"]),
		})
	}
	if len(dead) > 0 {
		_ = r.rdb.SRem(ctx, nodesSet, anySlice(dead)...).Err()
	}
	sort.Slice(out, func(i, j int) bool { return out[i].ID < out[j].ID })
	return out, nil
}

// NodeWarmAll returns a node's full warm map (question -> count).
func (r *Registry) NodeWarmAll(ctx context.Context, nodeID string) (map[string]int, error) {
	h, err := r.rdb.HGetAll(ctx, nodeWarmKey(nodeID)).Result()
	if err != nil {
		return nil, err
	}
	out := make(map[string]int, len(h))
	for q, v := range h {
		out[q] = int(atoi64(v))
	}
	return out, nil
}

// WarmDepth reads a node's warm count for a template (0 if absent).
func (r *Registry) WarmDepth(ctx context.Context, nodeID, question string) (int, error) {
	v, err := r.rdb.HGet(ctx, nodeWarmKey(nodeID), question).Result()
	if errors.Is(err, redis.Nil) {
		return 0, nil
	}
	if err != nil {
		return 0, err
	}
	return int(atoi64(v)), nil
}

var ErrNoNode = errors.New("no live node available")

// PickNode is the scheduler. It chooses the best node for a claim:
//  1. prefer a node that already has a WARM container of this template (instant
//     claim, the common case when capacity is pre-warmed for a window), breaking
//     ties by most free memory;
//  2. otherwise the live node with the most free memory (it'll cold-spin, but on
//     the emptiest box so we bin-pack evenly).
//
// Nodes with no measurable free memory are skipped so we never schedule onto a box
// that's about to OOM.
func (r *Registry) PickNode(ctx context.Context, question string, needMB int64) (Node, error) {
	nodes, err := r.LiveNodes(ctx)
	if err != nil {
		return Node{}, err
	}
	var bestWarm, bestFree *Node
	for i := range nodes {
		n := &nodes[i]
		if n.MemFreeMB < needMB {
			continue
		}
		if bestFree == nil || n.MemFreeMB > bestFree.MemFreeMB {
			bestFree = n
		}
		w, _ := r.WarmDepth(ctx, n.ID, question)
		if w > 0 {
			if bestWarm == nil || n.MemFreeMB > bestWarm.MemFreeMB {
				bestWarm = n
			}
		}
	}
	if bestWarm != nil {
		return *bestWarm, nil
	}
	if bestFree != nil {
		return *bestFree, nil
	}
	return Node{}, ErrNoNode
}

// TotalWarm aggregates warm depth across the fleet (for the dashboard /stats).
func (r *Registry) TotalWarm(ctx context.Context) (map[string]int, error) {
	nodes, err := r.LiveNodes(ctx)
	if err != nil {
		return nil, err
	}
	out := map[string]int{}
	for _, n := range nodes {
		h, err := r.rdb.HGetAll(ctx, nodeWarmKey(n.ID)).Result()
		if err != nil {
			return nil, err
		}
		for q, v := range h {
			out[q] += int(atoi64(v))
		}
	}
	return out, nil
}

func atoi64(s string) int64 {
	n, _ := strconv.ParseInt(s, 10, 64)
	return n
}

func anySlice(ss []string) []any {
	out := make([]any, len(ss))
	for i, s := range ss {
		out[i] = s
	}
	return out
}
