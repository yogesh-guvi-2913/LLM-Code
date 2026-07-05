# Development setup

Full local setup for working on the orchestrator, dashboard, and SDKs. For the
architecture overview and API reference, see the main [`README.md`](../README.md).

## Prerequisites

| Tool | Version | Used for |
|---|---|---|
| [Go](https://go.dev/dl/) | 1.25+ | orchestrator, node-agent, toolbox, Go SDK |
| [Docker](https://docs.docker.com/get-docker/) (or OrbStack/Colima) | any recent | running sandbox containers |
| [Node.js](https://nodejs.org/) | 20+ | dashboard |
| [Python](https://www.python.org/) | 3.12+ | Python SDK |
| [PostgreSQL](https://www.postgresql.org/) | 16+ | sessions/submissions store (run via Docker below, or a local install) |
| [Redis](https://redis.io/) | 7+ | only needed for cluster mode (`CLUSTER_MODE=true`) |

## 1. Clone and install dependencies

```bash
git clone https://github.com/guvi-geek/flash.git
cd flash
go mod download
cd dashboard && npm install && cd ..
cd sdk/python && pip install -e '.[dev]' && cd ../..
```

## 2. One-time local setup (network + database)

```bash
./scripts/setup.sh
```

This creates the `sandbox-net` Docker network (with inter-container
communication disabled — warm/active sandboxes can't talk to each other) and
the local `flash` Postgres database. If you'd rather run Postgres in Docker
instead of a local install:

```bash
docker run -d --name flash-pg -e POSTGRES_PASSWORD=flash -e POSTGRES_DB=flash \
  -p 5433:5432 postgres:16-alpine
```

## 3. Build the sandbox images

```bash
./scripts/build-image.sh                 # builds all templates (q1, q2, q3)
./scripts/build-image.sh q2-flask-api     # or just one, by directory name
```

This also builds `cmd/toolbox` (the static binary baked into every sandbox
image) and copies it into each `build/sandbox-images/*/` directory before the
`docker build`.

## 4. Run the orchestrator

```bash
DATABASE_URL='postgres://postgres:flash@127.0.0.1:5433/flash?sslmode=disable' \
  LISTEN_ADDR=':8090' go run ./cmd/orchestrator
```

On boot it warms both sandbox pools, then listens on `:8090`. The dashboard is
served at the same address — `open http://127.0.0.1:8090`.

Auth is **on by default**. For local dev, either set `AUTH_ENABLED=false`, or
let the orchestrator mint a bootstrap key on first boot (logged once to
stdout) and paste it into the dashboard's Settings tab.

See the [Env vars section of the README](../README.md#run-it) for the full
list of configuration options (`SANDBOX_RUNTIME`, `ORG_CONCURRENCY_LIMIT`,
cost-model vars, etc).

## 5. Verify the full loop

```bash
BASE=http://127.0.0.1:8090 ./scripts/e2e.sh
```

Drives claim → submit → score end-to-end against the running orchestrator.

## Working on the dashboard

The dashboard is a Next.js app that gets statically exported and embedded
(`go:embed`) into the orchestrator binary. Day to day, run it against a live
orchestrator instead of rebuilding the Go binary on every change:

```bash
cd dashboard
npm run dev
```

By default it targets `NEXT_PUBLIC_API_BASE` (see `dashboard/.env.local`, or
use the API field in the top-right of the UI / a `?api=` query param to point
it at any orchestrator).

Before committing a dashboard change that should ship in the binary, refresh
the embedded copy and confirm the orchestrator still builds clean:

```bash
./scripts/build-dashboard.sh   # regenerates internal/dashboard/dist
go build ./cmd/orchestrator
```

## Working on the SDKs

**Go** (`sdk/go`):

```bash
cd sdk/go
go build ./...
go test ./...                              # compiles the e2e suite; skips without FLASH_E2E=1
FLASH_E2E=1 FLASH_API_KEY=flash_… go test ./... -v   # against a live orchestrator
```

**Python** (`sdk/python`):

```bash
cd sdk/python
pip install -e '.[dev]'
pytest tests                                # collects/skips e2e without FLASH_E2E=1
FLASH_E2E=1 FLASH_API_KEY=flash_… pytest tests -v    # against a live orchestrator
```

Both e2e suites run against real containers, no mocks — start the
orchestrator (step 4 above) first.

## Running the full test/lint suite (what CI runs)

```bash
# Go — orchestrator, node-agent, toolbox, internal packages
go vet ./cmd/... ./internal/...
go build ./cmd/... ./internal/...
gofmt -l cmd internal        # must print nothing
go test ./cmd/... ./internal/...

# Go SDK
cd sdk/go && go vet ./... && go build ./... && gofmt -l . && go test ./...

# Python SDK
cd sdk/python && pip install -e '.[dev]' && pytest tests --collect-only -q

# Dashboard (type-check + lint + build)
cd dashboard && npm run build
```

`internal/cluster`'s tests exercise a real Redis instance
(`REDIS_URL=redis://127.0.0.1:6379/9`); CI spins one up as a service
container. Locally, run `redis-server` (or `docker run -p 6379:6379
redis:7-alpine`) if you're touching cluster scheduling.

## Cluster mode (multi-node)

To develop against the multi-node path (`internal/cluster`, `cmd/node-agent`):

```bash
redis-server &   # or docker run -d -p 6379:6379 redis:7-alpine

NODE_ID=node-1 NODE_ADDR=http://127.0.0.1:9001 NODE_HOST=127.0.0.1 \
  REDIS_URL=redis://127.0.0.1:6379/0 go run ./cmd/node-agent

CLUSTER_MODE=true REDIS_URL=redis://127.0.0.1:6379/0 \
  DATABASE_URL='postgres://postgres:flash@127.0.0.1:5433/flash?sslmode=disable' \
  go run ./cmd/orchestrator
```

`scripts/cluster-check.sh`, `scripts/window-check.sh`, and
`scripts/node-drain-check.sh` cover this path end-to-end and are a good
reference for exercising it manually.

## gVisor (optional, Linux only)

The sandbox runtime defaults to the standard Docker runtime. To run sandboxes
under gVisor's userspace kernel (the real isolation boundary for untrusted
code):

```bash
./scripts/install-gvisor.sh          # on a Linux host/VM
SANDBOX_RUNTIME=runsc go run ./cmd/orchestrator
```

OrbStack's managed VM can't register a custom runtime; use a Linux VM
(Colima, a cloud instance, etc.) for this.

## Troubleshooting

- **`docker network create` fails / already exists** — `scripts/setup.sh` is
  idempotent; a pre-existing `sandbox-net` is fine.
- **Orchestrator can't reach Postgres** — check `DATABASE_URL` matches the
  port you started Postgres on (`5433` in the examples above, to avoid
  colliding with a system Postgres on `5432`).
- **Sandbox claim hangs / pool never warms** — confirm the sandbox images
  built successfully (`docker images | grep flash-sandbox`) and that
  `SANDBOX_NET` matches the network `scripts/setup.sh` created.
- **`pids-limit too low` / frontend scorer reports a false 0** — the `q3`
  (vitest) scorer spawns a worker pool and needs `256` pids / `512MB`; see the
  note in the README's Playground section if you're modifying scoring
  container limits.
