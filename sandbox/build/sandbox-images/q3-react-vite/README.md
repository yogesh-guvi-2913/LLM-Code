# q3-react-vite — React + Vite Todo frontend

A warm-pool sandbox template that mirrors `q1-express-api` / `q2-flask-api`.
The candidate completes a small Todo list React app in `src/App.tsx`.

## Layout

```
q3-react-vite/
├── Dockerfile
├── README.md
├── template/                 # build context -> baked into the image
│   ├── package.json          # react/react-dom + vite + vitest toolchain
│   ├── vite.config.ts        # server (port 3000) + vitest config (FIXED)
│   ├── tsconfig.json         # (FIXED)
│   ├── index.html            # root entry, references /src/main.tsx (FIXED)
│   └── src/                  # CANDIDATE-EDITABLE, reset-on-claim (-> /app/src)
│       ├── main.tsx          # mounts <App/>
│       ├── App.tsx           # STARTER STUB the candidate completes
│       └── styles.css
└── harness/                  # scorer, NOT shipped to the candidate (-> /harness)
    ├── run-tests.sh
    ├── score.cjs
    ├── vitest.setup.ts
    ├── App.test.tsx
    └── solution/App.tsx      # reference full solution (scores 100)
```

`src/main.tsx` and `index.html` are fixed scaffolding; only `src/App.tsx` is
meaningfully graded. The whole `src/` tree is reset from `/template-src` on claim.

## Dev server (orchestrator boots this)

```
DEV_CMD = npx vite --host 0.0.0.0 --port 3000
```

`vite.config.ts` already sets `server.host=true`, `port=3000`, `strictPort=true`,
so the CLI flags are belt-and-suspenders. The server listens on `0.0.0.0:3000`
for the orchestrator's health check + proxy.

### Read-only rootfs notes

Only `/app/src` and `/tmp` are writable (tmpfs). The config redirects Vite's
cache to `/tmp/.vite` (`cacheDir`) so it never writes into the read-only baked
`node_modules`.

### Env vars `vite.config.ts` reads

| var               | default          | purpose                                                |
| ----------------- | ---------------- | ------------------------------------------------------ |
| `HMR_CLIENT_PORT` | `8090`           | public port the browser uses for HMR through the proxy |
| `APP_SRC`         | `<dir>/src`      | absolute path to candidate source (`@app` alias)       |
| `HARNESS_DIR`     | `<dir>/harness`  | absolute path to the scoring harness (setup file)      |

`run-tests.sh` exports `APP_SRC=/app/src` and `HARNESS_DIR=/harness` for scoring.
`server.allowedHosts=true` lets Vite accept proxied Host headers such as
`sess_abc.preview.localhost`; `server.hmr.host` is intentionally unset.

## Scoring

`harness/run-tests.sh` runs vitest (jsdom + @testing-library/react) against the
candidate's `App` and prints exactly one final JSON line:

```
{"score":N,"max_score":100,"test_results":[...]}
```

Weights are encoded inline in each test title (`[weight:N]`) and summed by
`score.cjs`:

| test                                 | weight |
| ------------------------------------ | -----: |
| adds a todo when Add is clicked      |     30 |
| renders multiple todos in order      |     35 |
| toggles completed state on click     |     35 |
| **total**                            | **100**|

- The **starter** (`template/src/App.tsx`) scores **0** — no list, button is a no-op.
- The **reference solution** (`harness/solution/App.tsx`) scores **100**.

## Verify locally (no docker)

Replicate the container layout in a temp dir and run the real vitest suite:

```sh
TMP=$(mktemp -d)
cp template/package.json template/vite.config.ts template/tsconfig.json template/index.html "$TMP/"
cp -r template/src "$TMP/src"
cp -r harness "$TMP/harness"
( cd "$TMP" && npm install --silent )

# starter (expect score 0)
( cd "$TMP" && npx vitest run harness/App.test.tsx --reporter=json --outputFile=/tmp/r.json >/dev/null 2>&1 || true; \
  VITEST_REPORT=/tmp/r.json node harness/score.cjs )

# solution (expect score 100)
cp harness/solution/App.tsx "$TMP/src/App.tsx"
( cd "$TMP" && npx vitest run harness/App.test.tsx --reporter=json --outputFile=/tmp/r.json >/dev/null 2>&1 || true; \
  VITEST_REPORT=/tmp/r.json node harness/score.cjs )
```
