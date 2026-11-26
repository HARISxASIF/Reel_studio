from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class BulkExportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    status: str
    reel_count: int
    download_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
