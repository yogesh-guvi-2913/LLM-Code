"""Sandbox provider configuration with feature flags"""

import os
import logging
from typing import Literal

SandboxProvider = Literal["legacy", "flash"]

logger = logging.getLogger(__name__)


class SandboxProviderConfig:
    """Feature flag-based sandbox provider selection"""

    def __init__(self):
        self.rollout_percentage = int(os.getenv("FLASH_ROLLOUT_PERCENTAGE", "0"))
        self.forced_provider = os.getenv("SANDBOX_PROVIDER", None)
        self.rollout_whitelist = self._parse_whitelist()
        self.rollout_blacklist = self._parse_blacklist()

    def _parse_whitelist(self) -> set:
        """Parse whitelist from env"""
        whitelist = os.getenv("FLASH_ROLLOUT_WHITELIST", "")
        if not whitelist:
            return set()
        return set(whitelist.split(","))

    def _parse_blacklist(self) -> set:
        """Parse blacklist from env"""
        blacklist = os.getenv("FLASH_ROLLOUT_BLACKLIST", "")
        if not blacklist:
            return set()
        return set(blacklist.split(","))

    def get_provider(self, user_hash: str) -> SandboxProvider:
        """Determine sandbox provider for user
        
        Priority:
        1. Forced provider (SANDBOX_PROVIDER env)
        2. Whitelist (always use Flash)
        3. Blacklist (always use legacy)
        4. Rollout percentage
        5. Default to legacy
        """
        
        if self.forced_provider:
            logger.debug(f"Forced provider: {self.forced_provider}")
            return self.forced_provider

        if user_hash in self.rollout_whitelist:
            logger.debug(f"User {user_hash} in whitelist → Flash")
            return "flash"

        if user_hash in self.rollout_blacklist:
            logger.debug(f"User {user_hash} in blacklist → Legacy")
            return "legacy"

        user_rollout_bucket = hash(user_hash) % 100

        if user_rollout_bucket < self.rollout_percentage:
            logger.debug(f"User {user_hash} in rollout bucket → Flash")
            return "flash"

        logger.debug(f"User {user_hash} using default → Legacy")
        return "legacy"

    def update_rollout_percentage(self, percentage: int):
        """Update rollout percentage (runtime)"""
        if percentage < 0 or percentage > 100:
            raise ValueError("Rollout percentage must be between 0 and 100")
        self.rollout_percentage = percentage
        logger.info(f"Rollout percentage updated to {percentage}%")

    def add_to_whitelist(self, user_hash: str):
        """Add user to Flash whitelist"""
        self.rollout_whitelist.add(user_hash)
        logger.info(f"Added {user_hash} to whitelist")

    def add_to_blacklist(self, user_hash: str):
        """Add user to legacy blacklist"""
        self.rollout_blacklist.add(user_hash)
        logger.info(f"Added {user_hash} to blacklist")

    def remove_from_whitelist(self, user_hash: str):
        """Remove user from whitelist"""
        self.rollout_whitelist.discard(user_hash)
        logger.info(f"Removed {user_hash} from whitelist")

    def remove_from_blacklist(self, user_hash: str):
        """Remove user from blacklist"""
        self.rollout_blacklist.discard(user_hash)
        logger.info(f"Removed {user_hash} from blacklist")

    def get_stats(self) -> dict:
        """Get rollout statistics"""
        return {
            "rollout_percentage": self.rollout_percentage,
            "whitelist_count": len(self.rollout_whitelist),
            "blacklist_count": len(self.rollout_blacklist),
            "forced_provider": self.forced_provider,
        }


sandbox_config = SandboxProviderConfig()