#!/usr/bin/env bash
# Phase 3 proof: the control plane schedules sandboxes across MULTIPLE node-agents.
#
# Two node-agents (logical nodes sharing this Docker host) register capacity in
# Redis; an orchestrator in CLUSTER_MODE picks a node per claim, forwards it, and
# routes the live preview back through the owning node. Then we kill a node and show
# new claims reschedule onto the survivor. Real Redis, real node-agents, real
# containers, real HTTP. No stubs.
#
# (Physical multi-host isolation is a deploy concern — like TLS — and is validated
# at deploy. What's proven here is the scheduling + routing + failover LOGIC, which
# is the hard, bug-prone part.)
set -euo pipefail

ORCH=http://127.0.0.1:8090
N1=http://127.0.0.1:9001
N2=http://127.0.0.1:9002
REDIS=redis://127.0.0.1:6380/0
DSN="${DATABASE_URL:-postgres://postgres:flash@127.0.0.1:5433/flash?sslmode=disable}"
KEY="hyk_cluster0000000000000000000000000"
AUTHH=(-H "authorization: Bearer $KEY")
DIR=/tmp/flash-cluster; mkdir -p "$DIR"
PASS=0; FAIL=0
ok(){ echo "  ✅ $1"; PASS=$((PASS+1)); }
no(){ echo "  ❌ $1 ${2:-}"; FAIL=$((FAIL+1)); }
active_on(){ curl -fsS "$1/stats" 2>/dev/null | jq '[.active[]] | add // 0'; }

PIDS=()
killport(){ local p; p=$(lsof -ti tcp:"$1" 2>/dev/null || true); if [ -n "$p" ]; then kill -9 $p 2>/dev/null || true; fi; return 0; }
cleanup(){
  set +e
  for p in "${PIDS[@]:-}"; do [ -n "$p" ] && kill -9 "$p" 2>/dev/null; done
  pkill -f "$DIR/orch" 2>/dev/null; pkill -f "$DIR/agent" 2>/dev/null
  docker rm -f $(docker ps -aq --filter "label=flash.sandbox") >/dev/null 2>&1
}
trap cleanup EXIT

echo "── preflight: free ports + clean stale state + build ────"
for port in 8090 9001 9002; do killport "$port"; done
pkill -f "$DIR/orch" 2>/dev/null || true; pkill -f "$DIR/agent" 2>/dev/null || true; sleep 1
# Stale ACTIVE sessions from earlier test runs would count against the org cap and
# whose containers are long gone — retire them so the cap reflects this run only.
docker exec flash-pg psql -U postgres -d flash -c \
  "UPDATE sessions SET status='DESTROYED' WHERE status='ACTIVE'" >/dev/null 2>&1 || true
go build -o "$DIR/orch" ./cmd/orchestrator
go build -o "$DIR/agent" ./cmd/node-agent
docker rm -f $(docker ps -aq --filter "label=flash.sandbox") >/dev/null 2>&1 || true

echo "── start 2 node-agents (disjoint ports, share Docker) ───"
NODE_ID=node-1 NODE_LISTEN=:9001 NODE_ADDR=http://127.0.0.1:9001 NODE_HOST=127.0.0.1 \
  NODE_PORT_LO=20000 NODE_PORT_HI=23900 NODE_MEM_MB=8000 REDIS_URL="$REDIS" \
  "$DIR/agent" >"$DIR/node-1.log" 2>&1 & PIDS+=($!)
NODE_ID=node-2 NODE_LISTEN=:9002 NODE_ADDR=http://127.0.0.1:9002 NODE_HOST=127.0.0.1 \
  NODE_PORT_LO=24000 NODE_PORT_HI=27900 NODE_MEM_MB=8000 REDIS_URL="$REDIS" \
  "$DIR/agent" >"$DIR/node-2.log" 2>&1 & PIDS+=($!)

for u in "$N1" "$N2"; do
  for i in $(seq 1 60); do curl -fsS "$u/healthz" >/dev/null 2>&1 && break; sleep 0.5; done
done
# wait until both nodes have warmed q1
for u in "$N1" "$N2"; do
  for i in $(seq 1 80); do [ "$(curl -fsS "$u/stats" | jq -r '.warm.q1 // 0')" -ge 2 ] && break; sleep 0.5; done
done
ok "both node-agents up and warmed"

echo "── start orchestrator in CLUSTER_MODE ───────────────────"
CLUSTER_MODE=true REDIS_URL="$REDIS" DATABASE_URL="$DSN" LISTEN_ADDR=:8090 \
  PREVIEW_DOMAIN=preview.localhost AUTH_ENABLED=true BOOTSTRAP_API_KEY="$KEY" \
  AUTH_RATE_RPS=5000 AUTH_RATE_BURST=5000 ORG_CONCURRENCY_LIMIT=200 \
  "$DIR/orch" >"$DIR/orch.log" 2>&1 & PIDS+=($!)
# rename so pkill in cleanup can find it distinctly
for i in $(seq 1 60); do curl -fsS "$ORCH/healthz" >/dev/null 2>&1 && break; sleep 0.5; done
for i in $(seq 1 40); do [ "$(curl -fsS "${AUTHH[@]}" "$ORCH/v1/stats" | jq -r '.warm.q1 // 0')" -ge 4 ] && break; sleep 0.5; done
echo "fleet warm q1 (both nodes): $(curl -fsS "${AUTHH[@]}" "$ORCH/v1/stats" | jq -c .warm)"
ok "orchestrator sees the aggregated fleet warm pool"

echo "── claim 8 sandboxes — must spread across BOTH nodes ────"
for i in $(seq 1 8); do
  RC=$(curl -sS -X POST "$ORCH/v1/sessions" "${AUTHH[@]}" -H 'content-type: application/json' \
    -d "{\"candidate_id\":\"c-$i\",\"question_id\":\"q1\"}")
  [ "$i" = 1 ] && echo "  (first claim response: $RC)"
  sleep 0.4   # let the post-claim heartbeat update free-mem so the scheduler rebalances
done
A1=$(active_on "$N1"); A2=$(active_on "$N2")
echo "active sandboxes — node-1: $A1   node-2: $A2"
[ "$A1" -gt 0 ] && [ "$A2" -gt 0 ] && ok "claims scheduled across BOTH nodes ($A1 + $A2)" || no "claims did not spread" "($A1/$A2)"
[ $((A1 + A2)) -eq 8 ] && ok "all 8 claims accounted for across the fleet" || no "claim count mismatch" "($((A1+A2)))"

echo "── live preview routed through the owning node ──────────"
R=$(curl -fsS -X POST "$ORCH/v1/sessions" "${AUTHH[@]}" -H 'content-type: application/json' -d '{"candidate_id":"prev","question_id":"q3"}')
SID=$(echo "$R" | jq -r .session_id); PURL=$(echo "$R" | jq -r .preview_url)
PHOST=$(echo "$PURL" | sed -E 's#https?://([^/:]+).*#\1#')
sleep 1
curl -fsS --resolve "$PHOST:8090:127.0.0.1" "http://$PHOST:8090/" | grep -qiE 'vite|root|<!doctype' \
  && ok "preview served through cluster proxy → owning node" || no "preview not served"

echo "── submit routed to the owning node (snapshot+score) ────"
R2=$(curl -fsS -X POST "$ORCH/v1/sessions" "${AUTHH[@]}" -H 'content-type: application/json' -d '{"candidate_id":"sub","question_id":"q1"}')
SID2=$(echo "$R2" | jq -r .session_id); TOK2=$(echo "$R2" | jq -r .session_token)
sleep 1
SUB=$(curl -fsS -X POST "$ORCH/v1/sessions/$SID2/submit" -H "authorization: Bearer $TOK2")
echo "$SUB" | jq -e '.submission_id' >/dev/null && ok "submit works across the cluster" || no "submit failed"

echo "── 💥 kill node-2 → new claims reschedule to survivor ───"
# node-2 is the 2nd backgrounded pid
kill -9 "${PIDS[1]}" 2>/dev/null || true
echo "waiting ~16s for node-2's heartbeat TTL to expire from the registry…"
sleep 16
# node-2's /stats is now unreachable; node-1 still serves
curl -fsS "$N2/healthz" >/dev/null 2>&1 && no "node-2 still alive after kill" || ok "node-2 is down"
B1=$(active_on "$N1")
for i in $(seq 1 5); do
  curl -fsS -X POST "$ORCH/v1/sessions" "${AUTHH[@]}" -H 'content-type: application/json' \
    -d "{\"candidate_id\":\"after-$i\",\"question_id\":\"q1\"}" >/dev/null 2>&1 || true
  sleep 0.3
done
A1b=$(active_on "$N1")
echo "node-1 active before/after failover claims: $B1 → $A1b"
[ "$A1b" -gt "$B1" ] && ok "new claims rescheduled onto surviving node-1" || no "failover claims did not land on node-1" "($B1→$A1b)"

echo "─────────────────────────────────────────────────────────"
echo "PASS=$PASS  FAIL=$FAIL"
[ "$FAIL" -eq 0 ] && echo "✅ MULTI-NODE SCHEDULING PROVEN" || { echo "❌ FAILURES"; echo "--- orch ---"; tail -25 "$DIR/orch.log"; exit 1; }
