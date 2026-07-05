## What changed and why

## How was this tested?

- [ ] `go vet`/`go build`/`gofmt` clean (`cmd`, `internal`, `sdk/go`)
- [ ] `go test ./cmd/... ./internal/...` and `sdk/go`'s test suite pass
- [ ] `pytest tests` passes in `sdk/python` (if touched)
- [ ] `npm run build` passes in `dashboard` (if touched)
- [ ] Ran the relevant e2e script(s) against a live orchestrator, if this
      touches sandbox lifecycle, auth, cluster scheduling, or scoring
      (`scripts/e2e.sh`, `auth-check.sh`, `cluster-check.sh`, etc.)

## Related issue(s)

Closes #
