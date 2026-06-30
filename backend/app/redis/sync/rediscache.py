import json
from app.redis.sync.config import get_redis_object

class RedisCache:
    def __init__(self):
        self.connection = get_redis_object()
    
    def getValue(self, redisKey: str):
        outputValue = self.connection.get(redisKey)
        return outputValue or False

    def setValue(self, redisKey: str, redisValue: str):
        return self.connection.set(redisKey, redisValue)
    
    def setex(self, redisKey: str, ttl: int, redisValue: str):
        return self.connection.setex(redisKey, ttl, redisValue)
    
    def deleteValue(self, redisKey: str):
        return self.connection.delete(redisKey)
    
    def deleteMultipleValues(self, redisKeys: list):
        return self.connection.delete(*redisKeys)
    
    def getData(self, redisKey: str, redisObjectKey: str):
        return self.connection.hget(redisKey, redisObjectKey)
    
    def setData(self, redisKey: str, key : str = None, stringValue: str = None, listValue : list = None, dictValue : dict = None):
        return self.connection.hset(redisKey, key, value = stringValue, mapping = dictValue, items = listValue)
    
    def getAllData(self, redisKey : str):
        return self.connection.hgetall(redisKey)
    
    def deleteData(self, redisKey: str, redisObjectKey: str):
        return self.connection.hdel(redisKey, redisObjectKey)
            
    def checkKeyExists(self, redisKey: str):
        return self.connection.exists(redisKey)
    
    def expireKey(self, redisKey: str, timeInSeconds: int):
        return self.connection.expire(redisKey, timeInSeconds)

    def getExpireTime(self, redisKey: str):
        return self.connection.ttl(redisKey)
    
    def incrementData(self, redisKey: str, redisObjectKey: str, incrementBy: int = 1):
        return self.connection.hincrby(redisKey, redisObjectKey, incrementBy)
    
    def incrementValue(self, redisKey: str, incrementBy: int = 1):
        return self.connection.incrby(redisKey, incrementBy)
    
    def acquireLock(self, redisKey: str, timeout: int = 180, blocking: bool = False, blockingTimeout: int = None):
        lock = self.connection.lock(redisKey, timeout=timeout)
        acquired = lock.acquire(blocking=blocking, blocking_timeout=blockingTimeout)
        return lock if acquired else False

    def releaseLock(self, lock):
        try:
            lock.release()
        except:
            pass