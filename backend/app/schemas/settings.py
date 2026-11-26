from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class IntegrationsSettingsResponse(BaseModel):
    # Google AI Studio (Gemini)
    gemini_configured: bool
    gemini_key_masked: Optional[str] = None
    gemini_status: str = "not_configured"  # connected, invalid, quota_exhausted, not_configured
    gemini_last_tested_at: Optional[datetime] = None
    gemini_model: str = "gemini-3.5-flash-lite"

    # Google Cloud YouTube OAuth
    youtube_configured: bool
    youtube_client_id: Optional[str] = None
    youtube_secret_masked: Optional[str] = None
    youtube_status: str = "not_configured"  # configured, not_configured
    youtube_redirect_uri: str

    # Safeguards and usage stats
    max_concurrent_jobs: int = 2
    storage_limit_mb: int = 10240
    storage_used_mb: float = 0.0
    active_jobs_count: int = 0


class GeminiSettingsPayload(BaseModel):
    action: str = Field(..., description="Action: 'save', 'test', or 'remove'")
    api_key: Optional[str] = None
    model: Optional[str] = "gemini-3.5-flash-lite"


class GeminiTestResponse(BaseModel):
    status: str  # 'connected', 'invalid', 'quota_exhausted', 'error'
    message: str


class YouTubeSettingsPayload(BaseModel):
    action: str = Field(..., description="Action: 'save' or 'remove'")
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
