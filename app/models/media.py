import uuid
from datetime import datetime
from typing import Any, Optional
from sqlmodel import Field, Relationship, SQLModel

from app.models.client import ClientProfile
from app.models.news import utc_now
from app.models.script import Script


class RenderedVideo(SQLModel, table=True):
    """Composited master vertical video with speech, subtitles, branding, and social caption."""

    __tablename__ = "rendered_video"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    script_id: uuid.UUID = Field(foreign_key="script.id", index=True)
    client_id: uuid.UUID | None = Field(default=None, foreign_key="client_profile.id", index=True)
    video_path: str  # Local file path or storage key
    video_url: str  # Web-accessible URL for streaming or downloading
    thumbnail_url: str | None = Field(default=None)
    audio_url: str | None = Field(default=None)
    duration_sec: float = Field(default=0.0)
    resolution: str = Field(default="1080x1920")
    file_size_bytes: int = Field(default=0)
    status: str = Field(default="ready", index=True)  # rendering, ready, failed
    error_message: str | None = Field(default=None)
    social_caption: str | None = Field(default=None)  # Auto-generated social media caption
    created_at: datetime = Field(default_factory=utc_now, index=True)

    script: Optional[Script] = Relationship()
    client: Optional[ClientProfile] = Relationship()

    def __admin_repr__(self, request: Any = None) -> str:
        s_title = self.script.title[:35] if self.script else "Video"
        return f"{s_title} ({self.duration_sec:.1f}s) [{self.status}]"

    def __str__(self) -> str:
        return f"Video {self.id} ({self.status})"
