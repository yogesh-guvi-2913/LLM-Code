from redis import Redis 
import app.config as config

host = config.REDIS_HOST
port = int(config.REDIS_PORT)

redis_conn = Redis(host=host,port=port, decode_responses=True)
redis_conn_without_decoder = Redis(host=host ,port=port)
def get_redis_object() : 
    return redis_conn

def get_redis_object_without_decoder() : 
    return redis_conn_without_decoder