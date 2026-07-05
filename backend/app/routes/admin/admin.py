from fastapi import APIRouter, HTTPException
import logging
from app.routes.admin.model import (
    TestEndpointRequestModel,
    TestMapperAssignRequest,
    TestMapperRemoveRequest,
    TestMapperListRequest,
)
from app.mongodb.sync.mongo import MongoDB
from app.redis.sync.rediscache import RedisCache

logger = logging.getLogger(__name__)

router = APIRouter()


def _validate_admin_auth(auth_token: str) -> dict:
    if not auth_token:
        raise HTTPException(status_code=400, detail="authToken is required")

    redis = RedisCache()
    user_data = redis.getAllData(auth_token)

    if not user_data or "hash" not in user_data:
        raise HTTPException(status_code=401, detail="token_expired")

    return user_data


def initTestEndpoint(requestBody):
    logger.info(f"Received request for testEndpoint with body: {requestBody}")
    return {"message": "testEndpoint endpoint is under construction", "receivedData": requestBody}


@router.post('/admin/testEndpoint')
def testEndpoint(requestBody: TestEndpointRequestModel):
    requestBody = requestBody.model_dump()
    return initTestEndpoint(requestBody)


@router.post('/admin/test-mapper/list')
def list_test_mappings(request: TestMapperListRequest):
    _validate_admin_auth(request.authToken)

    mongo = MongoDB()
    mongo.selectCollection("test-mapper")

    query = {}
    if request.hash:
        query["hash"] = request.hash
    if request.testId:
        query["testId"] = request.testId

    mappings = mongo.find(query, projection={'_id': 0})

    return {"success": True, "mappings": mappings}


@router.post('/admin/test-mapper/users')
def list_users(requestBody: dict):
    auth_token = requestBody.get("authToken")
    _validate_admin_auth(auth_token)

    mongo = MongoDB()
    mongo.selectCollection("users")

    users = mongo.find(
        {"active": {"$ne": 0}},
        projection={'_id': 0, 'hash': 1, 'email': 1, 'name': 1, 'role': 1}
    )

    return {"success": True, "users": users}


@router.post('/admin/test-mapper/tests')
def list_tests(requestBody: dict):
    auth_token = requestBody.get("authToken")
    _validate_admin_auth(auth_token)

    mongo = MongoDB()
    mongo.selectCollection("tests")

    tests = mongo.find(
        {},
        projection={'_id': 0, 'testId': 1, 'name': 1, 'description': 1, 'duration': 1}
    )

    return {"success": True, "tests": tests}


@router.post('/admin/test-mapper/assign')
def assign_test_to_user(request: TestMapperAssignRequest):
    user_data = _validate_admin_auth(request.authToken)

    mongo = MongoDB()

    mongo.selectCollection("users")
    user = mongo.find({"hash": request.hash}, limit=1)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    mongo.selectCollection("tests")
    test = mongo.find({"testId": request.testId}, limit=1)
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    mongo.selectCollection("test-mapper")
    existing = mongo.find({"hash": request.hash, "testId": request.testId}, limit=1)

    if existing:
        return {"success": True, "message": "Mapping already exists", "existing": True}

    from datetime import datetime
    mapping_doc = {
        "hash": request.hash,
        "testId": request.testId,
        "assignedBy": user_data.get("hash"),
        "assignedAt": datetime.utcnow(),
        "active": 1
    }

    mongo.insertOne(mapping_doc)
    logger.info(f"Assigned test {request.testId} to user {request.hash[:10]}...")

    return {"success": True, "message": "Test assigned to user", "existing": False}


@router.post('/admin/test-mapper/remove')
def remove_test_mapping(request: TestMapperRemoveRequest):
    _validate_admin_auth(request.authToken)

    mongo = MongoDB()
    mongo.selectCollection("test-mapper")

    result = mongo.deleteOne({"hash": request.hash, "testId": request.testId})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Mapping not found")

    logger.info(f"Removed test mapping: {request.testId} from user {request.hash[:10]}...")

    return {"success": True, "message": "Mapping removed"}