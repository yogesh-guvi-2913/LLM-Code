#!/usr/bin/env bash
# Phase 0 proof: config fail-fast, liveness vs readiness, request-id propagation,
# and graceful drain — a submission that is mid-score when SIGTERM arrives still
# gets persisted before the process exits ("nothing-in-limbo").
# Real Postgres, real containers, real signals. No stubs.
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8091}"
ADDR="${ADDR:-:8091}"
DSN="${DATABASE_URL:-postgres://postgres:flash@127.0.0.1:5433/flash?sslmode=disable}"
KEY="hyk_harden00000000000000000000000000"
Q="q2"
LOG=/tmp/flash-harden.log
PASS=0; FAIL=0
ok(){ echo "  ✅ $1"; PASS=$((PASS+1)); }
no(){ echo "  ❌ $1 (got: $2)"; FAIL=$((FAIL+1)); }
code(){ curl -s -o /dev/null -w '%{http_code}' "$@"; }
H=(-H "authorization: Bearer $KEY")
psql_q(){ docker exec flash-pg psql -U postgres -d flash -tAc "$1" 2>/dev/null; }

BIN=/tmp/flash-orch-harden
cleanup(){ set +e; [ -n "${ORCH:-}" ] && kill -9 "$ORCH" 2>/dev/null; pkill -f "$BIN" 2>/dev/null; rm -f "$BIN"; }
trap cleanup EXIT

# Build a real binary so SIGTERM hits the orchestrator directly (go run wraps it
# in a parent process that complicates signal delivery).
go build -o "$BIN" ./cmd/orchestrator

boot(){
  : > "$LOG"
  AUTH_ENABLED=true BOOTSTRAP_API_KEY="$KEY" ORG_CONCURRENCY_LIMIT=200 AUTH_RATE_RPS=5000 \
    DATABASE_URL="$DSN" LISTEN_ADDR="$ADDR" "$BIN" >>"$LOG" 2>&1 &
  ORCH=$!
  for _ in $(seq 1 60); do curl -fsS "$BASE/healthz" >/dev/null 2>&1 && break; sleep 0.5; done
}

echo "── config fail-fast ─────────────────────────────────────"
out=$(LISTEN_ADDR='bad:::' "$BIN" 2>&1 || true)
echo "$out" | grep -q "invalid configuration" && ok "bad LISTEN_ADDR → fails fast with message" || no "fail-fast" "$out"

echo "── boot + liveness/readiness ────────────────────────────"
boot
[ "$(code "$BASE/healthz")" = 200 ] && ok "/healthz 200 (liveness)" || no "/healthz" "$(code "$BASE/healthz")"
for _ in $(seq 1 80); do [ "$(code "$BASE/readyz")" = 200 ] && break; sleep 0.5; done
[ "$(code "$BASE/readyz")" = 200 ] && ok "/readyz 200 once warmed (readiness)" || no "/readyz" "$(code "$BASE/readyz")"

echo "── request-id propagation ───────────────────────────────"
rid=$(curl -fsS -D - -o /dev/null "${H[@]}" "$BASE/v1/stats" | tr -d '\r' | awk -F': ' 'tolower($1)=="x-request-id"{print $2}')
[ -n "$rid" ] && ok "X-Request-ID issued ($rid)" || no "request-id issued" "none"
echoed=$(curl -fsS -D - -o /dev/null -H "X-Request-ID: trace-abc123" "${H[@]}" "$BASE/v1/stats" | tr -d '\r' | awk -F': ' 'tolower($1)=="x-request-id"{print $2}')
[ "$echoed" = "trace-abc123" ] && ok "caller-supplied id echoed back" || no "request-id echo" "$echoed"
grep -q '"request_id"' "$LOG" && ok "structured access log carries request_id" || no "access log" "missing"

echo "── graceful drain: in-flight score survives SIGTERM ─────"
R=$(curl -fsS -X POST "${H[@]}" -H 'content-type: application/json' "$BASE/v1/sessions" -d "{\"candidate_id\":\"drain-test\",\"question_id\":\"$Q\"}")
SID=$(echo "$R" | jq -r .session_id); TOK=$(echo "$R" | jq -r .session_token)
c=$(code -X POST -H "authorization: Bearer $TOK" "$BASE/v1/sessions/$SID/submit")
[ "$c" = 202 ] && ok "submit accepted → 202 (scoring detached)" || no "submit" "$c"
# SIGTERM immediately — the score job is still running. A correct drain waits for it.
kill -TERM "$ORCH"
rc=124
for _ in $(seq 1 100); do  # bounded wait (~50s) so the script can't hang
  if ! kill -0 "$ORCH" 2>/dev/null; then wait "$ORCH"; rc=$?; break; fi
  sleep 0.5
done
[ "$rc" = 0 ] && ok "process exited cleanly on SIGTERM (rc=0)" || no "clean exit" "$rc"
grep -q "background jobs drained" "$LOG" && ok "log: background jobs drained" || no "drain log" "missing"
grep -q "shutdown complete" "$LOG" && ok "log: shutdown complete" || no "shutdown log" "missing"
# The submission must be finalized in Postgres — NOT left stuck at 'scoring'.
st=$(psql_q "SELECT status FROM submissions WHERE session_id='$SID' ORDER BY created_at DESC LIMIT 1")
[ -n "$st" ] && [ "$st" != "scoring" ] && ok "submission persisted (status=$st, not stuck 'scoring')" || no "submission finalized" "${st:-none}"

echo "─────────────────────────────────────────────────────────"
echo "PASS=$PASS  FAIL=$FAIL"
[ "$FAIL" -eq 0 ] && echo "✅ FOUNDATION HARDENING PROVEN" || { echo "❌ FAILURES"; tail -40 "$LOG"; exit 1; }
