#!/usr/bin/env bash
# Phase 2 proof: the operator control plane requires an org API key, candidate
# routes use the per-session token, and the per-org concurrency cap holds.
# Real Postgres, real containers, real HTTP. No stubs.
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8090}"
ADDR="${ADDR:-:8090}"
DSN="${DATABASE_URL:-postgres://postgres:flash@127.0.0.1:5433/flash?sslmode=disable}"
KEY="hyk_test0000000000000000000000000000"
LIMIT=2
LOG=/tmp/flash-auth.log
PASS=0; FAIL=0
ok(){ echo "  ✅ $1"; PASS=$((PASS+1)); }
no(){ echo "  ❌ $1 (got $2)"; FAIL=$((FAIL+1)); }
code(){ curl -s -o /dev/null -w '%{http_code}' "$@"; }

cleanup(){ set +e; [ -n "${ORCH:-}" ] && kill -9 "$ORCH" 2>/dev/null; pkill -f "cmd/orchestrator" 2>/dev/null; }
trap cleanup EXIT

: > "$LOG"
AUTH_ENABLED=true BOOTSTRAP_API_KEY="$KEY" ORG_CONCURRENCY_LIMIT="$LIMIT" \
  DATABASE_URL="$DSN" LISTEN_ADDR="$ADDR" go run ./cmd/orchestrator >>"$LOG" 2>&1 &
ORCH=$!
for i in $(seq 1 60); do curl -fsS "$BASE/healthz" >/dev/null 2>&1 && break; sleep 0.5; done
for i in $(seq 1 60); do [ "$(code -H "authorization: Bearer $KEY" "$BASE/v1/stats")" = 200 ] && \
  [ "$(curl -fsS -H "authorization: Bearer $KEY" "$BASE/v1/stats" | jq -r '.warm.q1 // 0')" -ge 2 ] && break; sleep 0.5; done

echo "── operator routes require an API key ───────────────────"
c=$(code "$BASE/v1/templates");                              [ "$c" = 401 ] && ok "no key → 401" || no "no key" "$c"
c=$(code -H "authorization: Bearer hyk_wrongwrongwrong" "$BASE/v1/templates"); [ "$c" = 401 ] && ok "wrong key → 401" || no "wrong key" "$c"
c=$(code -H "authorization: Bearer $KEY" "$BASE/v1/templates"); [ "$c" = 200 ] && ok "valid key → 200" || no "valid key" "$c"

echo "── open infra routes need no key ────────────────────────"
c=$(code "$BASE/healthz"); [ "$c" = 200 ] && ok "/healthz open" || no "/healthz" "$c"
c=$(code "$BASE/metrics"); [ "$c" = 200 ] && ok "/metrics open (internal scrape)" || no "/metrics" "$c"

echo "── per-org concurrency cap (limit=$LIMIT) ───────────────"
declare -a SIDS=() TOKS=()
for i in 1 2; do
  R=$(curl -fsS -X POST "$BASE/v1/sessions" -H "authorization: Bearer $KEY" -H 'content-type: application/json' \
        -d "{\"candidate_id\":\"cap-$i\",\"question_id\":\"q1\"}")
  SIDS+=("$(echo "$R" | jq -r .session_id)"); TOKS+=("$(echo "$R" | jq -r .session_token)")
done
ok "claimed $LIMIT sandboxes up to the cap"
c=$(code -X POST "$BASE/v1/sessions" -H "authorization: Bearer $KEY" -H 'content-type: application/json' -d '{"candidate_id":"cap-3","question_id":"q1"}')
[ "$c" = 429 ] && ok "claim past cap → 429" || no "over-cap claim" "$c"

echo "── candidate plane uses the SESSION token, not the org key ─"
# submit with the org key must NOT be accepted as the session credential
c=$(code -X POST "$BASE/v1/sessions/${SIDS[0]}/submit" -H "authorization: Bearer $KEY")
[ "$c" = 401 ] && ok "submit with org key → 401 (wrong credential type)" || no "submit w/ org key" "$c"
c=$(code -X POST "$BASE/v1/sessions/${SIDS[0]}/submit" -H "authorization: Bearer ${TOKS[0]}")
[ "$c" = 202 ] && ok "submit with session token → 202" || no "submit w/ session token" "$c"

echo "── cap frees as sessions end ────────────────────────────"
for i in 1 2; do [ -n "${TOKS[$((i-1))]:-}" ] && curl -fsS -X DELETE "$BASE/v1/sessions/${SIDS[$((i-1))]}" -H "authorization: Bearer $KEY" >/dev/null 2>&1 || true; done
sleep 1
c=$(code -X POST "$BASE/v1/sessions" -H "authorization: Bearer $KEY" -H 'content-type: application/json' -d '{"candidate_id":"cap-after","question_id":"q1"}')
[ "$c" = 201 ] && ok "claim succeeds again after release → 201" || no "post-release claim" "$c"

echo "─────────────────────────────────────────────────────────"
echo "PASS=$PASS  FAIL=$FAIL"
[ "$FAIL" -eq 0 ] && echo "✅ AUTH + CONCURRENCY CAP PROVEN" || { echo "❌ FAILURES"; tail -30 "$LOG"; exit 1; }
