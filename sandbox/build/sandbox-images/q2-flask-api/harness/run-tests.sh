#!/bin/sh
# Scoring harness. Runs inside a --network none container with the candidate's
# /app/src overlaid on the baked image. Boots the Flask API, runs test.py against
# it, and prints exactly one JSON line (the score) to stdout.
set -e
cd /app

PORT=3000 python server.py >/tmp/server.log 2>&1 &
SERVER_PID=$!

# Wait for the server to accept connections (max ~10s; Flask boot is slower).
i=0
while [ $i -lt 100 ]; do
  if python -c "import socket,sys; s=socket.socket(); s.settimeout(0.3); sys.exit(0 if s.connect_ex(('127.0.0.1',3000))==0 else 1)" 2>/dev/null; then
    break
  fi
  i=$((i+1))
  sleep 0.1
done

python /harness/test.py
RESULT=$?

kill $SERVER_PID 2>/dev/null || true
exit $RESULT
