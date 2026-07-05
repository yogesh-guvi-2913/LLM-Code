import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
import json
import time

from app.app import app

client = TestClient(app)


@pytest.mark.e2e
class TestFullFlow:
    """End-to-end tests for complete user journey"""

    @patch("app.routes.session.flash_routes.RedisCache")
    @patch("app.routes.session.flash_routes.MongoDB")
    @patch("app.routes.session.flash_routes.flash_client")
    @patch("app.routes.session.flash_routes.hybrid_scorer")
    def test_complete_session_lifecycle(self, mock_scorer, mock_flash, mock_mongo_class, mock_redis_class):
        """Test complete session: start -> exec -> files -> submit -> results"""
        
        mock_redis = Mock()
        mock_redis.getAllData.return_value = {"hash": "user-flow-test", "email": "test@example.com"}
        mock_redis_class.return_value = mock_redis
        
        mock_mongo = Mock()
        mock_mongo.selectCollection.return_value = None
        mock_mongo.find.side_effect = [
            [{"testId": "e2e-test", "name": "E2E Test", "flashTemplateId": "q1", "flashTemplateRegistered": True}],
            [],
            [{"testId": "e2e-test", "name": "E2E Test", "flashTemplateId": "q1", "flashTemplateRegistered": True}],
            [{"flashSessionId": "session-e2e"}],
            [{
                "status": "completed",
                "score": 85,
                "maxScore": 100,
                "flashScore": 90,
                "llmScore": 75,
                "testResults": [],
                "scoringMethod": "hybrid"
            }],
            [{"testId": "e2e-test", "name": "E2E Test"}]
        ]
        mock_mongo.insertOne.return_value = Mock(inserted_id="mapper-id")
        mock_mongo_class.return_value = mock_mongo
        
        mock_sandbox = Mock()
        mock_sandbox.id = "session-e2e"
        mock_sandbox.app_url = "http://localhost:3000"
        mock_sandbox.preview_url = "http://localhost:3000"
        mock_sandbox.terminal_url = "ws://localhost:8090/terminal"
        mock_sandbox.run.return_value = Mock(stdout="test passed", stderr="", exit_code=0, duration_ms=100)
        mock_sandbox.files.read_text.return_value = "file content"
        mock_sandbox.files.write.return_value = True
        mock_sandbox.files.list.return_value = ["/app/index.js"]
        
        mock_flash_client = Mock()
        mock_flash_client.sandboxes.create.return_value = mock_sandbox
        mock_flash_client.sandboxes.connect.return_value = mock_sandbox
        mock_flash.get_client.return_value = mock_flash_client
        
        mock_scorer.score_submission = AsyncMock(return_value={
            "final_score": 85,
            "max_score": 100,
            "flash_score": 90,
            "llm_score": 75,
            "scoring_method": "hybrid"
        })
        
        start_response = client.post("/flash/start", json={
            "authToken": "test-token",
            "testId": "e2e-test"
        })
        assert start_response.status_code == 200
        session_id = start_response.json()["flashSessionId"]
        
        exec_response = client.post("/flash/exec", json={
            "authToken": "test-token",
            "flashSessionId": session_id,
            "command": "npm test"
        })
        assert exec_response.status_code == 200
        assert exec_response.json()["exitCode"] == 0
        
        write_response = client.post("/flash/files/write", json={
            "authToken": "test-token",
            "flashSessionId": session_id,
            "path": "/app/src/index.js",
            "content": "console.log('hello')"
        })
        assert write_response.status_code == 200
        
        read_response = client.post("/flash/files/read", json={
            "authToken": "test-token",
            "flashSessionId": session_id,
            "path": "/app/src/index.js"
        })
        assert read_response.status_code == 200
        
        submit_response = client.post("/flash/submit", json={
            "authToken": "test-token",
            "testId": "e2e-test",
            "files": {"src/index.js": "code"},
            "chatHistory": []
        })
        assert submit_response.status_code == 200
        assert submit_response.json()["result"]["final_score"] == 85
        
        results_response = client.post("/flash/results", json={
            "authToken": "test-token",
            "testId": "e2e-test"
        })
        assert results_response.status_code == 200
        assert results_response.json()["score"] == 85

    @patch("app.routes.session.flash_routes.RedisCache")
    @patch("app.routes.session.flash_routes.MongoDB")
    @patch("app.routes.session.flash_routes.flash_client")
    def test_session_stop_cleanup(self, mock_flash, mock_mongo_class, mock_redis_class):
        """Test session cleanup on stop"""
        mock_redis = Mock()
        mock_redis.getAllData.return_value = {"hash": "user-cleanup"}
        mock_redis_class.return_value = mock_redis
        
        mock_sandbox = Mock()
        mock_sandbox.kill.return_value = True
        
        mock_client = Mock()
        mock_client.sandboxes.connect.return_value = mock_sandbox
        mock_flash.get_client.return_value = mock_client
        
        response = client.post("/flash/stop", json={
            "authToken": "test-token",
            "flashSessionId": "session-to-stop"
        })
        
        assert response.status_code == 200
        assert response.json()["success"] is True
        mock_sandbox.kill.assert_called_once()


@pytest.mark.e2e
class TestHybridScoringE2E:
    """E2E tests for hybrid scoring"""

    @patch("app.routes.session.flash_routes.RedisCache")
    @patch("app.routes.session.flash_routes.MongoDB")
    @patch("app.services.hybrid_scorer.flash_client")
    @patch("app.routes.evaluation.routes.evaluate_submission")
    async def test_hybrid_scoring_full_flow(self, mock_eval, mock_flash, mock_mongo_class, mock_redis_class):
        """Test hybrid scoring with Flash + LLM"""
        mock_redis = Mock()
        mock_redis.getAllData.return_value = {"hash": "hybrid-user"}
        mock_redis_class.return_value = mock_redis
        
        mock_mongo = Mock()
        mock_mongo.selectCollection.return_value = None
        mock_mongo.find.side_effect = [
            [{"testId": "hybrid-test", "requirements": []}],
            [{"flashSessionId": "hybrid-session"}]
        ]
        mock_mongo_class.return_value = mock_mongo
        
        session_mock = MagicMock()
        session_mock.submit.return_value = MagicMock(submission_id="sub-1")
        session_mock.wait_for_score.return_value = MagicMock(
            score=90,
            max_score=100,
            status="completed"
        )
        
        client_mock = MagicMock()
        client_mock.assessments.get_session.return_value = session_mock
        mock_flash.get_client.return_value = client_mock
        
        mock_eval.return_value = {
            "score": 80,
            "feedback": "Good code quality",
            "requirements_check": [
                {"requirement": "CRUD", "satisfied": True}
            ]
        }
        
        response = client.post("/flash/submit", json={
            "authToken": "token",
            "testId": "hybrid-test",
            "files": {"index.js": "code"},
            "chatHistory": []
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        
        result = data["result"]
        assert result["flash_score"] == 90
        assert result["llm_score"] == 80
        
        expected_final = 90 * 0.7 + 80 * 0.3
        assert result["final_score"] == expected_final


@pytest.mark.e2e
class TestFeatureFlagRollout:
    """E2E tests for feature flag rollout"""

    def test_rollout_distribution(self):
        """Test that rollout percentage distributes users correctly"""
        from app.config.sandbox_provider import SandboxProviderConfig
        
        with patch.dict("os.environ", {"FLASH_ROLLOUT_PERCENTAGE": "30"}):
            config = SandboxProviderConfig()
            
            users = [f"user-{i}" for i in range(1000)]
            flash_users = [u for u in users if config.get_provider(u) == "flash"]
            
            flash_percentage = len(flash_users) / len(users) * 100
            
            assert 25 <= flash_percentage <= 35

    def test_whitelist_always_gets_flash(self):
        """Test whitelisted users always get Flash"""
        from app.config.sandbox_provider import SandboxProviderConfig
        
        with patch.dict("os.environ", {
            "FLASH_ROLLOUT_PERCENTAGE": "0",
            "FLASH_ROLLOUT_WHITELIST": "vip1,vip2,vip3"
        }):
            config = SandboxProviderConfig()
            
            assert config.get_provider("vip1") == "flash"
            assert config.get_provider("vip2") == "flash"
            assert config.get_provider("vip3") == "flash"
            assert config.get_provider("normal-user") == "legacy"

    def test_blacklist_always_gets_legacy(self):
        """Test blacklisted users always get legacy"""
        from app.config.sandbox_provider import SandboxProviderConfig
        
        with patch.dict("os.environ", {
            "FLASH_ROLLOUT_PERCENTAGE": "100",
            "FLASH_ROLLOUT_BLACKLIST": "bad-user"
        }):
            config = SandboxProviderConfig()
            
            assert config.get_provider("bad-user") == "legacy"
            assert config.get_provider("normal-user") == "flash"


@pytest.mark.e2e
class TestErrorRecovery:
    """E2E tests for error recovery"""

    @patch("app.routes.session.flash_routes.RedisCache")
    @patch("app.routes.session.flash_routes.MongoDB")
    @patch("app.routes.session.flash_routes.flash_client")
    def test_flash_unavailable_falls_back_gracefully(self, mock_flash, mock_mongo_class, mock_redis_class):
        """Test graceful handling when Flash is unavailable"""
        mock_redis = Mock()
        mock_redis.getAllData.return_value = {"hash": "error-user"}
        mock_redis_class.return_value = mock_redis
        
        mock_mongo = Mock()
        mock_mongo.selectCollection.return_value = None
        mock_mongo.find.return_value = [{"testId": "test-1", "flashTemplateId": "q1"}]
        mock_mongo_class.return_value = mock_mongo
        
        mock_flash.get_client.side_effect = Exception("Flash service unavailable")
        
        response = client.post("/flash/start", json={
            "authToken": "token",
            "testId": "test-1"
        })
        
        assert response.status_code == 500
        assert "Failed to create sandbox" in response.json()["detail"]

    @patch("app.routes.session.flash_routes.RedisCache")
    @patch("app.routes.session.flash_routes.MongoDB")
    @patch("app.routes.session.flash_routes.flash_client")
    def test_exec_timeout_handled(self, mock_flash, mock_mongo_class, mock_redis_class):
        """Test command execution timeout handling"""
        mock_redis = Mock()
        mock_redis.getAllData.return_value = {"hash": "timeout-user"}
        mock_redis_class.return_value = mock_redis
        
        mock_sandbox = Mock()
        mock_sandbox.run.side_effect = TimeoutError("Command timed out")
        
        mock_client = Mock()
        mock_client.sandboxes.connect.return_value = mock_sandbox
        mock_flash.get_client.return_value = mock_client
        
        response = client.post("/flash/exec", json={
            "authToken": "token",
            "flashSessionId": "session-1",
            "command": "long-running-command"
        })
        
        assert response.status_code == 500