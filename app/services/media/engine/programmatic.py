import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import Sequence

from app.core.config import settings
from app.core.log import logger
from app.models.client import ClientBrandKit, ClientPersona, ClientProfile
from app.models.news import Article
from app.models.script import Script, ScriptBeat
from app.services.media.asset_resolver import AssetResolver
from app.services.media.canvas import render_beat_card
from app.services.media.compositor import VideoCompositor
from app.services.media.engine.base import BaseVideoEngine, VideoEngineResult
from app.services.media.storage.base import StorageProvider
from app.services.media.storage.factory import get_storage_provider
from app.services.media.subtitles import generate_ass_subtitles
from app.services.media.tts.base import TTSProvider
from app.services.media.tts.factory import get_tts_provider


class ProgrammaticVideoEngine(BaseVideoEngine):
    """Local programmatic motion compositor using Pillow, EdgeTTS/ElevenLabs, and FFmpeg."""

    def __init__(
        self,
        storage: StorageProvider | None = None,
        tts: TTSProvider | None = None,
        compositor: VideoCompositor | None = None,
        asset_resolver: AssetResolver | None = None,
    ) -> None:
        self.storage = storage or get_storage_provider()
        self.tts = tts
        self.compositor = compositor or VideoCompositor()
        self.asset_resolver = asset_resolver or AssetResolver(self.storage)

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
        sorted_beats = sorted(beats, key=lambda b: b.beat_index)
        if not sorted_beats:
            raise ValueError("No script beats provided for programmatic rendering.")

        # 1. Resolve Voice & TTS Provider
        selected_voice = voice_id or (brand_kit.voice_id if brand_kit else settings.TTS_DEFAULT_VOICE)
        tts_engine = (brand_kit.voice_engine if brand_kit else settings.TTS_PROVIDER) or "edge_tts"
        tts_provider = self.tts or get_tts_provider(tts_engine)

        spoken_segments = [b.spoken_script.strip() for b in sorted_beats if b.spoken_script.strip()]
        full_speech_text = " ... ".join(spoken_segments)

        logger.info(f"Synthesizing voice with {tts_engine} ({selected_voice})...")
        tts_result = await tts_provider.synthesize(full_speech_text, voice_id=selected_voice)

        # 2. Timing Allocation per Beat
        total_words = sum(len(b.spoken_script.split()) for b in sorted_beats)
        total_duration = max(3.0, tts_result.duration_seconds)
        beat_durations: list[float] = []

        for b in sorted_beats:
            words = len(b.spoken_script.split())
            if total_words > 0:
                dur = round(total_duration * (words / total_words), 2)
            else:
                dur = round(total_duration / len(sorted_beats), 2)
            beat_durations.append(max(1.0, dur))

        if beat_durations:
            diff = total_duration - sum(beat_durations)
            beat_durations[-1] = round(beat_durations[-1] + diff, 2)

        # 3. Brand Styling
        brand_colors = {
            "background_hex": brand_kit.background_hex if brand_kit else "#0F172A",
            "primary_hex": brand_kit.primary_hex if brand_kit else "#2563EB",
            "accent_hex": brand_kit.accent_hex if brand_kit else "#F59E0B",
            "subtitle_highlight_hex": brand_kit.subtitle_highlight_hex if brand_kit else "#10B981",
        }
        font_family = brand_kit.font_family if brand_kit else "Arial"
        client_name = client.name if client else "AI News Daily"
        persona_role = persona.persona_role if persona else (script.persona_role or "AI Executive")
        source_feed = article.source.name if (article and article.source) else "Verified Source"

        with tempfile.TemporaryDirectory() as temp_dir:
            td = Path(temp_dir)

            # Save and persist TTS audio
            audio_path = td / "voiceover.mp3"
            audio_path.write_bytes(tts_result.audio_bytes)
            audio_rel_path = f"audio/{script.id}.mp3"
            audio_url = self.storage.save_bytes(tts_result.audio_bytes, audio_rel_path, "audio/mpeg")

            # Resolve optional brand assets (watermark, intro bumper, outro bumper, avatar, bgm)
            watermark_path: Path | None = None
            intro_path: Path | None = None
            outro_path: Path | None = None
            avatar_path: Path | None = None
            bgm_path: Path | None = None

            if include_watermark and brand_kit and brand_kit.watermark_logo_url:
                watermark_path = await self.asset_resolver.resolve_asset(
                    brand_kit.watermark_logo_url, td, "watermark.png"
                )

            if brand_kit and brand_kit.intro_bumper_url:
                intro_path = await self.asset_resolver.resolve_asset(
                    brand_kit.intro_bumper_url, td, "intro.mp4"
                )

            if brand_kit and brand_kit.outro_bumper_url:
                outro_path = await self.asset_resolver.resolve_asset(
                    brand_kit.outro_bumper_url, td, "outro.mp4"
                )

            # Resolve Avatar Presenter Image (Custom Client Avatar or High-Res Default Anchor)
            if brand_kit and brand_kit.avatar_model_id:
                avatar_path = await self.asset_resolver.resolve_asset(
                    brand_kit.avatar_model_id, td, "custom_avatar.jpg"
                )
            if not avatar_path:
                default_anchor = Path("assets/avatars/default_anchor.jpg")
                if default_anchor.exists():
                    avatar_path = default_anchor

            # Resolve Ambient Background Music Loop
            default_bgm = Path("assets/audio/ambient_bed.mp3")
            if default_bgm.exists():
                bgm_path = default_bgm

            # 4-6. Render visual cards, generate subtitles, and composite master video in a worker thread
            def _render_visuals_and_composite() -> None:
                slides_with_durations: list[tuple[Path, float]] = []
                for idx, b in enumerate(sorted_beats):
                    headline = script.title or (article.title if article else f"Insight {b.beat_index}")
                    content = b.whiteboard_directive or b.spoken_script
                    card_img = render_beat_card(
                        beat_index=b.beat_index,
                        beat_type=b.beat_type,
                        headline=headline,
                        content_text=content,
                        client_name=client_name,
                        persona_role=persona_role,
                        source_feed=source_feed,
                        brand_colors=brand_colors,
                        font_family=font_family,
                        watermark_logo_path=watermark_path,
                        avatar_image_path=avatar_path,
                        visual_directive=b.visual_directive,
                    )
                    slide_path = td / f"beat_{b.beat_index}.png"
                    card_img.save(slide_path, format="PNG")
                    slides_with_durations.append((slide_path, beat_durations[idx]))

                # 5. Generate Subtitles
                subtitles_path: Path | None = None
                if include_subtitles and tts_result.cues:
                    subtitles_path = td / "subtitles.ass"
                    generate_ass_subtitles(
                        cues=tts_result.cues,
                        font_family=font_family,
                        highlight_hex=brand_colors["subtitle_highlight_hex"],
                        output_path=subtitles_path,
                    )

                # 6. Composite Master Video with Motion & Ambient Audio
                rendered_temp_mp4 = td / "final_composite.mp4"
                self.compositor.composite_video(
                    slides_with_durations=slides_with_durations,
                    audio_path=audio_path,
                    output_path=rendered_temp_mp4,
                    subtitles_ass_path=subtitles_path,
                    watermark_path=watermark_path,
                    intro_bumper_path=intro_path,
                    outro_bumper_path=outro_path,
                    background_music_path=bgm_path,
                    bgm_volume=0.08,
                    enable_camera_motion=True,
                )

                # Copy to requested output_path
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(rendered_temp_mp4, output_path)

            await asyncio.to_thread(_render_visuals_and_composite)

            return VideoEngineResult(
                video_path=output_path,
                duration_sec=total_duration,
                resolution="1080x1920",
                engine_name="programmatic",
                metadata={
                    "tts_engine": tts_engine,
                    "voice_id": selected_voice,
                    "audio_url": audio_url,
                    "has_watermark": bool(watermark_path),
                    "has_intro": bool(intro_path),
                    "has_outro": bool(outro_path),
                },
            )
