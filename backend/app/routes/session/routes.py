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
from app.services.flash_service import FlashClient, FlashTemplate, is_flash_enabled
from app.services.flash_adapter import (
    FlashSandboxAdapter,
    get_flash_adapter,
    is_flash_session,
    get_session_type,
)
from app.redis.sync.rediscache import RedisCache
from app.mongodb.sync.mongo import MongoDB
from app.routes.session.flash_terminal import handle_flash_terminal

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

    flash_template_id = test_data.get("flashTemplateId")
    
    if flash_template_id and is_flash_enabled():
        flash_adapter = get_flash_adapter()
        
        try:
            session_info = await flash_adapter.start_session(
                test_id=request.testId,
                user_hash=user_hash,
                template_id=flash_template_id,
                timeout_seconds=test_data.get("duration", 7200),
            )
            
            logger.info(f"Started Flash session: {session_info['sessionId']} for test {request.testId}")
            
            return {"success": True, "session": session_info}
            
        except Exception as e:
            logger.error(f"Failed to start Flash session: {e}")
            raise HTTPException(status_code=500, detail=str(e))

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
            "sessionType": "docker",
        }),
    )

    return {"success": True, "session": session_info}


@router.post("/session/stop")
async def stop_session(request: SessionStopRequest):
    _validate_auth(request.authToken)

    session_id = request.sessionId
    
    if is_flash_session(session_id):
        flash_adapter = get_flash_adapter()
        await flash_adapter.stop_session(session_id)
        logger.info(f"Stopped Flash session: {session_id}")
    else:
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

    if is_flash_session(session_id):
        flash_adapter = get_flash_adapter()
        status = flash_adapter.get_session_status(session_id)
    else:
        status = docker_orchestrator.get_session_status(session_id)
    
    return {"success": True, "status": status}


@router.post("/session/sync-files")
async def sync_files_endpoint(request: SyncFilesRequest):
    changes = [c.model_dump() for c in request.changes]
    
    if is_flash_session(request.sessionId):
        flash_adapter = get_flash_adapter()
        success = await flash_adapter.sync_files(request.sessionId, changes)
    else:
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


@router.websocket("/ws/flash-terminal/{session_id}")
async def flash_terminal_ws(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for Flash sandbox terminal access."""
    await handle_flash_terminal(websocket, session_id)


# ---------------------------------------------------------------------------
# Admin: template upload / management
# ---------------------------------------------------------------------------

@router.get("/admin/stacks/available")
async def list_available_stacks():
    return {"success": True, "stacks": AVAILABLE_STACKS}


@router.get("/admin/flash/templates")
async def list_flash_templates_for_admin():
    """List available Flash templates for test creation."""
    if not is_flash_enabled():
        return {"success": False, "enabled": False, "templates": [], "message": "Flash integration disabled"}
    
    try:
        flash_client = FlashClient()
        templates = flash_client.list_templates()
        stats = flash_client.get_stats()
        
        warm_counts = stats.get("warm", {})
        
        result = []
        for t in templates:
            result.append({
                "id": t.id,
                "title": t.title,
                "language": t.language,
                "kind": t.kind,
                "description": t.description,
                "min_warm": t.min_warm,
                "warm_count": warm_counts.get(t.id, 0),
                "image": t.image,
            })
        
        return {
            "success": True, 
            "enabled": True, 
            "templates": result
        }
        
    except Exception as e:
        logger.error(f"Failed to list Flash templates: {e}")
        return {
            "success": False, 
            "enabled": True, 
            "templates": [], 
            "message": str(e)
        }


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

    if not request.flashTemplateId:
        raise HTTPException(status_code=400, detail="flashTemplateId is required")

    if not is_flash_enabled():
        raise HTTPException(status_code=503, detail="Flash integration is disabled. Start Flash service to create tests.")

    mongo = MongoDB()
    mongo.selectCollection("tests")

    existing = mongo.find({"testId": request.testId}, limit=1)
    
    flash_template = None
    flash_initial_files = {}
    flash_sandbox = None
    
    try:
        flash_client = FlashClient()
        flash_template = flash_client.get_template(request.flashTemplateId)
        
        if not flash_template:
            raise HTTPException(
                status_code=404, 
                detail=f"Flash template '{request.flashTemplateId}' not found"
            )
        
        logger.info(f"Creating sandbox from template {request.flashTemplateId} to extract files...")
        
        flash_sandbox = flash_client.create_sandbox(
            template_id=request.flashTemplateId,
            timeout_seconds=120,
            metadata={"purpose": "test_creation", "testId": request.testId}
        )
        
        files = flash_client.list_files(flash_sandbox.id)
        
        EXCLUDED_PATTERNS = ['node_modules', '.git', '__pycache__', '.venv', 'venv', '.env', 
                             'dist', 'build', '.next', 'coverage', '.pytest_cache']
        
        for file_path in files:
            if any(pattern in file_path for pattern in EXCLUDED_PATTERNS):
                continue
            
            if file_path.startswith('.') and not file_path.startswith('./'):
                continue
            
            try:
                content = flash_client.read_file(flash_sandbox.id, file_path)
                if content and len(content) > 0:
                    flash_initial_files[file_path] = content
            except Exception as e:
                logger.warning(f"Could not read file {file_path}: {e}")
                continue
        
        logger.info(f"Extracted {len(flash_initial_files)} files from Flash template {request.flashTemplateId}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get Flash template: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get Flash template: {str(e)}")
    finally:
        if flash_sandbox:
            try:
                flash_client.kill_sandbox(flash_sandbox.id)
            except Exception as e:
                logger.warning(f"Failed to kill sandbox: {e}")

    project = {
        "files": flash_initial_files,
        "meta": {
            "template": flash_template.id,
            "title": flash_template.title,
            "language": flash_template.language,
            "kind": flash_template.kind,
            "description": flash_template.description,
        },
        "composeContent": "",
    }

    test_doc = {
        "testId": request.testId,
        "name": request.name,
        "description": request.description,
        "duration": request.duration,
        "codeEdit": request.codeEdit,
        "requirements": request.requirements,
        "checks": request.checks,
        "techStack": {},
        "projectFiles": project["files"],
        "composeContent": project["composeContent"],
        "projectMeta": project["meta"],
        "initialFiles": {},
        "flashTemplateId": request.flashTemplateId,
        "flashScoringEnabled": request.flashScoringEnabled,
        "flashTemplateMeta": {
            "id": flash_template.id,
            "title": flash_template.title,
            "language": flash_template.language,
            "kind": flash_template.kind,
            "image": flash_template.image,
        },
        "sessionType": "flash",
    }

    if existing:
        mongo.updateOne({"testId": request.testId}, {"$set": test_doc})
    else:
        mongo.insertOne(test_doc)

    return {
        "success": True, 
        "testId": request.testId, 
        "filesCount": len(project["files"]),
        "flashTemplate": request.flashTemplateId,
        "template": {
            "id": flash_template.id,
            "language": flash_template.language,
            "kind": flash_template.kind,
        }
    }


@router.post("/session/execute")
async def execute_command(requestBody: dict):
    _validate_auth(requestBody.get("authToken"))

    session_id = requestBody.get("sessionId")
    command = requestBody.get("command")
    service = requestBody.get("service", "frontend")

    if not session_id or not command:
        raise HTTPException(status_code=400, detail="sessionId and command required")

    if is_flash_session(session_id):
        flash_adapter = get_flash_adapter()
        result = await flash_adapter.execute_command(session_id, command)
    else:
        result = await docker_orchestrator.execute_command(session_id, command, service)
    
    return result


@router.post("/session/submit")
async def submit_session(requestBody: dict):
    """Submit session for scoring (Flash only)."""
    _validate_auth(requestBody.get("authToken"))
    
    session_id = requestBody.get("sessionId")
    if not session_id:
        raise HTTPException(status_code=400, detail="sessionId required")
    
    if not is_flash_session(session_id):
        raise HTTPException(status_code=400, detail="Submit/score only available for Flash sessions")
    
    flash_adapter = get_flash_adapter()
    score_result = await flash_adapter.submit_and_score(session_id)
    
    if score_result is None:
        raise HTTPException(status_code=500, detail="Failed to score submission")
    
    return {
        "success": True,
        "score": score_result.score,
        "maxScore": score_result.max_score,
        "percentage": score_result.percentage,
        "testResults": score_result.test_results,
    }


@router.get("/session/{session_id}/files")
async def list_session_files(session_id: str, authToken: str):
    """List files in a session."""
    _validate_auth(authToken)
    
    if is_flash_session(session_id):
        flash_adapter = get_flash_adapter()
        files = flash_adapter.list_files(session_id)
    else:
        files = docker_orchestrator.list_files(session_id)
    
    return {"success": True, "files": files}


@router.get("/session/{session_id}/file")
async def read_session_file(session_id: str, path: str, authToken: str):
    """Read a file from a session."""
    _validate_auth(authToken)
    
    if is_flash_session(session_id):
        flash_adapter = get_flash_adapter()
        content = flash_adapter.read_file(session_id, path)
    else:
        content = docker_orchestrator.read_file(session_id, path)
    
    return {"success": True, "path": path, "content": content}
