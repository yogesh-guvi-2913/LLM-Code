import logging
import json
from typing import Any, Dict, List, Optional, Union
from psycopg2 import sql
from psycopg2.extras import RealDictCursor, execute_values
from app.postgresql.sync.config import get_postgres_connection, release_postgres_connection
from app.config import POSTGRES_DB

logger = logging.getLogger(__name__)


class PostgreSQL:
    def __init__(self):
        self.connection = get_postgres_connection()
        self.dbName = POSTGRES_DB
        self.tableName = None
        self.cursor = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def selectDB(self, db: str = POSTGRES_DB):
        self.dbName = db
        return self

    def selectCollection(self, collection: str = None):
        if collection is None:
            return False
        self.tableName = collection
        self.cursor = self.connection.cursor(cursor_factory=RealDictCursor)
        return self.cursor

    def getAvailableDataBase(self):
        cursor = self.connection.cursor()
        cursor.execute("SELECT datname FROM pg_database WHERE datistemplate = false;")
        return [row[0] for row in cursor.fetchall()]

    def insertOne(self, document: dict = None):
        if document is None:
            return False

        columns = list(document.keys())
        values = list(document.values())

        query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING id").format(
            sql.Identifier(self.tableName),
            sql.SQL(', ').join(map(sql.Identifier, columns)),
            sql.SQL(', ').join(sql.Placeholder() * len(values))
        )

        self.cursor.execute(query, values)
        self.connection.commit()
        result = self.cursor.fetchone()
        return result['id'] if result else None

    def insertMany(self, documents: list = None):
        if documents is None:
            return False

        columns = list(documents[0].keys())
        values = [list(doc.values()) for doc in documents]

        query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            sql.Identifier(self.tableName),
            sql.SQL(', ').join(map(sql.Identifier, columns)),
            sql.SQL(', ').join(map(sql.Placeholder, columns))
        )

        execute_values(self.cursor, query, values)
        self.connection.commit()
        return True

    def find(
        self,
        query: dict = {},
        projection: dict = {},
        limit: int = None,
        sort: list = None,
        skip: int = None
    ):
        where_clause, params = self._build_where_clause(query)

        columns_str = '*'
        if projection and '_id' not in projection and len(projection) > 0:
            columns = [col for col, val in projection.items() if val == 1]
            if columns:
                columns_str = ', '.join(f'"{col}"' for col in columns)

        query_str = f"SELECT {columns_str} FROM {self.tableName}"

        if where_clause:
            query_str += f" WHERE {where_clause}"

        if sort:
            order_clause = self._build_order_clause(sort)
            query_str += f" ORDER BY {order_clause}"

        if skip is not None:
            query_str += f" OFFSET {skip}"

        if limit is not None:
            query_str += f" LIMIT {limit}"

        self.cursor.execute(query_str, params)
        return self._process_results(self.cursor.fetchall())

    def findNew(
        self,
        query: dict = {},
        projection: dict = {},
        limit: int = None,
        sort: list = None,
        skip: int = None
    ):
        return self.find(query, projection, limit, sort, skip)

    def count(self, query: dict = {}):
        where_clause, params = self._build_where_clause(query)
        query_str = f"SELECT COUNT(*) as count FROM {self.tableName}"

        if where_clause:
            query_str += f" WHERE {where_clause}"

        self.cursor.execute(query_str, params)
        result = self.cursor.fetchone()
        return result['count'] if result else 0

    def updateOne(self, query: dict = None, values: dict = {}, upsert=False):
        if query is None:
            return False

        where_clause, where_params = self._build_where_clause(query)

        if values.get('$set'):
            set_clause, set_params = self._build_set_clause(values['$set'])
        elif values.get('$inc'):
            set_clause, set_params = self._build_inc_clause(values['$inc'])
        else:
            set_clause, set_params = self._build_set_clause(values)

        query_str = f"UPDATE {self.tableName} SET {set_clause}"

        if where_clause:
            query_str += f" WHERE {where_clause}"

        query_str += " RETURNING *"

        params = set_params + where_params

        try:
            self.cursor.execute(query_str, params)
            self.connection.commit()
            return self.cursor.fetchone()
        except Exception:
            if upsert:
                return self._upsert(query, values.get('$set', values))
            raise

    def updateMany(self, query: dict = None, values: dict = {}, upsert=False):
        if query is None:
            return False

        where_clause, where_params = self._build_where_clause(query)

        if values.get('$set'):
            set_clause, set_params = self._build_set_clause(values['$set'])
        elif values.get('$inc'):
            set_clause, set_params = self._build_inc_clause(values['$inc'])
        else:
            set_clause, set_params = self._build_set_clause(values)

        query_str = f"UPDATE {self.tableName} SET {set_clause}"

        if where_clause:
            query_str += f" WHERE {where_clause}"

        params = set_params + where_params

        try:
            self.cursor.execute(query_str, params)
            self.connection.commit()
            return self.cursor.rowcount
        except Exception:
            if upsert:
                return self._upsert(query, values.get('$set', values))
            raise

    def delete(self, query: dict = {}):
        where_clause, params = self._build_where_clause(query)
        query_str = f"DELETE FROM {self.tableName}"

        if where_clause:
            query_str += f" WHERE {where_clause}"

        self.cursor.execute(query_str, params)
        self.connection.commit()
        return self.cursor.rowcount

    def aggregate(self, query: list = None):
        if query is None:
            return False

        result = []
        current_table = self.tableName

        for stage in query:
            if '$match' in stage:
                where_clause, params = self._build_where_clause(stage['$match'])
                current_query = f"SELECT * FROM {current_table}"
                if where_clause:
                    current_query += f" WHERE {where_clause}"
                self.cursor.execute(current_query, params)
                current_table = f"({current_query}) as subquery_{len(result)}"

            elif '$group' in stage:
                group_keys = stage['$group']
                group_columns = []

                for key, expr in group_keys.items():
                    if key == '_id':
                        group_columns.append(expr)
                    elif isinstance(expr, dict) and '$sum' in expr:
                        group_columns.append(f"SUM({expr['$sum']}) as {key}")
                    elif isinstance(expr, dict) and '$count' in expr:
                        group_columns.append(f"COUNT({expr['$count']}) as {key}")
                    elif isinstance(expr, dict) and '$avg' in expr:
                        group_columns.append(f"AVG({expr['$avg']}) as {key}")
                    elif isinstance(expr, dict) and '$max' in expr:
                        group_columns.append(f"MAX({expr['$max']}) as {key}")
                    elif isinstance(expr, dict) and '$min' in expr:
                        group_columns.append(f"MIN({expr['$min']}) as {key}")

                current_query = f"SELECT {', '.join(group_columns)} FROM {current_table} GROUP BY {group_keys['_id']}"
                self.cursor.execute(current_query)
                current_table = f"({current_query}) as subquery_{len(result)}"

            elif '$sort' in stage:
                order_clause = self._build_order_clause(stage['$sort'])
                current_query = f"SELECT * FROM {current_table} ORDER BY {order_clause}"
                self.cursor.execute(current_query)
                current_table = f"({current_query}) as subquery_{len(result)}"

            elif '$limit' in stage:
                current_query = f"SELECT * FROM {current_table} LIMIT {stage['$limit']}"
                self.cursor.execute(current_query)
                current_table = f"({current_query}) as subquery_{len(result)}"

            elif '$skip' in stage:
                current_query = f"SELECT * FROM {current_table} OFFSET {stage['$skip']}"
                self.cursor.execute(current_query)
                current_table = f"({current_query}) as subquery_{len(result)}"

        final_query = f"SELECT * FROM {current_table}"
        self.cursor.execute(final_query)
        return self._process_results(self.cursor.fetchall())

    def aggregateWithWrite(self, query: list = None):
        if query is None:
            return False

        self.aggregate(query)
        return True

    def ensureUniqueIndex(self, fields: list = None):
        if fields is None:
            return False

        try:
            index_name = f"idx_{'_'.join(fields)}_unique"
            columns = ', '.join(f'"{field}"' for field in fields)

            query = f"""
                CREATE UNIQUE INDEX IF NOT EXISTS {index_name}
                ON {self.tableName} ({columns})
            """

            self.cursor.execute(query)
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error creating unique index on fields {fields}: {str(e)}")
            return False

    def distinct(self, field: str = '', query: dict = {}, onlyCount=False):
        if field == '':
            return False

        where_clause, params = self._build_where_clause(query)
        query_str = f"SELECT DISTINCT {field} FROM {self.tableName}"

        if where_clause:
            query_str += f" WHERE {where_clause}"

        self.cursor.execute(query_str, params)

        if onlyCount:
            return self.cursor.rowcount
        else:
            return [row[field] for row in self.cursor.fetchall()]

    def tableExists(self, tableName: str = None) -> bool:
        if tableName is None:
            return False

        self.cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = %s
            )
        """, (tableName,))

        return self.cursor.fetchone()['exists']

    def createTable(self, tableName: str = None, columns: dict = None):
        if tableName is None:
            return False

        try:
            if columns:
                column_defs = []
                for col_name, col_type in columns.items():
                    column_defs.append(f'"{col_name}" {col_type}')
                columns_str = ', '.join(column_defs)
            else:
                columns_str = "id SERIAL PRIMARY KEY, data JSONB"

            query = f"CREATE TABLE IF NOT EXISTS {tableName} ({columns_str})"
            self.cursor.execute(query)
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error creating table {tableName}: {str(e)}")
            return False

    def bulkWrite(self, documents: list, uniqueFields: Union[str, list]):
        try:
            if isinstance(uniqueFields, str):
                uniqueFields = [uniqueFields]

            for doc in documents:
                where_clause, where_params = self._build_where_clause(
                    {field: doc[field] for field in uniqueFields if field in doc}
                )

                existing = self.find({field: doc[field] for field in uniqueFields if field in doc})
                if existing:
                    self.updateOne({field: doc[field] for field in uniqueFields if field in doc}, {'$set': doc})
                else:
                    self.insertOne(doc)

            return True
        except Exception as e:
            logger.error(f"Error in bulk write: {str(e)}")
            return False

    def findOneAndUpdate(self, query: dict = None, update: dict = None, upsert: bool = False, returnDocument: str = 'after'):
        if query is None or update is None:
            return False

        where_clause, where_params = self._build_where_clause(query)

        if update.get('$set'):
            set_clause, set_params = self._build_set_clause(update['$set'])
        elif update.get('$inc'):
            set_clause, set_params = self._build_inc_clause(update['$inc'])
        else:
            set_clause, set_params = self._build_set_clause(update)

        query_str = f"UPDATE {self.tableName} SET {set_clause}"

        if where_clause:
            query_str += f" WHERE {where_clause}"

        if returnDocument == 'after':
            query_str += " RETURNING *"

        params = set_params + where_params

        try:
            self.cursor.execute(query_str, params)
            self.connection.commit()

            if returnDocument == 'after':
                return self.cursor.fetchone()
            else:
                return self.find(query, limit=1)
        except Exception:
            if upsert:
                return self._upsert(query, update.get('$set', update))
            raise

    def close(self):
        if self.cursor:
            self.cursor.close()
        if self.connection:
            release_postgres_connection(self.connection)

    def _build_where_clause(self, query: dict, params: list = None):
        if params is None:
            params = []

        conditions = []
        for key, value in query.items():
            if isinstance(value, dict):
                for op, val in value.items():
                    if op == '$eq':
                        conditions.append(f'"{key}" = %s')
                        params.append(val)
                    elif op == '$ne':
                        conditions.append(f'"{key}" != %s')
                        params.append(val)
                    elif op == '$gt':
                        conditions.append(f'"{key}" > %s')
                        params.append(val)
                    elif op == '$gte':
                        conditions.append(f'"{key}" >= %s')
                        params.append(val)
                    elif op == '$lt':
                        conditions.append(f'"{key}" < %s')
                        params.append(val)
                    elif op == '$lte':
                        conditions.append(f'"{key}" <= %s')
                        params.append(val)
                    elif op == '$in':
                        placeholders = ', '.join(['%s'] * len(val))
                        conditions.append(f'"{key}" IN ({placeholders})')
                        params.extend(val)
                    elif op == '$nin':
                        placeholders = ', '.join(['%s'] * len(val))
                        conditions.append(f'"{key}" NOT IN ({placeholders})')
                        params.extend(val)
                    elif op == '$regex':
                        conditions.append(f'"{key}" ~ %s')
                        params.append(val)
                    elif op == '$exists':
                        if val:
                            conditions.append(f'"{key}" IS NOT NULL')
                        else:
                            conditions.append(f'"{key}" IS NULL')
            else:
                conditions.append(f'"{key}" = %s')
                params.append(value)

        return ' AND '.join(conditions) if conditions else '', params

    def _build_set_clause(self, values: dict):
        clauses = []
        params = []
        for key, value in values.items():
            clauses.append(f'"{key}" = %s')
            params.append(value)
        return ', '.join(clauses), params

    def _build_inc_clause(self, values: dict):
        clauses = []
        params = []
        for key, value in values.items():
            clauses.append(f'"{key}" = "{key}" + %s')
            params.append(value)
        return ', '.join(clauses), params

    def _build_order_clause(self, sort):
        if isinstance(sort[0], tuple):
            order_parts = []
            for field, direction in sort:
                dir_str = 'DESC' if direction == -1 else 'ASC'
                order_parts.append(f'"{field}" {dir_str}')
            return ', '.join(order_parts)
        else:
            dir_str = 'DESC' if sort[1] == -1 else 'ASC'
            return f'"{sort[0]}" {dir_str}'

    def _process_results(self, results: List[Dict]) -> List[Dict]:
        processed = []
        for row in results:
            processed_row = {}
            for key, value in row.items():
                if isinstance(value, dict):
                    processed_row[key] = value
                else:
                    processed_row[key] = value
            processed.append(processed_row)
        return processed

    def _upsert(self, query: dict, values: dict):
        where_clause, where_params = self._build_where_clause(query)

        check_query = f"SELECT * FROM {self.tableName}"
        if where_clause:
            check_query += f" WHERE {where_clause}"

        self.cursor.execute(check_query, where_params)
        existing = self.cursor.fetchone()

        if existing:
            set_clause, set_params = self._build_set_clause(values)
            update_query = f"UPDATE {self.tableName} SET {set_clause}"
            if where_clause:
                update_query += f" WHERE {where_clause}"
            self.cursor.execute(update_query, set_params + where_params)
        else:
            insert_values = {**query, **values}
            self.insertOne(insert_values)

        self.connection.commit()
        return True