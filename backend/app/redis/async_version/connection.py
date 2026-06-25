from redis import Redis
from redis.asyncio import Redis as AsyncRedis
import app.config
from redis.asyncio import BlockingConnectionPool , ConnectionPool
redis_host = app.config.REDIS_HOST 
redis_port = app.config.REDIS_PORT

redis_pool = BlockingConnectionPool(max_connections=20 , host=redis_host , port=redis_port , timeout=None ,decode_responses=True)

def get_redis_client():
    return redis_client

def get_redis_client_async() : 
    return AsyncRedis(connection_pool=redis_pool , decode_responses=True)

def get_new_connection_client_redis(db=0,decode_response=False) : 
    return Redis(host=redis_host, port=redis_port, decode_responses=decode_response , db=db ,)
