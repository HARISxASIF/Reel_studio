import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class AnalysisChunk(Base):
    __tablename__ = "analysis_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    
    status = Column(String(50), nullable=False, default="pending")  # pending, transcribing, scanning, completed, failed
    error_message = Column(String(2048), nullable=True)

    # Persisted chunk data
    transcript = Column(JSON, nullable=True)     # list of {"word": str, "start": float, "end": float, "prob": float}
    scene_changes = Column(JSON, nullable=True)  # list of float timestamps
    audio_peaks = Column(JSON, nullable=True)    # list of {"time": float, "level": float}

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    project = relationship("Project", back_populates="chunks")
