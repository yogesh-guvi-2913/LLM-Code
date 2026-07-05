# Contributing

Thanks for considering a contribution. This covers the basics for working in
this repo; see [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) for full local
setup instructions.

## Before you start

- For anything beyond a small fix, open an issue first describing the problem
  or proposal. It saves everyone time if the approach is agreed on before code
  is written.
- Check open issues and PRs to avoid duplicate work.

## Workflow

1. Fork the repo and create a branch off `main`.
2. Make your change. Keep commits focused — one logical change per commit.
3. Run the checks below before opening a PR.
4. Open a PR against `main` with a clear description of what changed and why.
   Link the related issue if there is one.

## Code style

- **Go**: `gofmt`-clean, `go vet` clean. No linter config beyond that — match
  the style already in the file you're editing.
- **TypeScript/React** (dashboard): follow the existing ESLint config
  (`dashboard/eslint.config.mjs`); `next build` includes type-checking and
  lint, and must pass clean.
- **Python** (SDK): keep to the style already used in `sdk/python/flash/`.

## Tests

- Go: `go test ./cmd/... ./internal/...` from the repo root, and
  `go test ./...` in `sdk/go`.
- Python SDK: `pytest tests` in `sdk/python`.
- Dashboard: `npm run build` in `dashboard` (type-checks, lints, and compiles).
- The SDK e2e suites run against a **live orchestrator with real containers —
  no mocks** (`FLASH_E2E=1 go test ./...` / `FLASH_E2E=1 pytest tests`). If
  your change touches sandbox lifecycle, exec, files, or scoring, run these
  against a local orchestrator (see [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md))
  before opening a PR.
- Don't add tests that mock the Docker daemon, Postgres, or Redis in place of
  the real thing — this project's tests are deliberately end-to-end against
  real infrastructure. Add narrow unit tests for pure logic (see
  `cmd/orchestrator/planner_test.go` for an example) instead.

CI (`.github/workflows/ci.yml`) runs all of the above except the e2e suites
(they need Docker and can't run in the CI sandbox as configured).

## Pull requests

- Keep PRs scoped to one change. Large unrelated diffs are hard to review and
  will likely be asked to split.
- Describe *why* the change is needed, not just what it does — the diff
  already shows what changed.
- Update `README.md` or `docs/DEVELOPMENT.md` if your change affects setup,
  configuration, or public API behavior.

## Reporting bugs / security issues

- Regular bugs: open a GitHub issue with steps to reproduce, expected vs.
  actual behavior, and relevant logs.
- Security vulnerabilities: do not open a public issue. See if the repo has a
  `SECURITY.md`/security policy for a private reporting channel; if not, open
  an issue asking for a contact path rather than posting exploit details
  publicly.
