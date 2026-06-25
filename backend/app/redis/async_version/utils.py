from app.redis.async_version.connection import get_redis_client_async

class MyRedis : 
    @staticmethod
    async def set(key , value) : 
        redis_client = get_redis_client_async()
        await redis_client.set(key , value)

    @staticmethod
    async def setx(key , time : int, value) : 
        redis_client = get_redis_client_async() 
        await redis_client.setex(key , time , value)
    
    @staticmethod
    async def get(key) : 
        redis_client =  get_redis_client_async()
        return await redis_client.get(key)
    
    @staticmethod
    async def delete(key) : 
        redis_client = get_redis_client_async()
        await redis_client.delete(key)

    @staticmethod
    async def hset(key , field , value) : 
        redis_client = get_redis_client_async()
        await redis_client.hset(key , field , value)

    @staticmethod
    async def hget(key , field) : 
        redis_client = get_redis_client_async()
        return await redis_client.hget(key , field)
    
    @staticmethod
    async def hdel(key , field) : 
        redis_client = get_redis_client_async()
        await redis_client.hdel(key , field)

    @staticmethod
    async def hgetall(key) : 
        redis_client =  get_redis_client_async()
        return await redis_client.hgetall(key)
    
    @staticmethod
    async def hdelall(key) : 
        redis_client =  get_redis_client_async()
        await redis_client.delete(key)

    @staticmethod
    async def hmset(key , values : dict , expire = None) : 
        redis_client = get_redis_client_async() 
        await redis_client.hmset(key , values)
        if expire != None : 
            await redis_client.expire(key , expire)

    @staticmethod
    async def flushAll() : 
        redis_client = get_redis_client_async() 
        await redis_client.flushall()

    @staticmethod
    async def exists(key) : 
        redis_client = get_redis_client_async() 
        await redis_client.exists(key)