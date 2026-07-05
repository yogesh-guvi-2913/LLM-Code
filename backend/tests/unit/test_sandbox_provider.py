import pytest
import os
from unittest.mock import patch, MagicMock

from app.config.sandbox_provider import SandboxProviderConfig, sandbox_config


class TestSandboxProviderConfig:
    """Tests for SandboxProviderConfig feature flag system"""

    def test_default_values(self):
        """Test default configuration values"""
        with patch.dict(os.environ, {}, clear=True):
            config = SandboxProviderConfig()
            assert config.rollout_percentage == 0
            assert config.forced_provider is None
            assert config.rollout_whitelist == set()
            assert config.rollout_blacklist == set()

    def test_forced_provider_flash(self, mock_env_flash_enabled):
        """Test forced provider returns 'flash' when SANDBOX_PROVIDER=flash"""
        config = SandboxProviderConfig()
        assert config.get_provider("any-user") == "flash"

    def test_forced_provider_legacy(self, mock_env_legacy):
        """Test forced provider returns 'legacy' when SANDBOX_PROVIDER=legacy"""
        config = SandboxProviderConfig()
        assert config.get_provider("any-user") == "legacy"

    def test_whitelist_user_gets_flash(self, mock_env_hybrid):
        """Test whitelisted user always gets Flash"""
        config = SandboxProviderConfig()
        config.add_to_whitelist("whitelisted-user-abc")
        
        assert config.get_provider("whitelisted-user-abc") == "flash"

    def test_blacklist_user_gets_legacy(self, mock_env_hybrid):
        """Test blacklisted user always gets legacy"""
        config = SandboxProviderConfig()
        config.add_to_blacklist("blacklisted-user-xyz")
        
        assert config.get_provider("blacklisted-user-xyz") == "legacy"

    def test_whitelist_overrides_blacklist(self, mock_env_hybrid):
        """Test whitelist takes priority over blacklist"""
        config = SandboxProviderConfig()
        config.add_to_blacklist("test-user")
        config.add_to_whitelist("test-user")
        
        assert config.get_provider("test-user") == "flash"

    def test_forced_provider_overrides_all(self, mock_env_flash_enabled):
        """Test forced provider overrides whitelist/blacklist"""
        config = SandboxProviderConfig()
        config.add_to_blacklist("test-user")
        
        assert config.get_provider("test-user") == "flash"

    def test_rollout_percentage(self):
        """Test percentage-based rollout"""
        with patch.dict(os.environ, {"FLASH_ROLLOUT_PERCENTAGE": "50"}):
            config = SandboxProviderConfig()
            
            assert config.rollout_percentage == 50
            
            user_hash_low = "user-in-low-bucket"
            user_hash_high = "user-in-high-bucket"
            
            bucket_low = hash(user_hash_low) % 100
            bucket_high = hash(user_hash_high) % 100
            
            assert (bucket_low < 50) == (config.get_provider(user_hash_low) == "flash")
            assert (bucket_high < 50) == (config.get_provider(user_hash_high) == "flash")

    def test_rollout_consistency(self):
        """Test that same user always gets same provider for same config"""
        with patch.dict(os.environ, {"FLASH_ROLLOUT_PERCENTAGE": "25"}):
            config = SandboxProviderConfig()
            
            user_hash = "consistent-user-hash"
            
            provider1 = config.get_provider(user_hash)
            provider2 = config.get_provider(user_hash)
            provider3 = config.get_provider(user_hash)
            
            assert provider1 == provider2 == provider3

    def test_update_rollout_percentage(self):
        """Test runtime rollout percentage update"""
        config = SandboxProviderConfig()
        
        assert config.rollout_percentage == 0
        
        config.update_rollout_percentage(50)
        assert config.rollout_percentage == 50
        
        config.update_rollout_percentage(100)
        assert config.rollout_percentage == 100
        
        with pytest.raises(ValueError):
            config.update_rollout_percentage(-1)
        
        with pytest.raises(ValueError):
            config.update_rollout_percentage(101)

    def test_add_remove_whitelist(self):
        """Test whitelist management"""
        config = SandboxProviderConfig()
        
        assert "new-user" not in config.rollout_whitelist
        
        config.add_to_whitelist("new-user")
        assert "new-user" in config.rollout_whitelist
        
        config.remove_from_whitelist("new-user")
        assert "new-user" not in config.rollout_whitelist

    def test_add_remove_blacklist(self):
        """Test blacklist management"""
        config = SandboxProviderConfig()
        
        assert "new-user" not in config.rollout_blacklist
        
        config.add_to_blacklist("new-user")
        assert "new-user" in config.rollout_blacklist
        
        config.remove_from_blacklist("new-user")
        assert "new-user" not in config.rollout_blacklist

    def test_get_stats(self):
        """Test statistics retrieval"""
        with patch.dict(os.environ, {"FLASH_ROLLOUT_PERCENTAGE": "75"}):
            config = SandboxProviderConfig()
            config.add_to_whitelist("user1")
            config.add_to_whitelist("user2")
            config.add_to_blacklist("user3")
            
            stats = config.get_stats()
            
            assert stats["rollout_percentage"] == 75
            assert stats["whitelist_count"] == 2
            assert stats["blacklist_count"] == 1
            assert stats["forced_provider"] is None

    def test_parse_whitelist_from_env(self):
        """Test parsing whitelist from environment"""
        with patch.dict(os.environ, {"FLASH_ROLLOUT_WHITELIST": "user1,user2,user3"}):
            config = SandboxProviderConfig()
            
            assert "user1" in config.rollout_whitelist
            assert "user2" in config.rollout_whitelist
            assert "user3" in config.rollout_whitelist

    def test_parse_blacklist_from_env(self):
        """Test parsing blacklist from environment"""
        with patch.dict(os.environ, {"FLASH_ROLLOUT_BLACKLIST": "bad-user1,bad-user2"}):
            config = SandboxProviderConfig()
            
            assert "bad-user1" in config.rollout_blacklist
            assert "bad-user2" in config.rollout_blacklist

    def test_empty_whitelist_blacklist_parsing(self):
        """Test empty whitelist/blacklist env vars"""
        with patch.dict(os.environ, {"FLASH_ROLLOUT_WHITELIST": "", "FLASH_ROLLOUT_BLACKLIST": ""}):
            config = SandboxProviderConfig()
            
            assert config.rollout_whitelist == set()
            assert config.rollout_blacklist == set()

    def test_singleton_instance(self):
        """Test that sandbox_config is a singleton"""
        from app.config.sandbox_provider import sandbox_config as config1
        from app.config.sandbox_provider import sandbox_config as config2
        
        assert config1 is config2


class TestSandboxProviderIntegration:
    """Integration tests for sandbox provider selection"""

    def test_full_rollout_flow(self):
        """Test complete rollout scenario from 0% to 100%"""
        with patch.dict(os.environ, {}, clear=True):
            config = SandboxProviderConfig()
            
            assert config.get_provider("user-a") == "legacy"
            
            config.update_rollout_percentage(50)
            
            users = [f"user-{i}" for i in range(100)]
            flash_count = sum(1 for u in users if config.get_provider(u) == "flash")
            
            assert 40 <= flash_count <= 60
            
            config.update_rollout_percentage(100)
            assert all(config.get_provider(u) == "flash" for u in users)

    def test_gradual_rollout_with_exceptions(self):
        """Test gradual rollout with whitelist/blacklist exceptions"""
        with patch.dict(os.environ, {"FLASH_ROLLOUT_WHITELIST": "vip-user", "FLASH_ROLLOUT_BLACKLIST": "problem-user"}):
            config = SandboxProviderConfig()
            
            assert config.get_provider("vip-user") == "flash"
            
            assert config.get_provider("problem-user") == "legacy"
            
            normal_users = [f"normal-user-{i}" for i in range(10)]
            for user in normal_users:
                provider = config.get_provider(user)
                assert provider in ["flash", "legacy"]