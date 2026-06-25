import logging
from typing import Literal, Optional, List, Dict
from app.postgresql.sync.config import get_postgres_connection, release_postgres_connection
from app.config import POSTGRES_DB

logger = logging.getLogger(__name__)


class PostgreSQLSchema:
    class Users:
        email: str
        hash: str
        role: Literal['user', 'admin']
        name: str
        active: Literal['true', 'false']
        createdAt: int
        lastLoginAt: Optional[int] = None
        imageUrl: Optional[str] = None
        organization: Optional[List[str]] = None


POSTGRES_BLUEPRINT = [
    {
        'table': 'users',
        'columns': {
            'id': 'SERIAL PRIMARY KEY',
            'email': 'VARCHAR(255) UNIQUE NOT NULL',
            'hash': 'VARCHAR(255) NOT NULL',
            'role': 'VARCHAR(50) DEFAULT \'user\'',
            'name': 'VARCHAR(255) NOT NULL',
            'active': 'VARCHAR(10) DEFAULT \'true\'',
            'createdAt': 'BIGINT NOT NULL',
            'lastLoginAt': 'BIGINT',
            'imageUrl': 'TEXT',
            'organization': 'JSONB'
        },
        'indexes': [
            {'columns': ['email'], 'unique': True},
            {'columns': ['hash'], 'unique': False},
            {'columns': ['role'], 'unique': False},
            {'columns': ['createdAt'], 'unique': False}
        ],
        'primaryKey': 'id'
    }
]


def getPostgresTableBlueprint(tablename: str):
    for blueprint in POSTGRES_BLUEPRINT:
        if blueprint['table'] == tablename:
            return blueprint
    return None


def initPostgresTables():
    """Initialize PostgreSQL tables based on blueprints"""
    connection = None
    cursor = None

    try:
        connection = get_postgres_connection()
        cursor = connection.cursor()

        for blueprint in POSTGRES_BLUEPRINT:
            table_name = blueprint['table']
            columns = blueprint['columns']

            # Build column definitions
            column_defs = []
            for col_name, col_type in columns.items():
                column_defs.append(f'"{col_name}" {col_type}')

            columns_str = ', '.join(column_defs)

            # Create table if not exists
            create_table_query = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({columns_str})'
            cursor.execute(create_table_query)

            logger.info(f"Table {table_name} created or already exists")

        connection.commit()
        logger.info('PostgreSQL tables created successfully.')

    except Exception as e:
        if connection:
            connection.rollback()
        logger.error(f"Error initializing PostgreSQL tables: {str(e)}")
        raise
    finally:
        if cursor:
            cursor.close()
        if connection:
            release_postgres_connection(connection)


def initPostgresIndexes():
    """Initialize PostgreSQL indexes based on blueprints"""
    connection = None
    cursor = None

    try:
        connection = get_postgres_connection()
        cursor = connection.cursor()

        for blueprint in POSTGRES_BLUEPRINT:
            table_name = blueprint['table']
            indexes = blueprint.get('indexes', [])

            for index in indexes:
                index_name = f"idx_{'_'.join(index['columns'])}"
                if index.get('unique'):
                    index_name += "_unique"

                columns_str = ', '.join(f'"{col}"' for col in index['columns'])

                create_index_query = f"""
                    CREATE INDEX IF NOT EXISTS "{index_name}"
                    ON "{table_name}" ({columns_str})
                """

                if index.get('unique'):
                    create_index_query = f"""
                        CREATE UNIQUE INDEX IF NOT EXISTS "{index_name}"
                        ON "{table_name}" ({columns_str})
                    """

                cursor.execute(create_index_query)

            logger.info(f"Indexes created for table: {table_name}")

        connection.commit()
        logger.info('PostgreSQL indexes created successfully.')

    except Exception as e:
        if connection:
            connection.rollback()
        logger.error(f"Error initializing PostgreSQL indexes: {str(e)}")
        raise
    finally:
        if cursor:
            cursor.close()
        if connection:
            release_postgres_connection(connection)


def initPostgreSQLSchema():
    """Initialize PostgreSQL schema with tables and indexes"""
    try:
        initPostgresTables()
        initPostgresIndexes()
        logger.info('PostgreSQL schema initialized successfully.')
    except Exception as e:
        logger.error(f"Error initializing PostgreSQL schema: {str(e)}")
        raise