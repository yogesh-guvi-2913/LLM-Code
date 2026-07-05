#!/usr/bin/env bash
# Scheduled-scaling proof: a booked assessment window raises a template's warm
# floor ahead of its start (by the lead), warm containers actually climb toward
# it, canceling restores the baseline, a manual scale becomes the baseline that
# windows add on top of, and the schedule survives a control-plane restart.
# Real Postgres, real containers, real HTTP. No stubs.
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8090}"
ADDR="${ADDR:-:8090}"
DSN="${DATABASE_URL:-postgres://postgres:flash@127.0.0.1:5433/flash?sslmode=disable}"
KEY="hyk_window000000000000000000000000000"
Q="q2"          # Flask API: light, single-process scorer, fast to warm
BASELINE=2      # q2's default min_warm
LOG=/tmp/flash-window.log
PASS=0; FAIL=0
ok(){ echo "  ✅ $1"; PASS=$((PASS+1)); }
no(){ echo "  ❌ $1 (got: $2)"; FAIL=$((FAIL+1)); }
H=(-H "authorization: Bearer $KEY")
CT=(-H 'content-type: application/json')

cleanup(){ set +e; [ -n "${ORCH:-}" ] && kill -9 "$ORCH" 2>/dev/null; pkill -f "cmd/orchestrator" 2>/dev/null; pkill -f "go-build.*orchestrator" 2>/dev/null; }
trap cleanup EXIT

iso(){ date -u -v"$1" +%Y-%m-%dT%H:%M:%SZ; }                 # e.g. iso +2M
minwarm(){ curl -fsS "${H[@]}" "$BASE/v1/templates" | jq -r ".[] | select(.id==\"$Q\") | .min_warm"; }
warm(){ curl -fsS "${H[@]}" "$BASE/v1/stats" | jq -r ".warm.$Q // 0"; }
desired(){ curl -fsS "${H[@]}" "$BASE/v1/windows" | jq -r ".desired_warm_now.$Q // 0"; }
# wait_minwarm <target> <secs>
wait_minwarm(){ for _ in $(seq 1 $(( $2 * 2 ))); do [ "$(minwarm)" = "$1" ] && return 0; sleep 0.5; done; return 1; }

boot(){
  : > "$LOG"
  AUTH_ENABLED=true BOOTSTRAP_API_KEY="$KEY" ORG_CONCURRENCY_LIMIT=200 AUTH_RATE_RPS=5000 \
    DATABASE_URL="$DSN" LISTEN_ADDR="$ADDR" go run ./cmd/orchestrator >>"$LOG" 2>&1 &
  ORCH=$!
  for _ in $(seq 1 60); do curl -fsS "$BASE/healthz" >/dev/null 2>&1 && break; sleep 0.5; done
  for _ in $(seq 1 80); do [ "$(warm)" -ge "$BASELINE" ] && break; sleep 0.5; done
}

# Fresh schedule each run so prior windows don't perturb the floor.
psql "$DSN" -c "DELETE FROM assessment_windows;" >/dev/null 2>&1 || \
  docker exec flash-pg psql -U postgres -d flash -c "DELETE FROM assessment_windows;" >/dev/null 2>&1 || true

echo "── boot + baseline ──────────────────────────────────────"
boot
[ "$(minwarm)" = "$BASELINE" ] && ok "baseline min_warm=$BASELINE" || no "baseline" "$(minwarm)"

echo "── a future window (outside its lead) does NOT scale yet ─"
curl -fsS -X POST "${H[@]}" "${CT[@]}" "$BASE/v1/windows" \
  -d "{\"question_id\":\"$Q\",\"seats\":6,\"lead_minutes\":5,\"label\":\"future\",\"starts_at\":\"$(iso +40M)\",\"ends_at\":\"$(iso +90M)\"}" >/dev/null
sleep 2
[ "$(minwarm)" = "$BASELINE" ] && ok "scheduled window leaves floor at baseline" || no "future window scaled early" "$(minwarm)"
ph=$(curl -fsS "${H[@]}" "$BASE/v1/windows" | jq -r '.windows[] | select(.label=="future") | .phase')
[ "$ph" = "scheduled" ] && ok "phase=scheduled" || no "future phase" "$ph"
[ "$(desired)" = "0" ] && ok "desired_warm_now has no $Q yet" || no "desired early" "$(desired)"

echo "── a window inside its lead span raises the floor ───────"
WIN=$(curl -fsS -X POST "${H[@]}" "${CT[@]}" "$BASE/v1/windows" \
  -d "{\"question_id\":\"$Q\",\"seats\":6,\"lead_minutes\":5,\"label\":\"now\",\"starts_at\":\"$(iso +2M)\",\"ends_at\":\"$(iso +30M)\"}" | jq -r .id)
ph=$(curl -fsS "${H[@]}" "$BASE/v1/windows" | jq -r '.windows[] | select(.label=="now") | .phase')
[ "$ph" = "prewarming" ] && ok "phase=prewarming (within lead)" || no "now phase" "$ph"
wait_minwarm 6 6 && ok "floor raised to 6 (immediate reconcile)" || no "raise to 6" "$(minwarm)"
[ "$(desired)" = "6" ] && ok "desired_warm_now.$Q=6" || no "desired now" "$(desired)"

echo "── warm containers actually climb toward the new floor ──"
climbed=0; for _ in $(seq 1 90); do [ "$(warm)" -ge $((BASELINE+2)) ] && { climbed=1; break; }; sleep 1; done
[ "$climbed" = 1 ] && ok "warm grew past baseline (now $(warm) ready)" || no "warm did not climb" "$(warm)"

echo "── canceling the window restores the baseline ───────────"
curl -fsS -X DELETE "${H[@]}" "$BASE/v1/windows/$WIN" >/dev/null
wait_minwarm "$BASELINE" 6 && ok "floor back to baseline=$BASELINE after cancel" || no "restore baseline" "$(minwarm)"

echo "── a manual scale becomes the baseline windows add onto ─"
curl -fsS -X POST "${H[@]}" "${CT[@]}" "$BASE/v1/templates/$Q/min_warm" -d '{"min_warm":4}' >/dev/null
wait_minwarm 4 4 && ok "manual scale → floor=4" || no "manual scale" "$(minwarm)"
WIN2=$(curl -fsS -X POST "${H[@]}" "${CT[@]}" "$BASE/v1/windows" \
  -d "{\"question_id\":\"$Q\",\"seats\":6,\"lead_minutes\":5,\"label\":\"onto\",\"starts_at\":\"$(iso +2M)\",\"ends_at\":\"$(iso +30M)\"}" | jq -r .id)
wait_minwarm 6 6 && ok "window seats(6) > baseline(4) → floor=6" || no "add onto baseline" "$(minwarm)"
curl -fsS -X DELETE "${H[@]}" "$BASE/v1/windows/$WIN2" >/dev/null
wait_minwarm 4 6 && ok "cancel restores manual baseline=4 (not original 2)" || no "restore manual baseline" "$(minwarm)"

echo "── schedule survives a control-plane restart ────────────"
# Re-open a window in its lead span, then kill & reboot: the stateless planner
# must recompute the raised floor from Postgres alone.
curl -fsS -X POST "${H[@]}" "${CT[@]}" "$BASE/v1/windows" \
  -d "{\"question_id\":\"$Q\",\"seats\":7,\"lead_minutes\":5,\"label\":\"resume\",\"starts_at\":\"$(iso +2M)\",\"ends_at\":\"$(iso +30M)\"}" >/dev/null
wait_minwarm 7 6 >/dev/null || true
kill -9 "$ORCH" 2>/dev/null; pkill -f "go-build.*orchestrator" 2>/dev/null || true; sleep 1
boot
# baseline persists in-process only, so after restart the baseline is q2's default
# (2); the active window (7) still dominates → floor must be 7.
wait_minwarm 7 8 && ok "reboot re-applies window floor=7 from Postgres" || no "resume after restart" "$(minwarm)"

echo "── history lists ended/canceled windows with phases ─────"
n=$(curl -fsS "${H[@]}" "$BASE/v1/windows?all=true" | jq '[.windows[] | select(.phase=="canceled")] | length')
[ "$n" -ge 2 ] && ok "canceled windows visible in history (?all=true)" || no "history canceled" "$n"

echo "─────────────────────────────────────────────────────────"
echo "PASS=$PASS  FAIL=$FAIL"
[ "$FAIL" -eq 0 ] && echo "✅ SCHEDULED SCALING PROVEN" || { echo "❌ FAILURES"; tail -40 "$LOG"; exit 1; }
