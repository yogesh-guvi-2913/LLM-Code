from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


class PostgreSQL:
    """Legacy PostgreSQL sync wrapper (stub for compatibility)"""

    def __init__(self):
        self.connection = None

    def connect(self):
        return self.connection

    def close(self):
        pass

    def execute(self, query, params=None):
        pass

    def fetchone(self, query, params=None):
        return None

    def fetchall(self, query, params=None):
        return []