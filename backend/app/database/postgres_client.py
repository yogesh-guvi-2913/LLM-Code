"""PostgreSQL database client for LLM-Code backend"""

import asyncpg
import logging
import os
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class PostgresClient:
    """Async PostgreSQL client for LLM-Code"""

    def __init__(self):
        self.pool = None
        self.database_url = os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:postgres@127.0.0.1:5432/llmcode"
        )

    async def connect(self):
        """Initialize connection pool"""
        if not self.pool:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=5,
                max_size=20,
                command_timeout=60
            )
            logger.info("PostgreSQL connection pool created")

    async def close(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("PostgreSQL connection pool closed")

    async def execute(self, query: str, *args) -> str:
        """Execute query and return status"""
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args) -> List[Dict[str, Any]]:
        """Fetch multiple rows"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]

    async def fetchone(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Fetch single row"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    async def insert(self, query: str, *args) -> int:
        """Insert and return ID"""
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)

    async def update(self, query: str, *args) -> int:
        """Update and return affected rows"""
        async with self.pool.acquire() as conn:
            result = await conn.execute(query, *args)
            return int(result.split()[-1])

    async def delete(self, query: str, *args) -> int:
        """Delete and return affected rows"""
        async with self.pool.acquire() as conn:
            result = await conn.execute(query, *args)
            return int(result.split()[-1])

    async def transaction(self):
        """Start transaction context"""
        return self.pool.acquire()


postgres_client = PostgresClient()