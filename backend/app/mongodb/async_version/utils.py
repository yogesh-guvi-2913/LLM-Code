
from motor.motor_asyncio import AsyncIOMotorClient 

from app.utils.common import my_print
import app.config as config
database_name = config.MONGO_DB

class MyMongoClient : 
    @staticmethod
    async def insert_one(collection_name , document) : 
        client = AsyncIOMotorClient(config.MONGO_URI)
        db = client[database_name]
        collection = db[collection_name]
        try : 
            await collection.insert_one(document)
        except Exception as e : 
            my_print(str(e))
        finally :
            client.close()

    @staticmethod
    async def find_one(collection_name , query , projection=None) : 
        client = AsyncIOMotorClient(config.MONGO_URI)
        db = client[database_name]
        collection = db[collection_name]
        try : 
            return await collection.find_one(query , projection=projection)
        except Exception as e : 
            my_print(str(e))
        finally :
            client.close()

    @staticmethod
    async def find(collection_name , query , projection=None) : 
        client = AsyncIOMotorClient(config.MONGO_URI)
        db = client[database_name]
        collection = db[collection_name]
        try : 
            cursor = collection.find(query , projection=projection)
            async for document in cursor : 
                yield document
            
        except Exception as e : 
            my_print(str(e))
        finally :
            client.close()

    @staticmethod
    async def update_one(collection_name , query , update , upsert=False) : 
        client = AsyncIOMotorClient(config.MONGO_URI)
        db = client[database_name]
        collection = db[collection_name]
        try : 
            await collection.update_one(query , update , upsert=upsert)
        except Exception as e : 
            my_print(str(e))
        finally :
            client.close()

    @staticmethod
    async def bulk_write(collection_name , operations) : 
        client = AsyncIOMotorClient(config.MONGO_URI)
        db = client[database_name]
        collection = db[collection_name]
        try : 
            await collection.bulk_write(operations)
        except Exception as e : 
            my_print(str(e))
        finally :
            client.close()

    @staticmethod
    async def delete_db() : 
        client = AsyncIOMotorClient(config.MONGO_URI) 
        await client.drop_database(database_name)