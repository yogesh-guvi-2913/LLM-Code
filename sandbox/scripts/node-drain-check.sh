#!/usr/bin/env bash
# Phase 3 deploy-readiness proof: a node-agent draining on SIGTERM (the ASG
# scale-in / lifecycle-hook path) refuses NEW claims and fails readiness, but
# keeps serving its ACTIVE session until it is released — only then does it exit.
# "Active sessions always finish first; never killed by a scale-in."
# Real Docker, real Redis, real signals. No stubs.
set -euo pipefail

NB="${NB:-http://127.0.0.1:9101}"
LISTEN="${LISTEN:-:9101}"
REDIS="${REDIS_URL:-redis://127.0.0.1:6380/7}"
LOG=/tmp/flash-nodedrain.log
BIN=/tmp/flash-nodeagent-drain
NODE_ID=drain-node
PASS=0; FAIL=0
ok(){ echo "  ✅ $1"; PASS=$((PASS+1)); }
no(){ echo "  ❌ $1 (got: $2)"; FAIL=$((FAIL+1)); }
code(){ curl -s -o /dev/null -w '%{http_code}' "$@"; }

cleanup(){ set +e; [ -n "${NA:-}" ] && kill -9 "$NA" 2>/dev/null; pkill -f "$BIN" 2>/dev/null; rm -f "$BIN"; docker ps -aq --filter "label=flash.node=$NODE_ID" | xargs -r docker rm -f >/dev/null 2>&1; }
trap cleanup EXIT

go build -o "$BIN" ./cmd/node-agent

: > "$LOG"
NODE_ID="$NODE_ID" NODE_LISTEN="$LISTEN" REDIS_URL="$REDIS" NODE_DRAIN_TIMEOUT_SEC=30 \
  "$BIN" >>"$LOG" 2>&1 &
NA=$!
for _ in $(seq 1 80); do curl -fsS "$NB/healthz" >/dev/null 2>&1 && break; sleep 0.5; done
# Wait for at least one warm q1 sandbox.
for _ in $(seq 1 80); do [ "$(curl -fsS "$NB/stats" | jq -r '.warm.q1 // 0')" -ge 1 ] && break; sleep 0.5; done

echo "── healthy node accepts work ────────────────────────────"
[ "$(code "$NB/readyz")" = 200 ] && ok "/readyz 200 before drain" || no "/readyz pre" "$(code "$NB/readyz")"
R=$(curl -fsS -X POST "$NB/claim" -H 'content-type: application/json' \
      -d '{"QuestionID":"q1","CandidateID":"drain-cand","SessionID":"sess-drain","Token":"tok-drain"}')
CID=$(echo "$R" | jq -r .container_id)
[ -n "$CID" ] && [ "$CID" != "null" ] && ok "claimed a sandbox (active=1)" || no "claim" "$R"
[ "$(curl -fsS "$NB/stats" | jq -r '.active.q1 // 0')" -ge 1 ] && ok "stats show 1 active" || no "active count" "$(curl -fsS "$NB/stats" | jq -c .active)"

echo "── SIGTERM → drain (active session must NOT be killed) ───"
kill -TERM "$NA"
sleep 2
kill -0 "$NA" 2>/dev/null && ok "process still alive (waiting for active session)" || no "alive during drain" "exited early"
[ "$(code "$NB/readyz")" = 503 ] && ok "/readyz 503 while draining (out of rotation)" || no "/readyz draining" "$(code "$NB/readyz")"
c=$(code -X POST "$NB/claim" -H 'content-type: application/json' -d '{"QuestionID":"q1","CandidateID":"x","SessionID":"y","Token":"z"}')
[ "$c" = 503 ] && ok "new claim refused → 503 during drain" || no "claim during drain" "$c"

echo "── active session can still be served, then released ────"
# The control plane can still reach the node for the active session (snapshot path).
[ "$(code "$NB/sandbox/$CID/files")" = 200 ] && ok "active sandbox still reachable (files 200)" || no "serve active" "$(code "$NB/sandbox/$CID/files")"
curl -fsS -X DELETE "$NB/sandbox/$CID" >/dev/null && ok "released the active session" || no "release" "fail"

echo "── node exits cleanly once drained ──────────────────────"
rc=124
for _ in $(seq 1 60); do
  if ! kill -0 "$NA" 2>/dev/null; then wait "$NA"; rc=$?; break; fi
  sleep 0.5
done
[ "$rc" = 0 ] && ok "exited cleanly after drain (rc=0)" || no "clean exit" "$rc"
grep -q "node drained — no active sessions" "$LOG" && ok "log: node drained (not a timeout)" || no "drain log" "missing"
grep -q "node-agent stopped" "$LOG" && ok "log: node-agent stopped" || no "stopped log" "missing"

echo "─────────────────────────────────────────────────────────"
echo "PASS=$PASS  FAIL=$FAIL"
[ "$FAIL" -eq 0 ] && echo "✅ GRACEFUL NODE DRAIN PROVEN" || { echo "❌ FAILURES"; tail -40 "$LOG"; exit 1; }
