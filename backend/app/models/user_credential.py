import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class UserCredential(Base):
    __tablename__ = "user_credentials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # Google AI Studio (Gemini)
    gemini_api_key_encrypted = Column(Text, nullable=True)
    gemini_status = Column(String(50), default="not_configured", nullable=False)
    gemini_last_tested_at = Column(DateTime, nullable=True)
    gemini_model = Column(String(100), default="gemini-3.5-flash-lite", nullable=False)

    # Google Cloud YouTube OAuth
    youtube_client_id = Column(String(255), nullable=True)
    youtube_client_secret_encrypted = Column(Text, nullable=True)
    youtube_status = Column(String(50), default="not_configured", nullable=False)

    # Per-user safeguards and quotas
    max_concurrent_jobs = Column(Integer, default=2, nullable=False)
    storage_limit_mb = Column(Integer, default=10240, nullable=False)  # 10 GB default

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationship back to User
    user = relationship("User", back_populates="credentials")
