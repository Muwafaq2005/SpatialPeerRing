"""
PeerRing Backend - Spatial AI Tutoring Platform
FastAPI Application Entry Point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from contextlib import asynccontextmanager

from app.config import settings
from app.api.ws_router import router as ws_router
from app.api.health_routes import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle management."""
    # Startup
    print(f"🚀 PeerRing Backend starting up...")
    print(f"📊 PRISM Integration: {'Enabled' if settings.PRISM_ENABLED else 'Disabled'}")
    print(f"🔧 Environment: {settings.ENVIRONMENT}")

    yield

    # Shutdown
    print("🛑 PeerRing Backend shutting down...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="PeerRing Backend API",
        description="Spatial AI Tutoring Platform - Foundation Layer",
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
    """Root endpoint for basic health check."""
    return {
        "service": "PeerRing Backend",
        "version": "0.1.0",
        "status": "active",
        "foundation_layer": "core-contracts-and-state"
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )