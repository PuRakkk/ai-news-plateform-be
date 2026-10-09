import subprocess
from pathlib import Path
from typing import Sequence

from app.core.config import settings
from app.core.log import logger
from app.models.client import ClientBrandKit, ClientPersona, ClientProfile
from app.models.news import Article
from app.models.script import Script, ScriptBeat
from app.services.media.engine.base import BaseVideoEngine, VideoEngineResult


class MockVideoEngine(BaseVideoEngine):
    """High-speed mock engine for offline development and instant CI/CD test runs."""

    def __init__(self, ffmpeg_bin: str = "ffmpeg") -> None:
        self.ffmpeg_bin = ffmpeg_bin

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
        output_path.parent.mkdir(parents=True, exist_ok=True)
        duration = max(3.0, len(beats) * 1.5)
        is_landscape = getattr(settings, "VIDEO_ASPECT_RATIO", "16:9") == "16:9"
        res_str = "1920x1080" if is_landscape else "1080x1920"

        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-f", "lavfi",
            "-i", f"color=c=0x0F172A:s={res_str}:d={duration:.1f}",
            "-f", "lavfi",
            "-i", f"sine=f=440:d={duration:.1f}",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-shortest",
            str(output_path),
        ]

        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        except Exception as exc:
            logger.warning(f"Mock FFmpeg invocation failed ({exc}); writing fallback mock MP4 bytes.")
            output_path.write_bytes(b"\x00\x00\x00 ftypmp42\x00\x00\x00\x00isommp42")

        return VideoEngineResult(
            video_path=output_path,
            duration_sec=duration,
            resolution=res_str,
            engine_name="mock",
            metadata={"mock": True, "beats_count": len(beats)},
        )
