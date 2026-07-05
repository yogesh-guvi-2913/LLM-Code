"""Session repository for PostgreSQL"""

from typing import Optional, Dict, Any
from app.database.postgres_client import postgres_client
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SessionRepository:
    """Session data repository"""

    async def create(self, session_data: Dict[str, Any]) -> int:
        """Create new session"""
        query = """
        INSERT INTO sessions (
            user_hash, test_id, flash_session_id, status, expires_at,
            created_at, updated_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id
        """

        return await postgres_client.insert(
            query,
            session_data.get("userHash"),
            session_data.get("testId"),
            session_data.get("flashSessionId"),
            session_data.get("status", "active"),
            session_data.get("expiresAt"),
            datetime.utcnow(),
            datetime.utcnow()
        )

    async def find_by_id(self, session_id: int) -> Optional[Dict[str, Any]]:
        """Find session by ID"""
        query = "SELECT * FROM sessions WHERE id = $1"
        return await postgres_client.fetchone(query, session_id)

    async def find_by_user_and_test(
        self,
        user_hash: str,
        test_id: str
    ) -> Optional[Dict[str, Any]]:
        """Find active session by user and test"""
        query = """
        SELECT * FROM sessions
        WHERE user_hash = $1 AND test_id = $2 AND status = 'active'
        ORDER BY created_at DESC LIMIT 1
        """
        return await postgres_client.fetchone(query, user_hash, test_id)

    async def find_by_flash_session(
        self,
        flash_session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Find session by Flash sandbox ID"""
        query = "SELECT * FROM sessions WHERE flash_session_id = $1"
        return await postgres_client.fetchone(query, flash_session_id)

    async def update_status(
        self,
        session_id: int,
        status: str
    ) -> int:
        """Update session status"""
        query = """
        UPDATE sessions
        SET status = $2, updated_at = CURRENT_TIMESTAMP
        WHERE id = $1
        """
        return await postgres_client.update(query, session_id, status)

    async def update_flash_session(
        self,
        session_id: int,
        flash_session_id: str
    ) -> int:
        """Update Flash session ID"""
        query = """
        UPDATE sessions
        SET flash_session_id = $2, updated_at = CURRENT_TIMESTAMP
        WHERE id = $1
        """
        return await postgres_client.update(query, session_id, flash_session_id)

    async def deactivate_expired(self) -> int:
        """Deactivate expired sessions"""
        query = """
        UPDATE sessions
        SET status = 'expired', updated_at = CURRENT_TIMESTAMP
        WHERE status = 'active' AND expires_at < CURRENT_TIMESTAMP
        """
        return await postgres_client.update(query)

    async def cleanup_old_sessions(self, days: int = 30) -> int:
        """Delete old sessions"""
        query = """
        DELETE FROM sessions
        WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '%s days'
        """
        return await postgres_client.delete(query % days)


session_repository = SessionRepository()