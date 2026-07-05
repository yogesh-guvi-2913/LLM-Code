from fastapi import APIRouter, Response
from datetime import datetime
import os
import json

import asyncpg
import redis.asyncio as redis
from app.services.flash.client import flash_client

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check"""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/health/ready")
async def readiness_check():
    """Readiness check - all dependencies"""
    checks = {}
    
    try:
        pg_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/llmcode")
        conn = await asyncpg.connect(pg_url)
        await conn.execute("SELECT 1")
        await conn.close()
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {str(e)}"
    
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        r = redis.from_url(redis_url)
        await r.ping()
        await r.close()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {str(e)}"
    
    try:
        if flash_client.health_check():
            checks["flash"] = "ok"
        else:
            checks["flash"] = "error: unhealthy"
    except Exception as e:
        checks["flash"] = f"error: {str(e)}"
    
    all_ok = all(v == "ok" for v in checks.values())
    
    status_code = 200 if all_ok else 503
    
    return Response(
        content=json.dumps({
            "status": "ready" if all_ok else "not_ready",
            "checks": checks,
            "timestamp": datetime.utcnow().isoformat()
        }),
        status_code=status_code,
        media_type="application/json"
    )


@router.get("/health/live")
async def liveness_check():
    """Liveness check"""
    return {"status": "alive"}