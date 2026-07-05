"""Test repository for PostgreSQL"""

from typing import Optional, Dict, Any, List
from app.database.postgres_client import postgres_client
import logging
import json

logger = logging.getLogger(__name__)


class TestRepository:
    """Test data repository"""

    async def create(self, test_data: Dict[str, Any]) -> int:
        """Create new test"""
        query = """
        INSERT INTO tests (
            test_id, name, description, test_type, difficulty,
            duration_minutes, requirements, starter_code, test_cases,
            flash_template_id, flash_template_registered, scoring_config,
            created_at, updated_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
        RETURNING id
        """

        return await postgres_client.insert(
            query,
            test_data.get("testId"),
            test_data.get("name"),
            test_data.get("description"),
            test_data.get("testType"),
            test_data.get("difficulty"),
            test_data.get("duration"),
            json.dumps(test_data.get("requirements", [])),
            json.dumps(test_data.get("starterCode", {})),
            json.dumps(test_data.get("testCases", [])),
            test_data.get("flashTemplateId"),
            test_data.get("flashTemplateRegistered", False),
            json.dumps(test_data.get("scoringConfig", {})),
            test_data.get("createdAt", datetime.utcnow()),
            test_data.get("updatedAt", datetime.utcnow())
        )

    async def find_by_id(self, test_id: str) -> Optional[Dict[str, Any]]:
        """Find test by ID"""
        query = "SELECT * FROM tests WHERE test_id = $1"
        return await postgres_client.fetchone(query, test_id)

    async def find_all(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Find all tests"""
        query = "SELECT * FROM tests ORDER BY created_at DESC LIMIT $1"
        return await postgres_client.fetch(query, limit)

    async def update(self, test_id: str, updates: Dict[str, Any]) -> int:
        """Update test"""
        set_clauses = []
        values = []
        param_num = 1

        for key, value in updates.items():
            snake_key = self._camel_to_snake(key)
            if snake_key in ["requirements", "starter_code", "test_cases", "scoring_config"]:
                value = json.dumps(value)
            set_clauses.append(f"{snake_key} = ${param_num}")
            values.append(value)
            param_num += 1

        values.append(test_id)
        query = f"UPDATE tests SET {', '.join(set_clauses)}, updated_at = CURRENT_TIMESTAMP WHERE test_id = ${param_num}"

        return await postgres_client.update(query, *values)

    async def delete(self, test_id: str) -> int:
        """Delete test"""
        query = "DELETE FROM tests WHERE test_id = $1"
        return await postgres_client.delete(query, test_id)

    async def find_by_template(self, template_id: str) -> List[Dict[str, Any]]:
        """Find tests by Flash template ID"""
        query = "SELECT * FROM tests WHERE flash_template_id = $1"
        return await postgres_client.fetch(query, template_id)

    def _camel_to_snake(self, name: str) -> str:
        """Convert camelCase to snake_case"""
        import re
        return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()


test_repository = TestRepository()