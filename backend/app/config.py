import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    PROJECT_NAME: str = "Reel Studio API"
    VERSION: str = "1.0.0"
    LOG_LEVEL: str = "INFO"

    # Security
    SECRET_KEY: str = "reelstudio_development_secret_key_change_in_production_min32chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/reelstudio"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://postgres:postgres@postgres:5432/reelstudio"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "reelstudio"

    # Redis & Celery
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/0"

    # MinIO / S3
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_PUBLIC_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "reel-studio"
    MINIO_SECURE: bool = False

    # AI Configuration
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    GEMINI_RPM: int = 15
    GEMINI_TPM: int = 250000
    GEMINI_RPD: int = 500
    GEMINI_RETRY_COOLDOWN_SECONDS: int = 30

    # Whisper Configuration
    WHISPER_MODEL: str = "base"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"
    WHISPER_CACHE_DIR: str = "/models"

    # Pipeline Chunking
    CHUNK_DURATION_SECONDS: int = 345  # 5 min 45 sec
    CHUNK_OVERLAP_SECONDS: int = 45   # 45 sec overlap
    MAX_WORKERS: int = 2

    # Live Stream Configuration
    LIVE_SEGMENT_DURATION_SECONDS: int = 4
    LIVE_BUFFER_RETENTION_SECONDS: int = 900  # 15 minutes rolling buffer
    LIVE_MAX_CONCURRENT_SESSIONS: int = 2
    LIVE_ANALYSIS_WINDOW_SECONDS: int = 60
    LIVE_ANALYSIS_STEP_SECONDS: int = 20
    LIVE_BUFFER_DIR: str = "/tmp/reelstudio_live"
    LIVE_MAX_STORAGE_MB_PER_SESSION: int = 1024  # 1 GB max per session
    LIVE_MIN_MANUAL_CLIP_SECONDS: float = 30.0
    ALLOW_LOCAL_FEEDS: bool = False

    # Reel Rules
    MIN_CLIP_DURATION: float = 30.0
    MAX_CLIP_DURATION: float = 150.0
    DEFAULT_MIN_SCORE: float = 65.0

    # Social Media & Publishing
    ENCRYPTION_KEY: Optional[str] = None
    BACKEND_PUBLIC_URL: str = "http://localhost:8000"
    FRONTEND_PUBLIC_URL: str = "http://localhost:3000"
    ALLOW_MOCK_PUBLISHING: bool = True

    # Google / YouTube OAuth
    YOUTUBE_CLIENT_ID: Optional[str] = None
    YOUTUBE_CLIENT_SECRET: Optional[str] = None
    YOUTUBE_REDIRECT_URI: str = "http://localhost:8000/api/social/youtube/callback"

    # Meta (Facebook / Instagram) OAuth
    META_APP_ID: Optional[str] = None
    META_APP_SECRET: Optional[str] = None
    META_REDIRECT_URI: str = "http://localhost:8000/api/social/meta/callback"

    # TikTok OAuth
    TIKTOK_CLIENT_KEY: Optional[str] = None
    TIKTOK_CLIENT_SECRET: Optional[str] = None
    TIKTOK_REDIRECT_URI: str = "http://localhost:8000/api/social/tiktok/callback"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )



settings = Settings()
