"""
Health Check Routes with Redis Integration
System status, diagnostic endpoints, and Redis monitoring
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import asyncio
import logging
from datetime import datetime

from app.config import settings
from app.state.redis_mutex import redis_mutex, RedisConnectionError

logger = logging.getLogger(__name__)

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    service: str
    version: str
    environment: str
    checks: Dict[str, Any]


class RedisHealthCheck(BaseModel):
    """Redis-specific health check response."""
    connected: bool
    status: str
    ping_ms: Optional[float] = None
    redis_version: Optional[str] = None
    used_memory_human: Optional[str] = None
    connected_clients: Optional[int] = None
    error: Optional[str] = None


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Enhanced health check with Redis status."""

    # Check Redis connectivity
    redis_health = await check_redis_health()

    # Determine overall system health
    overall_status = "healthy"
    if redis_health.status == "error":
        overall_status = "degraded"
    elif not redis_health.connected:
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        service="peerring-backend",
        version="0.1.0",
        environment=settings.ENVIRONMENT,
        checks={
            "foundation": "active",
            "contracts": "loaded",
            "redis": redis_health.status,
            "redis_connected": redis_health.connected,
            "prism": "disabled" if not settings.PRISM_ENABLED else "enabled",
            "websockets": "active"
        }
    )


@router.get("/health/detailed")
async def detailed_health_check():
    """Comprehensive health check with component details and performance metrics."""

    start_time = datetime.utcnow()

    # Redis health check
    redis_health = await check_redis_health()

    # Configuration checks
    config_checks = {
        "redis_configured": bool(settings.REDIS_URL),
        "prism_configured": bool(settings.PRISMTRACE_HOST and settings.PRISMTRACE_PROJECT_ID),
        "llm_providers": {
            "openai": "configured" if settings.OPENAI_API_KEY else "not_configured",
            "anthropic": "configured" if settings.ANTHROPIC_API_KEY else "not_configured"
        },
        "environment": settings.ENVIRONMENT,
        "debug_mode": settings.DEBUG
    }

    # Governance settings
    governance_checks = {
        "leak_judge": settings.LEAK_JUDGE_ENABLED,
        "help_judge": settings.HELP_JUDGE_ENABLED,
        "adversarial_resistance": settings.ADVERSARIAL_RESISTANCE_ENABLED,
        "default_model": settings.DEFAULT_MODEL,
        "max_tokens": settings.MAX_TOKENS
    }

    # Performance metrics
    health_check_time = (datetime.utcnow() - start_time).total_seconds() * 1000

    return {
        "status": "healthy" if redis_health.connected else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "health_check_time_ms": round(health_check_time, 2),
        "foundation_layer": "redis-turn-mutex",
        "branch": "foundation/redis-turn-mutex",
        "components": {
            "redis": redis_health.model_dump(),
            "configuration": config_checks,
            "governance": governance_checks,
            "websocket": {
                "status": "active",
                "endpoint": "/api/v1/ws/{session_id}"
            },
            "contracts": {
                "base_agent": "implemented",
                "base_judge": "implemented",
                "mock_registry": "active"
            }
        },
        "performance_targets": {
            "redis_operations": "< 100ms",
            "governance_evaluation": "< 250ms",
            "websocket_response": "< 500ms",
            "turn_lock_timeout": f"{settings.REDIS_TURN_LOCK_TTL}s"
        }
    }


@router.get("/health/redis", response_model=RedisHealthCheck)
async def redis_health_check():
    """Dedicated Redis health check endpoint."""
    return await check_redis_health()


async def check_redis_health() -> RedisHealthCheck:
    """
    Perform comprehensive Redis health check.

    Returns:
        RedisHealthCheck with connection status and metrics
    """
    if not redis_mutex._connected:
        try:
            await redis_mutex.connect()
        except Exception as e:
            return RedisHealthCheck(
                connected=False,
                status="error",
                error=f"Connection failed: {str(e)}"
            )

    try:
        # Get detailed health information from Redis mutex
        health_data = await redis_mutex.health_check()

        return RedisHealthCheck(
            connected=health_data.get("connected", False),
            status=health_data.get("status", "unknown"),
            ping_ms=health_data.get("ping_ms"),
            redis_version=health_data.get("redis_version"),
            used_memory_human=health_data.get("used_memory_human"),
            connected_clients=health_data.get("connected_clients"),
            error=health_data.get("error")
        )

    except Exception as e:
        return RedisHealthCheck(
            connected=False,
            status="error",
            error=str(e)
        )


@router.get("/setup-doctor")
async def setup_doctor():
    """
    Enhanced setup diagnostic for Redis mutex implementation.
    Verifies foundation + Redis integration readiness.
    """
    issues = []
    recommendations = []

    # Check foundation layer
    try:
        from app.contracts.base_agent import BaseAgent
        from app.contracts.base_judge import BaseJudge
        from app.state.pydantic_state import PeerRingState
        from app.contracts.mock_registry import MockAgentRegistry
        recommendations.append("✅ Foundation contracts available")
    except ImportError as e:
        issues.append(f"Foundation contracts import failed: {e}")

    # Check Redis configuration
    if not settings.REDIS_URL:
        issues.append("REDIS_URL not configured")
    else:
        recommendations.append(f"✅ Redis configured: {settings.REDIS_URL}")

    # Test Redis connectivity
    redis_health = await check_redis_health()
    if redis_health.connected:
        recommendations.append(f"✅ Redis connected (v{redis_health.redis_version})")
        recommendations.append(f"✅ Redis ping: {redis_health.ping_ms}ms")
    else:
        issues.append(f"Redis connection failed: {redis_health.error}")

    # Check LLM configuration
    if not settings.OPENAI_API_KEY and not settings.ANTHROPIC_API_KEY:
        issues.append("No LLM provider API keys configured")

    # Check production settings
    if settings.ENVIRONMENT == "production":
        if settings.SESSION_SECRET_KEY == "dev-secret-key-change-in-production":
            issues.append("Production using default secret key")
        if settings.DEBUG:
            issues.append("Debug mode enabled in production")

    # Determine readiness status
    if not issues:
        status = "ready"
    elif len(issues) <= 2 and redis_health.connected:
        status = "mostly_ready"
    else:
        status = "not_ready"

    # Next steps based on current implementation
    next_steps = [
        "✅ Foundation layer complete",
        "🚧 Redis turn mutex (IN PROGRESS)",
        "⏭️ Implement Leak Judge system",
        "⏭️ Implement Help Judge and Policy Rewriter",
        "⏭️ Implement Adversarial Resistance"
    ]

    return {
        "status": status,
        "foundation_layer": "redis-turn-mutex",
        "redis_integration": "active" if redis_health.connected else "failed",
        "issues": issues,
        "recommendations": recommendations,
        "next_steps": next_steps,
        "team_status": {
            "nad": "Implementing Redis mutex (Task #6 in progress)",
            "usm": "Ready to start feature/bob-socratic-tutor",
            "muw": "Ready to start feature/3d-study-pod"
        },
        "performance_check": {
            "redis_ping_ms": redis_health.ping_ms,
            "targets_met": redis_health.ping_ms < 100 if redis_health.ping_ms else False
        }
    }


@router.post("/health/redis/cleanup")
async def cleanup_redis_sessions():
    """
    Manual endpoint to clean up orphaned Redis sessions.
    Useful for development and maintenance.
    """
    try:
        if not redis_mutex._connected:
            await redis_mutex.connect()

        cleaned_count = await redis_mutex.cleanup_expired_sessions()

        return {
            "status": "success",
            "cleaned_sessions": cleaned_count,
            "timestamp": datetime.utcnow().isoformat(),
            "message": f"Cleaned {cleaned_count} orphaned sessions"
        }

    except Exception as e:
        logger.error(f"Redis cleanup failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Redis cleanup failed: {str(e)}"
        )


@router.get("/health/websocket-test")
async def websocket_connection_test():
    """
    Test endpoint for WebSocket connection validation.
    Returns connection info for testing.
    """
    return {
        "websocket_endpoint": "/api/v1/ws/{session_id}",
        "protocol": "ws" if settings.ENVIRONMENT == "development" else "wss",
        "example_url": f"{'ws' if settings.ENVIRONMENT == 'development' else 'wss'}://localhost:{settings.PORT}/api/v1/ws/test-session-123",
        "supported_message_types": [
            "USER_MESSAGE",
            "PING",
            "GET_STATE",
            "RELEASE_LOCK"
        ],
        "response_types": [
            "AGENT_RESPONSE",
            "PONG",
            "STATE_INFO",
            "TURN_LOCKED",
            "PROCESSING",
            "ERROR"
        ],
        "redis_coordination": redis_mutex._connected
    }