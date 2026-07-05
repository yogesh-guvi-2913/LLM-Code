#!/usr/bin/env bash
# Builds a sandbox image for a given template directory. Compiles the toolbox as
# a static linux binary matching the Docker server arch, drops it into the
# template build context, then docker builds + tags the image.
#
# Usage:
#   ./scripts/build-image.sh                       # builds all known templates
#   ./scripts/build-image.sh q2-flask-api          # builds one, default tag
#   ./scripts/build-image.sh q2-flask-api my:tag    # builds one, explicit tag
set -euo pipefail
cd "$(dirname "$0")/.."

ARCH="$(docker version --format '{{.Server.Arch}}')"   # amd64 | arm64

build_toolbox_into() {
  local dst="$1"
  CGO_ENABLED=0 GOOS=linux GOARCH="${ARCH}" \
    go build -trimpath -ldflags="-s -w" -o "${dst}/toolbox" ./cmd/toolbox
}

build_one() {
  local dir="$1" tag="$2"
  local ctx="build/sandbox-images/${dir}"
  [ -d "${ctx}" ] || { echo "no such template: ${ctx}" >&2; exit 1; }
  echo ">> toolbox (linux/${ARCH}) -> ${ctx}/toolbox"
  build_toolbox_into "${ctx}"
  echo ">> docker build ${tag}"
  docker build -t "${tag}" "${ctx}"
  echo ">> done: ${tag}"
}

# Default tag per template dir: flash-sandbox:<dir>-v1
default_tag() { echo "flash-sandbox:${1%-api}-v1" | sed 's/q\([0-9]*\)-\(.*\)/q\1-\2/'; }

if [ "$#" -eq 0 ]; then
  build_one "q1-express-api" "flash-sandbox:q1-express-api-v1"
  build_one "q2-flask-api"   "flash-sandbox:q2-flask-api-v1"
  build_one "q3-react-vite"  "flash-sandbox:q3-react-vite-v1"
else
  DIR="$1"
  TAG="${2:-flash-sandbox:${DIR}-v1}"
  build_one "${DIR}" "${TAG}"
fi
