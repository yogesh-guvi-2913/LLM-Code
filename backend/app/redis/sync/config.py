from redis import Redis 
import app.config as config
import os

_redis_url = os.getenv("REDIS_URL")

if _redis_url:
    redis_conn = Redis.from_url(_redis_url, decode_responses=True)
    redis_conn_without_decoder = Redis.from_url(_redis_url)
else:
    host = config.REDIS_HOST
    port = int(config.REDIS_PORT)
    redis_conn = Redis(host=host, port=port, decode_responses=True)
    redis_conn_without_decoder = Redis(host=host, port=port)

def get_redis_object() : 
    return redis_conn

def get_redis_object_without_decoder() : 
    return redis_conn_without_decoder