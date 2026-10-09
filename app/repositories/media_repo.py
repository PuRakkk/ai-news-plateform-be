import uuid
from typing import Sequence
from sqlmodel import Session, col, select

from app.models.media import RenderedVideo
from app.repositories.base import BaseRepository


class RenderedVideoRepository(BaseRepository[RenderedVideo]):
    def __init__(self, session: Session) -> None:
        super().__init__(RenderedVideo, session)

    def get_by_id(self, id: uuid.UUID) -> RenderedVideo | None:
        return self.session.get(RenderedVideo, id)

    def get_latest_by_script(self, script_id: uuid.UUID) -> RenderedVideo | None:
        statement = (
            select(RenderedVideo)
            .where(RenderedVideo.script_id == script_id)
            .order_by(col(RenderedVideo.created_at).desc())
        )
        return self.session.exec(statement).first()

    def list_videos(
        self,
        client_id: uuid.UUID | None = None,
        status: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Sequence[RenderedVideo]:
        statement = select(RenderedVideo)
        if client_id is not None:
            statement = statement.where(RenderedVideo.client_id == client_id)
        if status:
            statement = statement.where(RenderedVideo.status == status)

        statement = statement.order_by(col(RenderedVideo.created_at).desc()).offset(skip).limit(limit)
        return self.session.exec(statement).all()

    def create_video(
        self,
        script_id: uuid.UUID,
        client_id: uuid.UUID | None,
        video_path: str,
        video_url: str,
        thumbnail_url: str | None = None,
        audio_url: str | None = None,
        duration_sec: float = 0.0,
        resolution: str = "1920x1080",
        file_size_bytes: int = 0,
        status: str = "ready",
        social_caption: str | None = None,
    ) -> RenderedVideo:
        video = RenderedVideo(
            script_id=script_id,
            client_id=client_id,
            video_path=video_path,
            video_url=video_url,
            thumbnail_url=thumbnail_url,
            audio_url=audio_url,
            duration_sec=duration_sec,
            resolution=resolution,
            file_size_bytes=file_size_bytes,
            status=status,
            social_caption=social_caption,
        )
        self.session.add(video)
        self.session.commit()
        self.session.refresh(video)
        return video

    def update_status(
        self, id: uuid.UUID, status: str, error_message: str | None = None
    ) -> RenderedVideo | None:
        video = self.session.get(RenderedVideo, id)
        if not video:
            return None
        video.status = status
        if error_message:
            video.error_message = error_message
        self.session.add(video)
        self.session.commit()
        self.session.refresh(video)
        return video
