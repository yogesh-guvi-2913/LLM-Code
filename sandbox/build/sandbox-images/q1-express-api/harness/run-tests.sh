#!/bin/sh
# Scoring harness. Runs inside a --network none container with the candidate's
# /app/src overlaid on the baked image. Boots the API, runs test.js against it,
# and prints exactly one JSON line (the score) to stdout.
set -e
cd /app

PORT=3000 node server.js >/tmp/server.log 2>&1 &
SERVER_PID=$!

# Wait for the server to accept connections (max ~5s).
i=0
while [ $i -lt 50 ]; do
  if node -e "require('net').connect(3000,'127.0.0.1').on('connect',()=>process.exit(0)).on('error',()=>process.exit(1))" 2>/dev/null; then
    break
  fi
  i=$((i+1))
  sleep 0.1
done

node /harness/test.js
RESULT=$?

kill $SERVER_PID 2>/dev/null || true
exit $RESULT
