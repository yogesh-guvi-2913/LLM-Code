import logging
from app.mongodb.sync.mongo import MongoDB
from app.config import MONGO_DB

logger = logging.getLogger(__name__)


class MongoDBSchema:
    class Users:
        email: str
        hash: str
        password: str
        role: str
        name: str
        active: bool
        createdAt: int
        lastLoginAt: int = None
        imageUrl: str = None
        organization: list = None


MONGO_BLUEPRINT = [
    {
        'collection': 'users',
        'indexes': [
            {'fields': ['email'], 'unique': True},
            {'fields': ['hash'], 'unique': False},
            {'fields': ['role'], 'unique': False},
            {'fields': ['createdAt'], 'unique': False}
        ]
    }
]


def getMongoCollectionBlueprint(collection_name: str):
    for blueprint in MONGO_BLUEPRINT:
        if blueprint['collection'] == collection_name:
            return blueprint
    return None


def initMongoCollections():
    """Initialize MongoDB collections based on blueprints"""
    try:
        mongo = MongoDB()

        for blueprint in MONGO_BLUEPRINT:
            collection_name = blueprint['collection']

            # Create collection if not exists
            if not mongo.collectionExists(collection_name):
                mongo.createCollection(collection_name)
                logger.info(f"Collection {collection_name} created")

        logger.info('MongoDB collections initialized successfully.')

    except Exception as e:
        logger.error(f"Error initializing MongoDB collections: {str(e)}")
        raise


def initMongoIndexes():
    """Initialize MongoDB indexes based on blueprints"""
    try:
        mongo = MongoDB()

        for blueprint in MONGO_BLUEPRINT:
            collection_name = blueprint['collection']
            indexes = blueprint.get('indexes', [])

            mongo.selectCollection(collection_name)

            for index in indexes:
                fields = index['fields']
                unique = index.get('unique', False)

                if unique:
                    mongo.ensureUniqueIndex(fields)
                else:
                    # For non-unique indexes, we'll create them normally
                    try:
                        mongo.cursor.create_index([(field, 1) for field in fields])
                    except Exception as e:
                        logger.warning(f"Could not create index for {fields}: {str(e)}")

            logger.info(f"Indexes created for collection: {collection_name}")

        logger.info('MongoDB indexes initialized successfully.')

    except Exception as e:
        logger.error(f"Error initializing MongoDB indexes: {str(e)}")
        raise


def initMongoSchema():
    """Initialize MongoDB schema with collections and indexes"""
    try:
        initMongoCollections()
        initMongoIndexes()
        logger.info('MongoDB schema initialized successfully.')
    except Exception as e:
        logger.error(f"Error initializing MongoDB schema: {str(e)}")
        raise