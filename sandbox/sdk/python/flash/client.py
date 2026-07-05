"""Flash SDK client — mirrors the Go SDK surface 1:1.

Every service hangs off :class:`Flash`: ``client.sandboxes`` (the core
sandbox surface), ``client.templates``, ``client.api_keys``, and
``client.assessments`` (the submit → score layer on top).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterator, Optional
from urllib.parse import quote

import httpx

_DEFAULT_BASE_URL = "http://127.0.0.1:8090"


class APIError(Exception):
    """A non-2xx response from the orchestrator."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"API error {status_code}: {message}")


class Flash:
    """Entry point. Reads ``FLASH_API_KEY`` / ``FLASH_BASE_URL`` from the
    environment unless given explicitly. An empty API key is only valid against
    an orchestrator running with ``AUTH_ENABLED=false``."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 620.0,
    ):
        self._api_key = api_key if api_key is not None else os.environ.get("FLASH_API_KEY", "")
        self._base_url = (base_url or os.environ.get("FLASH_BASE_URL", _DEFAULT_BASE_URL)).rstrip("/")
        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        self._http = httpx.Client(base_url=self._base_url, headers=headers, timeout=timeout)

        self.sandboxes = SandboxService(self)
        self.templates = TemplateService(self)
        self.api_keys = APIKeyService(self)
        self.assessments = AssessmentService(self)

    @property
    def base_url(self) -> str:
        return self._base_url

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "Flash":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # -- transport ------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        resp = self._http.request(method, path, **kwargs)
        if resp.status_code >= 300:
            message = resp.text.strip()
            try:
                message = resp.json().get("error", message)
            except Exception:
                pass
            raise APIError(resp.status_code, message)
        return resp

    def _json(self, method: str, path: str, **kwargs: Any) -> Any:
        resp = self._request(method, path, **kwargs)
        return resp.json() if resp.content else None


def _parse_ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# -- sandboxes -----------------------------------------------------------


@dataclass
class ExecResult:
    """One command's outcome. A non-zero exit code is a normal result, not an
    exception — only transport failures and timeouts raise."""

    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int = 0

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


class Sandbox:
    """A live (or past) isolated environment. Supports ``with`` — the sandbox
    is killed on exit."""

    def __init__(self, client: Flash, data: dict):
        self._c = client
        self._apply(data)
        self.files = FileService(self)

    def _apply(self, data: dict) -> None:
        self.id: str = data["sandbox_id"]
        self.template_id: str = data.get("template_id", "")
        self.state: str = data.get("state", "")
        self.metadata: dict = data.get("metadata") or {}
        self.created_at = _parse_ts(data.get("created_at"))
        self.expires_at = _parse_ts(data.get("expires_at"))
        self.app_url: str = data.get("app_url", "")
        self.preview_url: str = data.get("preview_url", "")
        self.terminal_url: str = data.get("terminal_url", "")
        self.terminal_page: str = data.get("terminal_page", "")
        #: Per-sandbox candidate credential (terminal / preview / submit).
        self.token: str = data.get("token", "")

    def __repr__(self) -> str:
        return f"Sandbox(id={self.id!r}, template={self.template_id!r}, state={self.state!r})"

    def __enter__(self) -> "Sandbox":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.kill()

    # -- lifecycle --

    def refresh(self) -> "Sandbox":
        """Re-fetch state from the orchestrator in place."""
        data = self._c._json("GET", f"/v1/sandboxes/{quote(self.id)}")
        self._apply(data)
        return self

    def kill(self) -> None:
        """Destroy the sandbox immediately. Idempotent."""
        self._c._request("DELETE", f"/v1/sandboxes/{quote(self.id)}")

    def set_timeout(self, seconds: int) -> None:
        """Reset the sandbox's lifetime to now+seconds (keep-alive)."""
        data = self._c._json(
            "POST", f"/v1/sandboxes/{quote(self.id)}/timeout", json={"timeout_seconds": seconds}
        )
        self.expires_at = _parse_ts(data["expires_at"])

    # -- exec --

    def run(
        self,
        command: str,
        cwd: str = "",
        env: Optional[dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> ExecResult:
        """Run a shell command line (via ``sh -c``)."""
        return self._exec({"command": command}, cwd, env, timeout)

    def exec(
        self,
        argv: list[str],
        cwd: str = "",
        env: Optional[dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> ExecResult:
        """Run an argv directly (no shell interpretation)."""
        return self._exec({"cmd": argv}, cwd, env, timeout)

    def _exec(
        self, body: dict, cwd: str, env: Optional[dict[str, str]], timeout: Optional[int]
    ) -> ExecResult:
        if cwd:
            body["cwd"] = cwd
        if env:
            body["env"] = env
        if timeout:
            body["timeout_seconds"] = timeout
        data = self._c._json("POST", f"/v1/sandboxes/{quote(self.id)}/exec", json=body)
        return ExecResult(
            stdout=data["stdout"],
            stderr=data["stderr"],
            exit_code=data["exit_code"],
            duration_ms=data.get("duration_ms", 0),
        )


class FileService:
    """Files inside one sandbox's writable work dir. Paths are relative to the
    work dir; traversal outside it is rejected server-side."""

    def __init__(self, sandbox: Sandbox):
        self._sb = sandbox

    def list(self) -> list[str]:
        data = self._sb._c._json("GET", f"/v1/sandboxes/{quote(self._sb.id)}/files")
        return data.get("files") or []

    def read(self, path: str) -> bytes:
        resp = self._sb._c._request(
            "GET", f"/v1/sandboxes/{quote(self._sb.id)}/files/content", params={"path": path}
        )
        return resp.content

    def read_text(self, path: str, encoding: str = "utf-8") -> str:
        return self.read(path).decode(encoding)

    def write(self, path: str, content: bytes | str) -> None:
        if isinstance(content, str):
            content = content.encode("utf-8")
        self._sb._c._request(
            "PUT",
            f"/v1/sandboxes/{quote(self._sb.id)}/files/content",
            params={"path": path},
            content=content,
        )

    def delete(self, path: str) -> None:
        self._sb._c._request(
            "DELETE", f"/v1/sandboxes/{quote(self._sb.id)}/files/content", params={"path": path}
        )


class SandboxService:
    def __init__(self, client: Flash):
        self._c = client

    def create(
        self,
        template: str,
        timeout: Optional[int] = None,
        metadata: Optional[dict[str, str]] = None,
    ) -> Sandbox:
        """Claim a sandbox — warm-pool hit in well under 2s, cold boot otherwise.

        ``timeout`` is the sandbox lifetime in seconds (template default if
        omitted); extend later with :meth:`Sandbox.set_timeout`."""
        body: dict[str, Any] = {"template_id": template}
        if timeout:
            body["timeout_seconds"] = timeout
        if metadata:
            body["metadata"] = metadata
        return Sandbox(self._c, self._c._json("POST", "/v1/sandboxes", json=body))

    def connect(self, sandbox_id: str) -> Sandbox:
        """Attach to an existing sandbox by id."""
        return Sandbox(self._c, self._c._json("GET", f"/v1/sandboxes/{quote(sandbox_id)}"))

    def list(self, running_only: bool = False) -> list[Sandbox]:
        params = {"state": "running"} if running_only else {}
        data = self._c._json("GET", "/v1/sandboxes", params=params)
        return [Sandbox(self._c, d) for d in data.get("sandboxes") or []]


# -- templates -----------------------------------------------------------


@dataclass
class Template:
    id: str
    image: str = ""
    title: str = ""
    language: str = ""
    description: str = ""
    kind: str = "api"
    dev_cmd: str = ""
    min_warm: int = 0
    vcpu: float = 0.0
    memory_mb: int = 0
    pids_limit: int = 0
    #: Live warm-pool depth (populated on list).
    warm: int = 0

    @classmethod
    def _from_json(cls, d: dict) -> "Template":
        return cls(
            id=d["id"],
            image=d.get("image", ""),
            title=d.get("title", ""),
            language=d.get("language", ""),
            description=d.get("description", ""),
            kind=d.get("kind", "api"),
            dev_cmd=d.get("dev_cmd", ""),
            min_warm=d.get("min_warm", 0),
            vcpu=d.get("vcpu", 0.0),
            memory_mb=d.get("memory_mb", 0),
            pids_limit=d.get("pids_limit", 0),
            warm=d.get("warm", 0),
        )


class TemplateService:
    def __init__(self, client: Flash):
        self._c = client

    def list(self) -> list[Template]:
        return [Template._from_json(d) for d in self._c._json("GET", "/v1/templates")]

    def create(self, template: Template) -> Template:
        """Register a new template at runtime; the orchestrator validates the
        image exists and starts warming the pool immediately."""
        body = {
            "id": template.id,
            "image": template.image,
            "title": template.title,
            "language": template.language,
            "description": template.description,
            "kind": template.kind,
            "dev_cmd": template.dev_cmd,
            "min_warm": template.min_warm,
            "vcpu": template.vcpu,
            "memory_mb": template.memory_mb,
            "pids_limit": template.pids_limit,
        }
        return Template._from_json(self._c._json("POST", "/v1/templates", json=body))

    def scale(self, template_id: str, min_warm: int) -> None:
        """Set a template's warm-pool floor at runtime (the pre-warm knob)."""
        self._c._json(
            "POST", f"/v1/templates/{quote(template_id)}/min_warm", json={"min_warm": min_warm}
        )


# -- api keys ------------------------------------------------------------


@dataclass
class APIKey:
    id: str
    name: str
    prefix: str
    created_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None


@dataclass
class CreatedAPIKey:
    id: str
    name: str
    prefix: str
    #: The raw key — shown exactly once, unrecoverable afterwards.
    key: str


class APIKeyService:
    def __init__(self, client: Flash):
        self._c = client

    def create(self, name: str) -> CreatedAPIKey:
        d = self._c._json("POST", "/v1/api-keys", json={"name": name})
        return CreatedAPIKey(id=d["id"], name=d["name"], prefix=d["prefix"], key=d["key"])

    def list(self) -> list[APIKey]:
        data = self._c._json("GET", "/v1/api-keys")
        return [
            APIKey(
                id=d["id"],
                name=d.get("name", ""),
                prefix=d.get("prefix", ""),
                created_at=_parse_ts(d.get("created_at")),
                last_used_at=_parse_ts(d.get("last_used_at")),
            )
            for d in data.get("keys") or []
        ]

    def revoke(self, key_id: str) -> None:
        """Disable a key immediately. Revoking the key this client uses is
        refused by the server (409) — mint a replacement first."""
        self._c._request("DELETE", f"/v1/api-keys/{quote(key_id)}")


# -- assessments (submit → score layer) -----------------------------------


@dataclass
class Submission:
    submission_id: str = ""
    status: str = ""
    score: int = 0
    max_score: int = 0


class Session:
    """A candidate's assessment sandbox — created with the org key, driven by
    the per-session token (the candidate credential)."""

    def __init__(self, client: Flash, data: dict):
        self._c = client
        self.id: str = data["session_id"]
        self.token: str = data.get("session_token", "")
        self.candidate_id: str = data.get("candidate_id", "")
        self.question_id: str = data.get("question_id", "")
        self.status: str = data.get("status", "")
        self.app_url: str = data.get("app_url", "")
        self.preview_url: str = data.get("preview_url", "")
        self.terminal_url: str = data.get("terminal_url", "")
        self.expires_at = _parse_ts(data.get("expires_at"))

    def submit(self) -> Submission:
        """Snapshot the candidate's work, destroy the sandbox, start scoring."""
        resp = self._c._http.request(
            "POST",
            f"/v1/sessions/{quote(self.id)}/submit",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        if resp.status_code >= 300:
            raise APIError(resp.status_code, resp.text.strip())
        d = resp.json()
        return Submission(submission_id=d.get("submission_id", ""), status=d.get("status", ""))

    def result(self) -> Optional[Submission]:
        """The latest submission's score, or None if nothing submitted yet."""
        d = self._c._json(
            "GET", f"/v1/sessions/{quote(self.id)}/result", params={"token": self.token}
        )
        if not d.get("submitted"):
            return None
        return Submission(
            status=d.get("status", ""), score=d.get("score", 0), max_score=d.get("max_score", 0)
        )

    def wait_for_score(self, timeout: float = 180.0, poll: float = 2.0) -> Submission:
        """Poll :meth:`result` until scoring completes."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            sub = self.result()
            if sub is not None and sub.status != "scoring":
                return sub
            time.sleep(poll)
        raise TimeoutError(f"submission for session {self.id} not scored within {timeout}s")


class AssessmentService:
    def __init__(self, client: Flash):
        self._c = client

    def create_session(
        self,
        candidate_id: str,
        question_id: str,
        assessment_id: str = "",
        time_limit_minutes: int = 0,
    ) -> Session:
        """Claim a sandbox for a candidate. Hand ``Session.token`` to the
        candidate; keep your org key private."""
        body: dict[str, Any] = {"candidate_id": candidate_id, "question_id": question_id}
        if assessment_id:
            body["assessment_id"] = assessment_id
        if time_limit_minutes:
            body["time_limit_minutes"] = time_limit_minutes
        return Session(self._c, self._c._json("POST", "/v1/sessions", json=body))

    def get_session(self, session_id: str) -> Session:
        return Session(self._c, self._c._json("GET", f"/v1/sessions/{quote(session_id)}"))

    def destroy(self, session_id: str) -> None:
        """Tear the session down without scoring."""
        self._c._request("DELETE", f"/v1/sessions/{quote(session_id)}")
