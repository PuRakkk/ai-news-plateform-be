import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class RenderedVideoBase(BaseModel):
    script_id: uuid.UUID
    client_id: uuid.UUID | None = None
    video_path: str
    video_url: str
    thumbnail_url: str | None = None
    audio_url: str | None = None
    duration_sec: float = 0.0
    resolution: str = "1080x1920"
    file_size_bytes: int = 0
    status: str = "ready"
    error_message: str | None = None
    social_caption: str | None = None


class RenderedVideoCreate(RenderedVideoBase):
    pass


class RenderedVideoRead(RenderedVideoBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime


class VideoRenderRequest(BaseModel):
    script_id: uuid.UUID
    client_id: uuid.UUID | None = None
    engine_type: str | None = None
    voice_id: str | None = None
    include_subtitles: bool = True
    include_watermark: bool = True



class VideoRenderResultDTO(BaseModel):
    video: RenderedVideoRead
    message: str = "Video rendered successfully."
