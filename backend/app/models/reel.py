import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, JSON, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class Reel(Base):
    __tablename__ = "reels"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Metadata & AI scoring
    title = Column(String(512), nullable=False)
    reason = Column(String(2048), nullable=False)
    category = Column(String(50), nullable=False, default="highlight")  # hook, humor, insight, reaction, story, highlight
    
    source_start = Column(Float, nullable=False)
    source_end = Column(Float, nullable=False)
    clip_duration = Column(Float, nullable=False)

    score = Column(Float, nullable=False, default=70.0)
    score_hook = Column(Float, nullable=False, default=70.0)
    score_payoff = Column(Float, nullable=False, default=70.0)
    score_clarity = Column(Float, nullable=False, default=70.0)
    score_entertainment = Column(Float, nullable=False, default=70.0)
    is_borderline = Column(Boolean, default=False)

    # Visual & Subtitle configurations
    framing_mode = Column(String(50), nullable=False, default="crop")  # crop, fit, pan, split
    pan_x_offset = Column(Float, nullable=False, default=0.0)           # -1.0 to 1.0 (0.0 center)
    split_facecam_crop = Column(JSON, nullable=True)   # {"x": float, "y": float, "width": float, "height": float}
    split_gameplay_crop = Column(JSON, nullable=True)  # {"x": float, "y": float, "width": float, "height": float}
    split_order = Column(String(50), nullable=False, default="facecam_top")  # facecam_top, gameplay_top
    split_ratio = Column(Float, nullable=False, default=0.35)
    top_caption = Column(String(512), nullable=False)
    subtitles_json = Column(JSON, nullable=True)  # List of {"word": str, "start": float, "end": float} relative to clip start
    subtitle_font_size = Column(Integer, nullable=False, default=58)
    subtitle_position = Column(String(50), nullable=False, default="bottom")  # bottom, middle, top
    subtitle_y_percent = Column(Float, nullable=False, default=0.82)
    subtitle_color = Column(String(50), nullable=False, default="#FFE500")
    subtitle_font_family = Column(String(100), nullable=False, default="Noto Sans")

    # Render outputs
    source_media_key = Column(String(1024), nullable=True)  # Direct clip media (used for live clips to preserve footage after buffer expiration)
    is_live_clip = Column(Boolean, default=False)
    video_key = Column(String(1024), nullable=True)
    thumbnail_key = Column(String(1024), nullable=True)
    render_status = Column(String(50), nullable=False, default="pending")  # pending, rendering, completed, failed
    render_error = Column(String(2048), nullable=True)
    render_progress = Column(Float, default=0.0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    project = relationship("Project", back_populates="reels")
