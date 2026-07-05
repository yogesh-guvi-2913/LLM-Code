import asyncio
import os
import sys
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

TEST_MONGO_URI = os.getenv("TEST_MONGO_URI", "mongodb://localhost:27017")
TEST_REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6379")
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/llmcode_test")
TEST_FLASH_URL = os.getenv("TEST_FLASH_URL", "http://127.0.0.1:8090")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    redis = Mock()
    redis.getAllData = Mock(return_value={"hash": "test-user-hash", "email": "test@example.com"})
    redis.setex = Mock(return_value=True)
    redis.get = Mock(return_value=None)
    redis.delete = Mock(return_value=True)
    return redis


@pytest.fixture
def mock_mongo():
    """Mock MongoDB client"""
    mongo = Mock()
    mongo.selectCollection = Mock()
    mongo.find = Mock(return_value=[])
    mongo.findOne = Mock(return_value=None)
    mongo.insertOne = Mock(return_value=Mock(inserted_id="test-id"))
    mongo.updateOne = Mock(return_value=Mock(modified_count=1))
    mongo.deleteOne = Mock(return_value=Mock(deleted_count=1))
    return mongo


@pytest.fixture
def mock_flash_client():
    """Mock Flash client"""
    client = MagicMock()
    
    sandbox = MagicMock()
    sandbox.id = "test-sandbox-id"
    sandbox.app_url = "http://localhost:3000"
    sandbox.preview_url = "http://localhost:3000"
    sandbox.terminal_url = "ws://localhost:8090/v1/sessions/test-sandbox-id/terminal"
    sandbox.run = Mock(return_value=Mock(stdout="ok", stderr="", exit_code=0, duration_ms=100))
    sandbox.files = Mock()
    sandbox.files.read_text = Mock(return_value="file content")
    sandbox.files.write = Mock(return_value=True)
    sandbox.files.list = Mock(return_value=["/app/src/index.js", "/app/package.json"])
    sandbox.kill = Mock()
    
    client.sandboxes = Mock()
    client.sandboxes.create = Mock(return_value=sandbox)
    client.sandboxes.connect = Mock(return_value=sandbox)
    
    assessment = MagicMock()
    assessment.submit = Mock(return_value=Mock(submission_id="test-submission-id"))
    assessment.wait_for_score = Mock(return_value=Mock(score=85, max_score=100, status="completed"))
    
    client.assessments = Mock()
    client.assessments.get_session = Mock(return_value=assessment)
    
    return client, sandbox, assessment


@pytest.fixture
def mock_postgres_pool():
    """Mock PostgreSQL connection pool"""
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="INSERT 0 1")
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    
    pool = AsyncMock()
    pool.acquire = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    
    return pool, conn


@pytest.fixture
def test_user_data():
    """Test user data"""
    return {
        "hash": "test-user-hash-abc123",
        "email": "test@example.com",
        "name": "Test User",
        "role": "candidate"
    }


@pytest.fixture
def test_auth_token():
    """Test auth token"""
    return "test-auth-token-xyz789"


@pytest.fixture
def test_test_data():
    """Test data for a coding test"""
    return {
        "testId": "test-q1-express",
        "name": "Express API Challenge",
        "description": "Build a RESTful CRUD API",
        "testType": "coding",
        "difficulty": "medium",
        "duration": 45,
        "requirements": [
            {"id": "req-1", "description": "Implement GET /api/items", "weight": 20},
            {"id": "req-2", "description": "Implement POST /api/items", "weight": 20},
            {"id": "req-3", "description": "Implement PUT /api/items/:id", "weight": 20},
            {"id": "req-4", "description": "Implement DELETE /api/items/:id", "weight": 20},
            {"id": "req-5", "description": "Handle errors gracefully", "weight": 20},
        ],
        "flashTemplateId": "q1-express-api",
        "flashTemplateRegistered": True,
        "scoringConfig": {
            "method": "hybrid",
            "flashWeight": 0.7,
            "llmWeight": 0.3
        }
    }


@pytest.fixture
def test_session_data():
    """Test session data"""
    return {
        "hash": "test-user-hash-abc123",
        "testId": "test-q1-express",
        "flashSessionId": "test-sandbox-id",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    }


@pytest.fixture
def test_submission_data():
    """Test submission data"""
    return {
        "testId": "test-q1-express",
        "userHash": "test-user-hash-abc123",
        "status": "completed",
        "score": 85,
        "maxScore": 100,
        "flashScore": 90,
        "llmScore": 80,
        "files": {
            "src/index.js": "const express = require('express'); ..."
        },
        "chatHistory": [
            {"role": "user", "content": "How do I create a route?"},
            {"role": "assistant", "content": "Use app.get('/path', handler)"}
        ],
        "promptCount": 2,
        "scoringMethod": "hybrid",
        "submittedAt": datetime.utcnow(),
        "testResults": [
            {"name": "GET /api/items", "passed": True},
            {"name": "POST /api/items", "passed": True},
            {"name": "PUT /api/items/:id", "passed": True},
            {"name": "DELETE /api/items/:id", "passed": False, "error": "Expected 204"}
        ]
    }


@pytest.fixture
def mock_env_flash_enabled():
    """Set environment variables for Flash enabled"""
    env_vars = {
        "SANDBOX_PROVIDER": "flash",
        "FLASH_ROLLOUT_PERCENTAGE": "100",
        "FLASH_BASE_URL": TEST_FLASH_URL,
        "FLASH_SCORE_WEIGHT": "0.7",
        "LLM_SCORE_WEIGHT": "0.3"
    }
    with patch.dict(os.environ, env_vars):
        yield env_vars


@pytest.fixture
def mock_env_legacy():
    """Set environment variables for legacy mode"""
    env_vars = {
        "SANDBOX_PROVIDER": "legacy",
        "FLASH_ROLLOUT_PERCENTAGE": "0",
        "FLASH_BASE_URL": TEST_FLASH_URL,
    }
    with patch.dict(os.environ, env_vars):
        yield env_vars


@pytest.fixture
def mock_env_hybrid():
    """Set environment variables for hybrid rollout"""
    env_vars = {
        "SANDBOX_PROVIDER": "",
        "FLASH_ROLLOUT_PERCENTAGE": "50",
        "FLASH_ROLLOUT_WHITELIST": "whitelist-user-1",
        "FLASH_ROLLOUT_BLACKLIST": "blacklist-user-1",
        "FLASH_BASE_URL": TEST_FLASH_URL,
    }
    with patch.dict(os.environ, env_vars):
        yield env_vars