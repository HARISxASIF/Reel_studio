from typing import Optional, Any, Dict, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, HttpUrl, ConfigDict, Field


class ProjectBase(BaseModel):
    title: str


class ProjectCreateUrl(BaseModel):
    url: str
    title: Optional[str] = None


class ProjectCreateUpload(BaseModel):
    title: str
    file_name: str
    file_size: int


class UrlMetadataResponse(BaseModel):
    url: str
    platform: str  # youtube, twitch, kick, direct_url, unknown
    title: Optional[str] = None
    duration: Optional[float] = None
    thumbnail_url: Optional[str] = None
    can_import_media: bool
    message: str


class CropBox(BaseModel):
    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)
    width: float = Field(..., gt=0.0, le=1.0)
    height: float = Field(..., gt=0.0, le=1.0)


class ProjectSettingsUpdate(BaseModel):
    framing_mode: Optional[str] = Field(default="crop", description="crop, fit, pan, split")
    pan_x_offset: Optional[float] = Field(default=0.0, ge=-1.0, le=1.0)
    subtitle_font_size: Optional[int] = Field(default=54, ge=30, le=100)
    subtitle_position: Optional[str] = Field(default="bottom", description="bottom, middle, top")
    subtitle_y_percent: Optional[float] = Field(default=0.82, ge=0.1, le=0.95)
    subtitle_color: Optional[str] = Field(default="#FFE500")
    subtitle_font_family: Optional[str] = Field(default="Noto Sans")
    split_facecam_crop: Optional[Any] = None
    split_gameplay_crop: Optional[Any] = None
    split_order: Optional[str] = Field(default="facecam_top", description="facecam_top or gameplay_top")
    split_ratio: Optional[float] = Field(default=0.35, ge=0.1, le=0.9)


class ProjectResponse(ProjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    source_type: str
    source_url: Optional[str] = None
    source_file_key: Optional[str] = None
    source_video_url: Optional[str] = None
    source_file_size: Optional[int] = None
    duration: Optional[float] = None
    probe_data: Optional[Dict[str, Any]] = None
    
    status: str
    error_message: Optional[str] = None
    analyzed_duration: float
    total_chunks: int
    completed_chunks: int

    # Pre-generation Reel Settings & Snapshot
    framing_mode: str = "crop"
    pan_x_offset: float = 0.0
    subtitle_font_size: int = 54
    subtitle_position: str = "bottom"
    subtitle_y_percent: float = 0.82
    subtitle_color: str = "#FFE500"
    subtitle_font_family: str = "Noto Sans"
    split_facecam_crop: Optional[Dict[str, Any]] = None
    split_gameplay_crop: Optional[Dict[str, Any]] = None
    split_order: str = "facecam_top"
    split_ratio: float = 0.35
    settings_snapshot: Optional[Dict[str, Any]] = None

    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseModel):
    items: List[ProjectResponse]
    total: int
