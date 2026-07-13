"""
Flash Sandbox Engine Integration Service

This module provides integration with Flash sandbox engine for:
- Template management (list, create, scale warm pools)
- Sandbox lifecycle (create, manage, destroy)
- File operations (sync files to sandbox)
- Scoring (submit and get scores)

Flash runs as a separate service (default: http://localhost:8090)
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import httpx

from app.config import FLASH_API_URL, FLASH_API_KEY, FLASH_ENABLED

logger = logging.getLogger(__name__)


class FlashError(Exception):
    """Exception raised for Flash API errors."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Flash API error {status_code}: {message}")


@dataclass
class FlashTemplate:
    """Flash template metadata."""
    id: str
    slug: str = ""
    title: str = ""
    language: str = ""
    description: str = ""
    image: str = ""
    min_warm: int = 0
    vcpu: float = 0.5
    memory_mb: int = 512
    pids_limit: int = 150
    kind: str = "api"
    dev_cmd: str = ""
    
    @classmethod
    def from_dict(cls, data: Dict) -> "FlashTemplate":
        return cls(
            id=data.get("id", ""),
            slug=data.get("slug", ""),
            title=data.get("title", ""),
            language=data.get("language", ""),
            description=data.get("description", ""),
            image=data.get("image", ""),
            min_warm=data.get("min_warm", 0),
            vcpu=data.get("vcpu", 0.5),
            memory_mb=data.get("memory_mb", 512),
            pids_limit=data.get("pids_limit", 150),
            kind=data.get("kind", "api"),
            dev_cmd=data.get("dev_cmd", ""),
        )


@dataclass
class FlashSandbox:
    """Flash sandbox session."""
    id: str
    template_id: str = ""
    state: str = ""
    app_url: str = ""
    preview_url: str = ""
    terminal_url: str = ""
    terminal_page: str = ""
    token: str = ""
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    
    @classmethod
    def from_dict(cls, data: Dict) -> "FlashSandbox":
        created = data.get("created_at")
        expires = data.get("expires_at")
        return cls(
            id=data.get("sandbox_id", data.get("session_id", "")),
            template_id=data.get("template_id", ""),
            state=data.get("state", ""),
            app_url=data.get("app_url", ""),
            preview_url=data.get("preview_url", ""),
            terminal_url=data.get("terminal_url", ""),
            terminal_page=data.get("terminal_page", ""),
            token=data.get("token", ""),
            created_at=datetime.fromisoformat(created.replace("Z", "+00:00")) if created else None,
            expires_at=datetime.fromisoformat(expires.replace("Z", "+00:00")) if expires else None,
        )


@dataclass
class FlashScoreResult:
    """Flash scoring result."""
    score: int
    max_score: int
    test_results: List[Dict[str, Any]] = field(default_factory=list)
    passed: int = 0
    failed: int = 0
    
    @classmethod
    def from_dict(cls, data: Dict) -> "FlashScoreResult":
        test_results = data.get("test_results", [])
        passed = sum(1 for t in test_results if t.get("passed", False))
        failed = len(test_results) - passed
        return cls(
            score=data.get("score", 0),
            max_score=data.get("max_score", 100),
            test_results=test_results,
            passed=passed,
            failed=failed,
        )


class FlashClient:
    """
    HTTP client for Flash Sandbox Engine API.
    
    Provides methods for:
    - Template management
    - Sandbox creation and lifecycle
    - File operations
    - Scoring
    
    Usage:
        client = FlashClient()
        templates = client.list_templates()
        sandbox = client.create_sandbox(template_id="q1")
        score = client.submit_and_score(sandbox.id, token=sandbox.token)
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 120.0,
    ):
        self.base_url = (base_url or FLASH_API_URL).rstrip("/")
        self.api_key = api_key or FLASH_API_KEY
        self.timeout = timeout
        self._client: Optional[httpx.Client] = None
        
    def _get_client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._client is None:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._client = httpx.Client(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout,
            )
        return self._client
    
    def close(self):
        """Close HTTP client."""
        if self._client:
            self._client.close()
            self._client = None
    
    def _request(self, method: str, path: str, **kwargs) -> Dict:
        """Make HTTP request to Flash API."""
        client = self._get_client()
        try:
            response = client.request(method, path, **kwargs)
            if response.status_code >= 300:
                message = response.text.strip()
                try:
                    message = response.json().get("error", message)
                except Exception:
                    pass
                raise FlashError(response.status_code, message)
            return response.json() if response.content else {}
        except httpx.TimeoutException:
            raise FlashError(408, "Request timed out")
        except httpx.RequestError as e:
            raise FlashError(503, f"Connection failed: {str(e)}")
    
    def health_check(self) -> Dict[str, Any]:
        """Check Flash service health."""
        try:
            client = self._get_client()
            response = client.request("GET", "/healthz")
            if response.status_code == 200:
                return {"healthy": True, "response": {"status": response.text.strip()}}
            return {"healthy": False, "error": f"Status {response.status_code}"}
        except FlashError as e:
            return {"healthy": False, "error": e.message}
        except Exception as e:
            return {"healthy": False, "error": str(e)}
    
    # -------------------------------------------------------------------------
    # Template Management
    # -------------------------------------------------------------------------
    
    def list_templates(self) -> List[FlashTemplate]:
        """List all available templates with warm pool status."""
        response = self._request("GET", "/v1/templates")
        return [FlashTemplate.from_dict(t) for t in response]
    
    def get_template(self, template_id: str) -> Optional[FlashTemplate]:
        """Get a specific template by ID."""
        templates = self.list_templates()
        for t in templates:
            if t.id == template_id:
                return t
        return None
    
    def create_template(self, template: Dict) -> FlashTemplate:
        """
        Register a new template.
        
        Required fields:
        - id: Template ID (alphanumeric, dashes allowed)
        - image: Docker image name
        - dev_cmd: Development command to run
        
        Optional fields:
        - title: Display name
        - language: Programming language
        - kind: "api" or "frontend"
        - min_warm: Minimum warm pool size (0-10)
        - vcpu: CPU quota
        - memory_mb: Memory limit in MB
        - pids_limit: Process limit
        """
        response = self._request("POST", "/v1/templates", json=template)
        return FlashTemplate.from_dict(response)
    
    def scale_template(self, template_id: str, min_warm: int) -> Dict:
        """Scale warm pool for a template."""
        return self._request(
            "POST",
            f"/v1/templates/{template_id}/min_warm",
            json={"min_warm": min_warm}
        )
    
    # -------------------------------------------------------------------------
    # Sandbox Lifecycle
    # -------------------------------------------------------------------------
    
    def create_sandbox(
        self,
        template_id: str,
        timeout_seconds: int = 7200,
        metadata: Optional[Dict] = None,
    ) -> FlashSandbox:
        """
        Create a new sandbox from a template.
        
        Args:
            template_id: Template to use
            timeout_seconds: Sandbox lifetime (default: 2 hours)
            metadata: Optional metadata dict
        
        Returns:
            FlashSandbox with URLs and token
        """
        payload = {
            "template_id": template_id,
            "timeout_seconds": timeout_seconds,
        }
        if metadata:
            payload["metadata"] = metadata
        
        response = self._request("POST", "/v1/sandboxes", json=payload)
        return FlashSandbox.from_dict(response)
    
    def get_sandbox(self, sandbox_id: str) -> FlashSandbox:
        """Get sandbox details."""
        response = self._request("GET", f"/v1/sandboxes/{sandbox_id}")
        return FlashSandbox.from_dict(response)
    
    def list_sandboxes(self, state: Optional[str] = None) -> List[FlashSandbox]:
        """List all sandboxes, optionally filtered by state."""
        params = {}
        if state:
            params["state"] = state
        response = self._request("GET", "/v1/sandboxes", params=params)
        return [FlashSandbox.from_dict(s) for s in response]
    
    def kill_sandbox(self, sandbox_id: str) -> bool:
        """Kill a sandbox. Idempotent."""
        try:
            self._request("DELETE", f"/v1/sandboxes/{sandbox_id}")
            return True
        except FlashError:
            return False
    
    def extend_sandbox_timeout(self, sandbox_id: str, timeout_seconds: int) -> Dict:
        """Extend sandbox lifetime."""
        return self._request(
            "POST",
            f"/v1/sandboxes/{sandbox_id}/timeout",
            json={"timeout_seconds": timeout_seconds}
        )
    
    # -------------------------------------------------------------------------
    # File Operations
    # -------------------------------------------------------------------------
    
    def list_files(self, sandbox_id: str) -> List[str]:
        """List files in sandbox work directory."""
        response = self._request("GET", f"/v1/sandboxes/{sandbox_id}/files")
        return response.get("files", [])
    
    def read_file(self, sandbox_id: str, path: str) -> str:
        """Read a file from sandbox."""
        response = self._request(
            "GET",
            f"/v1/sandboxes/{sandbox_id}/files/content",
            params={"path": path}
        )
        return response.get("content", "")
    
    def write_file(self, sandbox_id: str, path: str, content: str) -> bool:
        """Write a file to sandbox."""
        self._request(
            "PUT",
            f"/v1/sandboxes/{sandbox_id}/files/content",
            params={"path": path},
            content=content,
        )
        return True
    
    def write_files(self, sandbox_id: str, files: Dict[str, str]) -> bool:
        """Write multiple files to sandbox."""
        for path, content in files.items():
            self.write_file(sandbox_id, path, content)
        return True
    
    def delete_file(self, sandbox_id: str, path: str) -> bool:
        """Delete a file from sandbox."""
        self._request(
            "DELETE",
            f"/v1/sandboxes/{sandbox_id}/files/content",
            params={"path": path}
        )
        return True
    
    # -------------------------------------------------------------------------
    # Execution
    # -------------------------------------------------------------------------
    
    def exec_command(
        self,
        sandbox_id: str,
        command: str,
        cwd: str = "",
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Execute a command in sandbox.
        
        Returns:
            {
                "stdout": str,
                "stderr": str,
                "exit_code": int,
                "duration_ms": int
            }
        """
        payload = {"command": command}
        if cwd:
            payload["cwd"] = cwd
        if env:
            payload["env"] = env
        if timeout:
            payload["timeout_seconds"] = timeout
        
        return self._request(
            "POST",
            f"/v1/sandboxes/{sandbox_id}/exec",
            json=payload
        )
    
    # -------------------------------------------------------------------------
    # Scoring (Assessment Layer)
    # -------------------------------------------------------------------------
    
    def create_session(
        self,
        template_id: str,
        candidate_id: str,
        timeout_seconds: int = 7200,
    ) -> FlashSandbox:
        """
        Create an assessment session.
        
        This is the Flash assessment API that combines sandbox creation
        with session tracking for scoring.
        """
        response = self._request(
            "POST",
            "/v1/sessions",
            json={
                "question_id": template_id,
                "candidate_id": candidate_id,
                "timeout_seconds": timeout_seconds,
            }
        )
        return FlashSandbox.from_dict(response)
    
    def submit_and_score(
        self,
        session_id: str,
        token: str,
    ) -> FlashScoreResult:
        """
        Submit session and get score.
        
        This runs the scoring harness and destroys the sandbox.
        """
        response = self._request(
            "POST",
            f"/v1/sessions/{session_id}/submit",
            headers={"Authorization": f"Bearer {token}"}
        )
        return FlashScoreResult.from_dict(response)
    
    def get_session_result(
        self,
        session_id: str,
        token: str,
    ) -> Optional[FlashScoreResult]:
        """Get the latest submission result for a session."""
        try:
            response = self._request(
                "GET",
                f"/v1/sessions/{session_id}/result",
                headers={"Authorization": f"Bearer {token}"}
            )
            return FlashScoreResult.from_dict(response)
        except FlashError:
            return None
    
    # -------------------------------------------------------------------------
    # Observability
    # -------------------------------------------------------------------------
    
    def get_stats(self) -> Dict:
        """Get warm pool statistics."""
        return self._request("GET", "/v1/stats")
    
    def get_usage(self) -> Dict:
        """Get usage and cost metrics."""
        return self._request("GET", "/v1/usage")


# Singleton instance
_flash_client: Optional[FlashClient] = None


def get_flash_client() -> FlashClient:
    """Get the Flash client singleton."""
    global _flash_client
    if _flash_client is None:
        _flash_client = FlashClient()
    return _flash_client


def is_flash_enabled() -> bool:
    """Check if Flash integration is enabled."""
    return FLASH_ENABLED


# Convenience functions
def check_flash_health() -> Dict[str, Any]:
    """Check Flash service health."""
    if not is_flash_enabled():
        return {"enabled": False, "healthy": False, "message": "Flash integration disabled"}
    
    client = get_flash_client()
    return {"enabled": True, **client.health_check()}


def list_flash_templates() -> List[FlashTemplate]:
    """List all Flash templates."""
    if not is_flash_enabled():
        return []
    
    client = get_flash_client()
    return client.list_templates()