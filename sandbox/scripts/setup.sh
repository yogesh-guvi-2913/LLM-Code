#!/usr/bin/env bash
# One-time local setup: sandbox network + Postgres database.
set -euo pipefail

NET="${SANDBOX_NET:-sandbox-net}"

echo ">> docker network ${NET}"
if ! docker network inspect "${NET}" >/dev/null 2>&1; then
  # icc=false: warm/active containers cannot talk to each other.
  docker network create --driver bridge \
    --opt com.docker.network.bridge.enable_icc=false \
    "${NET}"
else
  echo "   exists"
fi

echo ">> postgres database 'flash'"
if ! psql -lqt 2>/dev/null | cut -d '|' -f1 | grep -qw flash; then
  createdb flash
  echo "   created"
else
  echo "   exists"
fi

cat <<'EOF'

NOTE (Linux hosts only): block the cloud metadata endpoint on the node:
  sudo iptables -I DOCKER-USER -d 169.254.169.254 -j DROP
On macOS/OrbStack there is no IMDS to reach, so this is a no-op locally.
EOF
