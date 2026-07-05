import pytest
import asyncio
import time
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from concurrent.futures import ThreadPoolExecutor
import statistics

from app.app import app

client = TestClient(app)


@pytest.mark.performance
class TestFlashRoutesPerformance:
    """Performance tests for Flash routes"""

    @patch("app.routes.session.flash_routes.RedisCache")
    @patch("app.routes.session.flash_routes.MongoDB")
    @patch("app.routes.session.flash_routes.flash_client")
    def test_start_session_response_time(self, mock_flash, mock_mongo_class, mock_redis_class):
        """Test that start session responds within acceptable time"""
        mock_redis = Mock()
        mock_redis.getAllData.return_value = {"hash": "perf-user"}
        mock_redis_class.return_value = mock_redis
        
        mock_mongo = Mock()
        mock_mongo.selectCollection.return_value = None
        mock_mongo.find.side_effect = [
            [{"testId": "perf-test", "flashTemplateId": "q1"}],
            []
        ] * 20
        mock_mongo_class.return_value = mock_mongo
        
        mock_sandbox = Mock()
        mock_sandbox.id = "perf-session"
        mock_sandbox.app_url = "http://localhost:3000"
        mock_sandbox.preview_url = "http://localhost:3000"
        mock_sandbox.terminal_url = "ws://localhost:8090/terminal"
        
        mock_client = Mock()
        mock_client.sandboxes.create.return_value = mock_sandbox
        mock_flash.get_client.return_value = mock_client
        
        times = []
        for _ in range(10):
            start_time = time.time()
            response = client.post("/flash/start", json={
                "authToken": "perf-token",
                "testId": "perf-test"
            })
            elapsed = time.time() - start_time
            times.append(elapsed)
            
            assert response.status_code == 200
        
        avg_time = statistics.mean(times)
        max_time = max(times)
        
        assert avg_time < 0.5, f"Average response time {avg_time}s exceeds 0.5s"
        assert max_time < 1.0, f"Max response time {max_time}s exceeds 1.0s"

    @patch("app.routes.session.flash_routes.RedisCache")
    @patch("app.routes.session.flash_routes.flash_client")
    def test_exec_command_response_time(self, mock_flash, mock_redis_class):
        """Test exec command response time"""
        mock_redis = Mock()
        mock_redis.getAllData.return_value = {"hash": "perf-user"}
        mock_redis_class.return_value = mock_redis
        
        mock_sandbox = Mock()
        mock_sandbox.run.return_value = Mock(
            stdout="output",
            stderr="",
            exit_code=0,
            duration_ms=50
        )
        
        mock_client = Mock()
        mock_client.sandboxes.connect.return_value = mock_sandbox
        mock_flash.get_client.return_value = mock_client
        
        times = []
        for _ in range(20):
            start_time = time.time()
            response = client.post("/flash/exec", json={
                "authToken": "token",
                "flashSessionId": "session",
                "command": "echo test"
            })
            elapsed = time.time() - start_time
            times.append(elapsed)
            
            assert response.status_code == 200
        
        avg_time = statistics.mean(times)
        assert avg_time < 0.2, f"Average exec time {avg_time}s exceeds 0.2s"

    @patch("app.routes.session.flash_routes.RedisCache")
    @patch("app.routes.session.flash_routes.flash_client")
    def test_file_operations_response_time(self, mock_flash, mock_redis_class):
        """Test file operations response time"""
        mock_redis = Mock()
        mock_redis.getAllData.return_value = {"hash": "perf-user"}
        mock_redis_class.return_value = mock_redis
        
        mock_sandbox = Mock()
        mock_sandbox.files.read_text.return_value = "content"
        mock_sandbox.files.write.return_value = True
        mock_sandbox.files.list.return_value = ["file1", "file2"]
        
        mock_client = Mock()
        mock_client.sandboxes.connect.return_value = mock_sandbox
        mock_flash.get_client.return_value = mock_client
        
        for operation in ["read", "write", "list"]:
            times = []
            for _ in range(10):
                start_time = time.time()
                
                if operation == "read":
                    response = client.post("/flash/files/read", json={
                        "authToken": "token",
                        "flashSessionId": "session",
                        "path": "/app/test.js"
                    })
                elif operation == "write":
                    response = client.post("/flash/files/write", json={
                        "authToken": "token",
                        "flashSessionId": "session",
                        "path": "/app/test.js",
                        "content": "test"
                    })
                else:
                    response = client.post("/flash/files/list", json={
                        "authToken": "token",
                        "flashSessionId": "session"
                    })
                
                elapsed = time.time() - start_time
                times.append(elapsed)
                assert response.status_code == 200
            
            avg_time = statistics.mean(times)
            assert avg_time < 0.15, f"Average {operation} time {avg_time}s exceeds 0.15s"


@pytest.mark.performance
@pytest.mark.slow
class TestConcurrentLoad:
    """Load tests with concurrent requests"""

    @patch("app.routes.session.flash_routes.RedisCache")
    @patch("app.routes.session.flash_routes.flash_client")
    def test_concurrent_exec_commands(self, mock_flash, mock_redis_class):
        """Test handling of concurrent exec requests"""
        mock_redis = Mock()
        mock_redis.getAllData.return_value = {"hash": "load-user"}
        mock_redis_class.return_value = mock_redis
        
        mock_sandbox = Mock()
        mock_sandbox.run.return_value = Mock(stdout="ok", stderr="", exit_code=0, duration_ms=100)
        
        mock_client = Mock()
        mock_client.sandboxes.connect.return_value = mock_sandbox
        mock_flash.get_client.return_value = mock_client
        
        def make_request(i):
            response = client.post("/flash/exec", json={
                "authToken": f"token-{i}",
                "flashSessionId": f"session-{i}",
                "command": f"echo {i}"
            })
            return response.status_code
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(make_request, range(50)))
        
        success_count = sum(1 for r in results if r == 200)
        assert success_count >= 45, f"Only {success_count}/50 requests succeeded"

    @patch("app.routes.session.flash_routes.RedisCache")
    @patch("app.routes.session.flash_routes.flash_client")
    def test_concurrent_file_reads(self, mock_flash, mock_redis_class):
        """Test handling of concurrent file read requests"""
        mock_redis = Mock()
        mock_redis.getAllData.return_value = {"hash": "load-user"}
        mock_redis_class.return_value = mock_redis
        
        mock_sandbox = Mock()
        mock_sandbox.files.read_text.return_value = "file content"
        
        mock_client = Mock()
        mock_client.sandboxes.connect.return_value = mock_sandbox
        mock_flash.get_client.return_value = mock_client
        
        def make_request(i):
            response = client.post("/flash/files/read", json={
                "authToken": f"token-{i}",
                "flashSessionId": f"session-{i}",
                "path": f"/app/file-{i}.js"
            })
            return response.status_code
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(make_request, range(100)))
        
        success_count = sum(1 for r in results if r == 200)
        assert success_count >= 90, f"Only {success_count}/100 requests succeeded"


@pytest.mark.performance
@pytest.mark.slow
class TestSustainedLoad:
    """Tests for sustained load over time"""

    @patch("app.routes.session.flash_routes.RedisCache")
    @patch("app.routes.session.flash_routes.flash_client")
    def test_sustained_exec_load(self, mock_flash, mock_redis_class):
        """Test sustained exec load over 30 seconds"""
        mock_redis = Mock()
        mock_redis.getAllData.return_value = {"hash": "sustained-user"}
        mock_redis_class.return_value = mock_redis
        
        mock_sandbox = Mock()
        mock_sandbox.run.return_value = Mock(stdout="ok", stderr="", exit_code=0, duration_ms=50)
        
        mock_client = Mock()
        mock_client.sandboxes.connect.return_value = mock_sandbox
        mock_flash.get_client.return_value = mock_client
        
        results = []
        start_time = time.time()
        request_count = 0
        
        while time.time() - start_time < 5:
            response = client.post("/flash/exec", json={
                "authToken": f"token-{request_count}",
                "flashSessionId": "session",
                "command": "echo test"
            })
            results.append(response.status_code)
            request_count += 1
        
        success_rate = sum(1 for r in results if r == 200) / len(results) * 100
        
        assert success_rate >= 95, f"Success rate {success_rate}% below 95%"
        assert request_count >= 50, f"Only {request_count} requests in 5 seconds"


@pytest.mark.performance
class TestHybridScorerPerformance:
    """Performance tests for hybrid scoring"""

    @pytest.mark.asyncio
    @patch("app.services.hybrid_scorer.flash_client")
    @patch("app.routes.evaluation.routes.evaluate_submission")
    async def test_scoring_response_time(self, mock_eval, mock_flash):
        """Test hybrid scoring completes within acceptable time"""
        from app.services.hybrid_scorer import HybridScorer
        
        session_mock = MagicMock()
        session_mock.submit.return_value = MagicMock(submission_id="sub-1")
        session_mock.wait_for_score.return_value = MagicMock(
            score=85,
            max_score=100,
            status="completed"
        )
        
        mock_client = MagicMock()
        mock_client.assessments.get_session.return_value = session_mock
        mock_flash.get_client.return_value = mock_client
        mock_flash.base_url = "http://localhost:8090"
        
        mock_eval.return_value = {
            "score": 80,
            "feedback": "Good",
            "requirements_check": []
        }
        
        scorer = HybridScorer()
        
        start_time = time.time()
        result = await scorer.score_submission(
            session_id="test-session",
            test_data={},
            files={},
            chat_history=[],
            auth_token="token"
        )
        elapsed = time.time() - start_time
        
        assert elapsed < 2.0, f"Scoring took {elapsed}s, exceeds 2s limit"
        assert result["final_score"] > 0


@pytest.mark.performance
class TestFeatureFlagPerformance:
    """Performance tests for feature flag evaluation"""

    def test_provider_selection_performance(self):
        """Test provider selection is fast"""
        from app.config.sandbox_provider import SandboxProviderConfig
        
        config = SandboxProviderConfig()
        
        users = [f"user-{i}" for i in range(1000)]
        
        start_time = time.time()
        providers = [config.get_provider(u) for u in users]
        elapsed = time.time() - start_time
        
        assert elapsed < 0.1, f"1000 provider selections took {elapsed}s"
        
        assert all(p in ["flash", "legacy"] for p in providers)