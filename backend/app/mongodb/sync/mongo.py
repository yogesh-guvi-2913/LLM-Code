import logging
from app.mongodb.sync.config import get_mongo_client
from app.config import MONGO_DB
from pymongo import UpdateOne

logger = logging.getLogger(__name__)

class MongoDB:

    def __init__(self):
        self.connection = get_mongo_client()
        self.dbName = MONGO_DB
        self.collectionName = None
        self.cursor = None
    
    def selectDB(self, db : str = MONGO_DB):
        self.dbName = db
        return self.connection[db]
    
    def selectCollection(self, collection : str = None):
        if (collection == None): return False
        self.collectionName = collection
        self.cursor = self.connection[self.dbName][collection]
        return self.cursor
    
    def getAvailableDataBase(self):
        return self.connection.list_database_names()
    
    def getAvailableDataBase(self):
        return self.connection.list_database_names()

    def insertOne(self, document : dict | None = None):
        if (document == None): return False
        return self.cursor.insert_one(document)
    
    def insertMany(self, documents : list | None = None):
        if (documents == None): return False
        return self.cursor.insert_many(documents)
    
    def find(self, query : dict = {}, projection : dict = {'_id': 0}, limit : int | None = None, sort : list | None = None, skip : int | None = None):
        cursorObject = self.cursor.find(query, projection)
        if (sort != None):
            cursorObject.sort(sort[0], sort[1])
        if (limit != None):
            cursorObject.limit(limit)
        if (skip != None):
            cursorObject.skip(skip)
        return [obj for obj in cursorObject]

    def findNew(
        self,
        query: dict = {},
        projection: dict = {'_id': 0},
        limit: int | None = None,
        sort: list | None = None,
        skip: int | None = None
    ):
        cursorObject = self.cursor.find(query, projection)

        # ✅ Proper multi-field OR single-field support
        if sort is not None:
            if isinstance(sort[0], tuple):
                # Multi-field sort
                cursorObject = cursorObject.sort(sort)
            else:
                # Single-field sort
                cursorObject = cursorObject.sort(sort[0], sort[1])

        if skip is not None:
            cursorObject = cursorObject.skip(skip)

        if limit is not None:
            cursorObject = cursorObject.limit(limit)

        return [obj for obj in cursorObject]
    
    def count(self, query : dict = {}):
        return self.cursor.count_documents(query)
    
    def updateOne(self, query : dict | list | None = None, values : dict = {}, upsert = False):
        if (query == None): return False
        return self.cursor.update_one(query, values, upsert)
    
    def updateMany(self, query : dict | list | None = None, values : dict = {}, upsert = False):
        if (query == None): return False
        return self.cursor.update_many(query, values, upsert)
    
    def delete(self, query : dict = {}):
        return self.cursor.delete_many(query)
    
    def aggregate(self, query : list | None = None):
        if (query == None): return False
        cursorObject = self.cursor.aggregate(query)
        return [obj for obj in cursorObject]
    
    def aggregateWithWrite(self, query : list | None = None):
        if (query == None): return False
        list(self.cursor.aggregate(query))
        return True
    
    def ensureUniqueIndex(self, fields: list | None = None):
        if fields is None:
            return False
        try:
            # Create a list of tuples for the index key
            index_key = [(field, 1) for field in fields]
            self.cursor.create_index(index_key, unique=True)
            return True
        except Exception as e:
            logger.error(f"Error creating unique index on fields {fields}: {str(e)}")
            return False

    def distinct(self, field : str = '', query : dict = {}, onlyCount = False):
        if (field == ''): return False
        if (onlyCount):
            return len(self.cursor.distinct(field, query))
        else:
            return self.cursor.distinct(field, query)
        
    def collectionExists(self, collectionName: str = None) -> bool:
        if collectionName is None:
            return False
            
        return collectionName in self.connection[self.dbName].list_collection_names()
        
    def createCollection(self, collectionName: str = None):
        if collectionName is None:
            return False
        try:
            collection = self.connection[self.dbName].create_collection(collectionName)
            return collection.name == collectionName
        except Exception as e:
            return False
        
    def bulkWrite(self, documents, uniqueFields):
        try:
            if isinstance(uniqueFields, str):
                uniqueFields = [uniqueFields]

            update_operations = [
                UpdateOne(
                    {field: doc[field] for field in uniqueFields if field in doc},
                    {'$set': doc},
                    upsert=True
                )
                for doc in documents
            ]
            return self.cursor.bulk_write(update_operations)
        except Exception as e:
            logger.error(f"Error in bulk write: {str(e)}")
            return False

    def findOneAndUpdate(self, query: dict = None, update: dict = None, upsert: bool = False, returnDocument: str = 'after'):
        """
        Find a document and update it atomically.

        Args:
            query: Filter to find the document
            update: Update operations (e.g., {'$inc': {'seq': 1}}, {'$set': {'status': 'active'}})
            upsert: Create document if not found
            returnDocument: 'after' (default) or 'before' - whether to return the updated or original document

        Returns:
            The document (before or after update) or None
        """
        if query is None or update is None:
            return False

        from pymongo import ReturnDocument
        return_doc = ReturnDocument.AFTER if returnDocument == 'after' else ReturnDocument.BEFORE

        return self.cursor.find_one_and_update(
            query,
            update,
            upsert=upsert,
            return_document=return_doc
        )
