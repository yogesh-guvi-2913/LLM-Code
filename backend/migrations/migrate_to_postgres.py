"""MongoDB to PostgreSQL migration script"""

import asyncio
import asyncpg
import pymongo
import logging
from datetime import datetime
import json
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MongoToPostgresMigration:
    """Migrate data from MongoDB to PostgreSQL"""
    
    def __init__(self):
        self.mongo_client = pymongo.MongoClient(
            os.getenv("MONGO_URI", "mongodb://localhost:27017")
        )
        self.mongo_db = self.mongo_client["llm-code"]
        self.pg_pool = None
    
    async def connect_postgres(self):
        """Connect to PostgreSQL"""
        self.pg_pool = await asyncpg.create_pool(
            os.getenv(
                "DATABASE_URL",
                "postgresql://postgres:postgres@127.0.0.1:5432/llmcode"
            ),
            min_size=1,
            max_size=10
        )
        logger.info("Connected to PostgreSQL")
    
    async def close(self):
        """Close connections"""
        self.mongo_client.close()
        if self.pg_pool:
            await self.pg_pool.close()
    
    async def run_migrations(self):
        """Run all migrations"""
        try:
            await self.connect_postgres()
            
            await self.migrate_tests()
            await self.migrate_sessions()
            await self.migrate_submissions()
            
            logger.info("Migration completed successfully!")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}", exc_info=True)
            raise
        
        finally:
            await self.close()
    
    async def migrate_tests(self):
        """Migrate tests collection"""
        logger.info("Migrating tests...")
        
        mongo_tests = self.mongo_db.tests.find({})
        count = 0
        
        async with self.pg_pool.acquire() as conn:
            async for test in mongo_tests:
                try:
                    await conn.execute(
                        """
                        INSERT INTO tests (
                            test_id, name, description, test_type, difficulty,
                            duration_minutes, requirements, scoring_config,
                            created_at, updated_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        ON CONFLICT (test_id) DO UPDATE SET
                            name = $2, description = $3, updated_at = CURRENT_TIMESTAMP
                        """,
                        test.get("testId"),
                        test.get("name", ""),
                        test.get("description", ""),
                        test.get("testType", ""),
                        test.get("difficulty", ""),
                        test.get("duration", 0),
                        json.dumps(test.get("requirements", [])),
                        json.dumps(test.get("scoringConfig", {})),
                        test.get("createdAt", datetime.utcnow()),
                        test.get("updatedAt", datetime.utcnow())
                    )
                    count += 1
                except Exception as e:
                    logger.error(f"Failed to migrate test {test.get('testId')}: {e}")
        
        logger.info(f"Migrated {count} tests")
    
    async def migrate_sessions(self):
        """Migrate test-mapper collection"""
        logger.info("Migrating sessions...")
        
        mongo_sessions = self.mongo_db["test-mapper"].find({})
        count = 0
        
        async with self.pg_pool.acquire() as conn:
            async for session in mongo_sessions:
                try:
                    await conn.execute(
                        """
                        INSERT INTO sessions (
                            user_hash, test_id, flash_session_id, status, created_at, updated_at
                        ) VALUES ($1, $2, $3, $4, $5, $6)
                        ON CONFLICT (flash_session_id) DO NOTHING
                        """,
                        session.get("hash"),
                        session.get("testId"),
                        session.get("flashSessionId"),
                        "active",
                        session.get("createdAt", datetime.utcnow()),
                        session.get("updatedAt", datetime.utcnow())
                    )
                    count += 1
                except Exception as e:
                    logger.error(f"Failed to migrate session: {e}")
        
        logger.info(f"Migrated {count} sessions")
    
    async def migrate_submissions(self):
        """Migrate submissions collection"""
        logger.info("Migrating submissions...")
        
        mongo_submissions = self.mongo_db.submissions.find({})
        count = 0
        
        async with self.pg_pool.acquire() as conn:
            async for submission in mongo_submissions:
                try:
                    await conn.execute(
                        """
                        INSERT INTO submissions (
                            test_id, user_hash, status, score, files, chat_history,
                            prompt_count, submitted_at, scoring_method
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        """,
                        submission.get("testId"),
                        submission.get("userHash"),
                        submission.get("status", "pending"),
                        submission.get("score", 0),
                        json.dumps(submission.get("files", {})),
                        json.dumps(submission.get("chatHistory", [])),
                        submission.get("promptCount", 0),
                        submission.get("submittedAt"),
                        submission.get("scoringMethod", "llm")
                    )
                    count += 1
                except Exception as e:
                    logger.error(f"Failed to migrate submission: {e}")
        
        logger.info(f"Migrated {count} submissions")


async def main():
    migration = MongoToPostgresMigration()
    await migration.run_migrations()


if __name__ == "__main__":
    asyncio.run(main())