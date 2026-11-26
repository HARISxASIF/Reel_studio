import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, BigInteger, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    
    # Source details
    source_type = Column(String(50), nullable=False)  # upload, youtube, twitch, kick, direct_url
    source_url = Column(String(2048), nullable=True)
    source_file_key = Column(String(1024), nullable=True)
    source_file_size = Column(BigInteger, nullable=True)
    duration = Column(Float, nullable=True)
    probe_data = Column(JSON, nullable=True)  # width, height, fps, codecs, bitrate, audio_tracks

    # Pipeline progress & lifecycle
    status = Column(String(50), nullable=False, default="created")  # created, importing, probing, ready, analyzing, completed, failed, cancelled
    error_message = Column(String(2048), nullable=True)
    analyzed_duration = Column(Float, default=0.0)
    total_chunks = Column(Integer, default=0)
    completed_chunks = Column(Integer, default=0)

    # Pre-generation Reel Settings & Snapshot
    framing_mode = Column(String(50), nullable=False, default="crop")  # crop, fit, pan, split
    pan_x_offset = Column(Float, nullable=False, default=0.0)
    subtitle_font_size = Column(Integer, nullable=False, default=54)
    subtitle_position = Column(String(50), nullable=False, default="bottom")  # bottom, middle, top
    subtitle_y_percent = Column(Float, nullable=False, default=0.82)
    subtitle_color = Column(String(50), nullable=False, default="#FFE500")
    subtitle_font_family = Column(String(100), nullable=False, default="Noto Sans")
    split_facecam_crop = Column(JSON, nullable=True)   # {"x": float, "y": float, "width": float, "height": float}
    split_gameplay_crop = Column(JSON, nullable=True)  # {"x": float, "y": float, "width": float, "height": float}
    split_order = Column(String(50), nullable=False, default="facecam_top")  # facecam_top, gameplay_top
    split_ratio = Column(Float, nullable=False, default=0.35)
    settings_snapshot = Column(JSON, nullable=True)    # Snapshot captured when generation starts

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="projects")
    chunks = relationship("AnalysisChunk", back_populates="project", cascade="all, delete-orphan", order_by="AnalysisChunk.chunk_index")
    reels = relationship("Reel", back_populates="project", cascade="all, delete-orphan", order_by="Reel.score.desc()")
    uploads = relationship("UploadSession", back_populates="project", cascade="all, delete-orphan")
    bulk_exports = relationship("BulkExport", back_populates="project", cascade="all, delete-orphan")
    live_session = relationship("LiveSession", back_populates="project", uselist=False, cascade="all, delete-orphan")
