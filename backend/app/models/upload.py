import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, BigInteger, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class UploadSession(Base):
    __tablename__ = "upload_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    upload_id = Column(String(512), nullable=False)   # MinIO / S3 multipart upload ID
    file_key = Column(String(1024), nullable=False)
    file_name = Column(String(512), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    chunk_size = Column(Integer, nullable=False, default=10 * 1024 * 1024) # 10MB default
    total_parts = Column(Integer, nullable=False)
    completed_parts = Column(JSON, nullable=False, default=list) # [{"PartNumber": int, "ETag": str}]

    status = Column(String(50), nullable=False, default="in_progress") # in_progress, completed, aborted

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="uploads")
    user = relationship("User", back_populates="uploads")
