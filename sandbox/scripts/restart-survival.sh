#!/usr/bin/env bash
# Phase 1 proof: an orchestrator restart must NOT drop a live assessment.
#
# It claims a real q3 (frontend) sandbox, verifies its live preview + app + terminal,
# then KILLS the orchestrator with SIGKILL and starts a fresh one against the same
# Docker + Postgres. The new process has zero in-process pool state — it must
# reconcile from the durable truth and re-adopt the SAME container, so the
# candidate's preview/app/terminal keep working and their tmpfs work is intact.
#
# No stubs: real Docker containers, real Postgres, real HTTP.
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8090}"
ADDR="${ADDR:-:8090}"
DSN="${DATABASE_URL:-postgres://postgres:flash@127.0.0.1:5433/flash?sslmode=disable}"
Q="${Q:-q3}"
KEY="hyk_restart00000000000000000000000000"   # operator key; auth runs ON (production-faithful)
AUTHH=(-H "authorization: Bearer $KEY")
LOG=/tmp/flash-orch.log
PASS=0; FAIL=0
ok(){ echo "  ✅ $1"; PASS=$((PASS+1)); }
no(){ echo "  ❌ $1"; FAIL=$((FAIL+1)); }

start_orch(){
  AUTH_ENABLED=true BOOTSTRAP_API_KEY="$KEY" \
    DATABASE_URL="$DSN" LISTEN_ADDR="$ADDR" PREVIEW_DOMAIN=preview.localhost \
    go run ./cmd/orchestrator >>"$LOG" 2>&1 &
  echo $!
}
wait_http(){ for i in $(seq 1 60); do curl -fsS "$BASE/healthz" >/dev/null 2>&1 && return 0; sleep 0.5; done; return 1; }
wait_warm(){ for i in $(seq 1 60); do [ "$(curl -fsS "${AUTHH[@]}" "$BASE/v1/stats" | jq -r ".warm.$Q // 0")" -ge 1 ] && return 0; sleep 0.5; done; return 1; }
# curl a preview host without DNS: --resolve maps the vhost to loopback, Host header stays faithful.
preview_get(){ curl -fsS --resolve "$1:8090:127.0.0.1" "http://$1:8090/" ; }

cleanup(){
  set +e
  [ -n "${ORCH:-}" ] && kill -9 "$ORCH" 2>/dev/null
  pkill -f "cmd/orchestrator" 2>/dev/null
  [ -n "${SID:-}" ] && curl -fsS "${AUTHH[@]}" -X DELETE "$BASE/v1/sessions/$SID" >/dev/null 2>&1
}
trap cleanup EXIT

: > "$LOG"
echo "── boot #1 ──────────────────────────────────────────────"
ORCH=$(start_orch)
wait_http || { echo "orchestrator never came up"; tail -20 "$LOG"; exit 1; }
wait_warm || { echo "warm pool never filled for $Q"; tail -20 "$LOG"; exit 1; }
echo "orchestrator up (pid $ORCH), $Q warm pool ready"

echo "── claim a live $Q sandbox ──────────────────────────────"
CLAIM=$(curl -fsS -X POST "$BASE/v1/sessions" "${AUTHH[@]}" -H 'content-type: application/json' \
  -d "{\"candidate_id\":\"restart-proof\",\"question_id\":\"$Q\"}")
SID=$(echo "$CLAIM" | jq -r .session_id)
TOK=$(echo "$CLAIM" | jq -r .session_token)
PREVIEW=$(echo "$CLAIM" | jq -r .preview_url)
APP=$(echo "$CLAIM" | jq -r .app_url)
PHOST=$(echo "$PREVIEW" | sed -E 's#https?://([^/:]+).*#\1#')
echo "session=$SID  preview=$PREVIEW"

# Which container is serving this session, and its host ports — capture so we can
# prove the SAME one survives the restart.
CID1=$(docker ps --filter "label=flash.question=$Q" --format '{{.ID}} {{.Ports}}' | grep -F "$(echo "$APP" | sed -E 's#.*:([0-9]+)#\1#')" | awk '{print $1}' | head -1)
echo "serving container=$CID1"

echo "── verify live BEFORE restart ───────────────────────────"
preview_get "$PHOST" | grep -qiE 'vite|root|<!doctype' && ok "preview serves the app" || no "preview did not serve"
curl -fsS "$APP" >/dev/null 2>&1 && ok "app_url reachable" || no "app_url unreachable"
curl -fsS "$BASE/terminal?session=$SID&token=$TOK" | grep -qi 'xterm' && ok "terminal page served" || no "terminal page missing"
WARM1=$(curl -fsS "${AUTHH[@]}" "$BASE/v1/stats" | jq -r ".warm.$Q")
echo "warm depth before: $WARM1"

echo "── 💥 SIGKILL the orchestrator (no graceful shutdown) ────"
kill -9 "$ORCH"; wait "$ORCH" 2>/dev/null || true
sleep 1
docker ps --filter "id=$CID1" --format '{{.ID}}' | grep -q . && ok "candidate container still RUNNING after kill" || no "container died with orchestrator"

echo "── boot #2 (fresh process, zero pool state) ─────────────"
ORCH=$(start_orch)
wait_http || { echo "restart never came up"; tail -30 "$LOG"; exit 1; }
sleep 2 # let reconcile run
grep -q '"msg":"reconciled"' "$LOG" && ok "reconcile ran on boot" || no "no reconcile log line"

echo "── verify live AFTER restart ────────────────────────────"
GET=$(curl -fsS "${AUTHH[@]}" "$BASE/v1/sessions/$SID")
[ "$(echo "$GET" | jq -r .status)" = "ACTIVE" ] && ok "session still ACTIVE" || no "session not ACTIVE ($(echo "$GET" | jq -r .status))"
PREVIEW2=$(echo "$GET" | jq -r '.preview_url // empty')
[ -n "$PREVIEW2" ] && ok "preview_url re-served by getSession" || no "no preview_url after restart"
PHOST2=$(echo "$PREVIEW2" | sed -E 's#https?://([^/:]+).*#\1#')
preview_get "$PHOST2" | grep -qiE 'vite|root|<!doctype' && ok "PREVIEW still live after restart" || no "preview broke after restart"
curl -fsS "$(echo "$GET" | jq -r .app_url)" >/dev/null 2>&1 && ok "app still live after restart" || no "app broke after restart"
CID2=$(docker ps --filter "label=flash.question=$Q" --format '{{.ID}}' | grep -F "$CID1" || true)
[ -n "$CID2" ] && ok "SAME container re-adopted (id $CID1), not recreated" || no "container was replaced (work lost)"

echo "── submit through the re-adopted container ──────────────"
SUB=$(curl -fsS -X POST "$BASE/v1/sessions/$SID/submit" -H "authorization: Bearer $TOK")
echo "$SUB" | jq -e '.submission_id' >/dev/null && ok "submit works post-restart (snapshot+score)" || no "submit failed post-restart"

echo "─────────────────────────────────────────────────────────"
echo "PASS=$PASS  FAIL=$FAIL"
[ "$FAIL" -eq 0 ] && echo "✅ RESTART-SURVIVAL PROVEN" || { echo "❌ FAILURES"; tail -40 "$LOG"; exit 1; }
