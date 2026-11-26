from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class InitiateUploadRequest(BaseModel):
    project_id: Optional[UUID] = None
    file_name: str
    file_size: int
    chunk_size: int = 10 * 1024 * 1024  # 10MB default


class PartETag(BaseModel):
    PartNumber: int
    ETag: str


class InitiateUploadResponse(BaseModel):
    upload_session_id: UUID
    project_id: UUID
    upload_id: str
    file_key: str
    total_parts: int
    chunk_size: int
    completed_parts: List[PartETag]


class PresignedPartUrlResponse(BaseModel):
    part_number: int
    presigned_url: str


class CompleteUploadRequest(BaseModel):
    parts: List[PartETag]


class UploadSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    upload_id: str
    file_key: str
    file_name: str
    file_size: int
    chunk_size: int
    total_parts: int
    completed_parts: List[Dict[str, Any]]
    status: str
    created_at: datetime
    updated_at: datetime
