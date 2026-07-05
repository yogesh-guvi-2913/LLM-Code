import os
import sys
import pytest
import redis
from pymongo import MongoClient
from datetime import datetime
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

FLASH_E2E_ENABLED = os.getenv("FLASH_E2E", "0") == "1"

LIVE_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
LIVE_MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/llmcode")


@pytest.fixture(scope="module")
def live_redis():
    if not FLASH_E2E_ENABLED:
        pytest.skip("FLASH_E2E=1 not set")
    
    client = redis.from_url(LIVE_REDIS_URL, decode_responses=True)
    yield client
    
    test_tokens = [k for k in client.scan_iter(match="e2e-test-token-*")]
    if test_tokens:
        client.delete(*test_tokens)


@pytest.fixture(scope="module")
def live_mongo():
    if not FLASH_E2E_ENABLED:
        pytest.skip("FLASH_E2E=1 not set")
    
    client = MongoClient(LIVE_MONGO_URI)
    db_name = LIVE_MONGO_URI.split("/")[-1].split("?")[0]
    db = client[db_name]
    yield db
    
    db.test_mapper.delete_many({"hash": {"$regex": "^e2e-test-"}})
    db.tests.delete_many({"testId": {"$regex": "^e2e-test-"}})
    client.close()


@pytest.fixture(scope="module")
def live_test_data(live_mongo):
    if not FLASH_E2E_ENABLED:
        pytest.skip("FLASH_E2E=1 not set")
    
    test_id = f"e2e-test-{uuid.uuid4().hex[:8]}"
    test_doc = {
        "testId": test_id,
        "name": "E2E Test Express API",
        "description": "Build a RESTful CRUD API",
        "testType": "coding",
        "difficulty": "easy",
        "duration": 30,
        "flashTemplateId": "q1",
        "flashTemplateRegistered": True,
        "requirements": [
            {"id": "req-1", "description": "Implement GET /api/items", "weight": 25},
            {"id": "req-2", "description": "Implement POST /api/items", "weight": 25},
            {"id": "req-3", "description": "Handle errors", "weight": 50},
        ],
        "scoringConfig": {
            "method": "hybrid",
            "flashWeight": 0.7,
            "llmWeight": 0.3
        }
    }
    
    live_mongo.tests.insert_one(test_doc)
    yield test_id, test_doc
    
    live_mongo.tests.delete_one({"testId": test_id})


@pytest.fixture
def live_auth_token(live_redis):
    if not FLASH_E2E_ENABLED:
        pytest.skip("FLASH_E2E=1 not set")
    
    token = f"e2e-test-token-{uuid.uuid4().hex[:8]}"
    user_hash = f"e2e-test-user-{uuid.uuid4().hex[:8]}"
    
    live_redis.hset(token, mapping={
        "hash": user_hash,
        "email": f"e2e-test-{uuid.uuid4().hex[:8]}@example.com"
    })
    
    yield token, user_hash
    
    live_redis.delete(token)


@pytest.fixture
def live_sandbox(live_auth_token, live_test_data):
    if not FLASH_E2E_ENABLED:
        pytest.skip("FLASH_E2E=1 not set")
    
    from fastapi.testclient import TestClient
    from app.main import app
    
    token, user_hash = live_auth_token
    test_id, _ = live_test_data
    
    client = TestClient(app)
    
    start_response = client.post(
        "/flash/start",
        headers={"Authorization": f"Bearer {token}"},
        json={"testId": test_id}
    )
    
    if start_response.status_code != 200:
        pytest.fail(f"Failed to start sandbox: {start_response.json()}")
    
    sandbox_data = start_response.json()
    sandbox_id = sandbox_data.get("sandboxId") or sandbox_data.get("sessionId")
    
    yield {
        "client": client,
        "token": token,
        "user_hash": user_hash,
        "test_id": test_id,
        "sandbox_id": sandbox_id,
        "sandbox_data": sandbox_data
    }
    
    try:
        client.post(
            "/flash/stop",
            headers={"Authorization": f"Bearer {token}"},
            json={"testId": test_id}
        )
    except Exception:
        pass