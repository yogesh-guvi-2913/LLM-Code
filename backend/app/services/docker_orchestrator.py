import os
import shutil
import subprocess
import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

SESSIONS_DIR = Path(os.getenv("SESSIONS_DIR", "/sessions"))
PREVIEW_NETWORK = os.getenv("NGINX_NETWORK", "development_default")

COMPOSE_PROJECT_LABEL = "com.docker.compose.project"


def _run_compose(session_dir: Path, *args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    compose_file = str(session_dir / "docker-compose.yml")
    cmd = ["docker-compose", "-f", compose_file, "-p", session_dir.name, *args]
    return subprocess.run(cmd, cwd=str(session_dir), capture_output=True, text=True, timeout=timeout)


class DockerOrchestrator:

    def __init__(self):
        self._ensure_preview_network()

    def _ensure_preview_network(self):
        try:
            subprocess.run(
                ["docker", "network", "inspect", PREVIEW_NETWORK],
                capture_output=True, check=True, timeout=10
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            try:
                subprocess.run(
                    ["docker", "network", "create", PREVIEW_NETWORK],
                    capture_output=True, check=True, timeout=10
                )
                logger.info(f"Created preview network: {PREVIEW_NETWORK}")
            except Exception as e:
                logger.warning(f"Could not create preview network: {e}")

    async def start_session(
        self,
        test_id: str,
        user_hash: str,
        project_files: Optional[Dict[str, str]] = None,
        compose_content: str = "",
        initial_files: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        session_id = f"{test_id}_{user_hash[:12]}"
        session_dir = SESSIONS_DIR / session_id

        if session_dir.exists():
            await self.stop_session(session_id)

        if not project_files and not compose_content:
            raise FileNotFoundError(f"No project files or compose content for test: {test_id}")

        session_dir.mkdir(parents=True, exist_ok=True)

        for file_path, content in (project_files or {}).items():
            if file_path == "docker-compose.yml":
                continue
            full_path = session_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")

        if compose_content:
            (session_dir / "docker-compose.yml").write_text(compose_content, encoding="utf-8")

        session_network = f"net-{session_id}"
        db_name = f"db_{session_id}".replace("-", "_")
        redis_db = str(abs(hash(session_id)) % 15 + 1)

        env_content = (
            f"SESSION_ID={session_id}\n"
            f"SESSION_NETWORK={session_network}\n"
            f"DB_NAME={db_name}\n"
            f"REDIS_DB={redis_db}\n"
        )
        (session_dir / ".env").write_text(env_content)
        
        frontend_dir = session_dir / "frontend"
        if frontend_dir.exists():
            frontend_env = f"VITE_BASE_URL=/session/{session_id}/\nVITE_API_URL=/session/{session_id}/api\n"
            (frontend_dir / ".env").write_text(frontend_env)
            logger.info(f"Created frontend .env with base URL for session: {session_id}")

        if initial_files:
            for file_path, file_info in initial_files.items():
                content = file_info.get("content", "") if isinstance(file_info, dict) else str(file_info)
                full_path = session_dir / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content)

        result = _run_compose(session_dir, "up", "-d", "--build", timeout=180)

        if result.returncode != 0:
            logger.error(f"Docker compose up failed: {result.stderr}")
            await self.stop_session(session_id)
            raise RuntimeError(f"Failed to start containers: {result.stderr[:500]}")

        await self._wait_for_health(session_dir, timeout=90)

        containers = self._get_session_containers(session_id)
        
        for container in containers:
            if "frontend" in container or "backend" in container:
                try:
                    subprocess.run(
                        ["docker", "network", "connect", PREVIEW_NETWORK, container],
                        capture_output=True, timeout=10
                    )
                    logger.info(f"Connected {container} to {PREVIEW_NETWORK}")
                except Exception as e:
                    logger.warning(f"Could not connect {container} to {PREVIEW_NETWORK}: {e}")

        session_info = {
            "sessionId": session_id,
            "frontendUrl": f"/session/{session_id}/",
            "backendUrl": f"/session/{session_id}/api/",
            "status": "ready",
            "containers": containers,
            "dbName": db_name,
            "redisDb": redis_db,
            "sessionNetwork": session_network,
        }

        logger.info(f"Session started: {session_id} with containers: {containers}")
        return session_info

    async def _wait_for_health(self, session_dir: Path, timeout: int = 60):
        elapsed = 0
        interval = 3
        while elapsed < timeout:
            result = _run_compose(session_dir, "ps", "--format", "json", timeout=15)
            if result.returncode == 0:
                try:
                    lines = result.stdout.strip().split("\n")
                    all_healthy = True
                    has_services = False
                    for line in lines:
                        if not line.strip():
                            continue
                        data = json.loads(line)
                        state = data.get("State", "").lower()
                        health = data.get("Health", "").lower()
                        service = data.get("Service", "")
                        if service:
                            has_services = True
                        if state == "exited":
                            raise RuntimeError(f"Container exited: {service}")
                        if health and health not in ("healthy", ""):
                            all_healthy = False
                    if has_services and all_healthy:
                        await asyncio.sleep(2)
                        return
                except json.JSONDecodeError:
                    pass

            await asyncio.sleep(interval)
            elapsed += interval

        logger.warning(f"Health check timed out after {timeout}s, proceeding anyway")

    def _get_session_containers(self, session_id: str) -> List[str]:
        try:
            result = subprocess.run(
                ["docker-compose", "-p", session_id, "ps", "--format", "{{.Name}}"],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                return [name.strip() for name in result.stdout.strip().split("\n") if name.strip()]
        except Exception as e:
            logger.warning(f"Error listing containers: {e}")
        return []

    async def stop_session(self, session_id: str) -> bool:
        session_dir = SESSIONS_DIR / session_id

        if session_dir.exists() and (session_dir / "docker-compose.yml").exists():
            try:
                _run_compose(session_dir, "down", "--volumes", "--remove-orphans", timeout=60)
                logger.info(f"Containers stopped for session: {session_id}")
            except subprocess.TimeoutExpired:
                logger.warning(f"Timeout stopping containers for session: {session_id}")
            except Exception as e:
                logger.warning(f"Error stopping containers: {e}")

        session_network = f"net-{session_id}"
        try:
            subprocess.run(
                ["docker", "network", "rm", session_network],
                capture_output=True, timeout=10
            )
        except Exception:
            pass

        if session_dir.exists():
            shutil.rmtree(session_dir, ignore_errors=True)

        return True

    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        containers = self._get_session_containers(session_id)
        running = []
        for name in containers:
            try:
                result = subprocess.run(
                    ["docker", "inspect", "--format", "{{.State.Status}}", name],
                    capture_output=True, text=True, timeout=5
                )
                status = result.stdout.strip() if result.returncode == 0 else "unknown"
                if status == "running":
                    running.append(name)
            except Exception:
                pass

        return {
            "sessionId": session_id,
            "status": "ready" if running else "stopped",
            "totalContainers": len(containers),
            "runningContainers": running,
        }

    async def stream_logs(self, session_id: str, service: str = "all"):
        containers = self._get_session_containers(session_id)
        if not containers:
            yield {"service": "system", "line": "No running containers found."}
            return

        tasks = []
        for container_name in containers:
            container_service = container_name.split("-")[-1] if "-" in container_name else container_name
            if service != "all" and service not in container_name:
                continue
            tasks.append(self._stream_container_logs(container_name, container_service))

        if not tasks:
            yield {"service": "system", "line": f"No container matching '{service}' found."}
            return

        async for log in self._merge_streams(tasks):
            yield log

    async def _stream_container_logs(self, container_name: str, service_name: str):
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "logs", "-f", "--tail", "50", container_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            assert proc.stdout is not None
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                yield {"service": service_name, "line": line.decode("utf-8", errors="replace").rstrip()}
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error streaming logs from {container_name}: {e}")

    async def _merge_streams(self, tasks: list):
        queue: asyncio.Queue = asyncio.Queue()

        async def producer(coro, task_obj):
            try:
                async for item in coro:
                    await queue.put(item)
            except Exception as e:
                logger.error(f"Log stream error: {e}")

        wrapped = []
        for coro in tasks:
            task = asyncio.ensure_future(producer(coro, asyncio.current_task()))
            wrapped.append(task)

        try:
            while any(not t.done() for t in wrapped) or not queue.empty():
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield item
                except asyncio.TimeoutError:
                    continue
        finally:
            for t in wrapped:
                t.cancel()

    def get_container_files(self, session_id: str, sub_path: str = "") -> Dict[str, str]:
        session_dir = SESSIONS_DIR / session_id
        if not session_dir.exists():
            return {}

        base = session_dir / sub_path if sub_path else session_dir
        files = {}
        if base.exists() and base.is_dir():
            for filepath in base.rglob("*"):
                if filepath.is_file() and ".git" not in filepath.parts:
                    rel = filepath.relative_to(session_dir)
                    try:
                        content = filepath.read_text(encoding="utf-8")
                        files[str(rel)] = content
                    except (UnicodeDecodeError, PermissionError):
                        pass
        return files
