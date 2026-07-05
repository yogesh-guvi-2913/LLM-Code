"""Initialize PostgreSQL database"""

import asyncio
import asyncpg
import os


async def init_database():
    """Create database tables"""

    conn = await asyncpg.connect(
        os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:postgres@127.0.0.1:5432/llmcode"
        )
    )

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS tests (
            id SERIAL PRIMARY KEY,
            test_id VARCHAR(255) UNIQUE NOT NULL,
            name VARCHAR(500) NOT NULL,
            description TEXT,
            test_type VARCHAR(100),
            difficulty VARCHAR(50),
            duration_minutes INTEGER,
            requirements JSONB,
            starter_code JSONB,
            test_cases JSONB,
            flash_template_id VARCHAR(255),
            flash_template_registered BOOLEAN DEFAULT FALSE,
            scoring_config JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_tests_test_id ON tests(test_id);
        CREATE INDEX IF NOT EXISTS idx_tests_flash_template ON tests(flash_template_id);
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id SERIAL PRIMARY KEY,
            user_hash VARCHAR(255) NOT NULL,
            test_id VARCHAR(255) REFERENCES tests(test_id),
            flash_session_id VARCHAR(255) UNIQUE,
            status VARCHAR(50) DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_sessions_user_hash ON sessions(user_hash);
        CREATE INDEX IF NOT EXISTS idx_sessions_test_id ON sessions(test_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_flash_session ON sessions(flash_session_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id SERIAL PRIMARY KEY,
            test_id VARCHAR(255) REFERENCES tests(test_id),
            user_hash VARCHAR(255) NOT NULL,
            session_id INTEGER REFERENCES sessions(id),
            status VARCHAR(50) DEFAULT 'pending',
            score DECIMAL(5, 2),
            max_score DECIMAL(5, 2) DEFAULT 100,
            flash_score DECIMAL(5, 2),
            llm_score DECIMAL(5, 2),
            files JSONB,
            chat_history JSONB,
            test_results JSONB,
            feedback TEXT,
            requirements_check JSONB,
            scoring_breakdown JSONB,
            prompt_count INTEGER DEFAULT 0,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            evaluated_at TIMESTAMP,
            scoring_method VARCHAR(50) DEFAULT 'hybrid'
        );
        
        CREATE INDEX IF NOT EXISTS idx_submissions_test_user ON submissions(test_id, user_hash);
        CREATE INDEX IF NOT EXISTS idx_submissions_user_hash ON submissions(user_hash);
        CREATE INDEX IF NOT EXISTS idx_submissions_status ON submissions(status);
        CREATE INDEX IF NOT EXISTS idx_submissions_score ON submissions(score);
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS prompt_history (
            id SERIAL PRIMARY KEY,
            user_hash VARCHAR(255) NOT NULL,
            test_id VARCHAR(255) REFERENCES tests(test_id),
            session_id INTEGER REFERENCES sessions(id),
            user_message TEXT,
            ai_response TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_prompt_history_user_test ON prompt_history(user_hash, test_id);
        CREATE INDEX IF NOT EXISTS idx_prompt_history_timestamp ON prompt_history(timestamp);
    """)

    await conn.close()

    print("Database tables created successfully!")


if __name__ == "__main__":
    asyncio.run(init_database())