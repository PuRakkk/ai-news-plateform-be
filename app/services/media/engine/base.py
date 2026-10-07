from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Sequence
from pydantic import BaseModel, ConfigDict, Field

from app.models.client import ClientBrandKit, ClientPersona, ClientProfile
from app.models.news import Article
from app.models.script import Script, ScriptBeat


class VideoEngineResult(BaseModel):
    """Result emitted after video generation by any VideoEngineAdapter."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    video_path: Path
    duration_sec: float
    resolution: str = "1080x1920"
    engine_name: str
    metadata: dict[str, Any] = Field(default_factory=dict)



class BaseVideoEngine(ABC):
    """Abstract interface for all video generation engines (Mock, Programmatic, HeyGen, D-ID)."""

    @abstractmethod
    async def render(
        self,
        script: Script,
        beats: Sequence[ScriptBeat],
        client: ClientProfile | None,
        persona: ClientPersona | None,
        brand_kit: ClientBrandKit | None,
        article: Article | None,
        output_path: Path,
        voice_id: str | None = None,
        include_subtitles: bool = True,
        include_watermark: bool = True,
    ) -> VideoEngineResult:
        """Render complete vertical 1080x1920 video for the script."""
        pass
