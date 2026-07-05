# Roadmap

What's built and proven is documented in [`README.md`](README.md) (see
"Known limits" for current constraints). This tracks what's planned but not
yet built. Not a promise of dates — priority order, roughly top to bottom
within each section.

## Scaling & deploy

- **ASG autoscaler wiring.** The scaling signal (`flash_required_nodes`,
  published on `/metrics`), the node-agent ASG, and the IAM grant for
  `autoscaling:SetDesiredCapacity` all exist in [`deploy/aws/`](deploy/aws/).
  What's missing is the actual API call that reads the signal and drives
  desired capacity — a small, well-scoped gap that needs a live AWS account
  to finish and verify.
- **Multi-AZ spread.** The node-agent fleet isn't spread across availability
  zones yet — single-AZ today.
- **Docker socket-proxy sidecar.** Node-agents talk to the local Docker
  socket directly. Before running with fully untrusted external candidates
  at scale, that should sit behind a socket-proxy that only allows the
  specific Docker API calls the pool needs.
- **Predictive warm-pool smoothing.** The scheduled-window planner
  (`POST /v1/windows`) raises the warm floor ahead of a booked window using a
  fixed lead time. Learning real seat-show-up rates per template/time and
  widening the safety factor for historically over-booked windows is not
  implemented.

## Sandbox features

- **Snapshot / fork.** `docker commit` (or CRIU for live process state) →
  push → resume into a warm container, so a customized environment can be
  forked instantly instead of rebuilt from the base template each time. Not
  implemented — sandboxes today are always fresh from the template image.
- **Firecracker microVMs.** gVisor (`SANDBOX_RUNTIME=runsc`) is the current
  isolation boundary beyond standard containers, proven end-to-end on a real
  Linux node. Firecracker would be a stronger boundary still, at a real
  density cost (~125MB min overhead/VM) — only worth adding if gVisor's
  syscall coverage actually proves limiting for a template.

## SDKs

- **Publish to package registries.** Neither SDK is published yet — the Go
  SDK isn't tagged as a versioned module release, and the Python SDK isn't on
  PyPI (`pip install -e sdk/python` from a clone is the only install path
  today).
- **Versioning + changelog.** No `CHANGELOG.md` for either SDK yet.
- **Generated API reference.** Docs are README-only right now — no
  godoc-style or Sphinx-style reference site.
- **A JS/TS SDK.** Only Go and Python have official SDKs today, despite the
  dashboard itself being TypeScript.

## Project infra

- CI (`.github/workflows/ci.yml`) runs `vet`/`build`/`gofmt`/unit tests and a
  dashboard build, but not the real end-to-end suites
  (`scripts/e2e.sh`, `auth-check.sh`, `cluster-check.sh`,
  `hardening-check.sh`, `node-drain-check.sh`, `window-check.sh`) or anything
  gVisor-related — those need Docker (and for gVisor, a Linux host) and
  currently only run manually. Getting some subset running in CI (e.g. via a
  Docker-in-Docker runner) would catch regressions earlier.

## Contributing to any of these

Pick an item, open an issue describing your approach first (see
[`CONTRIBUTING.md`](CONTRIBUTING.md)), and we can align on scope before you
put the work in.
