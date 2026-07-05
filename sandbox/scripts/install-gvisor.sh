#!/usr/bin/env bash
# Installs gVisor (runsc) and registers it as a Docker runtime named "runsc".
# Run this ON THE LINUX RUNNER NODE (EC2), then start the orchestrator with
# SANDBOX_RUNTIME=runsc. gVisor interposes a userspace kernel between candidate
# code and the host kernel — the real isolation boundary for untrusted code.
#
# Not applicable on macOS/OrbStack: the Docker engine runs in a managed VM where
# a custom runtime cannot be persisted. Use this on the actual node.
set -euo pipefail

if [ "$(uname -s)" != "Linux" ]; then
  echo "gVisor runs on Linux nodes only. On macOS this is a no-op." >&2
  exit 1
fi

ARCH="$(uname -m)"   # x86_64 | aarch64
URL="https://storage.googleapis.com/gvisor/releases/release/latest/${ARCH}"

echo ">> downloading runsc + containerd-shim-runsc-v1 (${ARCH})"
wget -q "${URL}/runsc" "${URL}/runsc.sha512" \
     "${URL}/containerd-shim-runsc-v1" "${URL}/containerd-shim-runsc-v1.sha512"
sha512sum -c runsc.sha512 containerd-shim-runsc-v1.sha512
chmod +x runsc containerd-shim-runsc-v1
sudo mv runsc containerd-shim-runsc-v1 /usr/local/bin/
rm -f runsc.sha512 containerd-shim-runsc-v1.sha512

echo ">> registering the runsc runtime with dockerd"
# runsc can also self-register: `sudo runsc install`. We write daemon.json
# explicitly so it is reviewable and idempotent.
sudo mkdir -p /etc/docker
sudo runsc install   # adds the "runsc" runtime to /etc/docker/daemon.json
sudo systemctl restart docker

echo ">> verify"
docker info --format '{{json .Runtimes}}' | grep -q runsc && echo "runsc runtime registered ✔"
docker run --rm --runtime=runsc alpine dmesg 2>/dev/null | head -1 || true
echo ">> done. Start orchestrator with SANDBOX_RUNTIME=runsc"
