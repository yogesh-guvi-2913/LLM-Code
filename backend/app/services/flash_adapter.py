"""
Flash Sandbox Adapter for Session Management

Provides a unified interface for managing Flash sandbox sessions,
compatible with the existing session system but backed by Flash's
warm pool and scoring infrastructure.

This adapter bridges:
- LLM-Code session system <-> Flash sandbox API
- File operations (read/write) via Flash Files API
- Terminal access via Flash WebSocket proxy
- Scoring via Flash assessment layer
"""

import json
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.services.flash_service import (
    FlashClient,
    FlashSandbox,
    FlashScoreResult,
    FlashError,
    is_flash_enabled,
)
from app.redis.sync.rediscache import RedisCache
from app.mongodb.sync.mongo import MongoDB

logger = logging.getLogger(__name__)

FLASH_SESSION_PREFIX = "flash_session:"
FLASH_SESSION_EXPIRY = 7200


class FlashSessionInfo:
    """Session info for Flash sandbox."""
    
    def __init__(self, sandbox: FlashSandbox, test_id: str, user_hash: str, template_id: str):
        self.sandbox_id = sandbox.id
        self.test_id = test_id
        self.user_hash = user_hash
        self.template_id = template_id
        self.token = sandbox.token
        self.app_url = sandbox.app_url
        self.preview_url = sandbox.preview_url
        self.terminal_url = sandbox.terminal_url
        self.terminal_page = sandbox.terminal_page
        self.state = sandbox.state
        self.created_at = sandbox.created_at
        self.expires_at = sandbox.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sessionId": self.sandbox_id,
            "testId": self.test_id,
            "templateId": self.template_id,
            "token": self.token,
            "frontendUrl": self.app_url,
            "backendUrl": self.app_url,
            "previewUrl": self.preview_url,
            "terminalUrl": self.terminal_url,
            "terminalPage": self.terminal_page,
            "status": "ready",
            "sessionType": "flash",
            "expiresAt": self.expires_at.isoformat() if self.expires_at else None,
        }


class FlashSandboxAdapter:
    """
    Adapter for managing Flash sandbox sessions.
    
    Provides a unified interface similar to DockerOrchestrator but
    backed by Flash's warm pool management.
    """
    
    def __init__(self):
        self._client: Optional[FlashClient] = None
    
    def _get_client(self) -> FlashClient:
        if self._client is None:
            self._client = FlashClient()
        return self._client
    
    async def start_session(
        self,
        test_id: str,
        user_hash: str,
        template_id: str,
        timeout_seconds: int = 7200,
        initial_files: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Start a Flash sandbox session.
        
        Args:
            test_id: Test identifier
            user_hash: User hash for tracking
            template_id: Flash template ID (e.g., 'q1', 'q2', 'q3')
            timeout_seconds: Session lifetime
            initial_files: Files to write to sandbox
        
        Returns:
            Session info dict compatible with DockerOrchestrator format
        """
        if not is_flash_enabled():
            raise RuntimeError("Flash integration is disabled")
        
        client = self._get_client()
        
        try:
            sandbox = client.create_sandbox(
                template_id=template_id,
                timeout_seconds=timeout_seconds,
                metadata={
                    "test_id": test_id,
                    "user_hash": user_hash,
                    "created_via": "llm-code-adapter",
                }
            )
            
            logger.info(f"Created Flash sandbox: {sandbox.id} for test {test_id}")
            
            if initial_files:
                await self._write_initial_files(client, sandbox.id, initial_files)
            
            session_info = FlashSessionInfo(sandbox, test_id, user_hash, template_id)
            
            self._store_session_redis(session_info, timeout_seconds)
            
            self._store_session_mongodb(session_info)
            
            return session_info.to_dict()
            
        except FlashError as e:
            logger.error(f"Failed to create Flash sandbox: {e}")
            raise RuntimeError(f"Failed to create Flash sandbox: {e.message}")
    
    async def _write_initial_files(self, client: FlashClient, sandbox_id: str, files: Dict[str, str]):
        """Write initial files to sandbox."""
        for path, content in files.items():
            try:
                client.write_file(sandbox_id, path, content)
                logger.debug(f"Wrote file {path} to sandbox {sandbox_id}")
            except FlashError as e:
                logger.warning(f"Failed to write file {path}: {e}")
    
    def _store_session_redis(self, session_info: FlashSessionInfo, expiry: int):
        """Store session info in Redis for quick lookup."""
        redis = RedisCache()
        key = f"{FLASH_SESSION_PREFIX}{session_info.sandbox_id}"
        redis.setex(
            key,
            expiry,
            json.dumps({
                "testId": session_info.test_id,
                "userHash": session_info.user_hash,
                "templateId": session_info.template_id,
                "token": session_info.token,
                "frontendUrl": session_info.app_url,
                "backendUrl": session_info.app_url,
                "previewUrl": session_info.preview_url,
                "terminalUrl": session_info.terminal_url,
                "sessionType": "flash",
            })
        )
        logger.debug(f"Stored Flash session in Redis: {key}")
    
    def _store_session_mongodb(self, session_info: FlashSessionInfo):
        """Store session in MongoDB for persistence."""
        mongo = MongoDB()
        mongo.selectCollection("flash_sessions")
        
        session_doc = {
            "sandboxId": session_info.sandbox_id,
            "testId": session_info.test_id,
            "userHash": session_info.user_hash,
            "templateId": session_info.template_id,
            "token": session_info.token,
            "appUrl": session_info.app_url,
            "previewUrl": session_info.preview_url,
            "terminalUrl": session_info.terminal_url,
            "state": session_info.state,
            "createdAt": datetime.utcnow(),
            "expiresAt": session_info.expires_at,
        }
        
        existing = mongo.find({"sandboxId": session_info.sandbox_id}, limit=1)
        if existing:
            mongo.updateOne(
                {"sandboxId": session_info.sandbox_id},
                {"$set": session_doc}
            )
        else:
            mongo.insertOne(session_doc)
    
    async def stop_session(self, session_id: str) -> bool:
        """Stop a Flash sandbox session."""
        client = self._get_client()
        
        try:
            client.kill_sandbox(session_id)
            logger.info(f"Killed Flash sandbox: {session_id}")
        except FlashError as e:
            logger.warning(f"Error killing sandbox {session_id}: {e}")
        
        redis = RedisCache()
        redis.delete(f"{FLASH_SESSION_PREFIX}{session_id}")
        
        mongo = MongoDB()
        mongo.selectCollection("flash_sessions")
        mongo.updateOne(
            {"sandboxId": session_id},
            {"$set": {"state": "destroyed", "destroyedAt": datetime.utcnow()}}
        )
        
        return True
    
    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Get Flash sandbox status."""
        client = self._get_client()
        
        try:
            sandbox = client.get_sandbox(session_id)
            return {
                "sessionId": session_id,
                "status": "ready" if sandbox.state == "running" else sandbox.state,
                "sessionType": "flash",
                "expiresAt": sandbox.expires_at.isoformat() if sandbox.expires_at else None,
            }
        except FlashError as e:
            return {
                "sessionId": session_id,
                "status": "not_found",
                "error": e.message,
            }
    
    async def sync_files(self, session_id: str, changes: List[Dict[str, str]]) -> bool:
        """
        Sync files to Flash sandbox.
        
        Args:
            session_id: Flash sandbox ID
            changes: List of {path, content, action}
        """
        client = self._get_client()
        
        for change in changes:
            path = change.get("path", "")
            content = change.get("content", "")
            action = change.get("action", "update")
            
            if not path:
                continue
            
            try:
                if action == "update":
                    client.write_file(session_id, path, content)
                elif action == "delete":
                    client.delete_file(session_id, path)
                logger.debug(f"Synced file {path} to sandbox {session_id}")
            except FlashError as e:
                logger.warning(f"Failed to sync file {path}: {e}")
        
        return True
    
    def list_files(self, session_id: str) -> List[str]:
        """List files in Flash sandbox."""
        client = self._get_client()
        try:
            return client.list_files(session_id)
        except FlashError as e:
            logger.error(f"Failed to list files: {e}")
            return []
    
    def read_file(self, session_id: str, path: str) -> str:
        """Read a file from Flash sandbox."""
        client = self._get_client()
        try:
            return client.read_file(session_id, path)
        except FlashError as e:
            logger.error(f"Failed to read file {path}: {e}")
            return ""
    
    async def execute_command(
        self,
        session_id: str,
        command: str,
        cwd: str = "",
        env: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Execute a command in Flash sandbox."""
        client = self._get_client()
        
        try:
            result = client.exec_command(session_id, command, cwd, env)
            return {
                "success": result.get("exit_code", 1) == 0,
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
                "exitCode": result.get("exit_code", 1),
            }
        except FlashError as e:
            return {
                "success": False,
                "error": e.message,
            }
    
    async def submit_and_score(self, session_id: str) -> Optional[FlashScoreResult]:
        """
        Submit sandbox and get score.
        
        This runs the Flash scoring harness and destroys the sandbox.
        """
        client = self._get_client()
        
        redis = RedisCache()
        key = f"{FLASH_SESSION_PREFIX}{session_id}"
        session_data = redis.getAllData(key)
        
        if not session_data or "token" not in session_data:
            logger.error(f"No token found for session {session_id}")
            return None
        
        token = session_data["token"]
        
        try:
            score_result = client.submit_and_score(session_id, token)
            logger.info(f"Scored sandbox {session_id}: {score_result.score}/{score_result.max_score}")
            
            mongo = MongoDB()
            mongo.selectCollection("flash_submissions")
            mongo.insertOne({
                "sandboxId": session_id,
                "testId": session_data.get("testId"),
                "userHash": session_data.get("userHash"),
                "score": score_result.score,
                "maxScore": score_result.max_score,
                "testResults": score_result.test_results,
                "submittedAt": datetime.utcnow(),
            })
            
            redis.delete(key)
            
            return score_result
            
        except FlashError as e:
            logger.error(f"Failed to score sandbox {session_id}: {e}")
            return None
    
    def get_terminal_url(self, session_id: str) -> Optional[str]:
        """Get WebSocket URL for terminal access."""
        redis = RedisCache()
        key = f"{FLASH_SESSION_PREFIX}{session_id}"
        session_data = redis.getAllData(key)
        
        if session_data and "terminalUrl" in session_data:
            return session_data["terminalUrl"]
        
        client = self._get_client()
        try:
            sandbox = client.get_sandbox(session_id)
            return sandbox.terminal_url
        except FlashError:
            return None
    
    def get_preview_url(self, session_id: str) -> Optional[str]:
        """Get preview URL for frontend templates."""
        redis = RedisCache()
        key = f"{FLASH_SESSION_PREFIX}{session_id}"
        session_data = redis.getAllData(key)
        
        if session_data and "previewUrl" in session_data:
            return session_data["previewUrl"]
        
        client = self._get_client()
        try:
            sandbox = client.get_sandbox(session_id)
            return sandbox.preview_url
        except FlashError:
            return None


_adapter_instance: Optional[FlashSandboxAdapter] = None


def get_flash_adapter() -> FlashSandboxAdapter:
    """Get the Flash sandbox adapter singleton."""
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = FlashSandboxAdapter()
    return _adapter_instance


def is_flash_session(session_id: str) -> bool:
    """Check if a session is a Flash sandbox."""
    redis = RedisCache()
    key = f"{FLASH_SESSION_PREFIX}{session_id}"
    data = redis.getAllData(key)
    return bool(data)


def get_session_type(session_id: str) -> str:
    """Get the type of session ('flash' or 'docker')."""
    if is_flash_session(session_id):
        return "flash"
    return "docker"