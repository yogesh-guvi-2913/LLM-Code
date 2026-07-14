from fastapi import APIRouter, HTTPException
import logging
import time
from app.routes.admin.model import *
from app.mongodb.sync.mongo import MongoDB
from app.redis.sync.rediscache import RedisCache

logger = logging.getLogger(__name__)

router = APIRouter()

def validate_admin_token(auth_token: str) -> dict:
    redis_cache = RedisCache()
    user_data = redis_cache.getAllData(auth_token)
    if not user_data or 'hash' not in user_data:
        raise HTTPException(status_code=401, detail="token_expired")
    if user_data.get('role') not in ['admin', 'instructor']:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user_data

@router.post('/admin/testEndpoint')
def testEndpoint(requestBody: TestEndpointRequestModel):
    requestBody = requestBody.model_dump()
    return {"message": "testEndpoint endpoint is under construction", "receivedData": requestBody}

@router.get('/admin/tests')
def get_all_tests(authToken: str):
    user_data = validate_admin_token(authToken)
    
    try:
        mongo = MongoDB()
        mongo.selectCollection("tests")
        tests = mongo.find({}, projection={'_id': 0, 'testId': 1, 'name': 1, 'description': 1, 'duration': 1})
        
        return {
            "success": True,
            "tests": tests
        }
    except Exception as e:
        logger.error(f"Error fetching tests: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch tests")

@router.get('/admin/users')
def get_all_users(authToken: str):
    user_data = validate_admin_token(authToken)
    
    try:
        mongo = MongoDB()
        mongo.selectCollection("users")
        users = mongo.find(
            {"active": True}, 
            projection={'_id': 0, 'hash': 1, 'name': 1, 'email': 1, 'role': 1}
        )
        
        return {
            "success": True,
            "users": users
        }
    except Exception as e:
        logger.error(f"Error fetching users: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch users")

@router.get('/admin/test-mapper/{testId}')
def get_test_mappings(testId: str, authToken: str):
    user_data = validate_admin_token(authToken)
    
    try:
        mongo = MongoDB()
        mongo.selectCollection("test-mapper")
        mappings = mongo.find({"testId": testId}, projection={'_id': 0, 'hash': 1, 'assignedAt': 1})
        
        return {
            "success": True,
            "mappings": mappings
        }
    except Exception as e:
        logger.error(f"Error fetching test mappings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch test mappings")

@router.post('/admin/test-mapper')
def assign_test_to_users(requestBody: TestMapperRequestModel):
    user_data = validate_admin_token(requestBody.authToken)
    admin_hash = user_data.get('hash')
    current_time = int(time.time() * 1000)
    
    try:
        mongo = MongoDB()
        mongo.selectCollection("test-mapper")
        
        existing_mappings = mongo.find(
            {"testId": requestBody.testId, "hash": {"$in": requestBody.userHashes}},
            projection={'hash': 1}
        )
        existing_hashes = [m.get('hash') for m in existing_mappings]
        
        new_mappings = []
        for user_hash in requestBody.userHashes:
            if user_hash not in existing_hashes:
                new_mappings.append({
                    "testId": requestBody.testId,
                    "hash": user_hash,
                    "assignedAt": current_time,
                    "assignedBy": admin_hash
                })
        
        if new_mappings:
            mongo.insertMany(new_mappings)
        
        return {
            "success": True,
            "message": f"Assigned test to {len(new_mappings)} new users",
            "assignedCount": len(new_mappings),
            "skippedCount": len(existing_hashes)
        }
    except Exception as e:
        logger.error(f"Error assigning test: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to assign test")

@router.delete('/admin/test-mapper')
def remove_test_mapping(requestBody: RemoveTestMapperRequestModel):
    user_data = validate_admin_token(requestBody.authToken)
    
    try:
        mongo = MongoDB()
        mongo.selectCollection("test-mapper")
        
        result = mongo.deleteOne({
            "testId": requestBody.testId,
            "hash": requestBody.userHash
        })
        
        if result.deleted_count > 0:
            return {
                "success": True,
                "message": "Test mapping removed successfully"
            }
        else:
            return {
                "success": False,
                "message": "Mapping not found"
            }
    except Exception as e:
        logger.error(f"Error removing test mapping: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to remove test mapping")

@router.get('/admin/user-test-mappings/{userHash}')
def get_user_test_mappings(userHash: str, authToken: str):
    user_data = validate_admin_token(authToken)
    
    try:
        mongo = MongoDB()
        mongo.selectCollection("test-mapper")
        mappings = mongo.find({"hash": userHash}, projection={'_id': 0, 'testId': 1, 'assignedAt': 1})
        
        return {
            "success": True,
            "mappings": mappings
        }
    except Exception as e:
        logger.error(f"Error fetching user test mappings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch user test mappings")