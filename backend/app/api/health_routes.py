"""
Health Check Routes
System status and diagnostic endpoints
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import asyncio
import logging

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    service: str
    version: str
    environment: str
    checks: Dict[str, Any]


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Basic health check endpoint."""
    return HealthResponse(
        status="healthy",
        service="peerring-backend",
        version="0.1.0",
        environment=settings.ENVIRONMENT,
        checks={
            "foundation": "active",
            "contracts": "loaded",
            "redis": "not_configured",  # Will be updated when Redis is added
            "prism": "disabled" if not settings.PRISM_ENABLED else "enabled"
        }
    )


@router.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with component status."""
    checks = {}

    # Check Redis connectivity (placeholder)
    checks["redis"] = {
        "status": "not_configured",
        "url": settings.REDIS_URL,
        "message": "Redis integration pending"
    }

    # Check PRISM configuration
    checks["prism"] = {
        "status": "enabled" if settings.PRISM_ENABLED else "disabled",
        "configured": bool(settings.PRISMTRACE_HOST and settings.PRISMTRACE_PROJECT_ID)
    }

    # Check LLM providers
    checks["llm_providers"] = {
        "openai": "configured" if settings.OPENAI_API_KEY else "not_configured",
        "anthropic": "configured" if settings.ANTHROPIC_API_KEY else "not_configured"
    }

    # Check governance systems
    checks["governance"] = {
        "leak_judge": settings.LEAK_JUDGE_ENABLED,
        "help_judge": settings.HELP_JUDGE_ENABLED,
        "adversarial_resistance": settings.ADVERSARIAL_RESISTANCE_ENABLED
    }

    return {
        "status": "healthy",
        "timestamp": "2026-09-14T12:25:09.206Z",
        "foundation_layer": "core-contracts-and-state",
        "branch": "foundation/core-contracts-and-state",
        "checks": checks
    }


@router.get("/setup-doctor")
async def setup_doctor():
    """
    Setup diagnostic endpoint to verify foundation layer.
    Used by other team members to check if contracts are ready.
    """
    issues = []
    recommendations = []

    # Check if core contracts exist
    try:
        # These will be created next
        # from app.contracts.base_agent import BaseAgent
        # from app.contracts.base_judge import BaseJudge
        recommendations.append("Core contracts (BaseAgent, BaseJudge) not yet implemented")
    except ImportError:
        issues.append("Core contracts not found - foundation layer incomplete")

    # Check configuration
    if not settings.OPENAI_API_KEY and not settings.ANTHROPIC_API_KEY:
        issues.append("No LLM provider API keys configured")

    if settings.ENVIRONMENT == "production" and settings.SESSION_SECRET_KEY == "dev-secret-key-change-in-production":
        issues.append("Production environment using default secret key")

    status = "ready" if not issues else "incomplete"

    return {
        "status": status,
        "foundation_layer": "core-contracts-and-state",
        "issues": issues,
        "recommendations": recommendations,
        "next_steps": [
            "Implement PeerRingState Pydantic schema",
            "Create BaseAgent and BaseJudge abstract classes",
            "Build MockAgentRegistry for testing",
            "Add Redis turn mutex implementation"
        ]
    }