"""Flash client wrapper — lazy initialization, graceful degradation."""

import os
import sys
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_candidate_paths = [
    os.path.join(os.path.dirname(__file__), "../../../../sandbox/sdk/python"),  # local dev
    "/app/flash_sdk",           # Docker (COPY)
    "/app/flash_sdk/flash/..",  # Docker (volume mount fallback)
]
for _p in _candidate_paths:
    _p = os.path.normpath(_p)
    if os.path.isdir(os.path.join(_p, "flash")) and _p not in sys.path:
        sys.path.insert(0, _p)
        break

try:
    from flash import Flash, APIError
    _SDK_AVAILABLE = True
except ImportError:
    Flash = None
    APIError = Exception
    _SDK_AVAILABLE = False
    logger.warning("Flash SDK not found — flash routes will return 503 until SDK is installed")


class FlashClient:
    """Singleton Flash client wrapper with lazy initialization."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.base_url = os.getenv("FLASH_BASE_URL", "http://127.0.0.1:8090")
        self.api_key = os.getenv("FLASH_API_KEY", "")
        self._client = None
        self._initialized = True

        if _SDK_AVAILABLE:
            logger.info(f"Flash SDK available, base URL: {self.base_url}")
        else:
            logger.warning("Flash SDK not installed — health check will report unavailable")

    def get_client(self):
        """Get Flash client instance (created lazily)."""
        if not _SDK_AVAILABLE:
            raise RuntimeError("Flash SDK is not installed")
        if self._client is None:
            self._client = Flash(
                base_url=self.base_url,
                api_key=self.api_key if self.api_key else None
            )
            logger.info(f"Flash client initialized with base URL: {self.base_url}")
        return self._client

    def health_check(self) -> bool:
        """Check if Flash orchestrator is healthy"""
        try:
            import httpx
            response = httpx.get(f"{self.base_url}/health", timeout=5.0)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Flash health check failed: {e}")
            return False


flash_client = FlashClient()
