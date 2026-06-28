import json
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException
from typing import Optional

from app.mongodb.sync.mongo import MongoDB
from app.redis.sync.rediscache import RedisCache
from app.routes.evaluation.model import (
    SubmitTestRequest,
    SubmissionResponse,
    ResultsResponse,
    SubmissionStatus,
)
from app.routes.evaluation.runner import run_preview
from app.routes.evaluation.llm_evaluator import evaluate_submission

logger = logging.getLogger(__name__)

router = APIRouter()

PROMPT_HISTORY_KEY_PREFIX = "prompt_history:"


def _validate_auth(auth_token: str) -> str:
    if not auth_token:
        raise HTTPException(status_code=400, detail="authToken is required")

    redis_cache = RedisCache()
    user_data = redis_cache.getAllData(auth_token)

    if not user_data or "hash" not in user_data:
        raise HTTPException(status_code=401, detail="token_expired")

    return user_data["hash"]


def _get_test_data(test_id: str) -> dict:
    mongo = MongoDB()
    mongo.selectCollection("tests")
    test_results = mongo.find({"testId": test_id}, limit=1)

    if not test_results:
        raise HTTPException(status_code=404, detail="Test not found")

    return test_results[0]


def _get_prompt_history(user_hash: str, test_id: str) -> list:
    redis_cache = RedisCache()
    key = f"{PROMPT_HISTORY_KEY_PREFIX}{user_hash}:{test_id}"
    raw = redis_cache.getValue(key)

    if raw:
        try:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            pass

    return []


@router.post("/submit-test")
async def submit_test(request: SubmitTestRequest):
    user_hash = _validate_auth(request.authToken)
    test_data = _get_test_data(request.testId)

    mongo = MongoDB()
    mongo.selectCollection("test-mapper")
    mapper_result = mongo.find({"hash": user_hash, "testId": request.testId}, limit=1)
    if not mapper_result:
        raise HTTPException(status_code=403, detail="You do not have access to this test")

    prompt_history = _get_prompt_history(user_hash, request.testId)

    if prompt_history and not request.chatHistory:
        chat_history = []
        for entry in prompt_history:
            chat_history.append({"role": "user", "content": entry.get("userMessage", "")})
            chat_history.append({"role": "assistant", "content": entry.get("aiResponse", "")})
    else:
        chat_history = request.chatHistory

    files = request.files or {}

    submission_doc = {
        "testId": request.testId,
        "userHash": user_hash,
        "status": SubmissionStatus.evaluating.value,
        "submittedAt": datetime.utcnow(),
        "answers": request.answers,
        "files": files,
        "chatHistory": chat_history,
        "promptCount": len([m for m in chat_history if m.get("role") == "user"]),
    }

    mongo.selectCollection("submissions")
    existing = mongo.find({"testId": request.testId, "userHash": user_hash}, limit=1)
    if existing:
        mongo.updateOne(
            {"testId": request.testId, "userHash": user_hash},
            {"$set": submission_doc},
        )
        submission_id = str(existing[0].get("_id", ""))
    else:
        insert_result = mongo.insertOne(submission_doc)
        submission_id = str(insert_result.inserted_id)

    try:
        runtime_result = await run_preview(files)

        evaluation = await evaluate_submission(
            problem_name=test_data.get("name", "Unknown"),
            problem_description=test_data.get("description", ""),
            requirements=test_data.get("details", []),
            files=files,
            chat_history=chat_history,
            runtime_result=runtime_result,
        )

        update_data = {
            "status": SubmissionStatus.completed.value,
            "evaluation": evaluation,
            "runtimeResult": {
                "rendered": runtime_result.get("rendered", False),
                "runtimeError": runtime_result.get("runtime_error"),
                "consoleErrors": runtime_result.get("console_errors", []),
            },
            "screenshot": runtime_result.get("screenshot"),
            "screenshotMobile": runtime_result.get("screenshot_mobile"),
            "evaluatedAt": datetime.utcnow(),
        }

        mongo.updateOne(
            {"testId": request.testId, "userHash": user_hash},
            {"$set": update_data},
        )

    except Exception as e:
        logger.error(f"Evaluation failed for test {request.testId}: {e}", exc_info=True)
        mongo.updateOne(
            {"testId": request.testId, "userHash": user_hash},
            {
                "$set": {
                    "status": SubmissionStatus.failed.value,
                    "evaluationError": str(e),
                    "evaluatedAt": datetime.utcnow(),
                }
            },
        )

    return {
        "success": True,
        "submissionId": submission_id,
        "status": SubmissionStatus.evaluating.value,
        "message": "Test submitted. Evaluation in progress.",
    }


@router.post("/results")
def get_results(requestBody: dict):
    auth_token = requestBody.get("authToken")
    test_id = requestBody.get("testId")

    user_hash = _validate_auth(auth_token)

    mongo = MongoDB()
    mongo.selectCollection("submissions")
    submission = mongo.find({"testId": test_id, "userHash": user_hash}, limit=1)

    if not submission:
        return {
            "success": False,
            "status": "not_found",
            "message": "No submission found for this test.",
        }

    submission = submission[0]
    test_data = _get_test_data(test_id)

    status = submission.get("status", "pending")
    evaluation = submission.get("evaluation")
    screenshot = submission.get("screenshot")
    screenshot_mobile = submission.get("screenshotMobile")
    runtime = submission.get("runtimeResult", {})

    return {
        "success": True,
        "status": status,
        "testId": test_id,
        "testName": test_data.get("name", ""),
        "evaluation": evaluation,
        "screenshot": screenshot,
        "screenshotMobile": screenshot_mobile,
        "consoleErrors": runtime.get("consoleErrors", []),
        "runtimeError": runtime.get("runtimeError"),
        "files": submission.get("files", {}),
        "promptCount": submission.get("promptCount", 0),
        "submittedAt": submission.get("submittedAt"),
        "message": "" if status == "completed" else "Evaluation in progress...",
    }
