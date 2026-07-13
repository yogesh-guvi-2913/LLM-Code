"""
Flash template management routes for admin dashboard.

Provides endpoints for:
- Listing available templates
- Creating new templates
- Scaling warm pools
- Health checks
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.flash_service import (
    FlashClient,
    FlashTemplate,
    FlashError,
    get_flash_client,
    is_flash_enabled,
    check_flash_health,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# -------------------------------------------------------------------------
# Request/Response Models
# -------------------------------------------------------------------------

class FlashHealthResponse(BaseModel):
    enabled: bool
    healthy: bool
    message: Optional[str] = None
    response: Optional[dict] = None


class FlashTemplateResponse(BaseModel):
    id: str
    slug: str = ""
    title: str = ""
    language: str = ""
    description: str = ""
    image: str = ""
    min_warm: int = 0
    vcpu: float = 0.5
    memory_mb: int = 512
    pids_limit: int = 150
    kind: str = "api"
    dev_cmd: str = ""
    warm_count: Optional[int] = None
    active_count: Optional[int] = None


class CreateTemplateRequest(BaseModel):
    id: str = Field(..., pattern=r"^[a-z0-9][a-z0-9-]{0,31}$", description="Template ID")
    title: str = Field(..., min_length=1, max_length=100)
    language: str = Field(..., min_length=1)
    description: str = ""
    image: str = Field(..., description="Docker image name")
    kind: str = Field(default="api", pattern=r"^(api|frontend)$")
    dev_cmd: str = Field(..., description="Command to run dev server")
    min_warm: int = Field(default=1, ge=0, le=10)
    vcpu: float = Field(default=0.5, gt=0)
    memory_mb: int = Field(default=512, gt=0)
    pids_limit: int = Field(default=150, gt=0)


class ScaleTemplateRequest(BaseModel):
    min_warm: int = Field(..., ge=0, le=10)


class FlashStatsResponse(BaseModel):
    templates: List[dict]
    total_warm: int
    total_active: int


# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------

@router.get("/health", response_model=FlashHealthResponse)
async def get_flash_health():
    """
    Check Flash service health and connectivity.
    
    Returns:
        - enabled: Whether Flash integration is enabled
        - healthy: Whether Flash is responding
        - message: Error message if unhealthy
    """
    result = check_flash_health()
    return FlashHealthResponse(**result)


@router.get("/templates", response_model=List[FlashTemplateResponse])
async def list_templates():
    """
    List all available Flash templates with warm pool status.
    
    Each template includes:
    - Basic metadata (id, title, language, kind)
    - Resource limits (vcpu, memory, pids)
    - Warm pool status (min_warm, actual warm/active counts)
    """
    if not is_flash_enabled():
        raise HTTPException(status_code=503, detail="Flash integration is disabled")
    
    try:
        client = get_flash_client()
        templates = client.list_templates()
        
        stats = client.get_stats()
        warm_counts = {s.get("question_id"): s for s in stats}
        
        result = []
        for t in templates:
            stat = warm_counts.get(t.id, {})
            result.append(FlashTemplateResponse(
                id=t.id,
                slug=t.slug,
                title=t.title,
                language=t.language,
                description=t.description,
                image=t.image,
                min_warm=t.min_warm,
                vcpu=t.vcpu,
                memory_mb=t.memory_mb,
                pids_limit=t.pids_limit,
                kind=t.kind,
                dev_cmd=t.dev_cmd,
                warm_count=stat.get("warm", 0),
                active_count=stat.get("active", 0),
            ))
        
        return result
        
    except FlashError as e:
        logger.error(f"Failed to list templates: {e}")
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/templates/{template_id}", response_model=FlashTemplateResponse)
async def get_template(template_id: str):
    """Get details for a specific template."""
    if not is_flash_enabled():
        raise HTTPException(status_code=503, detail="Flash integration is disabled")
    
    try:
        client = get_flash_client()
        template = client.get_template(template_id)
        
        if not template:
            raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
        
        stats = client.get_stats()
        stat = next((s for s in stats if s.get("question_id") == template_id), {})
        
        return FlashTemplateResponse(
            id=template.id,
            slug=template.slug,
            title=template.title,
            language=template.language,
            description=template.description,
            image=template.image,
            min_warm=template.min_warm,
            vcpu=template.vcpu,
            memory_mb=template.memory_mb,
            pids_limit=template.pids_limit,
            kind=template.kind,
            dev_cmd=template.dev_cmd,
            warm_count=stat.get("warm", 0),
            active_count=stat.get("active", 0),
        )
        
    except FlashError as e:
        logger.error(f"Failed to get template {template_id}: {e}")
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/templates", response_model=FlashTemplateResponse)
async def create_template(request: CreateTemplateRequest):
    """
    Register a new Flash template.
    
    The Docker image must already exist in the daemon.
    Flash will validate the image and start warming the pool.
    
    Required:
    - id: Alphanumeric with dashes, 1-32 chars
    - title: Display name
    - language: Programming language
    - image: Docker image name (must exist)
    - dev_cmd: Command to run dev server
    
    Optional:
    - kind: "api" (default) or "frontend"
    - min_warm: Pool size (default 1, max 10)
    - resource limits: vcpu, memory_mb, pids_limit
    """
    if not is_flash_enabled():
        raise HTTPException(status_code=503, detail="Flash integration is disabled")
    
    try:
        client = get_flash_client()
        
        template_data = {
            "id": request.id,
            "title": request.title,
            "language": request.language,
            "description": request.description,
            "image": request.image,
            "kind": request.kind,
            "dev_cmd": request.dev_cmd,
            "min_warm": request.min_warm,
            "vcpu": request.vcpu,
            "memory_mb": request.memory_mb,
            "pids_limit": request.pids_limit,
        }
        
        template = client.create_template(template_data)
        
        logger.info(f"Created Flash template: {template.id}")
        
        return FlashTemplateResponse(
            id=template.id,
            slug=template.slug,
            title=template.title,
            language=template.language,
            description=template.description,
            image=template.image,
            min_warm=template.min_warm,
            vcpu=template.vcpu,
            memory_mb=template.memory_mb,
            pids_limit=template.pids_limit,
            kind=template.kind,
            dev_cmd=template.dev_cmd,
            warm_count=0,
            active_count=0,
        )
        
    except FlashError as e:
        logger.error(f"Failed to create template: {e}")
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/templates/{template_id}/scale")
async def scale_template(template_id: str, request: ScaleTemplateRequest):
    """
    Scale the warm pool size for a template.
    
    min_warm: Number of pre-warmed containers (0-10)
    """
    if not is_flash_enabled():
        raise HTTPException(status_code=503, detail="Flash integration is disabled")
    
    try:
        client = get_flash_client()
        result = client.scale_template(template_id, request.min_warm)
        
        logger.info(f"Scaled template {template_id} to min_warm={request.min_warm}")
        
        return {"success": True, "template_id": template_id, "min_warm": request.min_warm}
        
    except FlashError as e:
        logger.error(f"Failed to scale template {template_id}: {e}")
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/stats", response_model=FlashStatsResponse)
async def get_flash_stats():
    """
    Get Flash service statistics.
    
    Returns warm pool and active session counts per template.
    """
    if not is_flash_enabled():
        raise HTTPException(status_code=503, detail="Flash integration is disabled")
    
    try:
        client = get_flash_client()
        stats = client.get_stats()
        
        total_warm = sum(s.get("warm", 0) for s in stats)
        total_active = sum(s.get("active", 0) for s in stats)
        
        return FlashStatsResponse(
            templates=stats,
            total_warm=total_warm,
            total_active=total_active,
        )
        
    except FlashError as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/usage")
async def get_flash_usage():
    """
    Get Flash usage and cost metrics.
    
    Returns:
    - sandbox_hours: Total billed sandbox hours
    - density: Containers per node
    - cost_per_sandbox_hour: Estimated cost
    """
    if not is_flash_enabled():
        raise HTTPException(status_code=503, detail="Flash integration is disabled")
    
    try:
        client = get_flash_client()
        usage = client.get_usage()
        return {"success": True, "usage": usage}
        
    except FlashError as e:
        logger.error(f"Failed to get usage: {e}")
        raise HTTPException(status_code=e.status_code, detail=e.message)