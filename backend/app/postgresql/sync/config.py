from __future__ import annotations
import logging
import os

logger = logging.getLogger(__name__)

_pool = None


def get_postgres_connection():
    """Get a PostgreSQL connection (stub for compatibility)"""
    global _pool
    if _pool is None:
        try:
            import psycopg2
            database_url = os.getenv(
                "DATABASE_URL",
                "postgresql://postgres:postgres@127.0.0.1:5432/llmcode"
            )
            _pool = psycopg2.connect(database_url)
        except Exception as e:
            logger.warning(f"PostgreSQL not available: {e}")
            return None
    return _pool


def release_postgres_connection(connection):
    """Release a PostgreSQL connection back to pool (stub)"""
    pass
