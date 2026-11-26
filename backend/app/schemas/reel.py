from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class SubtitleWord(BaseModel):
    word: str
    start: float  # relative to clip start
    end: float    # relative to clip start
    prob: Optional[float] = 1.0


class ReelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    title: str
    reason: str
    category: str
    source_start: float
    source_end: float
    clip_duration: float
    
    score: float
    score_hook: float
    score_payoff: float
    score_clarity: float
    score_entertainment: float
    is_borderline: bool

    framing_mode: str
    pan_x_offset: float
    split_facecam_crop: Optional[Dict[str, Any]] = None
    split_gameplay_crop: Optional[Dict[str, Any]] = None
    split_order: str = "facecam_top"
    split_ratio: float = 0.35
    top_caption: str
    subtitles_json: Optional[List[Dict[str, Any]]] = None
    subtitle_font_size: int = 58
    subtitle_position: str = "bottom"
    subtitle_y_percent: float = 0.82
    subtitle_color: str = "#FFE500"
    subtitle_font_family: str = "Noto Sans"

    video_url: Optional[str] = None
    source_video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    render_status: str
    render_error: Optional[str] = None
    render_progress: float

    created_at: datetime
    updated_at: datetime


class ReelUpdate(BaseModel):
    title: Optional[str] = None
    top_caption: Optional[str] = None
    framing_mode: Optional[str] = None  # crop, fit, pan, split
    pan_x_offset: Optional[float] = None
    split_facecam_crop: Optional[Dict[str, Any]] = None
    split_gameplay_crop: Optional[Dict[str, Any]] = None
    split_order: Optional[str] = None
    split_ratio: Optional[float] = None
    source_start: Optional[float] = None
    source_end: Optional[float] = None
    subtitles_json: Optional[List[Dict[str, Any]]] = None
    subtitle_font_size: Optional[int] = None
    subtitle_position: Optional[str] = None
    subtitle_y_percent: Optional[float] = None
    subtitle_color: Optional[str] = None
    subtitle_font_family: Optional[str] = None


class ManualReelCreate(BaseModel):
    source_start: float = Field(..., description="Start time in seconds in the source recording")
    source_end: float = Field(..., description="End time in seconds in the source recording (30-60s range)")
    title: Optional[str] = "Manual Highlight"
    top_caption: Optional[str] = None
    framing_mode: str = "crop"
    pan_x_offset: float = 0.0
    split_facecam_crop: Optional[Dict[str, Any]] = None
    split_gameplay_crop: Optional[Dict[str, Any]] = None
    split_order: Optional[str] = "facecam_top"
    split_ratio: Optional[float] = 0.35
    subtitle_font_size: Optional[int] = 58
    subtitle_position: Optional[str] = "bottom"
    subtitle_y_percent: Optional[float] = 0.82
    subtitle_color: Optional[str] = "#FFE500"
    subtitle_font_family: Optional[str] = "Noto Sans"


class ReelListResponse(BaseModel):
    items: List[ReelResponse]
    total: int
    borderline_count: int
