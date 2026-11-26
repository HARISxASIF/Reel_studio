from typing import Optional, Any, Dict, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.project import ProjectSettingsUpdate


class LiveProbeRequest(BaseModel):
    url: str


class LiveProbeResponse(BaseModel):
    url: str
    platform: str  # direct_hls, youtube_live, twitch_live, kick_live
    capability: str  # live_available, waiting_for_stream, stream_ended, media_unavailable
    message: str
    title: Optional[str] = None
    thumbnail_url: Optional[str] = None
    resolved_stream_url: Optional[str] = None
    preview_frame_url: Optional[str] = None


class LiveCreateProjectRequest(BaseModel):
    url: str
    title: Optional[str] = None


class LiveSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    status: str  # created, ready, capturing, draining, stopped, ended, failed
    feed_url: str
    resolved_stream_url: Optional[str] = None
    platform: str
    capability: str
    capability_message: Optional[str] = None
    preview_frame_url: Optional[str] = None

    capture_started_at: Optional[datetime] = None
    capture_stopped_at: Optional[datetime] = None
    last_captured_timestamp: float = 0.0
    last_analyzed_timestamp: float = 0.0
    total_captured_seconds: float = 0.0
    continuous_buffer_seconds: float = 0.0

    coverage_gaps: List[Dict[str, Any]] = Field(default_factory=list)
    ai_backlog_count: int = 0
    ai_status: str = "idle"
    ai_rate_limit_resumes_at: Optional[datetime] = None
    storage_used_bytes: int = 0
    settings_snapshot: Optional[Dict[str, Any]] = None

    created_at: datetime
    updated_at: datetime


class LiveStartRequest(BaseModel):
    settings: Optional[ProjectSettingsUpdate] = None


class LiveManualClipRequest(BaseModel):
    duration: float = Field(default=60.0, ge=30.0, le=150.0)
