from fastapi import APIRouter, HTTPException
import logging
import time
from app.routes.auth.model import *
from app.utils.auth_utils import validate_email, validate_password, hash_password, sha512_hash
from app.postgresql.sync.config import get_postgres_connection, release_postgres_connection
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
    connection = None
    cursor = None

    try:
        connection = get_postgres_connection()
        cursor = connection.cursor()

        query = 'SELECT id FROM "users" WHERE email = %s'
        cursor.execute(query, (email,))
        result = cursor.fetchone()

        return result is not None

    except Exception as e:
        logger.error(f"Error checking user existence: {str(e)}")
        raise
    finally:
        if cursor:
            cursor.close()
        if connection:
            release_postgres_connection(connection)

def create_user(name: str, email: str, password: str) -> dict:
    """Create new user in database"""
    connection = None
    cursor = None

    try:
        connection = get_postgres_connection()
        cursor = connection.cursor()

        email_hash = sha512_hash(email)
        password_hash = hash_password(password)
        current_time = int(time.time() * 1000)

        query = '''
            INSERT INTO "users" (name, email, hash, password, role, active, "createdAt")
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id, name, email, role
        '''

        cursor.execute(query, (name, email, email_hash, password_hash, 'user', 'true', current_time))
        result = cursor.fetchone()
        connection.commit()

        return {
            'id': result[0],
            'name': result[1],
            'email': result[2],
            'role': result[3]
        }

    except Exception as e:
        if connection:
            connection.rollback()
        logger.error(f"Error creating user: {str(e)}")
        raise
    finally:
        if cursor:
            cursor.close()
        if connection:
            release_postgres_connection(connection)

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

    connection = None
    cursor = None

    try:
        connection = get_postgres_connection()
        cursor = connection.cursor()

        # Check if user exists by email
        query = 'SELECT id, name, email, hash, password, role, active FROM "users" WHERE email = %s'
        cursor.execute(query, (requestBody.email,))
        result = cursor.fetchone()

        if not result:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        user_id, name, email, user_hash, stored_password, role, active = result

        # Verify password
        input_password_hash = hash_password(requestBody.password)
        if input_password_hash != stored_password:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Check if user is active
        if active != 'true':
            raise HTTPException(status_code=403, detail="Account is not active")

        # Generate auth token using sha512(email + currentTime)
        current_time = int(time.time() * 1000)
        auth_token = sha512_hash(f"{email}:{current_time}")

        # Store session in Redis using HSET with key = authToken
        redis_cache = RedisCache()
        logger.info(f"Storing Redis session for token: {auth_token[:10]}...")
        redis_cache.setData(
            redisKey=auth_token,
            dictValue={
                'email': email,
                'hash': user_hash,
                'name': name,
                'role': role
            }
        )
        logger.info(f"Redis data set, setting expiry to 30 days")
        redis_cache.expireKey(auth_token, 2592000)  # Set expiry to 30 days
        logger.info(f"Redis expiry set successfully")

        # Update last login time
        update_query = 'UPDATE "users" SET "lastLoginAt" = %s WHERE id = %s'
        cursor.execute(update_query, (current_time, user_id))
        connection.commit()

        logger.info(f"User logged in successfully: {email}")

        return {
            "success": True,
            "status": "success",
            "authToken": auth_token,
            "name": name,
            "email": email,
            "role": role
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during login: {str(e)}")
        raise HTTPException(status_code=500, detail="Login failed. Please try again.")
    finally:
        if cursor:
            cursor.close()
        if connection:
            release_postgres_connection(connection)