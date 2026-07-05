"""Real end-to-end tests — drive a live orchestrator (real containers, real
Postgres). No mocks, no stubs. Run with:

    FLASH_E2E=1 FLASH_BASE_URL=http://127.0.0.1:8090 FLASH_API_KEY=flash_… \
        pytest sdk/python/tests -v
"""

import os

import pytest

from flash import APIError, Flash

pytestmark = pytest.mark.skipif(
    not os.environ.get("FLASH_E2E"),
    reason="set FLASH_E2E=1 (with FLASH_BASE_URL/FLASH_API_KEY) to run against a live orchestrator",
)


@pytest.fixture
def client():
    with Flash() as c:
        yield c


def test_sandbox_lifecycle(client):
    templates = client.templates.list()
    assert templates, "no templates registered"

    sbx = client.sandboxes.create(template="q1", timeout=600, metadata={"purpose": "py-e2e"})
    try:
        assert sbx.state == "running"
        assert sbx.metadata["purpose"] == "py-e2e"
        assert sbx.app_url

        # Shell command: stdout, exit 0.
        res = sbx.run("echo hello from python sdk")
        assert res.ok and res.stdout.strip() == "hello from python sdk"

        # Non-zero exit is a result, not an exception.
        res = sbx.run("exit 4")
        assert res.exit_code == 4

        # Argv exec + env + stderr separation.
        res = sbx.exec(["sh", "-c", "echo out; echo err >&2; echo $FOO"], env={"FOO": "bar"})
        assert "out" in res.stdout and "bar" in res.stdout
        assert "err" in res.stderr

        # Files: write / read / list / delete.
        sbx.files.write("e2e/hello.txt", "python sdk wrote this")
        assert sbx.files.read_text("e2e/hello.txt") == "python sdk wrote this"
        assert "e2e/hello.txt" in sbx.files.list()
        sbx.files.delete("e2e/hello.txt")
        with pytest.raises(APIError):
            sbx.files.read("e2e/hello.txt")

        # Keep-alive moves expiry.
        before = sbx.expires_at
        sbx.set_timeout(1800)
        assert sbx.expires_at > before

        # Connect + list see it.
        again = client.sandboxes.connect(sbx.id)
        assert again.state == "running"
        assert any(s.id == sbx.id for s in client.sandboxes.list(running_only=True))
    finally:
        sbx.kill()

    sbx.kill()  # idempotent
    sbx.refresh()
    assert sbx.state == "destroyed"
    with pytest.raises(APIError):
        sbx.run("echo nope")


def test_context_manager_kills(client):
    with client.sandboxes.create(template="q1") as sbx:
        assert sbx.run("true").ok
    assert client.sandboxes.connect(sbx.id).state == "destroyed"


def test_api_key_lifecycle(client):
    if not os.environ.get("FLASH_API_KEY"):
        pytest.skip("auth disabled — key lifecycle needs AUTH_ENABLED=true")

    created = client.api_keys.create("py-e2e")
    assert created.key.startswith("flash_")

    with Flash(api_key=created.key) as c2:
        assert c2.templates.list()  # new key authenticates

        assert any(k.id == created.id and k.name == "py-e2e" for k in client.api_keys.list())

        # A key cannot revoke itself…
        with pytest.raises(APIError) as exc:
            c2.api_keys.revoke(created.id)
        assert exc.value.status_code == 409

        # …but another key can, after which it stops working.
        client.api_keys.revoke(created.id)
        with pytest.raises(APIError):
            c2.templates.list()


def test_assessment_flow(client):
    sess = client.assessments.create_session(
        candidate_id="py-e2e-candidate", question_id="q1", time_limit_minutes=10
    )
    assert sess.token

    sub = sess.submit()
    assert sub.submission_id

    scored = sess.wait_for_score(timeout=180)
    assert scored.status == "scored"
    assert scored.max_score > 0
    print(f"starter code scored {scored.score}/{scored.max_score}")
