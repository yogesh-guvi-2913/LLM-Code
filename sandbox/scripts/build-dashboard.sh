#!/usr/bin/env bash
# Build the Next.js dashboard as a static export and refresh the copy the
# orchestrator embeds (internal/dashboard/dist). Run before `go build` whenever
# the dashboard changes; the embedded assets are committed so a plain
# `go build ./cmd/orchestrator` always produces the full product.
set -euo pipefail
cd "$(dirname "$0")/.."

(cd dashboard && npm run build)

rm -rf internal/dashboard/dist
cp -R dashboard/out internal/dashboard/dist
echo "embedded dashboard refreshed: internal/dashboard/dist ($(du -sh internal/dashboard/dist | cut -f1))"
