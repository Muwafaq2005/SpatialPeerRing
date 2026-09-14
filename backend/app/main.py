"""
PeerRing Backend - Spatial AI Tutoring Platform
FastAPI Application Entry Point with Redis Integration
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from contextlib import asynccontextmanager
import logging
import asyncio

from app.config import settings
from app.api.ws_router import router as ws_router
from app.api.health_routes import router as health_router
from app.state.redis_mutex import redis_mutex, RedisConnectionError

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup and shutdown lifecycle management with Redis.
    """
    # Startup
    logger.info("🚀 PeerRing Backend starting up...")
    logger.info(f"📊 PRISM Integration: {'Enabled' if settings.PRISM_ENABLED else 'Disabled'}")
    logger.info(f"🔧 Environment: {settings.ENVIRONMENT}")
    logger.info(f"🔒 Redis URL: {settings.REDIS_URL}")

    # Initialize Redis connection
    redis_connected = False
    try:
        logger.info("🔗 Connecting to Redis...")
        await redis_mutex.connect()
        redis_connected = True
        logger.info("✅ Redis connection established successfully")

        # Run initial cleanup of orphaned sessions
        cleaned_count = await redis_mutex.cleanup_expired_sessions()
        if cleaned_count > 0:
            logger.info(f"🧹 Cleaned {cleaned_count} orphaned Redis sessions on startup")

    except RedisConnectionError as e:
        logger.error(f"❌ Redis connection failed: {e}")
        logger.warning("⚠️ Application starting without Redis - WebSocket features will be limited")
    except Exception as e:
        logger.error(f"❌ Redis initialization error: {e}")

    # Health check on startup
    try:
        health_data = await redis_mutex.health_check()
        if health_data.get("connected"):
            logger.info(f"💚 Redis health check passed - ping: {health_data.get('ping_ms', 'N/A')}ms")
        else:
            logger.warning(f"⚠️ Redis health check failed: {health_data.get('error', 'Unknown error')}")
    except Exception as e:
        logger.warning(f"⚠️ Redis health check error: {e}")

    logger.info("🎉 PeerRing Backend startup complete!")
    logger.info("=" * 60)
    logger.info("📋 Foundation Status:")
    logger.info("   ✅ Core contracts and state management")
    logger.info("   ✅ Redis turn mutex system")
    logger.info("   ✅ WebSocket coordination")
    logger.info("   ✅ Mock agent registry")
    logger.info("   🚧 Leak Judge (next: Task #7)")
    logger.info("   🚧 Help Judge & Policy Rewriter (Task #8)")
    logger.info("   🚧 Adversarial Resistance (Task #9)")
    logger.info("=" * 60)

    yield

    # Shutdown
    logger.info("🛑 PeerRing Backend shutting down...")

    # Clean up Redis connection
    if redis_connected:
        try:
            # Final cleanup of any remaining sessions
            cleaned_count = await redis_mutex.cleanup_expired_sessions()
            if cleaned_count > 0:
                logger.info(f"🧹 Final cleanup: removed {cleaned_count} sessions")

            await redis_mutex.disconnect()
            logger.info("🔌 Redis connection closed gracefully")
        except Exception as e:
            logger.error(f"❌ Redis cleanup error during shutdown: {e}")

    logger.info("👋 PeerRing Backend shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application with Redis integration."""
    app = FastAPI(
        title="PeerRing Backend API",
        description="Spatial AI Tutoring Platform - Foundation + Redis Layer",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health_router, prefix="/api/v1", tags=["health"])
    app.include_router(ws_router, prefix="/api/v1", tags=["websocket"])

    return app


# Create the app instance
app = create_app()


@app.get("/")
async def root():
    """Root endpoint with Redis integration status."""
    redis_status = "connected" if redis_mutex._connected else "disconnected"

    return {
        "service": "PeerRing Backend",
        "version": "0.1.0",
        "status": "active",
        "foundation_layer": "redis-turn-mutex",
        "redis_status": redis_status,
        "features": {
            "websocket_coordination": redis_mutex._connected,
            "state_persistence": redis_mutex._connected,
            "turn_locking": redis_mutex._connected,
            "mock_agents": True,
            "governance_pipeline": "partial"  # Will be "complete" after Task #7-9
        },
        "endpoints": {
            "websocket": "/api/v1/ws/{session_id}",
            "health": "/api/v1/health",
            "detailed_health": "/api/v1/health/detailed",
            "redis_health": "/api/v1/health/redis",
            "setup_doctor": "/api/v1/setup-doctor"
        }
    }


@app.get("/api/v1/info")
async def api_info():
    """API information endpoint for development."""
    return {
        "api_version": "v1",
        "foundation_implementation": "redis-turn-mutex",
        "implemented_features": [
            "Redis turn mutex with SETNX locking",
            "WebSocket coordination with turn locks",
            "State persistence to Redis with JSON serialization",
            "Automatic session cleanup and TTL management",
            "Comprehensive health monitoring",
            "Mock agent pipeline for testing"
        ],
        "next_implementations": [
            "Leak Judge system (Task #7)",
            "Help Judge and Policy Rewriter (Task #8)",
            "Adversarial Resistance (Task #9)"
        ],
        "team_status": {
            "nad": "Implementing Redis mutex system (Task #6)",
            "usm": "Ready for feature/bob-socratic-tutor",
            "muw": "Ready for feature/3d-study-pod"
        },
        "performance_targets": {
            "redis_operations": "< 100ms",
            "websocket_response": "< 500ms",
            "turn_lock_timeout": f"{settings.REDIS_TURN_LOCK_TTL}s",
            "governance_evaluation": "< 250ms (upcoming)"
        }
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )