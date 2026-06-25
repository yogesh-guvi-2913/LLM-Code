import json
from typing import Dict, Any, List, Optional
from app.utils.common import my_print
import app.config as config
from app.postgresql.async_version.connection import get_async_postgres_connection, release_async_postgres_connection

database_name = config.POSTGRES_DB


class AsyncPostgresClient:
    @staticmethod
    async def insert_one(table_name: str, document: Dict[str, Any]) -> bool:
        conn = None
        try:
            conn = await get_async_postgres_connection()

            columns = list(document.keys())
            values = list(document.values())
            placeholders = ', '.join(['${}'.format(i + 1) for i in range(len(values))])

            query = f"""
                INSERT INTO {table_name} ({', '.join(f'"{col}"' for col in columns)})
                VALUES ({placeholders})
                RETURNING id
            """

            await conn.execute(query, *values)
            return True

        except Exception as e:
            my_print(str(e))
            return False
        finally:
            if conn:
                await release_async_postgres_connection(conn)

    @staticmethod
    async def find_one(table_name: str, query: Dict[str, Any], projection: Optional[List[str]] = None) -> Optional[Dict]:
        conn = None
        try:
            conn = await get_async_postgres_connection()

            where_clause, params = AsyncPostgresClient._build_where_clause(query)

            columns_str = '*'
            if projection:
                columns_str = ', '.join(f'"{col}"' for col in projection)

            sql_query = f"SELECT {columns_str} FROM {table_name}"

            if where_clause:
                sql_query += f" WHERE {where_clause}"

            sql_query += " LIMIT 1"

            result = await conn.fetchrow(sql_query, *params)

            if result:
                return dict(result)
            return None

        except Exception as e:
            my_print(str(e))
            return None
        finally:
            if conn:
                await release_async_postgres_connection(conn)

    @staticmethod
    async def find(table_name: str, query: Dict[str, Any], projection: Optional[List[str]] = None):
        conn = None
        try:
            conn = await get_async_postgres_connection()

            where_clause, params = AsyncPostgresClient._build_where_clause(query)

            columns_str = '*'
            if projection:
                columns_str = ', '.join(f'"{col}"' for col in projection)

            sql_query = f"SELECT {columns_str} FROM {table_name}"

            if where_clause:
                sql_query += f" WHERE {where_clause}"

            results = await conn.fetch(sql_query, *params)

            for row in results:
                yield dict(row)

        except Exception as e:
            my_print(str(e))
        finally:
            if conn:
                await release_async_postgres_connection(conn)

    @staticmethod
    async def update_one(table_name: str, query: Dict[str, Any], update: Dict[str, Any], upsert: bool = False) -> bool:
        conn = None
        try:
            conn = await get_async_postgres_connection()

            where_clause, where_params = AsyncPostgresClient._build_where_clause(query)
            set_clause, set_params = AsyncPostgresClient._build_set_clause(update)

            sql_query = f"UPDATE {table_name} SET {set_clause}"

            if where_clause:
                sql_query += f" WHERE {where_clause}"

            sql_query += " RETURNING *"

            params = set_params + where_params

            result = await conn.fetchrow(sql_query, *params)

            if not result and upsert:
                return await AsyncPostgresClient._upsert(table_name, query, update)

            return bool(result)

        except Exception as e:
            my_print(str(e))
            return False
        finally:
            if conn:
                await release_async_postgres_connection(conn)

    @staticmethod
    async def bulk_write(table_name: str, operations: List[Dict[str, Any]]) -> bool:
        conn = None
        try:
            conn = await get_async_postgres_connection()
            async with conn.transaction():
                for operation in operations:
                    if operation.get('operation') == 'insert_one':
                        await AsyncPostgresClient.insert_one(table_name, operation['document'])
                    elif operation.get('operation') == 'update_one':
                        await AsyncPostgresClient.update_one(
                            table_name,
                            operation['query'],
                            operation['update'],
                            operation.get('upsert', False)
                        )
            return True

        except Exception as e:
            my_print(str(e))
            return False
        finally:
            if conn:
                await release_async_postgres_connection(conn)

    @staticmethod
    async def delete_db() -> bool:
        conn = None
        try:
            conn = await get_async_postgres_connection()

            query = f"""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
            """

            tables = await conn.fetch(query)

            for table in tables:
                await conn.execute(f'DROP TABLE IF EXISTS "{table["table_name"]}" CASCADE')

            return True

        except Exception as e:
            my_print(str(e))
            return False
        finally:
            if conn:
                await release_async_postgres_connection(conn)

    @staticmethod
    def _build_where_clause(query: Dict[str, Any]) -> tuple:
        params = []
        conditions = []

        for key, value in query.items():
            if isinstance(value, dict):
                for op, val in value.items():
                    if op == '$eq':
                        conditions.append(f'"{key}" = ${len(params) + 1}')
                        params.append(val)
                    elif op == '$ne':
                        conditions.append(f'"{key}" != ${len(params) + 1}')
                        params.append(val)
                    elif op == '$gt':
                        conditions.append(f'"{key}" > ${len(params) + 1}')
                        params.append(val)
                    elif op == '$gte':
                        conditions.append(f'"{key}" >= ${len(params) + 1}')
                        params.append(val)
                    elif op == '$lt':
                        conditions.append(f'"{key}" < ${len(params) + 1}')
                        params.append(val)
                    elif op == '$lte':
                        conditions.append(f'"{key}" <= ${len(params) + 1}')
                        params.append(val)
                    elif op == '$in':
                        placeholders = ', '.join(['${}'.format(i + len(params) + 1) for i in range(len(val))])
                        conditions.append(f'"{key}" IN ({placeholders})')
                        params.extend(val)
                    elif op == '$nin':
                        placeholders = ', '.join(['${}'.format(i + len(params) + 1) for i in range(len(val))])
                        conditions.append(f'"{key}" NOT IN ({placeholders})')
                        params.extend(val)
                    elif op == '$regex':
                        conditions.append(f'"{key}" ~ ${len(params) + 1}')
                        params.append(val)
                    elif op == '$exists':
                        if val:
                            conditions.append(f'"{key}" IS NOT NULL')
                        else:
                            conditions.append(f'"{key}" IS NULL')
            else:
                conditions.append(f'"{key}" = ${len(params) + 1}')
                params.append(value)

        return ' AND '.join(conditions) if conditions else '', params

    @staticmethod
    def _build_set_clause(values: Dict[str, Any]) -> tuple:
        clauses = []
        params = []
        for key, value in values.items():
            clauses.append(f'"{key}" = ${len(params) + 1}')
            params.append(value)
        return ', '.join(clauses), params

    @staticmethod
    async def _upsert(table_name: str, query: Dict[str, Any], update: Dict[str, Any]) -> bool:
        conn = None
        try:
            conn = await get_async_postgres_connection()

            where_clause, where_params = AsyncPostgresClient._build_where_clause(query)

            check_query = f"SELECT * FROM {table_name}"
            if where_clause:
                check_query += f" WHERE {where_clause}"

            existing = await conn.fetchrow(check_query, *where_params)

            if existing:
                set_clause, set_params = AsyncPostgresClient._build_set_clause(update)
                update_query = f"UPDATE {table_name} SET {set_clause}"
                if where_clause:
                    update_query += f" WHERE {where_clause}"
                await conn.execute(update_query, *(set_params + where_params))
            else:
                insert_values = {**query, **update}
                await AsyncPostgresClient.insert_one(table_name, insert_values)

            return True

        except Exception as e:
            my_print(str(e))
            return False
        finally:
            if conn:
                await release_async_postgres_connection(conn)