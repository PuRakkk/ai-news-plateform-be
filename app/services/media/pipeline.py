import asyncio
import tempfile
import uuid
from pathlib import Path
from sqlmodel import Session

from app.core.config import settings
from app.core.database import get_session
from app.core.log import logger
from app.models.client import ClientBrandKit, ClientPersona, ClientProfile
from app.models.media import RenderedVideo
from app.models.news import Article
from app.models.script import Script, ScriptBeat
from app.repositories.client_repo import (
    ClientBrandKitRepository,
    ClientPersonaRepository,
    ClientProfileRepository,
)
from app.repositories.media_repo import RenderedVideoRepository
from app.repositories.news_repo import ArticleRepository
from app.repositories.script_repo import ScriptBeatRepository, ScriptRepository
from app.services.media.asset_resolver import AssetResolver
from app.services.media.canvas import render_beat_card
from app.services.media.compositor import VideoCompositor
from app.services.media.engine.base import BaseVideoEngine
from app.services.media.engine.factory import get_video_engine
from app.services.media.engine.programmatic import ProgrammaticVideoEngine
from app.services.media.social_copy import generate_social_caption
from app.services.media.storage.base import StorageProvider
from app.services.media.storage.factory import get_storage_provider
from app.services.media.tts.base import TTSProvider
from app.services.media.tts.factory import get_tts_provider


class VideoAssemblyService:
    """Orchestrates end-to-end multimedia synthesis and video rendering across pluggable engines."""

    def __init__(
        self,
        storage: StorageProvider | None = None,
        tts: TTSProvider | None = None,
        compositor: VideoCompositor | None = None,
        video_engine: BaseVideoEngine | None = None,
    ) -> None:
        self.storage = storage or get_storage_provider()
        self.tts = tts
        self.compositor = compositor or VideoCompositor()
        self.video_engine = video_engine
        self.asset_resolver = AssetResolver(self.storage)

    async def render_video(
        self,
        script_id: uuid.UUID,
        client_id: uuid.UUID | None = None,
        engine_type: str | None = None,
        voice_id: str | None = None,
        include_subtitles: bool = True,
        include_watermark: bool = True,
        session: Session | None = None,
    ) -> RenderedVideo:
        """Render a vertical 1080x1920 video from a script and client branding."""
        if session:
            return await self._execute_render(
                session=session,
                script_id=script_id,
                client_id=client_id,
                engine_type=engine_type,
                voice_id=voice_id,
                include_subtitles=include_subtitles,
                include_watermark=include_watermark,
            )

        with get_session() as db_session:
            return await self._execute_render(
                session=db_session,
                script_id=script_id,
                client_id=client_id,
                engine_type=engine_type,
                voice_id=voice_id,
                include_subtitles=include_subtitles,
                include_watermark=include_watermark,
            )

    async def _execute_render(
        self,
        session: Session,
        script_id: uuid.UUID,
        client_id: uuid.UUID | None,
        engine_type: str | None,
        voice_id: str | None,
        include_subtitles: bool,
        include_watermark: bool,
    ) -> RenderedVideo:
        script_repo = ScriptRepository(session)
        beat_repo = ScriptBeatRepository(session)
        article_repo = ArticleRepository(session)
        client_repo = ClientProfileRepository(session)
        persona_repo = ClientPersonaRepository(session)
        brand_repo = ClientBrandKitRepository(session)
        video_repo = RenderedVideoRepository(session)

        # 1. Fetch Script and its Beats
        script = script_repo.get_by_id(script_id)
        if not script:
            raise ValueError(f"Script with ID {script_id} not found.")

        beats = beat_repo.get_beats_by_script(script_id)
        if not beats:
            raise ValueError(f"Script {script_id} has no segment beats.")

        # Resolve Client, Persona, and Brand Kit
        target_client_id = client_id or script.client_id
        client: ClientProfile | None = None
        persona: ClientPersona | None = None
        brand_kit: ClientBrandKit | None = None

        if target_client_id:
            client = client_repo.get_by_id(target_client_id)
            persona = persona_repo.get_by_client_id(target_client_id)
            brand_kit = brand_repo.get_by_client_id(target_client_id)

        article: Article | None = None
        if script.article_id:
            article = article_repo.get_by_id(script.article_id)

        # 2. Select Video Engine Adapter
        selected_engine_type = (
            engine_type
            or (brand_kit.avatar_engine if brand_kit else None)
            or settings.VIDEO_ENGINE
        )
        engine = self.video_engine or get_video_engine(
            selected_engine_type,
            storage=self.storage,
            tts=self.tts,
            compositor=self.compositor,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            td = Path(temp_dir)
            temp_output_mp4 = td / "rendered.mp4"

            # 3. Generate Video via Pluggable Engine
            logger.info(
                f"Executing video rendering with engine '{selected_engine_type}' for script {script_id}..."
            )
            result = await engine.render(
                script=script,
                beats=beats,
                client=client,
                persona=persona,
                brand_kit=brand_kit,
                article=article,
                output_path=temp_output_mp4,
                voice_id=voice_id,
                include_subtitles=include_subtitles,
                include_watermark=include_watermark,
            )

            # 4. Generate & Save Thumbnail from Beat 1
            sorted_beats = sorted(beats, key=lambda b: b.beat_index)
            first_beat = sorted_beats[0]
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

            def _render_thumbnail_file() -> Path:
                thumb_card = render_beat_card(
                    beat_index=first_beat.beat_index,
                    beat_type=first_beat.beat_type,
                    headline=script.title or (article.title if article else "AI Intelligence Brief"),
                    content_text=first_beat.whiteboard_directive or first_beat.spoken_script,
                    client_name=client_name,
                    persona_role=persona_role,
                    source_feed=source_feed,
                    brand_colors=brand_colors,
                    font_family=font_family,
                )
                t_path = td / "thumbnail.png"
                thumb_card.save(t_path, format="PNG")
                return t_path

            thumb_path = await asyncio.to_thread(_render_thumbnail_file)
            thumb_rel_path = f"thumbnails/{script_id}.png"
            thumb_url = self.storage.save_file(thumb_path, thumb_rel_path, "image/png")

            # 5. Persist Master Video to Storage
            video_rel_path = f"rendered/{script_id}.mp4"
            video_url = self.storage.save_file(temp_output_mp4, video_rel_path, "video/mp4")
            file_size = temp_output_mp4.stat().st_size

            # Audio stem url
            audio_url: str | None = result.metadata.get("audio_url")
            if not audio_url:
                audio_rel_path = f"audio/{script_id}.mp3"
                if self.storage.file_exists(audio_rel_path):
                    audio_url = self.storage.get_url(audio_rel_path)

            # 6. Generate Ready-to-Publish Social Caption
            social_caption = generate_social_caption(
                script=script,
                article=article,
                client=client,
                persona=persona,
                beats=sorted_beats,
            )

            # 7. Persist Record in Database
            video_record = video_repo.create_video(
                script_id=script.id,
                client_id=target_client_id,
                video_path=video_rel_path,
                video_url=video_url,
                thumbnail_url=thumb_url,
                audio_url=audio_url,
                duration_sec=result.duration_sec,
                resolution=result.resolution,
                file_size_bytes=file_size,
                status="ready",
                social_caption=social_caption,
            )

            logger.info(
                f"Video successfully rendered and saved: id={video_record.id}, duration={result.duration_sec:.1f}s, url={video_url}"
            )
            return video_record
