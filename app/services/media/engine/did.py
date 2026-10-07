import asyncio
from pathlib import Path
from typing import Any, Sequence
import httpx

from app.core.cipher import validate_outbound_url
from app.core.config import settings
from app.core.log import logger
from app.models.client import ClientBrandKit, ClientPersona, ClientProfile
from app.models.news import Article
from app.models.script import Script, ScriptBeat
from app.services.media.engine.base import BaseVideoEngine, VideoEngineResult
from app.services.media.engine.programmatic import ProgrammaticVideoEngine


class DIDVideoEngine(BaseVideoEngine):
    """D-ID API adapter for presenter lip-sync animation and avatar video generation."""

    BASE_URL = "https://api.d-id.com"

    def __init__(
        self,
        api_key: str | None = None,
        fallback_engine: BaseVideoEngine | None = None,
        poll_interval_sec: float = 4.0,
        max_poll_attempts: int = 50,
    ) -> None:
        self.api_key = api_key
        self.fallback = fallback_engine or ProgrammaticVideoEngine()
        self.poll_interval_sec = poll_interval_sec
        self.max_poll_attempts = max_poll_attempts

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
        if not self.api_key:
            logger.warning("D-ID API key not configured. Falling back to ProgrammaticVideoEngine.")
            return await self.fallback.render(
                script=script,
                beats=beats,
                client=client,
                persona=persona,
                brand_kit=brand_kit,
                article=article,
                output_path=output_path,
                voice_id=voice_id,
                include_subtitles=include_subtitles,
                include_watermark=include_watermark,
            )

        sorted_beats = sorted(beats, key=lambda b: b.beat_index)
        full_text = " ".join(b.spoken_script.strip() for b in sorted_beats if b.spoken_script.strip())
        source_url = (
            brand_kit.avatar_model_id
            if (brand_kit and brand_kit.avatar_model_id and brand_kit.avatar_model_id.startswith("http"))
            else "https://create-images-results.d-id.com/DefaultPresenters/Emma_f/image.jpeg"
        )

        headers = {
            "Authorization": f"Basic {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        payload: dict[str, Any] = {
            "script": {
                "type": "text",
                "input": full_text,
                "subtitles": include_subtitles,
            },
            "source_url": source_url,
            "config": {
                "stitch": True,
                "pad_audio": 0.0,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as http_client:
                # 1. Create Talk Job
                resp = await http_client.post(f"{self.BASE_URL}/talks", json=payload, headers=headers)
                if resp.status_code not in (200, 201):
                    logger.error(f"D-ID create talk failed ({resp.status_code}): {resp.text[:300]}. Falling back.")
                    return await self.fallback.render(
                        script=script,
                        beats=beats,
                        client=client,
                        persona=persona,
                        brand_kit=brand_kit,
                        article=article,
                        output_path=output_path,
                        voice_id=voice_id,
                        include_subtitles=include_subtitles,
                        include_watermark=include_watermark,
                    )

                data = resp.json()
                talk_id = data.get("id")
                if not talk_id:
                    return await self.fallback.render(
                        script=script,
                        beats=beats,
                        client=client,
                        persona=persona,
                        brand_kit=brand_kit,
                        article=article,
                        output_path=output_path,
                        voice_id=voice_id,
                        include_subtitles=include_subtitles,
                        include_watermark=include_watermark,
                    )

                # 2. Poll for Status
                result_url: str | None = None
                duration_sec: float = 12.0

                for _ in range(self.max_poll_attempts):
                    await asyncio.sleep(self.poll_interval_sec)
                    poll_resp = await http_client.get(f"{self.BASE_URL}/talks/{talk_id}", headers=headers)
                    if poll_resp.status_code != 200:
                        continue

                    poll_data = poll_resp.json()
                    status = poll_data.get("status")

                    if status == "done":
                        result_url = poll_data.get("result_url")
                        duration_sec = float(poll_data.get("duration", 12.0))
                        break
                    elif status == "error":
                        logger.error(f"D-ID talk {talk_id} errored. Falling back.")
                        return await self.fallback.render(
                            script=script,
                            beats=beats,
                            client=client,
                            persona=persona,
                            brand_kit=brand_kit,
                            article=article,
                            output_path=output_path,
                            voice_id=voice_id,
                            include_subtitles=include_subtitles,
                            include_watermark=include_watermark,
                        )

                if not result_url or not validate_outbound_url(result_url):
                    return await self.fallback.render(
                        script=script,
                        beats=beats,
                        client=client,
                        persona=persona,
                        brand_kit=brand_kit,
                        article=article,
                        output_path=output_path,
                        voice_id=voice_id,
                        include_subtitles=include_subtitles,
                        include_watermark=include_watermark,
                    )

                dl = await http_client.get(result_url)
                if dl.status_code == 200:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_bytes(dl.content)
                    return VideoEngineResult(
                        video_path=output_path,
                        duration_sec=duration_sec,
                        resolution="1080x1920",
                        engine_name="did",
                        metadata={"talk_id": talk_id},
                    )

        except Exception as exc:
            logger.error(f"D-ID engine error ({exc}). Falling back.")
            return await self.fallback.render(
                script=script,
                beats=beats,
                client=client,
                persona=persona,
                brand_kit=brand_kit,
                article=article,
                output_path=output_path,
                voice_id=voice_id,
                include_subtitles=include_subtitles,
                include_watermark=include_watermark,
            )
