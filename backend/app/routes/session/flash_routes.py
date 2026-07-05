"""Flash sandbox integration routes"""

import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from datetime import datetime
from typing import Dict, Any

from app.config.sandbox_provider import sandbox_config
from app.services.flash.client import flash_client
from app.services.hybrid_scorer import HybridScorer
from app.mongodb.sync.mongo import MongoDB
from app.redis.sync.rediscache import RedisCache

logger = logging.getLogger(__name__)

router = APIRouter()

hybrid_scorer = HybridScorer()


def _validate_auth(auth_token: str) -> str:
    """Validate auth token and return user hash"""
    if not auth_token:
        raise HTTPException(status_code=400, detail="authToken required")

    redis = RedisCache()
    user_data = redis.getAllData(auth_token)

    if not user_data or "hash" not in user_data:
        raise HTTPException(status_code=401, detail="token_expired")

    return user_data["hash"]


def _get_test_data(test_id: str) -> dict:
    """Get test data from MongoDB"""
    mongo = MongoDB()
    mongo.selectCollection("tests")
    result = mongo.find({"testId": test_id}, limit=1)

    if not result:
        raise HTTPException(status_code=404, detail="Test not found")

    return result[0]


@router.post("/flash/start")
async def start_flash_session(requestBody: dict):
    """Start a Flash sandbox session"""
    auth_token = requestBody.get("authToken")
    test_id = requestBody.get("testId")

    user_hash = _validate_auth(auth_token)
    test_data = _get_test_data(test_id)

    flash_template_id = test_data.get("flashTemplateId", "q1")

    if not test_data.get("flashTemplateRegistered", False):
        flash_template_id = "q1"

    try:
        client = flash_client.get_client()
        sandbox = client.sandboxes.create(
            template=flash_template_id,
            timeout=3600
        )

        logger.info(f"Created Flash sandbox: {sandbox.id}")

        mongo = MongoDB()
        mongo.selectCollection("test-mapper")
        mapper_result = mongo.find({"hash": user_hash, "testId": test_id}, limit=1)

        if mapper_result:
            mongo.updateOne(
                {"hash": user_hash, "testId": test_id},
                {"$set": {
                    "flashSessionId": sandbox.id,
                    "updatedAt": datetime.utcnow()
                }}
            )
        else:
            mongo.insertOne({
                "hash": user_hash,
                "testId": test_id,
                "flashSessionId": sandbox.id,
                "createdAt": datetime.utcnow(),
                "updatedAt": datetime.utcnow()
            })

        return {
            "success": True,
            "flashSessionId": sandbox.id,
            "sandboxProvider": "flash",
            "appUrl": sandbox.app_url,
            "previewUrl": sandbox.preview_url,
            "terminalUrl": sandbox.terminal_url,
            "message": "Flash sandbox created successfully"
        }

    except Exception as e:
        logger.error(f"Failed to create Flash sandbox: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create sandbox: {str(e)}")


@router.post("/flash/stop")
async def stop_flash_session(requestBody: dict):
    """Stop a Flash sandbox session"""
    auth_token = requestBody.get("authToken")
    session_id = requestBody.get("flashSessionId")

    _validate_auth(auth_token)

    if not session_id:
        raise HTTPException(status_code=400, detail="flashSessionId required")

    try:
        client = flash_client.get_client()
        sandbox = client.sandboxes.connect(session_id)
        sandbox.kill()

        logger.info(f"Destroyed Flash sandbox: {session_id}")

        return {"success": True, "message": "Flash sandbox destroyed"}

    except Exception as e:
        logger.error(f"Failed to destroy Flash sandbox: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to destroy sandbox: {str(e)}")


@router.post("/flash/exec")
async def exec_flash_command(requestBody: dict):
    """Execute command in Flash sandbox"""
    auth_token = requestBody.get("authToken")
    session_id = requestBody.get("flashSessionId")
    command = requestBody.get("command")

    _validate_auth(auth_token)

    if not session_id or not command:
        raise HTTPException(status_code=400, detail="flashSessionId and command required")

    try:
        client = flash_client.get_client()
        sandbox = client.sandboxes.connect(session_id)
        result = sandbox.run(command)

        return {
            "success": True,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exitCode": result.exit_code,
            "duration_ms": result.duration_ms
        }

    except Exception as e:
        logger.error(f"Failed to execute command: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to execute command: {str(e)}")


@router.post("/flash/files/read")
async def read_flash_file(requestBody: dict):
    """Read file from Flash sandbox"""
    auth_token = requestBody.get("authToken")
    session_id = requestBody.get("flashSessionId")
    file_path = requestBody.get("path")

    _validate_auth(auth_token)

    if not session_id or not file_path:
        raise HTTPException(status_code=400, detail="flashSessionId and path required")

    try:
        client = flash_client.get_client()
        sandbox = client.sandboxes.connect(session_id)
        content = sandbox.files.read_text(file_path)

        return {
            "success": True,
            "content": content,
            "path": file_path
        }

    except Exception as e:
        logger.error(f"Failed to read file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")


@router.post("/flash/files/write")
async def write_flash_file(requestBody: dict):
    """Write file to Flash sandbox"""
    auth_token = requestBody.get("authToken")
    session_id = requestBody.get("flashSessionId")
    file_path = requestBody.get("path")
    content = requestBody.get("content")

    _validate_auth(auth_token)

    if not session_id or not file_path or content is None:
        raise HTTPException(status_code=400, detail="flashSessionId, path, and content required")

    try:
        client = flash_client.get_client()
        sandbox = client.sandboxes.connect(session_id)
        sandbox.files.write(file_path, content)

        return {
            "success": True,
            "message": "File written successfully",
            "path": file_path
        }

    except Exception as e:
        logger.error(f"Failed to write file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to write file: {str(e)}")


@router.post("/flash/files/list")
async def list_flash_files(requestBody: dict):
    """List files in Flash sandbox"""
    auth_token = requestBody.get("authToken")
    session_id = requestBody.get("flashSessionId")

    _validate_auth(auth_token)

    if not session_id:
        raise HTTPException(status_code=400, detail="flashSessionId required")

    try:
        client = flash_client.get_client()
        sandbox = client.sandboxes.connect(session_id)
        files = sandbox.files.list()

        return {
            "success": True,
            "files": files,
            "flashSessionId": session_id
        }

    except Exception as e:
        logger.error(f"Failed to list files: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")


@router.post("/flash/submit")
async def submit_flash_test(requestBody: dict):
    """Submit Flash test for scoring"""
    auth_token = requestBody.get("authToken")
    test_id = requestBody.get("testId")
    files = requestBody.get("files", {})
    chat_history = requestBody.get("chatHistory", [])

    user_hash = _validate_auth(auth_token)
    test_data = _get_test_data(test_id)

    mongo = MongoDB()
    mongo.selectCollection("test-mapper")
    mapper_result = mongo.find({"hash": user_hash, "testId": test_id}, limit=1)

    if not mapper_result:
        raise HTTPException(status_code=404, detail="No active Flash session found")

    session_id = mapper_result[0].get("flashSessionId")

    if not session_id:
        raise HTTPException(status_code=404, detail="No Flash session found for this test")

    try:
        scoring_result = await hybrid_scorer.score_submission(
            session_id=session_id,
            test_data=test_data,
            files=files,
            chat_history=chat_history,
            auth_token=auth_token
        )

        return {
            "success": True,
            "scoringMethod": "hybrid",
            "result": scoring_result
        }

    except Exception as e:
        logger.error(f"Failed to score submission: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to score submission: {str(e)}")


@router.post("/flash/results")
async def get_flash_results(requestBody: dict):
    """Get Flash test results"""
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
            "message": "No submission found for this test."
        }

    submission_data = submission[0]
    test_data = _get_test_data(test_id)

    status = submission_data.get("status", "pending")
    scoring_method = submission_data.get("scoringMethod", "hybrid")

    return {
        "success": True,
        "status": status,
        "testId": test_id,
        "testName": test_data.get("name", ""),
        "score": submission_data.get("score", 0),
        "maxScore": submission_data.get("maxScore", 100),
        "flashScore": submission_data.get("flashScore", 0),
        "llmScore": submission_data.get("llmScore", 0),
        "testResults": submission_data.get("testResults", []),
        "feedback": submission_data.get("feedback", ""),
        "requirementsCheck": submission_data.get("requirementsCheck", []),
        "scoringBreakdown": submission_data.get("scoringBreakdown", {}),
        "files": submission_data.get("files", {}),
        "promptCount": submission_data.get("promptCount", 0),
        "submittedAt": submission_data.get("submittedAt"),
        "evaluatedAt": submission_data.get("evaluatedAt"),
        "scoringMethod": scoring_method,
        "message": "" if status == "completed" else "Evaluation in progress...",
    }


@router.websocket("/flash/ws/terminal/{session_id}")
async def flash_terminal_ws(websocket: WebSocket, session_id: str):
    """WebSocket terminal proxy to Flash"""
    await websocket.accept()

    try:
        import websockets

        flash_url = f"{flash_client.base_url.replace('http', 'ws')}/v1/sessions/{session_id}/terminal"

        async with websockets.connect(flash_url) as flash_ws:
            async def forward_to_flash():
                try:
                    while True:
                        data = await websocket.receive_bytes()
                        await flash_ws.send(data)
                except Exception:
                    pass

            async def forward_from_flash():
                try:
                    while True:
                        data = await flash_ws.recv()
                        await websocket.send_bytes(data)
                except Exception:
                    pass

            import asyncio
            await asyncio.gather(
                forward_to_flash(),
                forward_from_flash()
            )

    except WebSocketDisconnect:
        logger.info(f"Terminal WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"Terminal WebSocket error: {e}", exc_info=True)
        try:
            await websocket.close()
        except Exception:
            pass