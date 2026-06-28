from fastapi import APIRouter, HTTPException
import logging
from app.mongodb.sync.mongo import MongoDB
from app.redis.sync.rediscache import RedisCache
from app.routes.dashboard.model import *

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post('/dashboard')
def get_dashboard_data(requestBody: DashboardRequestModel):
    """Get dashboard data including available tests for authenticated user"""
    auth_token = requestBody.authToken

    if not auth_token:
        raise HTTPException(status_code=400, detail="authToken is required")

    # Step 1: Validate authToken in Redis
    redis_cache = RedisCache()

    # Step 2: Get user data from Redis (including hash)
    user_data = redis_cache.getAllData(auth_token)
    if not user_data or 'hash' not in user_data:
        logger.warning(f"Token not found in Redis: {auth_token[:10]}...")
        raise HTTPException(status_code=401, detail="token_expired")

    # Decode bytes to string for hash
    user_hash = user_data['hash']

    logger.info(f"Getting dashboard data for user hash: {user_hash[:10]}...")

    try:
        mongo = MongoDB()

        # Step 3: Query test-mapper collection for hash and active=1
        mongo.selectCollection("test-mapper")
        test_mapper_query = {
            "hash": user_hash
        }
        test_mapper_results = mongo.find(test_mapper_query, projection={'_id': 0, 'testId': 1})

        if not test_mapper_results:
            logger.info(f"No active tests found for user hash: {user_hash[:10]}...")
            return {
                "success": True,
                "tests": []
            }

        logger.info(f"Found {len(test_mapper_results)} test mappings for user")

        # Step 4: For each testId, query tests collection
        tests_list = []
        test_ids = [tm.get('testId') for tm in test_mapper_results if tm.get('testId')]

        if test_ids:
            mongo.selectCollection("tests")
            tests_query = {
                "testId": {"$in": test_ids}
            }
            tests_results = mongo.find(tests_query, projection={'_id': 0})

            # Create a dictionary for quick lookup
            tests_dict = {test.get('testId'): test for test in tests_results}

            # Build the tests list
            for test_id in test_ids:
                if test_id in tests_dict:
                    test_data = tests_dict[test_id]
                    tests_list.append({
                        "problemTitle": test_data.get('name'),
                        "problemDescription": test_data.get('description'),
                        "problemDetails": test_data.get('details'),
                        "testId": test_id,
                        "status": "Available"
                    })

        logger.info(f"Returning {len(tests_list)} tests for user")

        return {
            "success": True,
            "tests": tests_list
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dashboard data: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve dashboard data")

@router.post('/test-details')
def get_test_details(requestBody: dict):
    """Get test details including questions for a specific test"""
    auth_token = requestBody.get('authToken')
    test_id = requestBody.get('testId')

    if not auth_token:
        raise HTTPException(status_code=400, detail="authToken is required")

    if not test_id:
        raise HTTPException(status_code=400, detail="testId is required")

    # Step 1: Validate authToken in Redis
    redis_cache = RedisCache()
    user_data = redis_cache.getAllData(auth_token)
    if not user_data or 'hash' not in user_data:
        logger.warning(f"Token not found in Redis: {auth_token[:10]}...")
        raise HTTPException(status_code=401, detail="token_expired")

    user_hash = user_data['hash']
    logger.info(f"Getting test details for testId: {test_id}, user hash: {user_hash[:10]}...")

    try:
        mongo = MongoDB()

        # Step 2: Verify user has access to this test via test-mapper
        mongo.selectCollection("test-mapper")
        test_mapper_query = {
            "hash": user_hash,
            "testId": test_id
        }
        test_mapper_result = mongo.find(test_mapper_query, limit=1)

        if not test_mapper_result:
            logger.warning(f"User does not have access to testId: {test_id}")
            raise HTTPException(status_code=403, detail="You do not have access to this test")

        # Step 3: Get test details from tests collection
        mongo.selectCollection("tests")
        test_query = {
            "testId": test_id
        }
        test_results = mongo.find(test_query, limit=1)

        if not test_results:
            logger.error(f"Test not found with testId: {test_id}")
            raise HTTPException(status_code=404, detail="Test not found")

        test_data = test_results[0]

        logger.info(f"Returning test details for testId: {test_id}")

        return {
            "success": True,
            "test": {
                "testId": test_data.get('testId'),
                "name": test_data.get('name'),
                "description": test_data.get('description'),
                "details": test_data.get('details'),
                "questions": test_data.get('questions', []),
                "codeEdit": test_data.get('codeEdit', 0),
                "duration": test_data.get('duration', 1800),
                "initialFiles": test_data.get('initialFiles', None),
                "evaluationCriteria": test_data.get('evaluationCriteria', None)
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting test details: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve test details")