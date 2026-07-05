import pytest
from unittest.mock import Mock, patch, MagicMock
import os
import sys

from app.services.flash.client import FlashClient, flash_client


class TestFlashClient:
    """Tests for FlashClient wrapper"""

    def test_singleton_pattern(self):
        """Test FlashClient is a singleton"""
        c1 = FlashClient()
        c2 = FlashClient()
        assert c1 is c2

    def test_initialization_with_env(self):
        """Test Flash client initialization with environment variables"""
        with patch.dict(os.environ, {
            "FLASH_BASE_URL": "http://test-flash:8090",
            "FLASH_API_KEY": "test-key"
        }):
            with patch("app.services.flash.client.Flash") as mock_flash:
                FlashClient._instance = None
                client = FlashClient()
                
                assert client.base_url == "http://test-flash:8090"
                assert client.api_key == "test-key"
                mock_flash.assert_called_once_with(
                    base_url="http://test-flash:8090",
                    api_key="test-key"
                )

    def test_initialization_without_api_key(self):
        """Test Flash client initialization without API key"""
        with patch.dict(os.environ, {
            "FLASH_BASE_URL": "http://localhost:8090",
            "FLASH_API_KEY": ""
        }):
            with patch("app.services.flash.client.Flash") as mock_flash:
                FlashClient._instance = None
                client = FlashClient()
                
                mock_flash.assert_called_once_with(
                    base_url="http://localhost:8090",
                    api_key=None
                )

    def test_default_base_url(self):
        """Test default base URL when not set"""
        with patch.dict(os.environ, {}, clear=True):
            with patch("app.services.flash.client.Flash"):
                FlashClient._instance = None
                client = FlashClient()
                
                assert client.base_url == "http://127.0.0.1:8090"

    def test_get_client_returns_instance(self):
        """Test get_client returns the Flash instance"""
        with patch("app.services.flash.client.Flash"):
            FlashClient._instance = None
            wrapper = FlashClient()
            
            client = wrapper.get_client()
            assert client is wrapper.client

    def test_health_check_success(self):
        """Test health check when Flash is healthy"""
        mock_httpx = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_httpx.get.return_value = mock_response
        
        with patch.dict('sys.modules', {'httpx': mock_httpx}):
            with patch("app.services.flash.client.Flash"):
                FlashClient._instance = None
                client = FlashClient()
                
                assert client.health_check() is True

    def test_health_check_failure(self):
        """Test health check when Flash is unhealthy"""
        mock_httpx = Mock()
        mock_response = Mock()
        mock_response.status_code = 503
        mock_httpx.get.return_value = mock_response
        
        with patch.dict('sys.modules', {'httpx': mock_httpx}):
            with patch("app.services.flash.client.Flash"):
                FlashClient._instance = None
                client = FlashClient()
                
                assert client.health_check() is False

    def test_health_check_connection_error(self):
        """Test health check handles connection errors"""
        mock_httpx = Mock()
        mock_httpx.get.side_effect = ConnectionError("Connection refused")
        
        with patch.dict('sys.modules', {'httpx': mock_httpx}):
            with patch("app.services.flash.client.Flash"):
                FlashClient._instance = None
                client = FlashClient()
                
                assert client.health_check() is False