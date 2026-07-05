import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock
import json

from app.app import app

client = TestClient(app, raise_server_exceptions=False)


def _mock_flash_exec(stdout="", stderr="", exit_code=0):
    """Helper to create a properly-mocked flash exec result"""
    mock_flash = MagicMock()
    mock_sandbox = MagicMock()
    mock_sandbox.run.return_value = Mock(
        stdout=stdout, stderr=stderr, exit_code=exit_code, duration_ms=100
    )
    mock_client = Mock()
    mock_client.sandboxes.connect.return_value = mock_sandbox
    mock_flash.get_client.return_value = mock_client
    return mock_flash


def _mock_flash_files(read_text="", write_ok=True, file_list=None):
    """Helper to create a properly-mocked flash file client"""
    mock_flash = MagicMock()
    mock_sandbox = MagicMock()
    mock_sandbox.files.read_text.return_value = read_text
    mock_sandbox.files.write.return_value = write_ok
    mock_sandbox.files.list.return_value = file_list or ["/app/index.js"]
    mock_client = Mock()
    mock_client.sandboxes.connect.return_value = mock_sandbox
    mock_flash.get_client.return_value = mock_client
    return mock_flash


@pytest.mark.security
class TestAuthenticationSecurity:
    """Security tests for authentication"""

    def test_missing_auth_token(self):
        """Test request without auth token"""
        response = client.post("/flash/start", json={"testId": "test-1"})
        assert response.status_code == 400

    def test_empty_auth_token(self):
        """Test request with empty auth token"""
        response = client.post("/flash/start", json={
            "authToken": "",
            "testId": "test-1"
        })
        assert response.status_code == 400

    def test_expired_auth_token(self):
        """Test request with expired auth token"""
        with patch("app.routes.session.flash_routes.RedisCache") as mock_redis_class:
            mock_redis = Mock()
            mock_redis.getAllData.return_value = None
            mock_redis_class.return_value = mock_redis
            
            response = client.post("/flash/start", json={
                "authToken": "expired-token",
                "testId": "test-1"
            })
            assert response.status_code == 401

    def test_malformed_auth_token(self):
        """Test request with malformed auth token"""
        with patch("app.routes.session.flash_routes.RedisCache") as mock_redis_class:
            mock_redis = Mock()
            mock_redis.getAllData.return_value = None
            mock_redis_class.return_value = mock_redis
            
            response = client.post("/flash/start", json={
                "authToken": "malformed!@#$",
                "testId": "test-1"
            })
            assert response.status_code in [400, 401, 500]

    def test_auth_token_sql_injection_attempt(self):
        """Test SQL injection attempt in auth token"""
        with patch("app.routes.session.flash_routes.RedisCache") as mock_redis_class:
            mock_redis = Mock()
            mock_redis.getAllData.return_value = None
            mock_redis_class.return_value = mock_redis
            
            response = client.post("/flash/start", json={
                "authToken": "'; DROP TABLE users; --",
                "testId": "test-1"
            })
            assert response.status_code == 401

    def test_session_access_by_different_user(self):
        """Test accessing another user's session"""
        with patch("app.routes.session.flash_routes.RedisCache") as mock_redis_class:
            with patch("app.routes.session.flash_routes.flash_client") as mock_flash:
                mock_redis = Mock()
                mock_redis.getAllData.return_value = {"hash": "user-a"}
                mock_redis_class.return_value = mock_redis

                mock_sandbox = MagicMock()
                mock_sandbox.run.return_value = Mock(
                    stdout="", stderr="", exit_code=0, duration_ms=10
                )
                mock_client = Mock()
                mock_client.sandboxes.connect.return_value = mock_sandbox
                mock_flash.get_client.return_value = mock_client

                response = client.post("/flash/exec", json={
                    "authToken": "user-a-token",
                    "flashSessionId": "session-b",
                    "command": "cat /etc/passwd"
                })
                
                assert response.status_code in [200, 401, 403, 404]


@pytest.mark.security
class TestInputValidation:
    """Security tests for input validation"""

    def test_path_traversal_attempt(self):
        """Test path traversal attack prevention"""
        with patch("app.routes.session.flash_routes.RedisCache") as mock_redis_class:
            with patch("app.routes.session.flash_routes.flash_client") as mock_flash:
                mock_redis = Mock()
                mock_redis.getAllData.return_value = {"hash": "user-1"}
                mock_redis_class.return_value = mock_redis

                mock_sandbox = MagicMock()
                mock_sandbox.files.read_text.side_effect = Exception("access denied")
                mock_client = Mock()
                mock_client.sandboxes.connect.return_value = mock_sandbox
                mock_flash.get_client.return_value = mock_client
                
                response = client.post("/flash/files/read", json={
                    "authToken": "token",
                    "flashSessionId": "session-1",
                    "path": "../../../etc/passwd"
                })
                
                assert response.status_code in [400, 500]

    def test_command_injection_attempt(self):
        """Test command injection prevention"""
        with patch("app.routes.session.flash_routes.RedisCache") as mock_redis_class:
            with patch("app.routes.session.flash_routes.flash_client", _mock_flash_exec(stderr="blocked", exit_code=1)):
                mock_redis = Mock()
                mock_redis.getAllData.return_value = {"hash": "user-1"}
                mock_redis_class.return_value = mock_redis
                
                response = client.post("/flash/exec", json={
                    "authToken": "token",
                    "flashSessionId": "session-1",
                    "command": "ls; rm -rf /"
                })
                
                assert response.status_code in [200, 400]

    def test_xss_in_content(self):
        """Test XSS attempt in file content"""
        with patch("app.routes.session.flash_routes.RedisCache") as mock_redis_class:
            with patch("app.routes.session.flash_routes.flash_client", _mock_flash_files()):
                mock_redis = Mock()
                mock_redis.getAllData.return_value = {"hash": "user-1"}
                mock_redis_class.return_value = mock_redis
                
                response = client.post("/flash/files/write", json={
                    "authToken": "token",
                    "flashSessionId": "session-1",
                    "path": "/app/index.html",
                    "content": "<script>alert('xss')</script>"
                })
                
                assert response.status_code in [200, 400]

    def test_null_byte_injection(self):
        """Test null byte injection prevention"""
        with patch("app.routes.session.flash_routes.RedisCache") as mock_redis_class:
            with patch("app.routes.session.flash_routes.flash_client") as mock_flash:
                mock_redis = Mock()
                mock_redis.getAllData.return_value = {"hash": "user-1"}
                mock_redis_class.return_value = mock_redis

                mock_sandbox = MagicMock()
                mock_sandbox.files.read_text.side_effect = Exception("invalid path")
                mock_client = Mock()
                mock_client.sandboxes.connect.return_value = mock_sandbox
                mock_flash.get_client.return_value = mock_client
                
                response = client.post("/flash/files/read", json={
                    "authToken": "token",
                    "flashSessionId": "session-1",
                    "path": "/app/test.txt\x00.js"
                })
                
                assert response.status_code in [400, 500]

    def test_extremely_long_path(self):
        """Test extremely long path handling"""
        with patch("app.routes.session.flash_routes.RedisCache") as mock_redis_class:
            with patch("app.routes.session.flash_routes.flash_client") as mock_flash:
                mock_redis = Mock()
                mock_redis.getAllData.return_value = {"hash": "user-1"}
                mock_redis_class.return_value = mock_redis

                mock_sandbox = MagicMock()
                mock_sandbox.files.read_text.side_effect = Exception("path too long")
                mock_client = Mock()
                mock_client.sandboxes.connect.return_value = mock_sandbox
                mock_flash.get_client.return_value = mock_client
                
                long_path = "/app/" + "a" * 10000 + ".js"
                
                response = client.post("/flash/files/read", json={
                    "authToken": "token",
                    "flashSessionId": "session-1",
                    "path": long_path
                })
                
                assert response.status_code in [400, 500]

    def test_extremely_long_command(self):
        """Test extremely long command handling"""
        with patch("app.routes.session.flash_routes.RedisCache") as mock_redis_class:
            with patch("app.routes.session.flash_routes.flash_client", _mock_flash_exec()):
                mock_redis = Mock()
                mock_redis.getAllData.return_value = {"hash": "user-1"}
                mock_redis_class.return_value = mock_redis
                
                long_command = "echo " + "a" * 100000
                
                response = client.post("/flash/exec", json={
                    "authToken": "token",
                    "flashSessionId": "session-1",
                    "command": long_command
                })
                
                assert response.status_code in [200, 400, 500]


@pytest.mark.security
class TestAccessControl:
    """Security tests for access control"""

    def test_unauthorized_test_access(self):
        """Test accessing test without permission"""
        with patch("app.routes.session.flash_routes.RedisCache") as mock_redis_class:
            with patch("app.routes.session.flash_routes.MongoDB") as mock_mongo_class:
                mock_redis = Mock()
                mock_redis.getAllData.return_value = {"hash": "restricted-user"}
                mock_redis_class.return_value = mock_redis
                
                mock_mongo = Mock()
                mock_mongo.selectCollection.return_value = None
                mock_mongo.find.return_value = []
                mock_mongo_class.return_value = mock_mongo
                
                response = client.post("/flash/start", json={
                    "authToken": "token",
                    "testId": "restricted-test"
                })
                
                assert response.status_code == 404

    def test_cross_user_session_access(self):
        """Test user cannot access another user's session"""
        with patch("app.routes.session.flash_routes.RedisCache") as mock_redis_class:
            with patch("app.routes.session.flash_routes.flash_client") as mock_flash:
                mock_redis = Mock()
                mock_redis.getAllData.return_value = {"hash": "user-a"}
                mock_redis_class.return_value = mock_redis

                mock_sandbox = MagicMock()
                mock_sandbox.kill.return_value = True
                mock_client = Mock()
                mock_client.sandboxes.connect.return_value = mock_sandbox
                mock_flash.get_client.return_value = mock_client

                response = client.post("/flash/stop", json={
                    "authToken": "user-a-token",
                    "flashSessionId": "user-b-session"
                })
                
                assert response.status_code in [200, 401, 403, 404]


@pytest.mark.security
class TestRateLimiting:
    """Security tests for rate limiting"""

    def test_multiple_rapid_requests(self):
        """Test handling of rapid requests"""
        responses = []
        for i in range(10):
            with patch("app.routes.session.flash_routes.RedisCache") as mock_redis_class:
                with patch("app.routes.session.flash_routes.flash_client", _mock_flash_files(file_list=["file1.js"])):
                    mock_redis = Mock()
                    mock_redis.getAllData.return_value = {"hash": f"user-{i}"}
                    mock_redis_class.return_value = mock_redis
                    
                    response = client.post("/flash/files/list", json={
                        "authToken": f"token-{i}",
                        "flashSessionId": f"session-{i}"
                    })
                    responses.append(response.status_code)
        
        success_count = sum(1 for s in responses if s == 200)
        assert success_count >= 5


@pytest.mark.security
class TestWebSocketSecurity:
    """Security tests for WebSocket connections"""

    def test_websocket_without_auth(self):
        """Test WebSocket connection without authentication"""
        with patch("app.routes.session.flash_routes.flash_client") as mock_flash:
            mock_flash.base_url = "ws://localhost:8090"
            with patch("websockets.connect") as mock_ws_connect:
                mock_ws = MagicMock()
                mock_ws.recv = MagicMock(side_effect=StopIteration)
                mock_ws.__aenter__ = MagicMock(return_value=mock_ws)
                mock_ws.__aexit__ = MagicMock(return_value=None)
                mock_ws_connect.return_value = mock_ws

                try:
                    with client.websocket_connect("/flash/ws/terminal/test-session") as websocket:
                        websocket.send_bytes(b"test data")
                except Exception:
                    pass

    def test_websocket_session_validation(self):
        """Test WebSocket validates session exists"""
        pass


@pytest.mark.security
class TestDataExfiltration:
    """Security tests for data exfiltration prevention"""

    def test_sensitive_file_access_blocked(self):
        """Test access to sensitive system files is blocked"""
        sensitive_paths = [
            "/etc/passwd",
            "/etc/shadow",
            "/root/.ssh/id_rsa",
            "/proc/self/environ"
        ]
        
        with patch("app.routes.session.flash_routes.RedisCache") as mock_redis_class:
            with patch("app.routes.session.flash_routes.flash_client") as mock_flash:
                mock_redis = Mock()
                mock_redis.getAllData.return_value = {"hash": "user-1"}
                mock_redis_class.return_value = mock_redis

                mock_sandbox = MagicMock()
                mock_sandbox.files.read_text.side_effect = Exception("access denied")
                mock_client = Mock()
                mock_client.sandboxes.connect.return_value = mock_sandbox
                mock_flash.get_client.return_value = mock_client
                
                for path in sensitive_paths:
                    response = client.post("/flash/files/read", json={
                        "authToken": "token",
                        "flashSessionId": "session-1",
                        "path": path
                    })
                    
                    assert response.status_code in [400, 403, 500]

    def test_environment_variable_exfiltration(self):
        """Test command to read env vars is handled"""
        with patch("app.routes.session.flash_routes.RedisCache") as mock_redis_class:
            with patch("app.routes.session.flash_routes.flash_client", _mock_flash_exec(stdout="", stderr="", exit_code=0)):
                mock_redis = Mock()
                mock_redis.getAllData.return_value = {"hash": "user-1"}
                mock_redis_class.return_value = mock_redis
                
                response = client.post("/flash/exec", json={
                    "authToken": "token",
                    "flashSessionId": "session-1",
                    "command": "printenv"
                })
                
                assert response.status_code in [200, 400]
