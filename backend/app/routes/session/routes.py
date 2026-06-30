import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException

from app.routes.session.model import (
    SessionStartRequest,
    SessionStopRequest,
    SyncFilesRequest,
    CreateTestRequest,
)
from app.services.docker_orchestrator import DockerOrchestrator
from app.services.file_sync import sync_files_to_session
from app.services.nginx_config import create_session_config, remove_session_config
from app.services.stack_generator import generate_project, AVAILABLE_STACKS
from app.redis.sync.rediscache import RedisCache
from app.mongodb.sync.mongo import MongoDB

logger = logging.getLogger(__name__)

router = APIRouter()

docker_orchestrator = DockerOrchestrator()

SESSION_KEY_PREFIX = "session:"
SESSION_EXPIRY = 7200


def _validate_auth(auth_token: str) -> str:
    if not auth_token:
        raise HTTPException(status_code=400, detail="authToken required")

    redis = RedisCache()
    user_data = redis.getAllData(auth_token)

    if not user_data or "hash" not in user_data:
        raise HTTPException(status_code=401, detail="token_expired")

    return user_data["hash"]


def _get_test_data(test_id: str) -> dict:
    mongo = MongoDB()
    mongo.selectCollection("tests")
    result = mongo.find({"testId": test_id}, limit=1)

    if not result:
        raise HTTPException(status_code=404, detail="Test not found")

    return result[0]


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

@router.post("/session/start")
async def start_session(request: SessionStartRequest):
    user_hash = _validate_auth(request.authToken)
    test_data = _get_test_data(request.testId)

    project_files = test_data.get("projectFiles", {})
    compose_content = test_data.get("composeContent", "")
    initial_files = test_data.get("initialFiles", {})

    try:
        session_info = await docker_orchestrator.start_session(
            test_id=request.testId,
            user_hash=user_hash,
            project_files=project_files,
            compose_content=compose_content,
            initial_files=initial_files,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    create_session_config(session_info["sessionId"])

    redis = RedisCache()
    key = f"{SESSION_KEY_PREFIX}{session_info['sessionId']}"
    redis.setex(
        key,
        SESSION_EXPIRY,
        json.dumps({
            "testId": request.testId,
            "userHash": user_hash,
            "frontendUrl": session_info["frontendUrl"],
            "backendUrl": session_info["backendUrl"],
        }),
    )

    return {"success": True, "session": session_info}


@router.post("/session/stop")
async def stop_session(request: SessionStopRequest):
    _validate_auth(request.authToken)

    session_id = request.sessionId

    await docker_orchestrator.stop_session(session_id)
    remove_session_config(session_id)

    redis = RedisCache()
    redis.delete(f"{SESSION_KEY_PREFIX}{session_id}")

    return {"success": True}


@router.post("/session/status")
async def session_status(requestBody: dict):
    auth_token = requestBody.get("authToken")
    _validate_auth(auth_token)

    session_id = requestBody.get("sessionId")
    if not session_id:
        raise HTTPException(status_code=400, detail="sessionId required")

    status = docker_orchestrator.get_session_status(session_id)
    return {"success": True, "status": status}


@router.post("/session/sync-files")
async def sync_files_endpoint(request: SyncFilesRequest):
    changes = [c.model_dump() for c in request.changes]
    success = await sync_files_to_session(request.sessionId, changes)
    return {"success": success}


# ---------------------------------------------------------------------------
# Container logs via WebSocket
# ---------------------------------------------------------------------------

@router.websocket("/ws/session-logs/{session_id}")
async def session_logs_ws(websocket: WebSocket, session_id: str):
    await websocket.accept()

    try:
        async for log in docker_orchestrator.stream_logs(session_id):
            await websocket.send_json(log)
    except WebSocketDisconnect:
        logger.info(f"Logs WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"Logs WebSocket error: {e}")
        try:
            await websocket.send_json({"service": "system", "line": f"Error: {e}"})
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Admin: template upload / management
# ---------------------------------------------------------------------------

@router.get("/admin/stacks/available")
async def list_available_stacks():
    return {"success": True, "stacks": AVAILABLE_STACKS}


@router.post("/admin/stacks/generate")
async def generate_stack_project(requestBody: dict):
    _validate_auth(requestBody.get("authToken"))

    tech_stack = requestBody.get("techStack", {})
    project = generate_project(tech_stack)
    return {"success": True, "project": project}


# ---------------------------------------------------------------------------
# Admin: create/update test document
# ---------------------------------------------------------------------------

@router.post("/admin/test/create")
async def create_test(request: CreateTestRequest):
    _validate_auth(request.authToken)

    mongo = MongoDB()
    mongo.selectCollection("tests")

    existing = mongo.find({"testId": request.testId}, limit=1)

    project = generate_project(request.techStack) if request.techStack else {"files": {}, "meta": {}, "composeContent": ""}

    test_doc = {
        "testId": request.testId,
        "name": request.name,
        "description": request.description,
        "duration": request.duration,
        "codeEdit": request.codeEdit,
        "requirements": request.requirements,
        "checks": request.checks,
        "techStack": request.techStack,
        "projectFiles": project["files"],
        "composeContent": project["composeContent"],
        "projectMeta": project["meta"],
        "initialFiles": {},
    }

    if existing:
        mongo.updateOne({"testId": request.testId}, {"$set": test_doc})
    else:
        mongo.insertOne(test_doc)

    return {"success": True, "testId": request.testId, "filesCount": len(project["files"])}
