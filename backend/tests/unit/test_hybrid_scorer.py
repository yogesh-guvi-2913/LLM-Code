import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import os

from app.services.hybrid_scorer import HybridScorer


class TestHybridScorer:
    """Tests for HybridScorer service"""

    @pytest.fixture
    def scorer(self):
        """Create HybridScorer instance with mocked Flash client"""
        with patch.dict(os.environ, {
            "FLASH_SCORE_WEIGHT": "0.7",
            "LLM_SCORE_WEIGHT": "0.3",
            "FLASH_BASE_URL": "http://localhost:8090"
        }):
            with patch("app.services.hybrid_scorer.flash_client") as mock_flash:
                mock_client = MagicMock()
                mock_client.health_check = Mock(return_value=True)
                mock_flash.get_client.return_value = mock_client
                mock_flash.base_url = "http://localhost:8090"
                
                scorer = HybridScorer()
                scorer._flash_client = mock_client
                yield scorer
    def test_initialization(self, scorer):
        """Test HybridScorer initializes with correct weights"""
        assert scorer.flash_weight == 0.7
        assert scorer.llm_weight == 0.3

    def test_custom_weights_from_env(self):
        """Test custom weights from environment"""
        with patch.dict(os.environ, {
            "FLASH_SCORE_WEIGHT": "0.8",
            "LLM_SCORE_WEIGHT": "0.2",
            "FLASH_BASE_URL": "http://localhost:8090"
        }):
            with patch("app.services.hybrid_scorer.flash_client"):
                scorer = HybridScorer()
                assert scorer.flash_weight == 0.8
                assert scorer.llm_weight == 0.2

    @pytest.mark.asyncio
    async def test_run_flash_scoring_success(self, scorer):
        """Test successful Flash scoring"""
        session_mock = MagicMock()
        submission_mock = MagicMock()
        submission_mock.submission_id = "test-submission-id"
        session_mock.submit.return_value = submission_mock
        
        result_mock = MagicMock()
        result_mock.score = 85
        result_mock.max_score = 100
        result_mock.status = "completed"
        session_mock.wait_for_score.return_value = result_mock
        
        scorer.flash_client.assessments.get_session.return_value = session_mock
        
        result = await scorer.run_flash_scoring(
            session_id="test-session",
            test_data={"testId": "test-1"},
            auth_token="test-token"
        )
        
        assert result["score"] == 85
        assert result["max_score"] == 100
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_run_flash_scoring_failure(self, scorer):
        """Test Flash scoring handles errors gracefully"""
        scorer.flash_client.assessments.get_session.side_effect = Exception("Connection refused")
        
        result = await scorer.run_flash_scoring(
            session_id="test-session",
            test_data={"testId": "test-1"},
            auth_token="test-token"
        )
        
        assert result["score"] == 0
        assert "error" in result

    @pytest.mark.asyncio
    async def test_run_llm_evaluation_success(self, scorer):
        """Test successful LLM evaluation"""
        mock_evaluate = AsyncMock(return_value={
            "score": 80,
            "feedback": "Good code quality",
            "requirements_check": [
                {"requirement": "CRUD operations", "satisfied": True},
                {"requirement": "Error handling", "satisfied": False}
            ]
        })
        
        mock_module = MagicMock()
        mock_module.evaluate_submission = mock_evaluate
        
        with patch.dict('sys.modules', {'app.routes.evaluation.routes': mock_module}):
            result = await scorer.run_llm_evaluation(
                test_data={"name": "Test", "description": "Desc", "requirements": []},
                files={"index.js": "code"},
                chat_history=[],
                runtime_score=85
            )
        
        assert result["score"] == 80
        assert "feedback" in result
        assert len(result["requirements_check"]) == 2

    @pytest.mark.asyncio
    async def test_run_llm_evaluation_failure(self, scorer):
        """Test LLM evaluation handles errors gracefully"""
        mock_module = MagicMock()
        mock_module.evaluate_submission = AsyncMock(side_effect=Exception("LLM error"))
        
        with patch.dict('sys.modules', {'app.routes.evaluation.routes': mock_module}):
            result = await scorer.run_llm_evaluation(
                test_data={"name": "Test"},
                files={},
                chat_history=[],
                runtime_score=0
            )
        
        assert result["score"] == 0
        assert "error" in result

    @pytest.mark.asyncio
    async def test_score_submission_integration(self, scorer, test_test_data):
        """Test complete hybrid scoring flow"""
        session_mock = MagicMock()
        submission_mock = MagicMock()
        submission_mock.submission_id = "sub-123"
        session_mock.submit.return_value = submission_mock
        session_mock.wait_for_score.return_value = MagicMock(
            score=90,
            max_score=100,
            status="completed"
        )
        scorer.flash_client.assessments.get_session.return_value = session_mock
        
        mock_evaluate = AsyncMock(return_value={
            "score": 80,
            "feedback": "Good structure",
            "requirements_check": []
        })
        
        mock_module = MagicMock()
        mock_module.evaluate_submission = mock_evaluate
        
        with patch.dict('sys.modules', {'app.routes.evaluation.routes': mock_module}):
            result = await scorer.score_submission(
                session_id="session-123",
                test_data=test_test_data,
                files={"index.js": "code"},
                chat_history=[],
                auth_token="token"
            )
        
        assert "final_score" in result
        assert result["flash_score"] == 90
        assert result["llm_score"] == 80
        assert result["final_score"] == 90 * 0.7 + 80 * 0.3
        assert result["scoring_method"] == "hybrid"

    def test_generate_feedback(self, scorer):
        """Test feedback generation"""
        feedback = scorer.generate_feedback(
            flash_score=85,
            llm_score=75,
            test_results=[
                {"name": "Test 1", "passed": True},
                {"name": "Test 2", "passed": False, "error": "Assertion failed"}
            ],
            llm_feedback="Good code organization",
            requirements_check=[
                {"requirement": "GET endpoint", "satisfied": True},
                {"requirement": "POST endpoint", "satisfied": False}
            ]
        )
        
        assert "Overall Score" in feedback
        assert "85/100" in feedback
        assert "75/100" in feedback
        assert "Test 2" in feedback
        assert "Good code organization" in feedback
        assert "GET endpoint" in feedback
        assert "POST endpoint" in feedback

    def test_generate_feedback_all_passed(self, scorer):
        """Test feedback when all tests pass"""
        feedback = scorer.generate_feedback(
            flash_score=100,
            llm_score=100,
            test_results=[
                {"name": "Test 1", "passed": True},
                {"name": "Test 2", "passed": True}
            ],
            llm_feedback="Perfect solution!",
            requirements_check=[
                {"requirement": "CRUD", "satisfied": True}
            ]
        )
        
        assert "100/100" in feedback
        assert "Passed: 2/2" in feedback

    def test_generate_feedback_all_failed(self, scorer):
        """Test feedback when all tests fail"""
        feedback = scorer.generate_feedback(
            flash_score=0,
            llm_score=50,
            test_results=[
                {"name": "Test 1", "passed": False, "error": "Error 1"},
                {"name": "Test 2", "passed": False, "error": "Error 2"}
            ],
            llm_feedback="Needs improvement",
            requirements_check=[]
        )
        
        assert "0/100" in feedback
        assert "50/100" in feedback
        assert "Error 1" in feedback
        assert "Error 2" in feedback

    @pytest.mark.asyncio
    async def test_weighted_score_calculation(self, scorer):
        """Test that final score is correctly weighted"""
        flash_score = 100
        llm_score = 0
        expected_final = 100 * 0.7 + 0 * 0.3
        
        session_mock = MagicMock()
        session_mock.submit.return_value = MagicMock(submission_id="sub-1")
        session_mock.wait_for_score.return_value = MagicMock(
            score=flash_score,
            max_score=100,
            status="completed"
        )
        scorer.flash_client.assessments.get_session.return_value = session_mock
        
        mock_module = MagicMock()
        mock_module.evaluate_submission = AsyncMock(return_value={"score": llm_score, "feedback": "", "requirements_check": []})
        
        with patch.dict('sys.modules', {'app.routes.evaluation.routes': mock_module}):
            result = await scorer.score_submission(
                session_id="s1",
                test_data={},
                files={},
                chat_history=[],
                auth_token="t"
            )
        
        assert result["final_score"] == expected_final

    @pytest.mark.asyncio
    async def test_score_submission_with_empty_files(self, scorer):
        """Test scoring with empty files"""
        session_mock = MagicMock()
        session_mock.submit.return_value = MagicMock(submission_id="sub-1")
        session_mock.wait_for_score.return_value = MagicMock(score=0, max_score=100, status="completed")
        scorer.flash_client.assessments.get_session.return_value = session_mock
        
        mock_module = MagicMock()
        mock_module.evaluate_submission = AsyncMock(return_value={"score": 0, "feedback": "", "requirements_check": []})
        
        with patch.dict('sys.modules', {'app.routes.evaluation.routes': mock_module}):
            result = await scorer.score_submission(
                session_id="s1",
                test_data={},
                files={},
                chat_history=[],
                auth_token="t"
            )
        
        assert result["final_score"] == 0


class TestHybridScorerWeights:
    """Tests for weight configuration"""

    def test_default_weights(self):
        """Test default weight configuration"""
        with patch.dict(os.environ, {}, clear=True):
            with patch("app.services.hybrid_scorer.flash_client"):
                scorer = HybridScorer()
                assert scorer.flash_weight == 0.7
                assert scorer.llm_weight == 0.3

    def test_custom_weights_must_sum_to_one(self):
        """Test that weights can be customized"""
        with patch.dict(os.environ, {"FLASH_SCORE_WEIGHT": "0.6", "LLM_SCORE_WEIGHT": "0.4"}):
            with patch("app.services.hybrid_scorer.flash_client"):
                scorer = HybridScorer()
                assert scorer.flash_weight == 0.6
                assert scorer.llm_weight == 0.4

    def test_equal_weights(self):
        """Test equal weight distribution"""
        with patch.dict(os.environ, {"FLASH_SCORE_WEIGHT": "0.5", "LLM_SCORE_WEIGHT": "0.5"}):
            with patch("app.services.hybrid_scorer.flash_client"):
                scorer = HybridScorer()
                assert scorer.flash_weight == 0.5
                assert scorer.llm_weight == 0.5