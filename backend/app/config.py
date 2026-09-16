"""
PeerRing Backend Configuration
Environment settings and constants
"""

import os
from typing import List
from pydantic_settings import BaseSettings
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Basic App Settings
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    # CORS Settings
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",  # Next.js frontend
        "http://localhost:3001",
        "http://127.0.0.1:3000",
    ]

    # Redis Configuration
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_DB: int = 0
    REDIS_TURN_LOCK_TTL: int = 30  # seconds

    # LLM Provider Settings
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "groq/compound-mini"
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # PRISM Telemetry Settings
    PRISM_ENABLED: bool = False
    PRISMTRACE_HOST: str = ""
    PRISMTRACE_PROJECT_ID: str = ""
    PRISMTRACE_API_KEY: str = ""

    # Session Configuration
    SESSION_SECRET_KEY: str = "dev-secret-key-change-in-production"
    MAX_TURN_DURATION: int = 300  # seconds

    # Agent Configuration
    DEFAULT_MODEL: str = "gpt-4"
    MAX_TOKENS: int = 512
    TEMPERATURE: float = 0.7

    # Governance Settings
    LEAK_JUDGE_ENABLED: bool = True
    HELP_JUDGE_ENABLED: bool = True
    POLICY_REWRITER_ENABLED: bool = True
    POLICY_REWRITER_MAX_RETRIES: int = 2
    ADVERSARIAL_RESISTANCE_ENABLED: bool = True

    class Config:
        env_file = BASE_DIR / ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()