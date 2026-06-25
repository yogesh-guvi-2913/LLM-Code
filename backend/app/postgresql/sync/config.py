import psycopg2
from psycopg2 import pool
import app.config as config

connection_pool = None

def get_postgres_connection():
    """Get a connection from the PostgreSQL connection pool"""
    global connection_pool
    if connection_pool is None:
        connection_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            host=config.POSTGRES_HOST,
            port=config.POSTGRES_PORT,
            database=config.POSTGRES_DB,
            user=config.POSTGRES_USER,
            password=config.POSTGRES_PASSWORD
        )
    return connection_pool.getconn()

def release_postgres_connection(conn):
    """Release a connection back to the pool"""
    global connection_pool
    if connection_pool:
        connection_pool.putconn(conn)

def close_postgres_pool():
    """Close all connections in the pool"""
    global connection_pool
    if connection_pool:
        connection_pool.closeall()
        connection_pool = None