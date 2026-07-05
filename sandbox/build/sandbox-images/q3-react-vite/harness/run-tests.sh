#!/bin/sh
# Scoring harness. Runs inside a --network none container with the candidate's
# submitted code extracted into /app/src over the baked image. Runs the vitest
# suite (jsdom + @testing-library/react) against the candidate's App component
# and prints exactly one JSON line (the score) to stdout.
set -e
cd /app

# Tell vite.config.ts where the candidate source and the harness live (they are
# at fixed absolute paths in the container, not relative to /app).
export APP_SRC=/app/src

# Vite enforces fs.strict — the dev server (and vitest) only load files UNDER the
# project root (/app). The harness lives at /harness (outside root), so both the
# test file and the setup file must be STAGED into /app before running, or vitest
# fails with "Failed to load url /harness/...". The scorer container has a
# writable rootfs, so this copy is safe.
#
# We deliberately do NOT widen Vite's fs.allow to include /harness: that same
# config drives the live candidate preview dev server, and exposing /harness
# would leak the reference solution (/harness/solution) to candidates via /@fs.
# Staging keeps everything the scorer needs inside /app and /harness private.
cp /harness/vitest.setup.ts /app/vitest.setup.ts
TESTFILE=/app/.score.test.tsx
cp /harness/App.test.tsx "$TESTFILE"
export HARNESS_DIR=/app          # config resolves setupFiles -> /app/vitest.setup.ts

# Vitest's own caches/temp must land in the writable tmpfs, not read-only paths.
export TMPDIR=/tmp
export HOME=/tmp

REPORT=/tmp/vitest-results.json
rm -f "$REPORT"

# Run the suite. We never want a non-zero vitest exit (failing tests are
# expected and are scored, not errors) to abort the scorer — hence `|| true`.
npx vitest run "$TESTFILE" \
  --reporter=json --outputFile="$REPORT" \
  >/tmp/vitest.log 2>&1 || true

# Map pass/fail -> weighted score and emit the final JSON line.
VITEST_REPORT="$REPORT" node /harness/score.cjs
