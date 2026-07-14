"""
Flash Terminal WebSocket Proxy

Proxies terminal connections from frontend to Flash sandbox terminals.
This allows real-time terminal access to Flash sandboxes through
LLM-Code's WebSocket endpoint.
"""

import asyncio
import logging
import json
import websockets
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect

from app.services.flash_adapter import get_flash_adapter, is_flash_session

logger = logging.getLogger(__name__)


class FlashTerminalProxy:
    """
    Proxies terminal WebSocket connections to Flash sandbox.
    
    Flow:
    Frontend WebSocket <-> LLM-Code <-> Flash Terminal WebSocket
    """
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.flash_ws: Optional[websockets.WebSocketClientProtocol] = None
        self.client_ws: Optional[WebSocket] = None
        self._running = False
    
    async def connect_to_flash(self) -> bool:
        """Connect to Flash terminal WebSocket."""
        flash_adapter = get_flash_adapter()
        terminal_url = flash_adapter.get_terminal_url(self.session_id)
        
        if not terminal_url:
            logger.error(f"No terminal URL for session {self.session_id}")
            return False
        
        try:
            self.flash_ws = await websockets.connect(
                terminal_url,
                ping_interval=30,
                ping_timeout=10,
            )
            logger.info(f"Connected to Flash terminal: {terminal_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Flash terminal: {e}")
            return False
    
    async def proxy_loop(self, client_ws: WebSocket):
        """Run the proxy loop between client and Flash."""
        self.client_ws = client_ws
        self._running = True
        
        if not await self.connect_to_flash():
            await client_ws.send_json({"error": "Failed to connect to Flash terminal"})
            return
        
        await asyncio.gather(
            self._client_to_flash(),
            self._flash_to_client(),
        )
    
    async def _client_to_flash(self):
        """Forward messages from client to Flash."""
        try:
            while self._running:
                try:
                    data = await self.client_ws.receive_text()
                    
                    try:
                        msg = json.loads(data)
                        if msg.get("type") == "resize":
                            resize_msg = json.dumps({
                                "type": "resize",
                                "cols": msg.get("cols", 80),
                                "rows": msg.get("rows", 24),
                            })
                            await self.flash_ws.send(resize_msg)
                        elif msg.get("type") == "input":
                            input_data = msg.get("data", "")
                            await self.flash_ws.send(input_data)
                        else:
                            await self.flash_ws.send(data)
                    except json.JSONDecodeError:
                        await self.flash_ws.send(data)
                        
                except WebSocketDisconnect:
                    logger.info(f"Client disconnected from session {self.session_id}")
                    break
                    
        except Exception as e:
            logger.error(f"Error in client->Flash proxy: {e}")
        finally:
            self._running = False
    
    async def _flash_to_client(self):
        """Forward messages from Flash to client."""
        try:
            while self._running:
                try:
                    data = await asyncio.wait_for(
                        self.flash_ws.recv(),
                        timeout=1.0
                    )
                    
                    if isinstance(data, bytes):
                        data = data.decode("utf-8", errors="replace")
                    
                    await self.client_ws.send_json({
                        "type": "output",
                        "data": data,
                    })
                    
                except asyncio.TimeoutError:
                    continue
                except websockets.exceptions.ConnectionClosed:
                    logger.info(f"Flash terminal closed for session {self.session_id}")
                    break
                    
        except Exception as e:
            logger.error(f"Error in Flash->client proxy: {e}")
        finally:
            self._running = False
    
    async def close(self):
        """Close all connections."""
        self._running = False
        if self.flash_ws:
            await self.flash_ws.close()
        logger.info(f"Closed Flash terminal proxy for session {self.session_id}")


async def handle_flash_terminal(websocket: WebSocket, session_id: str):
    """
    Handle Flash terminal WebSocket connection.
    
    Args:
        websocket: FastAPI WebSocket from frontend
        session_id: Flash sandbox ID
    """
    await websocket.accept()
    
    if not is_flash_session(session_id):
        await websocket.send_json({"error": "Not a Flash session"})
        await websocket.close()
        return
    
    proxy = FlashTerminalProxy(session_id)
    
    try:
        await proxy.proxy_loop(websocket)
    except Exception as e:
        logger.error(f"Terminal proxy error: {e}")
    finally:
        await proxy.close()