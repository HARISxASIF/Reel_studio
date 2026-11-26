import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class SocialAccount(Base):
    __tablename__ = "social_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    platform = Column(String(50), nullable=False, index=True)  # youtube, facebook, instagram, tiktok
    platform_account_id = Column(String(255), nullable=False)
    account_name = Column(String(255), nullable=False)
    account_username = Column(String(255), nullable=True)
    profile_picture_url = Column(String(1024), nullable=True)

    access_token_encrypted = Column(Text, nullable=True)
    refresh_token_encrypted = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    scopes = Column(JSON, nullable=True)
    metadata_json = Column(JSON, nullable=True)

    status = Column(String(50), nullable=False, default="connected")  # connected, reconnect_required, disconnected
    is_active = Column(Boolean, default=True)
    is_mock = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="social_accounts")
    posts = relationship("SocialPost", back_populates="social_account", cascade="all, delete-orphan")


class SocialPost(Base):
    __tablename__ = "social_posts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    reel_id = Column(UUID(as_uuid=True), ForeignKey("reels.id", ondelete="CASCADE"), nullable=False, index=True)
    social_account_id = Column(UUID(as_uuid=True), ForeignKey("social_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    platform = Column(String(50), nullable=False, index=True)  # youtube, facebook, instagram, tiktok

    # Snapshot of approved metadata & video at queue time
    post_title = Column(String(512), nullable=False)
    post_description = Column(Text, nullable=True)
    post_hashtags = Column(JSON, nullable=True)  # list of strings e.g. ["#GTA6", "#Gaming"]
    combined_caption = Column(Text, nullable=True)
    platform_options = Column(JSON, nullable=True)
    video_key_snapshot = Column(String(1024), nullable=True)
    rendered_video_url = Column(String(2048), nullable=True)

    # Status tracking & idempotency
    status = Column(String(50), nullable=False, default="queued")  # queued, uploading, processing, published, failed, reconnect_required, manual_upload_required
    progress = Column(Integer, default=0)
    provider_upload_id = Column(String(255), nullable=True)
    provider_post_id = Column(String(255), nullable=True)
    provider_post_url = Column(String(1024), nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    idempotency_key = Column(String(128), unique=True, index=True, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published_at = Column(DateTime, nullable=True)

    # Relationships
    project = relationship("Project")
    reel = relationship("Reel")
    social_account = relationship("SocialAccount", back_populates="posts")
    user = relationship("User")
