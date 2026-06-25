import asyncpg
import app.config as config


class AsyncPostgresPool:
    _pool = None

    @classmethod
    async def get_pool(cls):
        if cls._pool is None:
            cls._pool = await asyncpg.create_pool(
                host=config.POSTGRES_HOST,
                port=config.POSTGRES_PORT,
                database=config.POSTGRES_DB,
                user=config.POSTGRES_USER,
                password=config.POSTGRES_PASSWORD,
                min_size=1,
                max_size=10
            )
        return cls._pool

    @classmethod
    async def close_pool(cls):
        if cls._pool:
            await cls._pool.close()
            cls._pool = None

    @classmethod
    async def get_connection(cls):
        pool = await cls.get_pool()
        return await pool.acquire()

    @classmethod
    async def release_connection(cls, conn):
        if cls._pool:
            await cls._pool.release(conn)


async def get_async_postgres_connection():
    """Get an async PostgreSQL connection from the pool"""
    pool = await AsyncPostgresPool.get_pool()
    return await pool.acquire()


async def release_async_postgres_connection(conn):
    """Release an async PostgreSQL connection back to the pool"""
    await AsyncPostgresPool.release_connection(conn)


async def close_async_postgres_pool():
    """Close the async PostgreSQL connection pool"""
    await AsyncPostgresPool.close_pool()