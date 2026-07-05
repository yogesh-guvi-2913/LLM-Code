# Flash Python SDK

Official Python SDK for the [Flash sandbox engine](../../README.md) — a
self-hosted sandbox platform: claim an isolated sandbox from a warm pool in
under 2 seconds, run commands, read/write files, open a live browser preview,
and destroy it.

## Install

```bash
pip install flash-sandbox-sdk          # once published
pip install -e sdk/python    # from this repo
```

## Quick start

```python
from flash import Flash

client = Flash()  # FLASH_API_KEY / FLASH_BASE_URL from env

with client.sandboxes.create(template="q1", timeout=600) as sbx:
    res = sbx.run("node -e 'console.log(40+2)'")
    print(res.stdout)                     # 42
    sbx.files.write("notes.txt", "hello")
    print(sbx.files.read_text("notes.txt"))
    print(sbx.preview_url)                # frontend templates: live browser preview
# sandbox is killed on exiting the with-block
```

A non-zero exit code is a **result** (`res.exit_code`), not an exception; only
transport failures and timeouts raise `flash.APIError` / `TimeoutError`.

## Services

- `client.sandboxes` — `create / connect / list`, then `sbx.run / exec / files / set_timeout / kill`
- `client.templates` — `list / create / scale` (warm-pool floor)
- `client.api_keys` — `create / list / revoke` (raw key shown once)
- `client.assessments` — the scoring layer: `create_session`, `session.submit()`, `session.wait_for_score()`

## Tests

The test suite is fully end-to-end against a live orchestrator (real
containers — no mocks):

```bash
FLASH_E2E=1 FLASH_BASE_URL=http://127.0.0.1:8090 FLASH_API_KEY=flash_… \
    pytest sdk/python/tests -v
```
