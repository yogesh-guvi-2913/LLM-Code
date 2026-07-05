"""Hybrid Scoring Service: Flash automated tests + LLM qualitative evaluation"""

import os
import logging
import asyncio
import json
from typing import Dict, Any
from datetime import datetime

from app.services.flash.client import flash_client

logger = logging.getLogger(__name__)


class HybridScorer:
    """Combines Flash automated scoring with LLM evaluation"""

    def __init__(self):
        self._flash_client = None
        self.flash_base_url = flash_client.base_url

        self.flash_weight = float(os.getenv("FLASH_SCORE_WEIGHT", "0.7"))
        self.llm_weight = float(os.getenv("LLM_SCORE_WEIGHT", "0.3"))

    @property
    def flash_client(self):
        """Lazily get Flash client"""
        if self._flash_client is None:
            self._flash_client = flash_client.get_client()
        return self._flash_client

    async def score_submission(
        self,
        session_id: str,
        test_data: dict,
        files: Dict[str, str],
        chat_history: list,
        auth_token: str
    ) -> Dict[str, Any]:
        """Perform hybrid scoring: Flash tests + LLM evaluation
        
        Args:
            session_id: Flash sandbox ID
            test_data: Test metadata from MongoDB
            files: Candidate's submitted files
            chat_history: AI conversation history
            auth_token: Auth token for LLM
            
        Returns:
            Scoring result with final_score, breakdown, feedback
        """

        logger.info(f"Starting hybrid scoring for session: {session_id}")

        flash_result = await self.run_flash_scoring(session_id, test_data, auth_token)

        flash_score = flash_result.get("score", 0)
        test_results = flash_result.get("test_results", [])

        logger.info(f"Flash score: {flash_score}/100")

        llm_result = await self.run_llm_evaluation(
            test_data,
            files,
            chat_history,
            flash_score
        )

        llm_score = llm_result.get("score", 0)
        llm_feedback = llm_result.get("feedback", "")
        requirements_check = llm_result.get("requirements_check", [])

        logger.info(f"LLM score: {llm_score}/100")

        final_score = (flash_score * self.flash_weight) + (llm_score * self.llm_weight)
        final_score = round(final_score, 2)

        logger.info(f"Final hybrid score: {final_score}/100")

        detailed_feedback = self.generate_feedback(
            flash_score,
            llm_score,
            test_results,
            llm_feedback,
            requirements_check
        )

        return {
            "final_score": final_score,
            "max_score": 100,
            "flash_score": flash_score,
            "flash_weight": self.flash_weight,
            "llm_score": llm_score,
            "llm_weight": self.llm_weight,
            "test_results": test_results,
            "llm_feedback": llm_feedback,
            "requirements_check": requirements_check,
            "detailed_feedback": detailed_feedback,
            "scoring_method": "hybrid",
        }

    async def run_flash_scoring(
        self,
        session_id: str,
        test_data: dict,
        auth_token: str
    ) -> Dict[str, Any]:
        """Trigger Flash's automated scoring"""

        try:
            session = self.flash_client.assessments.get_session(session_id)
            submission = session.submit()

            logger.info(f"Flash submission created: {submission.submission_id}")

            result = session.wait_for_score(timeout=180.0, poll=2.0)

            return {
                "score": result.score,
                "max_score": result.max_score,
                "test_results": [],
                "submission_id": submission.submission_id,
                "status": result.status,
            }

        except Exception as e:
            logger.error(f"Flash scoring failed: {e}", exc_info=True)
            return {
                "score": 0,
                "error": str(e),
                "test_results": [],
            }

    async def run_llm_evaluation(
        self,
        test_data: dict,
        files: Dict[str, str],
        chat_history: list,
        runtime_score: int
    ) -> Dict[str, Any]:
        """Run LLM-based qualitative evaluation"""

        try:
            from app.routes.evaluation.routes import evaluate_submission

            llm_result = await evaluate_submission(
                problem_name=test_data.get("name", ""),
                problem_description=test_data.get("description", ""),
                requirements=test_data.get("requirements", []),
                files=files,
                chat_history=chat_history,
                runtime_result={"score": runtime_score, "rendered": True}
            )

            return {
                "score": llm_result.get("score", 0),
                "feedback": llm_result.get("feedback", ""),
                "requirements_check": llm_result.get("requirements_check", []),
                "strengths": llm_result.get("strengths", []),
                "improvements": llm_result.get("improvements", []),
            }

        except Exception as e:
            logger.error(f"LLM evaluation failed: {e}", exc_info=True)
            return {
                "score": 0,
                "feedback": f"LLM evaluation error: {str(e)}",
                "error": str(e),
            }

    def generate_feedback(
        self,
        flash_score: int,
        llm_score: int,
        test_results: list,
        llm_feedback: str,
        requirements_check: list
    ) -> str:
        """Generate comprehensive feedback combining both scores"""

        feedback_parts = []

        feedback_parts.append(
            f"**Overall Score**: {round((flash_score * self.flash_weight) + (llm_score * self.llm_weight), 2)}/100\n"
        )

        feedback_parts.append("**Score Breakdown:**")
        feedback_parts.append(f"- Functional Tests (automated): {flash_score}/100 ({self.flash_weight*100}% weight)")
        feedback_parts.append(f"- Code Quality (LLM): {llm_score}/100 ({self.llm_weight*100}% weight)")
        feedback_parts.append("")

        if test_results:
            feedback_parts.append("**Test Results:**")
            passed_tests = [t for t in test_results if t.get("passed")]
            failed_tests = [t for t in test_results if not t.get("passed")]

            feedback_parts.append(f"- Passed: {len(passed_tests)}/{len(test_results)}")

            if failed_tests:
                feedback_parts.append("- Failed tests:")
                for test in failed_tests:
                    feedback_parts.append(f"  - {test.get('name', 'Unknown')}: {test.get('error', 'No error message')}")

            feedback_parts.append("")

        if requirements_check:
            feedback_parts.append("**Requirements Check:**")
            for req in requirements_check:
                status = "✓" if req.get("satisfied") else "✗"
                feedback_parts.append(f"- {status} {req.get('requirement', '')}")
            feedback_parts.append("")

        if llm_feedback:
            feedback_parts.append("**Qualitative Feedback:**")
            feedback_parts.append(llm_feedback)

        return "\n".join(feedback_parts)