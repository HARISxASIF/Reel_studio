from uuid import UUID
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class SocialAccountOut(BaseModel):
    id: UUID
    platform: str
    platform_account_id: str
    account_name: str
    account_username: Optional[str] = None
    profile_picture_url: Optional[str] = None
    status: str
    is_active: bool
    is_mock: bool = False
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConnectMockAccountRequest(BaseModel):
    platform: str = Field(..., description="youtube, facebook, instagram, tiktok")
    account_name: str = Field(..., min_length=1, max_length=100)
    account_username: Optional[str] = None
    profile_picture_url: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None


class DisconnectAccountRequest(BaseModel):
    account_id: UUID


class HashtagSuggestionRequest(BaseModel):
    reel_id: UUID
    project_id: Optional[UUID] = None
    title: str
    description: Optional[str] = None
    brand_tags: Optional[List[str]] = Field(default_factory=list)


class HashtagSuggestionResponse(BaseModel):
    reel_id: UUID
    suggestions: List[str]
    context_keywords: List[str] = Field(default_factory=list)
    cached: bool = False


class PublishBatchItem(BaseModel):
    reel_id: UUID
    account_ids: List[UUID]
    post_title: str
    post_description: Optional[str] = ""
    post_hashtags: List[str] = Field(default_factory=list)
    platform_options: Optional[Dict[str, Any]] = Field(default_factory=dict)


class PublishBatchRequest(BaseModel):
    project_id: UUID
    items: List[PublishBatchItem]


class SocialPostOut(BaseModel):
    id: UUID
    project_id: UUID
    reel_id: UUID
    social_account_id: UUID
    platform: str
    post_title: str
    post_description: Optional[str] = None
    post_hashtags: Optional[List[str]] = None
    combined_caption: Optional[str] = None
    platform_options: Optional[Dict[str, Any]] = None
    status: str
    progress: int = 0
    provider_upload_id: Optional[str] = None
    provider_post_id: Optional[str] = None
    provider_post_url: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None
    account_name: Optional[str] = None
    account_username: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TikTokPrepareResponse(BaseModel):
    reel_id: UUID
    download_url: str
    caption: str
    hashtags: List[str]
    combined_text: str
    tiktok_web_upload_url: str = "https://www.tiktok.com/upload"
    instructions: str
