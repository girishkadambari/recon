"""
Application configuration — loads from environment variables.
All settings are typed using Pydantic BaseSettings.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── App ─────────────────────────────────────────────────────────
    APP_NAME: str = "AI Reconciliation Worker"
    APP_ENV: Literal["local", "test", "staging", "production"] = "local"
    APP_DEBUG: bool = False
    API_BASE_URL: str = "http://localhost:8000"
    FRONTEND_BASE_URL: str = "http://localhost:3000"

    # ── Database ─────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="postgresql+psycopg://recon:recon@localhost:5432/recon_worker"
    )

    # ── Redis ────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── JWT ──────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "change-me-local-only"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # ── Google OAuth ─────────────────────────────────────────────────
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/auth/google/callback"

    # ── S3 / LocalStack ──────────────────────────────────────────────
    S3_ENDPOINT_URL: str = "http://localhost:4566"
    S3_ACCESS_KEY_ID: str = "test"
    S3_SECRET_ACCESS_KEY: str = "test"
    S3_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = "recon-worker-local-files"
    S3_FORCE_PATH_STYLE: bool = True

    # ── AI Provider ──────────────────────────────────────────────────
    AI_PROVIDER: Literal["anthropic", "openai"] = "anthropic"
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    AI_MODEL_COLUMN_MAPPING: str = "claude-haiku-4-5-20251001"
    AI_MODEL_EXPLANATION: str = "claude-haiku-4-5-20251001"
    AI_MODEL_SUMMARY: str = "claude-haiku-4-5-20251001"
    AI_REQUEST_TIMEOUT_SECONDS: int = 30

    # ── File Upload ──────────────────────────────────────────────────
    MAX_UPLOAD_SIZE_MB: int = 25
    ALLOWED_FILE_TYPES: str = ".csv,.xlsx"

    # ── Logging ──────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"

    # ── Security ─────────────────────────────────────────────────────
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3001,http://localhost:8000"

    # ── Derived helpers ──────────────────────────────────────────────
    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def allowed_file_extensions(self) -> list[str]:
        return [ext.strip().lower() for ext in self.ALLOWED_FILE_TYPES.split(",")]

    @property
    def is_local(self) -> bool:
        return self.APP_ENV in ("local", "test")

    @property
    def ai_api_key(self) -> str:
        if self.AI_PROVIDER == "anthropic":
            return self.ANTHROPIC_API_KEY
        return self.OPENAI_API_KEY


@lru_cache
def get_settings() -> Settings:
    return Settings()
