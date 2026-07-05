#!/usr/bin/env bash
# End-to-end smoke test against a running orchestrator (LISTEN_ADDR, default :8080).
# Drives the full v1 loop: create session -> submit -> poll score.
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8080}"

echo ">> warm pool state"
curl -fsS "${BASE}/v1/stats"; echo

echo ">> POST /v1/sessions"
CREATE=$(curl -fsS -X POST "${BASE}/v1/sessions" \
  -H 'Content-Type: application/json' \
  -d '{"candidate_id":"cand_demo","question_id":"q1","time_limit_minutes":90}')
echo "${CREATE}"

SID=$(echo "${CREATE}"   | sed -n 's/.*"session_id":"\([^"]*\)".*/\1/p')
TOK=$(echo "${CREATE}"   | sed -n 's/.*"session_token":"\([^"]*\)".*/\1/p')
APP=$(echo "${CREATE}"   | sed -n 's/.*"app_url":"\([^"]*\)".*/\1/p')
echo ">> session=${SID} app=${APP}"

echo ">> candidate hits the live API"
curl -fsS "${APP}/todos"; echo

echo ">> POST submit"
curl -fsS -X POST "${BASE}/v1/sessions/${SID}/submit" \
  -H "Authorization: Bearer ${TOK}"; echo

echo ">> waiting for score (scoring runs in a --network none container)"
sleep 8
echo ">> querying Postgres for the score"
psql -d flash -t -A -F'|' -c \
  "SELECT status, score, max_score FROM submissions WHERE session_id='${SID}';"

echo ">> pool replenished?"
curl -fsS "${BASE}/v1/stats"; echo
