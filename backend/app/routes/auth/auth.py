from fastapi import APIRouter, HTTPException
import logging
import time
from app.routes.auth.model import *
from app.utils.auth_utils import validate_email, validate_password, hash_password, sha512_hash
from app.mongodb.sync.mongo import MongoDB
from app.redis.sync.rediscache import RedisCache
from app.config import TOKEN_SALT
import uuid

logger = logging.getLogger(__name__)

router = APIRouter()

def generate_auth_token(email: str) -> str:
    """Generate authentication token"""
    token_data = f"{email}:{time.time()}:{str(uuid.uuid4())}"
    if TOKEN_SALT:
        token_data += f":{TOKEN_SALT}"
    return sha512_hash(token_data)

def check_user_exists(email: str) -> bool:
    """Check if user already exists in database"""
    try:
        mongo = MongoDB()
        mongo.selectCollection("users")

        query = {"email": email}
        result = mongo.find(query, projection={'_id': 1}, limit=1)

        return len(result) > 0

    except Exception as e:
        logger.error(f"Error checking user existence: {str(e)}")
        raise

def create_user(name: str, email: str, password: str) -> dict:
    """Create new user in database"""
    try:
        mongo = MongoDB()
        mongo.selectCollection("users")

        email_hash = sha512_hash(email)
        password_hash = hash_password(password)
        current_time = int(time.time() * 1000)

        user_doc = {
            "name": name,
            "email": email,
            "hash": email_hash,
            "password": password_hash,
            "role": "user",
            "active": True,
            "createdAt": current_time,
            "lastLoginAt": None
        }

        result = mongo.insertOne(user_doc)
        if result.inserted_id:
            return {
                'id': str(result.inserted_id),
                'name': name,
                'email': email,
                'role': 'user'
            }

    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        raise

@router.post('/register')
def register(requestBody: RegisterRequestModel):
    """Register new user"""
    logger.info(f"Received registration request for email: {requestBody.email}")

    # Validate email
    if not validate_email(requestBody.email):
        raise HTTPException(status_code=400, detail="Invalid email format")

    # Validate password
    is_valid, error_msg = validate_password(requestBody.password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    # Check if user already exists
    if check_user_exists(requestBody.email):
        raise HTTPException(status_code=400, detail="User already exists with this email")

    # Create user
    try:
        user = create_user(requestBody.name, requestBody.email, requestBody.password)

        logger.info(f"User registered successfully: {requestBody.email}")

        return {
            "success": True,
            "message": "User registered successfully",
            "user": user
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during registration: {str(e)}")
        raise HTTPException(status_code=500, detail="Registration failed. Please try again.")

@router.post('/login')
def login(requestBody: LoginRequestModel):
    """Login user"""
    logger.info(f"Received login request for email: {requestBody.email}")

    # Validate email
    if not validate_email(requestBody.email):
        raise HTTPException(status_code=400, detail="Invalid email format")

    try:
        mongo = MongoDB()
        mongo.selectCollection("users")

        # Check if user exists by email
        query = {"email": requestBody.email}
        result = mongo.find(query, projection={'_id': 1, 'name': 1, 'email': 1, 'hash': 1, 'password': 1, 'role': 1, 'active': 1}, limit=1)

        if not result:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        user = result[0]

        # Verify password
        input_password_hash = hash_password(requestBody.password)
        if input_password_hash != user.get('password'):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Check if user is active
        if not user.get('active'):
            raise HTTPException(status_code=403, detail="Account is not active")

        # Generate auth token using sha512(email + currentTime)
        current_time = int(time.time() * 1000)
        auth_token = sha512_hash(f"{user.get('email')}:{current_time}")

        # Store session in Redis using HSET with key = authToken
        redis_cache = RedisCache()
        logger.info(f"Storing Redis session for token: {auth_token[:10]}...")
        redis_cache.setData(
            redisKey=auth_token,
            dictValue={
                'email': user.get('email'),
                'hash': user.get('hash'),
                'name': user.get('name'),
                'role': user.get('role')
            }
        )
        logger.info(f"Redis data set, setting expiry to 30 days")
        redis_cache.expireKey(auth_token, 2592000)  # Set expiry to 30 days
        logger.info(f"Redis expiry set successfully")

        # Update last login time
        mongo.updateOne(
            query={"_id": user.get('_id')},
            values={"$set": {"lastLoginAt": current_time}}
        )

        logger.info(f"User logged in successfully: {user.get('email')}")

        return {
            "success": True,
            "status": "success",
            "authToken": auth_token,
            "name": user.get('name'),
            "email": user.get('email'),
            "role": user.get('role')
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during login: {str(e)}")
        raise HTTPException(status_code=500, detail="Login failed. Please try again.")

@router.post('/logout')
def logout(requestBody: LogoutRequestModel):
    """Logout user by invalidating auth token"""
    logger.info(f"Received logout request for token: {requestBody.authToken[:10]}...")

    try:
        redis_cache = RedisCache()

        # Check if token exists in Redis
        token_exists = redis_cache.checkKeyExists(requestBody.authToken)
        logger.info(f"Token exists in Redis: {token_exists}")

        if token_exists:
            # Delete the token from Redis
            redis_cache.deleteValue(requestBody.authToken)
            logger.info(f"Token deleted from Redis successfully")

            return {
                "success": True,
                "message": "Logout successful"
            }
        else:
            logger.warning(f"Token not found in Redis: {requestBody.authToken[:10]}...")
            return {
                "success": True,
                "message": "Logout successful (token was already expired or invalid)"
            }

    except Exception as e:
        logger.error(f"Error during logout: {str(e)}")
        raise HTTPException(status_code=500, detail="Logout failed. Please try again.")