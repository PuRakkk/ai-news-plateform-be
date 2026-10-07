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


class HeyGenVideoEngine(BaseVideoEngine):
    """HeyGen API adapter for photorealistic digital presenter video synthesis."""

    BASE_URL = "https://api.heygen.com"

    def __init__(
        self,
        api_key: str | None = None,
        fallback_engine: BaseVideoEngine | None = None,
        poll_interval_sec: float = 5.0,
        max_poll_attempts: int = 60,
    ) -> None:
        self.api_key = api_key or settings.HEYGEN_API_KEY
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
            logger.warning(
                "HEYGEN_API_KEY not configured. Falling back to ProgrammaticVideoEngine."
            )
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
        avatar_id = (
            brand_kit.avatar_model_id
            if (brand_kit and brand_kit.avatar_model_id)
            else "Wayne_20240711"
        )
        selected_voice = voice_id or (brand_kit.voice_id if brand_kit else "en-US-ChristopherNeural")
        bg_hex = brand_kit.background_hex if brand_kit else "#0F172A"

        headers = {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        payload: dict[str, Any] = {
            "video_inputs": [
                {
                    "character": {
                        "type": "avatar",
                        "avatar_id": avatar_id,
                        "avatar_style": "normal",
                    },
                    "voice": {
                        "type": "text",
                        "input_text": full_text,
                        "voice_id": selected_voice,
                    },
                    "background": {
                        "type": "color",
                        "value": bg_hex,
                    },
                }
            ],
            "dimension": {
                "width": 1080,
                "height": 1920,
            },
            "test": settings.is_development,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as http_client:
                # 1. Trigger Video Generation
                create_resp = await http_client.post(
                    f"{self.BASE_URL}/v2/video/generate",
                    json=payload,
                    headers=headers,
                )
                if create_resp.status_code != 200:
                    logger.error(
                        f"HeyGen generation failed ({create_resp.status_code}): {create_resp.text[:300]}. Falling back."
                    )
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

                data = create_resp.json()
                video_id = data.get("data", {}).get("video_id")
                if not video_id:
                    logger.error(f"HeyGen response missing video_id: {data}. Falling back.")
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

                logger.info(f"HeyGen job submitted: video_id={video_id}. Polling for completion...")

                # 2. Poll for Completion
                video_url: str | None = None
                duration_sec: float = 15.0

                for attempt in range(self.max_poll_attempts):
                    await asyncio.sleep(self.poll_interval_sec)
                    status_resp = await http_client.get(
                        f"{self.BASE_URL}/v1/video_status.get",
                        params={"video_id": video_id},
                        headers=headers,
                    )
                    if status_resp.status_code != 200:
                        continue

                    status_data = status_resp.json().get("data", {})
                    v_status = status_data.get("status")

                    if v_status == "completed":
                        video_url = status_data.get("video_url")
                        duration_sec = float(status_data.get("duration", 15.0))
                        break
                    elif v_status == "failed":
                        logger.error(f"HeyGen task {video_id} failed: {status_data.get('error')}. Falling back.")
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

                if not video_url:
                    logger.warning(f"HeyGen task {video_id} timed out. Falling back to programmatic rendering.")
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

                # 3. Download the Rendered Video
                if not validate_outbound_url(video_url):
                    logger.error(f"HeyGen returned unsafe URL: {video_url}. Falling back.")
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

                dl_resp = await http_client.get(video_url)
                if dl_resp.status_code == 200:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_bytes(dl_resp.content)
                    return VideoEngineResult(
                        video_path=output_path,
                        duration_sec=duration_sec,
                        resolution="1080x1920",
                        engine_name="heygen",
                        metadata={"video_id": video_id, "avatar_id": avatar_id},
                    )

        except Exception as exc:
            logger.error(f"HeyGen engine failed with exception ({exc}). Falling back to programmatic engine.")
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
