from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from app.setup.mongo import initMongoSchema
from app.setup.logging import initLogging

from app.routes.admin.admin import router as admin
from app.routes.auth.auth import router as auth
from app.routes.dashboard.dashboard import router as dashboard
from app.routes.evaluation.routes import router as evaluation
from app.routes.session.routes import router as session
from app.routes.ai.chat import handle_websocket_connection

initLogging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application...")
    initMongoSchema()
    yield
    logger.info("Stopping application...")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin)
app.include_router(auth)
app.include_router(dashboard)
app.include_router(evaluation)
app.include_router(session)


@app.websocket("/ws/ai-chat/{test_id}")
async def websocket_ai_chat(websocket: WebSocket, test_id: str):
    token = websocket.query_params.get("token")
    await handle_websocket_connection(websocket, test_id, token or "")


@app.get('/')
def index():
    """Root endpoint - API health check"""
    return {
        "status": "success",
        "message": "LLM Code API is running",
        "database": "MongoDB",
        "version": "1.0.0"
    }