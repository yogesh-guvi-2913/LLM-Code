import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
import json

from app.app import app
from app.config.sandbox_provider import SandboxProviderConfig


client = TestClient(app)


class TestFlashRoutesAuth:
    """Tests for authentication in Flash routes"""

    def test_start_session_missing_auth_token(self):
        """Test start session without auth token"""
        response = client.post("/flash/start", json={"testId": "test-1"})
        assert response.status_code == 400
        assert "authToken required" in response.json()["detail"]

    def test_start_session_invalid_auth_token(self):
        """Test start session with invalid auth token"""
        with patch("app.routes.session.flash_routes.RedisCache") as mock_redis_class:
            mock_redis = Mock()
            mock_redis.getAllData.return_value = None
            mock_redis_class.return_value = mock_redis
            
            response = client.post("/flash/start", json={
                "authToken": "invalid-token",
                "testId": "test-1"
            })
            
            assert response.status_code == 401
            assert "token_expired" in response.json()["detail"]

    def test_stop_session_missing_session_id(self):
        """Test stop session without session ID"""
        with patch("app.routes.session.flash_routes.RedisCache") as mock_redis_class:
            mock_redis = Mock()
            mock_redis.getAllData.return_value = {"hash": "user-1"}
            mock_redis_class.return_value = mock_redis
            
            response = client.post("/flash/stop", json={
                "authToken": "valid-token"
            })
            
            assert response.status_code == 400
            assert "flashSessionId required" in response.json()["detail"]

    def test_exec_missing_command(self):
        """Test exec without command"""
        with patch("app.routes.session.flash_routes.RedisCache") as mock_redis_class:
            mock_redis = Mock()
            mock_redis.getAllData.return_value = {"hash": "user-1"}
            mock_redis_class.return_value = mock_redis
            
            response = client.post("/flash/exec", json={
                "authToken": "valid-token",
                "flashSessionId": "session-1"
            })
            
            assert response.status_code == 400
            assert "command required" in response.json()["detail"]


class TestFlashStartSession:
    """Tests for /flash/start endpoint"""

    @patch("app.routes.session.flash_routes.RedisCache")
    @patch("app.routes.session.flash_routes.MongoDB")
    @patch("app.routes.session.flash_routes.flash_client")
    def test_start_session_success(self, mock_flash, mock_mongo_class, mock_redis_class):
        """Test successful session creation"""
        mock_redis = Mock()
        mock_redis.getAllData.return_value = {"hash": "user-hash-123"}
        mock_redis_class.return_value = mock_redis
        
        mock_mongo = Mock()
        mock_mongo.selectCollection.return_value = None
        mock_mongo.find.return_value = [{
            "testId": "test-1",
            "name": "Express API",
            "flashTemplateId": "q1-express-api",
            "flashTemplateRegistered": True
        }]
        mock_mongo_class.return_value = mock_mongo
        
        mock_sandbox = Mock()
        mock_sandbox.id = "sandbox-123"
        mock_sandbox.app_url = "http://localhost:3000"
        mock_sandbox.preview_url = "http://localhost:3000"
        mock_sandbox.terminal_url = "ws://localhost:8090/terminal"
        
        mock_client = Mock()
        mock_client.sandboxes.create.return_value = mock_sandbox
        mock_flash.get_client.return_value = mock_client
        
        mock_mongo.find.side_effect = [
            [{"testId": "test-1", "name": "Express API", "flashTemplateId": "q1-express-api", "flashTemplateRegistered": True}],
            []
        ]
        
        response = client.post("/flash/start", json={
            "authToken": "valid-token",
            "testId": "test-1"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["flashSessionId"] == "sandbox-123"
        assert data["sandboxProvider"] == "flash"

    @patch("app.routes.session.flash_routes.RedisCache")
    @patch("app.routes.session.flash_routes.MongoDB")
    @patch("app.routes.session.flash_routes.flash_client")
    def test_start_session_test_not_found(self, mock_flash, mock_mongo_class, mock_redis_class):
        """Test start session with non-existent test"""
        mock_redis = Mock()
        mock_redis.getAllData.return_value = {"hash": "user-1"}
        mock_redis_class.return_value = mock_redis
        
        mock_mongo = Mock()
        mock_mongo.selectCollection.return_value = None
        mock_mongo.find.return_value = []
        mock_mongo_class.return_value = mock_mongo
        
        response = client.post("/flash/start", json={
            "authToken": "valid-token",
            "testId": "nonexistent"
        })
        
        assert response.status_code == 404
        assert "Test not found" in response.json()["detail"]

    @patch("app.routes.session.flash_routes.RedisCache")
    @patch("app.routes.session.flash_routes.MongoDB")
    @patch("app.routes.session.flash_routes.flash_client")
    def test_start_session_uses_default_template(self, mock_flash, mock_mongo_class, mock_redis_class):
        """Test start session uses default template when not registered"""
        mock_redis = Mock()
        mock_redis.getAllData.return_value = {"hash": "user-1"}
        mock_redis_class.return_value = mock_redis
        
        mock_mongo = Mock()
        mock_mongo.selectCollection.return_value = None
        mock_mongo.find.side_effect = [
            [{"testId": "test-1", "flashTemplateId": "custom-template", "flashTemplateRegistered": False}],
            []
        ]
        mock_mongo_class.return_value = mock_mongo
        
        mock_client = Mock()
        mock_sandbox = Mock()
        mock_sandbox.id = "sb-1"
        mock_sandbox.app_url = "http://localhost:3000"
        mock_sandbox.preview_url = "http://localhost:3000"
        mock_sandbox.terminal_url = "ws://localhost:8090/terminal"
        mock_client.sandboxes.create.return_value = mock_sandbox
        mock_flash.get_client.return_value = mock_client
        
        response = client.post("/flash/start", json={
            "authToken": "valid-token",
            "testId": "test-1"
        })
        
        assert response.status_code == 200
        mock_client.sandboxes.create.assert_called_once_with(
            template="q1",
            timeout=3600
        )


class TestFlashExec:
    """Tests for /flash/exec endpoint"""

    @patch("app.routes.session.flash_routes.RedisCache")
    @patch("app.routes.session.flash_routes.flash_client")
    def test_exec_success(self, mock_flash, mock_redis_class):
        """Test successful command execution"""
        mock_redis = Mock()
        mock_redis.getAllData.return_value = {"hash": "user-1"}
        mock_redis_class.return_value = mock_redis
        
        mock_sandbox = Mock()
        mock_sandbox.run.return_value = Mock(
            stdout="command output",
            stderr="",
            exit_code=0,
            duration_ms=150
        )
        
        mock_client = Mock()
        mock_client.sandboxes.connect.return_value = mock_sandbox
        mock_flash.get_client.return_value = mock_client
        
        response = client.post("/flash/exec", json={
            "authToken": "valid-token",
            "flashSessionId": "session-1",
            "command": "npm test"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["stdout"] == "command output"
        assert data["exitCode"] == 0

    @patch("app.routes.session.flash_routes.RedisCache")
    @patch("app.routes.session.flash_routes.flash_client")
    def test_exec_with_error(self, mock_flash, mock_redis_class):
        """Test command execution with error"""
        mock_redis = Mock()
        mock_redis.getAllData.return_value = {"hash": "user-1"}
        mock_redis_class.return_value = mock_redis
        
        mock_sandbox = Mock()
        mock_sandbox.run.return_value = Mock(
            stdout="",
            stderr="Command failed: npm test",
            exit_code=1,
            duration_ms=100
        )
        
        mock_client = Mock()
        mock_client.sandboxes.connect.return_value = mock_sandbox
        mock_flash.get_client.return_value = mock_client
        
        response = client.post("/flash/exec", json={
            "authToken": "valid-token",
            "flashSessionId": "session-1",
            "command": "npm test"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["stderr"] == "Command failed: npm test"
        assert data["exitCode"] == 1


class TestFlashFiles:
    """Tests for /flash/files/* endpoints"""

    @patch("app.routes.session.flash_routes.RedisCache")
    @patch("app.routes.session.flash_routes.flash_client")
    def test_read_file_success(self, mock_flash, mock_redis_class):
        """Test successful file read"""
        mock_redis = Mock()
        mock_redis.getAllData.return_value = {"hash": "user-1"}
        mock_redis_class.return_value = mock_redis
        
        mock_sandbox = Mock()
        mock_sandbox.files.read_text.return_value = "file content here"
        
        mock_client = Mock()
        mock_client.sandboxes.connect.return_value = mock_sandbox
        mock_flash.get_client.return_value = mock_client
        
        response = client.post("/flash/files/read", json={
            "authToken": "valid-token",
            "flashSessionId": "session-1",
            "path": "/app/src/index.js"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["content"] == "file content here"

    @patch("app.routes.session.flash_routes.RedisCache")
    @patch("app.routes.session.flash_routes.flash_client")
    def test_write_file_success(self, mock_flash, mock_redis_class):
        """Test successful file write"""
        mock_redis = Mock()
        mock_redis.getAllData.return_value = {"hash": "user-1"}
        mock_redis_class.return_value = mock_redis
        
        mock_sandbox = Mock()
        mock_sandbox.files.write.return_value = True
        
        mock_client = Mock()
        mock_client.sandboxes.connect.return_value = mock_sandbox
        mock_flash.get_client.return_value = mock_client
        
        response = client.post("/flash/files/write", json={
            "authToken": "valid-token",
            "flashSessionId": "session-1",
            "path": "/app/src/index.js",
            "content": "console.log('hello')"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "written successfully" in data["message"]

    @patch("app.routes.session.flash_routes.RedisCache")
    @patch("app.routes.session.flash_routes.flash_client")
    def test_list_files_success(self, mock_flash, mock_redis_class):
        """Test successful file listing"""
        mock_redis = Mock()
        mock_redis.getAllData.return_value = {"hash": "user-1"}
        mock_redis_class.return_value = mock_redis
        
        mock_sandbox = Mock()
        mock_sandbox.files.list.return_value = [
            "/app/src/index.js",
            "/app/package.json",
            "/app/README.md"
        ]
        
        mock_client = Mock()
        mock_client.sandboxes.connect.return_value = mock_sandbox
        mock_flash.get_client.return_value = mock_client
        
        response = client.post("/flash/files/list", json={
            "authToken": "valid-token",
            "flashSessionId": "session-1"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["files"]) == 3

    def test_read_file_missing_path(self):
        """Test read file without path"""
        with patch("app.routes.session.flash_routes.RedisCache") as mock_redis_class:
            mock_redis = Mock()
            mock_redis.getAllData.return_value = {"hash": "user-1"}
            mock_redis_class.return_value = mock_redis
            
            response = client.post("/flash/files/read", json={
                "authToken": "valid-token",
                "flashSessionId": "session-1"
            })
            
            assert response.status_code == 400

    def test_write_file_missing_content(self):
        """Test write file without content"""
        with patch("app.routes.session.flash_routes.RedisCache") as mock_redis_class:
            mock_redis = Mock()
            mock_redis.getAllData.return_value = {"hash": "user-1"}
            mock_redis_class.return_value = mock_redis
            
            response = client.post("/flash/files/write", json={
                "authToken": "valid-token",
                "flashSessionId": "session-1",
                "path": "/app/test.js"
            })
            
            assert response.status_code == 400


class TestFlashSubmit:
    """Tests for /flash/submit endpoint"""

    @patch("app.routes.session.flash_routes.RedisCache")
    @patch("app.routes.session.flash_routes.MongoDB")
    @patch("app.routes.session.flash_routes.hybrid_scorer")
    def test_submit_success(self, mock_scorer, mock_mongo_class, mock_redis_class):
        """Test successful submission and scoring"""
        mock_redis = Mock()
        mock_redis.getAllData.return_value = {"hash": "user-1"}
        mock_redis_class.return_value = mock_redis
        
        mock_mongo = Mock()
        mock_mongo.selectCollection.return_value = None
        mock_mongo.find.side_effect = [
            [{"testId": "test-1"}],
            [{"flashSessionId": "session-1"}]
        ]
        mock_mongo_class.return_value = mock_mongo
        
        mock_scorer.score_submission = AsyncMock(return_value={
            "final_score": 85,
            "max_score": 100,
            "flash_score": 90,
            "llm_score": 75,
            "scoring_method": "hybrid"
        })
        
        response = client.post("/flash/submit", json={
            "authToken": "valid-token",
            "testId": "test-1",
            "files": {"index.js": "code"},
            "chatHistory": []
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["scoringMethod"] == "hybrid"
        assert data["result"]["final_score"] == 85

    @patch("app.routes.session.flash_routes.RedisCache")
    @patch("app.routes.session.flash_routes.MongoDB")
    def test_submit_no_session(self, mock_mongo_class, mock_redis_class):
        """Test submit without active session"""
        mock_redis = Mock()
        mock_redis.getAllData.return_value = {"hash": "user-1"}
        mock_redis_class.return_value = mock_redis
        
        mock_mongo = Mock()
        mock_mongo.select_collection.return_value = None
        mock_mongo.find.side_effect = [[{"testId": "test-1"}], []]
        mock_mongo_class.return_value = mock_mongo
        
        response = client.post("/flash/submit", json={
            "authToken": "valid-token",
            "testId": "test-1",
            "files": {}
        })
        
        assert response.status_code == 404


class TestFlashResults:
    """Tests for /flash/results endpoint"""

    @patch("app.routes.session.flash_routes.RedisCache")
    @patch("app.routes.session.flash_routes.MongoDB")
    def test_get_results_success(self, mock_mongo_class, mock_redis_class):
        """Test getting results for completed submission"""
        mock_redis = Mock()
        mock_redis.getAllData.return_value = {"hash": "user-1"}
        mock_redis_class.return_value = mock_redis
        
        mock_mongo = Mock()
        mock_mongo.selectCollection.return_value = None
        mock_mongo.find.side_effect = [
            [{
                "status": "completed",
                "score": 85,
                "maxScore": 100,
                "flashScore": 90,
                "llmScore": 75,
                "testResults": [],
                "files": {},
                "scoringMethod": "hybrid"
            }],
            [{"testId": "test-1", "name": "Express API"}]
        ]
        mock_mongo_class.return_value = mock_mongo
        
        response = client.post("/flash/results", json={
            "authToken": "valid-token",
            "testId": "test-1"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "completed"
        assert data["score"] == 85

    @patch("app.routes.session.flash_routes.RedisCache")
    @patch("app.routes.session.flash_routes.MongoDB")
    def test_get_results_not_found(self, mock_mongo_class, mock_redis_class):
        """Test getting results for non-existent submission"""
        mock_redis = Mock()
        mock_redis.getAllData.return_value = {"hash": "user-1"}
        mock_redis_class.return_value = mock_redis
        
        mock_mongo = Mock()
        mock_mongo.selectCollection.return_value = None
        mock_mongo.find.return_value = []
        mock_mongo_class.return_value = mock_mongo
        
        response = client.post("/flash/results", json={
            "authToken": "valid-token",
            "testId": "test-1"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["status"] == "not_found"


class TestHealthEndpoints:
    """Tests for health check endpoints"""

    def test_health_basic(self):
        """Test basic health endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_liveness(self):
        """Test liveness endpoint"""
        response = client.get("/health/live")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"

    @patch("app.routes.health.asyncpg.connect")
    @patch("app.routes.health.redis.from_url")
    @patch("app.routes.health.flash_client")
    def test_readiness_all_healthy(self, mock_flash, mock_redis_from_url, mock_pg_connect):
        """Test readiness when all services are healthy"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="SELECT 1")
        mock_conn.close = AsyncMock()
        mock_pg_connect.return_value = mock_conn
        
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_redis.close = AsyncMock()
        mock_redis_from_url.return_value = mock_redis
        
        mock_flash.health_check.return_value = True
        
        response = client.get("/health/ready")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["checks"]["postgres"] == "ok"
        assert data["checks"]["redis"] == "ok"
        assert data["checks"]["flash"] == "ok"

    @patch("app.routes.health.asyncpg.connect")
    def test_readiness_postgres_down(self, mock_pg_connect):
        """Test readiness when PostgreSQL is down"""
        mock_pg_connect.side_effect = Exception("Connection refused")
        
        response = client.get("/health/ready")
        
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert "error" in data["checks"]["postgres"]


class TestMetricsEndpoint:
    """Tests for Prometheus metrics endpoint"""

    def test_metrics_endpoint(self):
        """Test metrics endpoint returns Prometheus format"""
        response = client.get("/metrics")
        
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]