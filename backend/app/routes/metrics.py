from fastapi import APIRouter
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from fastapi.responses import PlainTextResponse

router = APIRouter()

active_sessions = Gauge(
    'active_sessions_total',
    'Number of active sandbox sessions'
)

sessions_created = Counter(
    'sessions_created_total',
    'Total sessions created',
    ['provider']
)

sessions_destroyed = Counter(
    'sessions_destroyed_total',
    'Total sessions destroyed'
)

scoring_requests = Counter(
    'scoring_requests_total',
    'Total scoring requests',
    ['method', 'status']
)

scoring_duration = Histogram(
    'scoring_duration_seconds',
    'Scoring duration in seconds',
    ['scoring_method'],
    buckets=[5, 10, 20, 30, 60, 120]
)

rollout_provider_requests = Counter(
    'rollout_provider_requests_total',
    'Total requests by provider',
    ['provider']
)

rollout_percentage_gauge = Gauge(
    'rollout_percentage',
    'Current rollout percentage'
)

http_requests = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'path', 'status']
)


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    """Prometheus metrics endpoint"""
    
    from app.config.sandbox_provider import sandbox_config
    
    rollout_percentage_gauge.set(sandbox_config.rollout_percentage)
    
    return generate_latest()