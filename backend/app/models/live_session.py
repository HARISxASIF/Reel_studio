import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, BigInteger, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class LiveSession(Base):
    __tablename__ = "live_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    status = Column(String(50), nullable=False, default="created")  # created, ready, capturing, draining, stopped, ended, failed
    feed_url = Column(String(2048), nullable=False)
    resolved_stream_url = Column(String(2048), nullable=True)
    platform = Column(String(50), nullable=False, default="direct_hls")  # direct_hls, youtube_live, twitch_live, kick_live
    capability = Column(String(50), nullable=False, default="live_available")  # live_available, waiting_for_stream, stream_ended, media_unavailable
    capability_message = Column(String(1024), nullable=True)
    preview_frame_key = Column(String(1024), nullable=True)

    capture_started_at = Column(DateTime, nullable=True)
    capture_stopped_at = Column(DateTime, nullable=True)
    last_captured_timestamp = Column(Float, default=0.0)
    last_analyzed_timestamp = Column(Float, default=0.0)
    total_captured_seconds = Column(Float, default=0.0)
    continuous_buffer_seconds = Column(Float, default=0.0)

    # Coverage gaps: list of {"start": float, "end": float, "reason": str}
    coverage_gaps = Column(JSON, default=list)

    # AI Status & Backlog tracking
    ai_backlog_count = Column(Integer, default=0)
    ai_status = Column(String(50), default="idle")  # idle, analyzing, rate_limited, delayed
    ai_rate_limit_resumes_at = Column(DateTime, nullable=True)

    # Storage and quota bounds
    storage_used_bytes = Column(BigInteger, default=0)
    settings_snapshot = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    project = relationship("Project", back_populates="live_session")
