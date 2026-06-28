import asyncio
import json
import logging
from typing import Dict, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime

from app.redis.async_version.utils import MyRedis
from app.mongodb.sync.mongo import MongoDB
from app.routes.ai.llm_router import get_llm_router
from app.routes.ai.prompt_builder import build_system_prompt

logger = logging.getLogger(__name__)

PROMPT_HISTORY_KEY_PREFIX = "prompt_history:"


async def _safe_send(websocket: WebSocket, data: dict) -> bool:
    try:
        await websocket.send_json(data)
        return True
    except (WebSocketDisconnect, RuntimeError, Exception):
        return False


async def _safe_close(websocket: WebSocket):
    try:
        await websocket.close()
    except (WebSocketDisconnect, RuntimeError, Exception):
        pass


async def validate_token(token: str) -> Optional[str]:
    if not token:
        return None
    try:
        user_data = await MyRedis.hgetall(token)
        if not user_data or 'hash' not in user_data:
            return None
        if isinstance(user_data.get('hash'), bytes):
            return user_data['hash'].decode('utf-8')
        return user_data.get('hash')
    except Exception as e:
        logger.error(f"Token validation error: {e}")
        return None


async def get_test_data(test_id: str) -> Optional[Dict[str, Any]]:
    try:
        mongo = MongoDB()
        mongo.selectCollection("tests")
        test_results = mongo.find({"testId": test_id}, limit=1)
        if test_results:
            return test_results[0]
        return None
    except Exception as e:
        logger.error(f"Error fetching test data: {e}")
        return None


async def store_prompt_history(
    user_hash: str,
    test_id: str,
    user_message: str,
    ai_response: str,
    code_changes: list
):
    try:
        key = f"{PROMPT_HISTORY_KEY_PREFIX}{user_hash}:{test_id}"
        
        history = await MyRedis.get(key)
        if history:
            if isinstance(history, bytes):
                history = history.decode('utf-8')
            history_list = json.loads(history)
        else:
            history_list = []
        
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "userMessage": user_message,
            "aiResponse": ai_response,
            "codeChanges": code_changes
        }
        history_list.append(entry)
        
        await MyRedis.setx(key, 86400, json.dumps(history_list))
        
    except Exception as e:
        logger.error(f"Error storing prompt history: {e}")


async def handle_websocket_connection(
    websocket: WebSocket,
    test_id: str,
    token: str
):
    try:
        await websocket.accept()
    except Exception as e:
        logger.warning(f"Failed to accept WebSocket: {e}")
        return
    
    logger.info(f"WebSocket connected for testId: {test_id}")
    
    user_hash = await validate_token(token)
    if not user_hash:
        if not await _safe_send(websocket, {"type": "error", "error": "Invalid or expired token"}):
            return
        await _safe_close(websocket)
        return
    
    test_data = await get_test_data(test_id)
    if not test_data:
        if not await _safe_send(websocket, {"type": "error", "error": "Test not found"}):
            return
        await _safe_close(websocket)
        return
    
    problem_name = test_data.get("name", "Unknown Problem")
    problem_description = test_data.get("description", "")
    requirements = test_data.get("details", [])
    
    llm = get_llm_router()
    if not llm.is_available():
        if not await _safe_send(websocket, {"type": "error", "error": "AI service not configured"}):
            return
        await _safe_close(websocket)
        return
    
    if not await _safe_send(websocket, {"type": "connected"}):
        return
    
    conversation_history = []
    
    try:
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "ping":
                await _safe_send(websocket, {"type": "pong"})
                continue
            
            user_message = data.get("message", "")
            current_files = data.get("currentFiles", {})
            
            if not user_message:
                continue
            
            conversation_history.append({
                "role": "user",
                "content": user_message
            })
            
            system_prompt = build_system_prompt(
                problem_name=problem_name,
                problem_description=problem_description,
                requirements=requirements,
                current_files=current_files
            )
            
            accumulated_response = ""
            code_changes_received = []
            client_disconnected = False
            
            try:
                async for chunk in llm.stream_chat(
                    system_prompt=system_prompt,
                    messages=conversation_history
                ):
                    chunk_type = chunk.get("type")
                    
                    if chunk_type == "text":
                        text = chunk.get("content", "")
                        accumulated_response += text
                        if not await _safe_send(websocket, {"type": "text", "content": text}):
                            client_disconnected = True
                            break
                    
                    elif chunk_type == "code":
                        files = chunk.get("files", [])
                        code_changes_received = files
                        if not await _safe_send(websocket, {"type": "code", "files": files}):
                            client_disconnected = True
                            break
                    
                    elif chunk_type == "done":
                        await _safe_send(websocket, {"type": "done"})
                    
                    elif chunk_type == "error":
                        await _safe_send(websocket, {"type": "error", "error": chunk.get("error")})
                
                if not client_disconnected:
                    conversation_history.append({
                        "role": "assistant",
                        "content": accumulated_response
                    })
                    
                    await store_prompt_history(
                        user_hash=user_hash,
                        test_id=test_id,
                        user_message=user_message,
                        ai_response=accumulated_response,
                        code_changes=code_changes_received
                    )
                    
            except Exception as e:
                logger.error(f"Error streaming LLM response: {e}")
                await _safe_send(websocket, {"type": "error", "error": str(e)})
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for testId: {test_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await _safe_close(websocket)
