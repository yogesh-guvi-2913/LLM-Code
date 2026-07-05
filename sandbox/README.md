# Flash Sandbox Engine

A self-hosted sandbox engine: warm pools of isolated Docker sandboxes
claimable in <2s via **API key + SDK** (Go and Python), a generic
`/v1/sandboxes` API (create / exec / files / preview / kill), and a **native
dashboard embedded in the orchestrator binary** — one binary is the whole
product. On top of the generic engine sits the assessment layer (candidate
sessions, submit → automated scoring) it was originally built for.

> Setting up a local dev environment? See [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md).
> Want to contribute? See [`CONTRIBUTING.md`](CONTRIBUTING.md). Curious what's
> planned but not built yet? See [`ROADMAP.md`](ROADMAP.md).

## SDKs

**Go** ([`sdk/go`](sdk/go/)) — stdlib-only:

```go
client, _ := flash.New() // FLASH_API_KEY + FLASH_BASE_URL from env
sbx, _ := client.Sandboxes.Create(ctx, flash.CreateSandboxOpts{Template: "q1"})
defer sbx.Kill(ctx)
res, _ := sbx.Run(ctx, "node -e 'console.log(40+2)'") // res.Stdout, res.ExitCode
sbx.Files().Write(ctx, "notes.txt", []byte("hello"))
```

**Python** ([`sdk/python`](sdk/python/)):

```python
client = Flash()
with client.sandboxes.create(template="q1") as sbx:
    print(sbx.run("echo hi").stdout)
    sbx.files.write("notes.txt", "hello")
```

Both SDKs cover sandboxes (create/exec/files/preview/keep-alive/kill),
templates, API-key lifecycle, and the assessment layer (submit → score). Their
test suites are **fully end-to-end against a live orchestrator** — real
containers, no mocks (`FLASH_E2E=1 go test ./...` / `pytest`).

What v1 deliberately drops vs the spec, and why: see [Design choices](#design-choices).

## What works today (proven end-to-end)

```
POST /v1/sessions   → claim warm container (<2s) → candidate hits live API
POST /v1/sessions/:id/submit → snapshot src → score in --network none container → Postgres
                    → container destroyed, port released, pool replenished to min_warm
```

Measured locally: starter code scores **25/100**, a correct solution scores
**100/100**, warm pool self-heals back to 3.

### Live terminal (xterm.js)

A token-authed WebSocket gives the candidate a real shell in `/app/src`:

```
browser  ─WS→  orchestrator  ─WS→  toolbox  ─PTY→  /bin/sh
         token-auth         transparent     resize-aware
```

- `GET /terminal?session=<id>&token=<tok>` — self-contained xterm.js page
  (embed in an iframe, or lift the WS wiring into the candidate IDE).
- `GET /v1/sessions/:id/terminal?token=<tok>` — the WebSocket itself.
- Protocol: binary frames = terminal I/O, text frames = `{"type":"resize",...}`.
  The orchestrator proxies frames verbatim, so resize works end-to-end.

Verified: PTY runs in `/app/src`, sees the starter code, the rootfs is immutable
from inside the shell, and a wrong token is rejected with 401.

## Architecture (v1)

```
 browser (xterm.js)
       │  WS /v1/sessions/:id/terminal?token=…   (token-authed)
       ▼
 cmd/orchestrator   one Go binary: HTTP API + WS terminal proxy +
                    in-process warm pool + health/timeout/replenish + scoring
       │ Docker SDK (local socket)   │ WS proxy        │ pgx
       ▼                             ▼                 ▼
 sandbox containers (warm/active)                  Postgres (sessions, submissions)
   └ cmd/toolbox (in-image): /claim /health /ws/terminal(PTY) + dev server
 scoring container (--network none, one-shot, harness → JSON)
```

No SQS, no Redis, no ElastiCache, no ECS — pool state is a mutex-guarded map in
the orchestrator. Correct for one node; swap in Redis when you add a second.

## Layout

```
cmd/orchestrator        control plane (API + auth + scheduler + scoring + proxies)
cmd/node-agent          per-box sandbox runner (Docker + warm pool + HTTP API)
cmd/toolbox             static binary baked into every sandbox image
internal/docker         thin Docker SDK wrapper (create, reap, run-scorer, stats)
internal/pool           warm pool: claim, spin, replenish, health, ports, adopt
internal/cluster        Redis node registry + scheduler (multi-node)
internal/metrics        Prometheus collectors
internal/templates      shared template domain (control plane + node-agent)
internal/store          Postgres: sessions + submissions + orgs/api_keys
internal/dashboard      the embedded (go:embed) static-export of dashboard/
sdk/go                  Go SDK (stdlib-only) — sandboxes/templates/keys/assessments
sdk/python              Python SDK (httpx) — same surface
build/sandbox-images/q1-express-api   Node/Express template + harness + Dockerfile
build/sandbox-images/q2-flask-api     Python/Flask template + harness + Dockerfile
build/sandbox-images/q3-react-vite    React/Vite frontend template (browser preview) + vitest harness
dashboard               Next.js + shadcn/ui control-plane UI (static-exported & embedded)
scripts                 setup.sh, build-image.sh, install-gvisor.sh, e2e.sh
```

## Templates (v1)

Two pre-baked templates prove the pool is language-agnostic — the toolbox runs a
per-template `DEV_CMD`, everything else is identical:

| ID | Title | Language | Kind | Image | Min warm |
|----|-------|----------|------|-------|----------|
| `q1` | Express Todo API | Node.js | api | `flash-sandbox:q1-express-api-v1` | 3 |
| `q2` | Flask Todo API | Python | api | `flash-sandbox:q2-flask-api-v1` | 2 |
| `q3` | React Todo App | React/Vite | frontend | `flash-sandbox:q3-react-vite-v1` | 2 |

- `q1`/`q2` (API): starter **25/100**, full solution **100/100** (verified end-to-end).
- `q3` (frontend): a live **browser preview** (see below); vitest-scored, starter **0/100**,
  full solution **100/100** (verified through the real in-container scorer).

Templates are a runtime-mutable registry: more can be registered live via
`POST /v1/templates` (the dashboard's "Create Template") without a restart —
the orchestrator validates the image exists, then starts warming the new pool.

## Run it

```bash
# 1. Postgres (Docker, self-contained) + sandbox network
docker run -d --name flash-pg -e POSTGRES_PASSWORD=flash -e POSTGRES_DB=flash \
  -p 5433:5432 postgres:16-alpine
docker network create --opt com.docker.network.bridge.enable_icc=false sandbox-net

# 2. Build the toolbox + both sandbox images
./scripts/build-image.sh                 # all templates
# ./scripts/build-image.sh q2-flask-api  # or just one

# 3. Start the orchestrator (warms both pools, then listens)
DATABASE_URL='postgres://postgres:flash@127.0.0.1:5433/flash?sslmode=disable' \
  LISTEN_ADDR=':8090' go run ./cmd/orchestrator

# 4. Drive the full loop
BASE=http://127.0.0.1:8090 ./scripts/e2e.sh

# 5. Dashboard — already there: it is embedded in the orchestrator binary.
open http://127.0.0.1:8090            # (dev-only alternative: cd dashboard && npm run dev)

# 6. SDK e2e suites against the live stack (real containers, no mocks)
FLASH_E2E=1 FLASH_API_KEY=flash_… go test ./sdk/go/... -v
FLASH_E2E=1 FLASH_API_KEY=flash_… pytest sdk/python/tests -v
```

> After changing the dashboard UI, run `./scripts/build-dashboard.sh` to refresh
> the embedded copy (`internal/dashboard/dist`), then rebuild the orchestrator.

Env: `DATABASE_URL`, `LISTEN_ADDR`, `SANDBOX_NET`, `SANDBOX_RUNTIME`, `Q1_IMAGE`, `Q2_IMAGE`,
`PREVIEW_DOMAIN`, `PREVIEW_PORT`, `AUTH_ENABLED` (default `true`), `BOOTSTRAP_API_KEY`,
`ORG_CONCURRENCY_LIMIT` (default 20), `AUTH_RATE_RPS`/`AUTH_RATE_BURST`,
`COST_NODE_USD_PER_HR`/`COST_NODE_RAM_GB` (cost model for `/v1/usage`).

> Auth is **on by default**. For local dev either set `AUTH_ENABLED=false`, or pass
> `BOOTSTRAP_API_KEY=flash_…` and give it to the dashboard (Settings → API key). With
> neither, the orchestrator mints a key on first boot and logs it once.

## Dashboard

`dashboard/` — a Next.js 16 + React 19 + **shadcn/ui** app, **served
natively by the orchestrator**: `next build` static-exports it and `go:embed`
bakes it into the binary (`internal/dashboard`), so `http://<orchestrator>/` IS
the dashboard — same origin as the API (zero config), no Node runtime in
production. It is a **native control plane**, not a read-only viewer: you
create and operate sandboxes from the UI, polling live every 3s.

- Collapsible **sidebar** (icon-rail mode): node header, nav with live badges
  (Sessions / Templates counts), user in the footer.
- **Create sandbox** (header) — pick a template (with kind + live warm count),
  candidate id, optional time limit → claims a session and opens its detail.
- **Create template** (Templates tab) — id, kind (api/frontend), image, dev
  command, resources → registers + warms a new template at runtime (the
  orchestrator validates the image exists first).
- **Session detail** (slide-over) — click any session for:
  - **Preview** — the candidate's live app embedded in an `<iframe>` (frontend
    templates) via the host-token proxy; HMR works inside the iframe.
  - **Terminal** — a live xterm.js shell into the running container, embedded.
  - **Info** + **Destroy** / **Submit & score** actions.
- Sections: **Overview** (4 metric cards + live chart + Recent Sessions + a
  **Cost & density** panel reading `/v1/usage` — conservative vs. overcommit
  $/sandbox-hr), **Sessions** (table), **Templates** (resources, warm-pool gauges,
  and an inline **Scale** control that drives `min_warm`), **Fleet** (each node's
  capacity/warm/active/liveness from `/v1/nodes` — one row locally, N in cluster),
  **Settings** (operator API key + the **API keys** lifecycle: mint named keys —
  raw shown once — see last-used, revoke).

Point it at any orchestrator via the API field (top-right) or `?api=` query param.
`NEXT_PUBLIC_API_BASE` sets the default; in production it defaults to same-origin
since the dashboard is served by the orchestrator itself. `npm run build` is
green (typechecked).

## API

### Generic sandbox API (SDK-facing, org key)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/v1/sandboxes` | claim a sandbox from a template (`template_id`, `timeout_seconds`, `metadata`) |
| `GET` | `/v1/sandboxes` | list the org's sandboxes (`?state=running` for live only) |
| `GET` | `/v1/sandboxes/:id` | one sandbox + live URLs |
| `DELETE` | `/v1/sandboxes/:id` | kill (idempotent) |
| `POST` | `/v1/sandboxes/:id/timeout` | keep-alive: reset expiry to now+`timeout_seconds` |
| `POST` | `/v1/sandboxes/:id/exec` | run `cmd` (argv) or `command` (sh -c) → `{stdout, stderr, exit_code, duration_ms}` |
| `GET` | `/v1/sandboxes/:id/files` | list work-dir files |
| `GET/PUT/DELETE` | `/v1/sandboxes/:id/files/content?path=` | read / write / delete one file |
| `POST` | `/v1/api-keys` | mint a named org key (raw shown once) |
| `GET` | `/v1/api-keys` | list keys (name, prefix, last used) |
| `DELETE` | `/v1/api-keys/:id` | revoke (self-revocation refused with 409) |

A non-zero exit from `exec` is a **200 with the code** — only transport
failures/timeouts are HTTP errors. Sandboxes are org-scoped: another org's
sandbox id is a 404. Exec runs as the non-root sandbox user inside the same
hardened container the terminal uses.

### Assessment API (sessions, submit → score)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/v1/sessions` | claim a sandbox → session id + token + app/terminal/preview URLs |
| `GET` | `/v1/sessions/:id` | one session + live URLs (app, preview, terminal) while ACTIVE |
| `POST` | `/v1/sessions/:id/submit` | snapshot → score → destroy (Bearer token) |
| `DELETE` | `/v1/sessions/:id` | destroy a session |
| `GET` | `/v1/sessions/:id/terminal?token=` | terminal WebSocket |
| `GET` | `/terminal?session=&token=` | xterm.js terminal page (embeddable) |
| `GET` | `/v1/templates` | templates + live warm depth (dashboard) |
| `POST` | `/v1/templates` | register a new template at runtime + start warming |
| `POST` | `/v1/templates/:id/min_warm` | set warm depth at runtime (also sets the planner baseline) |
| `GET` | `/v1/windows` | booked pre-warm windows + the planner's live `desired_warm_now` |
| `POST` | `/v1/windows` | book a window `{question_id, seats, lead_minutes, starts_at, ends_at}` |
| `DELETE` | `/v1/windows/:id` | cancel a window |
| `GET` | `/v1/sessions` | recent sessions + scores (dashboard) |
| `GET` | `/v1/stats` | warm-pool depth per question |
| `GET` | `/v1/usage` | billed sandbox-hours + measured density + $/sandbox-hr |
| `GET` | `/v1/nodes` | fleet: each node's capacity/warm/active/liveness |
| `GET` | `/metrics` | Prometheus metrics (warm/active/claim-latency/density + `required_nodes` autoscaling signal) |
| `GET` | `/healthz`, `/readyz` | liveness / readiness (readiness 503 while warming or draining) |
| `*` | `<id>.preview.<domain>/…` | reverse proxy to a session's live dev server (preview) |

### Browser preview (frontend templates)

Frontend templates (e.g. `q3`) run a live Vite dev server the candidate sees in a
browser. The orchestrator fronts it on a single authenticated entrypoint using
wildcard subdomains — the spec's Caddy + wildcard-DNS shape, with **zero DNS
setup**: browsers resolve any `*.localhost` name to loopback (RFC 6761), so
`http://<session-id>.preview.localhost:8090/` reaches the orchestrator, which
reverse-proxies (HTTP **and** the Vite HMR WebSocket) to that session's
container. Auth: the first load carries `?token=`, which mints a host-scoped
cookie and redirects to a clean URL; every later asset/HMR request rides the
cookie, so the token never leaks into asset URLs. `POST /v1/sessions` returns a
`preview_url` for frontend templates. Verified end-to-end in a browser: app
renders, `[vite] connected.` over the proxied WebSocket, wrong/no token → 401.

## Scaling: single node → fleet (the concurrency unlock)

The control plane talks to a **`Provisioner`**, not to Docker directly. Two impls,
same control-plane code:

- **local** (default, `CLUSTER_MODE` unset) — an in-process warm pool on one box.
  This is the v1 path; everything in Phases 1–2 runs here unchanged.
- **cluster** (`CLUSTER_MODE=true` + `REDIS_URL`) — the control plane is stateless
  and schedules sandboxes across **`node-agent`** processes:

```
 candidate / dashboard ──HTTPS──> orchestrator (control plane, stateless, N≥1)
                                     │  pick node, forward claim
                                     ▼
            ┌─────────── node-agent ──────────┐   ┌────── node-agent ──────┐
            │ Docker + warm pool + HTTP API   │ … │  (another box)         │
            └─────────────────────────────────┘   └────────────────────────┘
                         └──── Redis registry (capacity + TTL liveness) ────┘
            Postgres holds each session's node routing (durable; survives restart)
```

The scheduler (`internal/cluster`) prefers a node already **warm** for the template,
else bin-packs onto the box with the most free memory. A node heartbeats its
capacity to Redis on a TTL; stop heartbeating and it drops out of scheduling. The
preview/terminal proxies and submit/score route to the **owning node** via the
durable session row.

Proven by `scripts/cluster-check.sh` (8/8): claims spread across 2 nodes, preview +
submit routed to the owning node, and **killing a node reschedules** new claims onto
the survivor. (Physical multi-host isolation is validated at deploy, like TLS; an
ungraceful node death loses that node's in-flight sessions.)

**Scheduled scaling.** Book a pre-warm window (`POST /v1/windows`, or the dashboard
**Schedule** view) and the planner raises that template's warm floor `lead` minutes
ahead and restores it after — so a 10:00 assessment is warm at 09:55, not cold at
10:00. It also publishes `flash_required_nodes` (warm target ÷ density), the signal
an ASG scales the fleet on. Proven by `scripts/window-check.sh` (14/14, survives a
control-plane restart). **Graceful scale-in** (`scripts/node-drain-check.sh`, 11/11):
SIGTERM makes a node refuse new claims and fail `/readyz` but finish its active
sessions before exiting. AWS IaC (ASG + ALB/TLS + lifecycle-hook drain) lives in
[`deploy/aws/`](deploy/aws/) (`terraform validate`-clean; apply needs a real account).

```bash
# one node-agent per box (REDIS_URL shared); then the control plane in cluster mode
NODE_ID=node-1 NODE_ADDR=http://10.0.0.11:9001 NODE_HOST=10.0.0.11 \
  REDIS_URL=redis://10.0.0.5:6379/0 go run ./cmd/node-agent
CLUSTER_MODE=true REDIS_URL=redis://10.0.0.5:6379/0 \
  DATABASE_URL=… go run ./cmd/orchestrator
```

## Playground (candidate IDE)

`GET /play?session=<id>&token=<token>` (in the dashboard) is the candidate IDE an
assessment embeds — a **Monaco** editor over the *live* sandbox files, a live
preview, an embedded terminal, and submit→score. It is the candidate plane:
authorized purely by the per-session token, no operator key.

File ops use `docker exec` on the sandbox (no toolbox rebuild) and route through the
`Provisioner`, so they work local and cluster. Candidate-plane API:

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/v1/sessions/:id/play?token=` | kind + live preview/terminal URLs |
| `GET` | `/v1/sessions/:id/files?token=` | list editable files |
| `GET` | `/v1/sessions/:id/file?path=&token=` | read a file |
| `PUT` | `/v1/sessions/:id/file?path=&token=` | save a file (frontend HMR updates preview) |
| `POST`| `/v1/sessions/:id/submit` | snapshot → score → destroy |
| `GET` | `/v1/sessions/:id/result?token=` | latest submission score |

Paths are confined to the work dir (`..` can't escape `/app/src`). Proven in a real
browser: edit `App.tsx`, ⌘S saves to the live sandbox, the preview updates, and
**Submit & score returns 100/100** for the solution (starter 0/100). Open it from
the dashboard session detail → **Open playground**.

> Scorer note: the frontend (vitest) harness spawns a worker pool, so the scoring
> container runs with **256 pids / 512 MB** — a `pids-limit` too low silently yields
> a wrong 0 ("no test report produced").

## Auth (operator vs. candidate)

Two credential types, never conflated:

- **Org API key** (`flash_…`) — the operator/SDK credential. Gates the `/v1/*`
  control plane (sandboxes, sessions, templates, dashboard reads) via the
  `requireOrg` Bearer middleware, carries the org's **concurrency cap**, and is rate
  limited per org. Keys are stored SHA-256-hashed, with a full lifecycle:
  `POST/GET/DELETE /v1/api-keys` (named keys, raw shown once, last-used tracking,
  revocation — self-revocation refused so you can't lock yourself out). Auth is **on by default**
  (`AUTH_ENABLED=true`); set `BOOTSTRAP_API_KEY` or read the one-time minted key from
  the boot logs, then paste it into the dashboard **Settings**.
- **Session token** (`tok_…`) — the candidate credential, scoped to one session.
  Authorizes only that session's submit, terminal, and preview.

`scripts/auth-check.sh` proves it end-to-end (10/10): missing/wrong key → 401, the
per-org concurrency cap → 429, an org key is rejected for `submit` while the session
token is accepted, and the cap frees as sessions end.

## Observability & the cost number

`GET /metrics` is a Prometheus surface (warm/active gauges, claims counter, claim
latency histogram, and **measured** per-sandbox memory from live `docker stats`).
`GET /v1/usage` turns that into money: billed sandbox-hours from the session ledger,
plus a **conservative** ($/sandbox-hr at the OOM-safe configured reservation) and an
**overcommit-ceiling** density derived from measured RAM. It deliberately reports a
*range*, not one rosy number — the conservative figure (~$0.008/sandbox-hr on a
c7g.4xlarge locally) is the one to quote; the ceiling is an upper bound to validate
under real load. Node cost model is configurable via `COST_NODE_USD_PER_HR` /
`COST_NODE_RAM_GB`.

## Design choices

| Spec (v2, AWS) | v1 here | Reason |
|---|---|---|
| API → SQS → orchestrator | one binary, direct HTTP | a queue between two of your own processes is ceremony at one node |
| ElastiCache Redis | in-process map | pool state is small and lives in the orchestrator anyway |
| RDS Postgres | local/Docker Postgres | identical schema; same `pgx` code points at RDS later |
| ECR + CodeBuild | local `docker build` | one template in v1 |
| Caddy + wildcard DNS | none | v1 template is a backend API — no browser preview needed |
| socket-proxy sidecar | direct Docker socket | add before external candidates |

## Hardening in place

- **`cap-drop ALL`, zero added caps** — a node dev server needs none (verified).
- **read-only root filesystem** — `node_modules`, binaries, and the whole image
  are immutable; only the candidate work dir `/app/src` and `/tmp` are writable,
  both on size-capped tmpfs (`mode=1777`, 64m / 16m).
- `no-new-privileges`, default **seccomp** + AppArmor (never `unconfined`).
- `--pids-limit`, `--memory`, CPU quota; non-root `node` user.
- `icc=false` sandbox network; scoring runs `--network none`.
- **Restart-survivable.** On boot the orchestrator *reconciles* from the durable
  truth (Docker + Postgres) instead of reaping every sandbox: it re-adopts the
  containers ACTIVE sessions still point at (preview/terminal/submit keep working
  across a `kill -9`), re-adopts healthy warm containers, and reaps only true
  orphans. Proven by `scripts/restart-survival.sh` (11/11, real SIGKILL).

### gVisor (the real boundary for untrusted code)

Containers share the host kernel — fine for hardening, not a guarantee against a
kernel exploit. The runtime is configurable:

```bash
# On the Linux runner node (EC2), once:
./scripts/install-gvisor.sh
# Then run the orchestrator with:
SANDBOX_RUNTIME=runsc go run ./cmd/orchestrator
```

The orchestrator passes the runtime straight to Docker (`HostConfig.Runtime`);
with `runsc` installed, every sandbox boots inside gVisor's userspace kernel.

**Proven end-to-end on a real Linux node.** OrbStack's managed VM can't register
a custom runtime, so this was verified on a [colima](https://github.com/abiosoft/colima)
Ubuntu 24.04 VM (`brew install colima && colima start`, then
`scripts/install-gvisor.sh` inside it). With the orchestrator pointed at that
node (`DOCKER_HOST=<colima sock> SANDBOX_RUNTIME=runsc`), the warm pool came up
under gVisor and a claimed sandbox reported kernel **`4.19.0-gvisor`** (gVisor's
synthetic kernel, not the host's), `Runtime=runsc`, `ReadonlyRootfs=true`, with
the candidate dev server serving normally. Same path runs on an EC2 node.

## Known limits (read before going external)

1. **Kernel boundary.** Read-only rootfs + caps-dropped + seccomp are in place, and
   gVisor (`SANDBOX_RUNTIME=runsc`) is now proven end-to-end on a real Linux node
   (see above) — deploy the runner on Linux to use it. Beyond gVisor, Firecracker
   microVMs are the strongest option — only worth it if gVisor's syscall coverage
   proves limiting.
2. **In-process pool state is rebuilt on restart, not persisted.** A `kill -9` no
   longer drops live sessions — boot reconcile re-adopts them from Docker+Postgres
   (see Hardening). What's still single-node: this works because one orchestrator
   can inspect its own Docker. A *second* node can't see the first's containers —
   that's where Redis-backed shared state comes in (see cluster mode above).
3. **Density.** ~512 MB/container → ~20 warm on 16 GB. Size memory to the real dev
   server footprint or OOM kills sessions.
4. **arch.** Build images for the deploy arch (`buildx`); local arm64 ≠ EC2 x86_64.
5. **Single node.** No ASG/failover yet — fine for first real assessment, add a
   second node + Redis before scale.
