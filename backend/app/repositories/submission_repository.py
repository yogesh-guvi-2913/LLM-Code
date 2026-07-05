"""Submission repository for PostgreSQL"""

from typing import Optional, Dict, Any, List
from app.database.postgres_client import postgres_client
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)


class SubmissionRepository:
    """Submission data repository"""

    async def create(self, submission_data: Dict[str, Any]) -> int:
        """Create new submission"""
        query = """
        INSERT INTO submissions (
            test_id, user_hash, session_id, status, files,
            chat_history, prompt_count, scoring_method,
            submitted_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        RETURNING id
        """

        return await postgres_client.insert(
            query,
            submission_data.get("testId"),
            submission_data.get("userHash"),
            submission_data.get("sessionId"),
            submission_data.get("status", "pending"),
            json.dumps(submission_data.get("files", {})),
            json.dumps(submission_data.get("chatHistory", [])),
            submission_data.get("promptCount", 0),
            submission_data.get("scoringMethod", "hybrid"),
            datetime.utcnow()
        )

    async def find_by_id(self, submission_id: int) -> Optional[Dict[str, Any]]:
        """Find submission by ID"""
        query = "SELECT * FROM submissions WHERE id = $1"
        return await postgres_client.fetchone(query, submission_id)

    async def find_by_test_and_user(
        self,
        test_id: str,
        user_hash: str
    ) -> Optional[Dict[str, Any]]:
        """Find latest submission by test and user"""
        query = """
        SELECT * FROM submissions
        WHERE test_id = $1 AND user_hash = $2
        ORDER BY submitted_at DESC LIMIT 1
        """
        return await postgres_client.fetchone(query, test_id, user_hash)

    async def find_all_by_user(self, user_hash: str) -> List[Dict[str, Any]]:
        """Find all submissions by user"""
        query = """
        SELECT * FROM submissions
        WHERE user_hash = $1
        ORDER BY submitted_at DESC
        """
        return await postgres_client.fetch(query, user_hash)

    async def update_results(
        self,
        submission_id: int,
        results: Dict[str, Any]
    ) -> int:
        """Update submission with evaluation results"""
        query = """
        UPDATE submissions SET
            status = $2,
            score = $3,
            max_score = $4,
            flash_score = $5,
            llm_score = $6,
            test_results = $7,
            feedback = $8,
            requirements_check = $9,
            scoring_breakdown = $10,
            evaluated_at = CURRENT_TIMESTAMP
        WHERE id = $1
        """

        return await postgres_client.update(
            query,
            submission_id,
            results.get("status", "completed"),
            results.get("score"),
            results.get("maxScore", 100),
            results.get("flashScore"),
            results.get("llmScore"),
            json.dumps(results.get("testResults", [])),
            results.get("feedback"),
            json.dumps(results.get("requirementsCheck", [])),
            json.dumps(results.get("scoringBreakdown", {})),
        )

    async def update_status(
        self,
        submission_id: int,
        status: str
    ) -> int:
        """Update submission status"""
        query = """
        UPDATE submissions SET status = $2 WHERE id = $1
        """
        return await postgres_client.update(query, submission_id, status)

    async def get_statistics(self) -> Dict[str, Any]:
        """Get submission statistics"""
        query = """
        SELECT
            scoring_method,
            COUNT(*) as count,
            AVG(score) as avg_score,
            AVG(flash_score) as avg_flash_score,
            AVG(llm_score) as avg_llm_score
        FROM submissions
        WHERE status = 'completed'
        GROUP BY scoring_method
        """

        return await postgres_client.fetch(query)

    async def cleanup_old_submissions(self, days: int = 90) -> int:
        """Delete old submissions"""
        query = """
        DELETE FROM submissions
        WHERE submitted_at < CURRENT_TIMESTAMP - INTERVAL '%s days'
        """
        return await postgres_client.delete(query % days)


submission_repository = SubmissionRepository()