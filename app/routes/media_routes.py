import uuid
from typing import Sequence
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.core.deps import get_db
from app.repositories.media_repo import RenderedVideoRepository
from app.schemas.media import (
    RenderedVideoRead,
    VideoRenderRequest,
    VideoRenderResultDTO,
)
from app.services.media.pipeline import VideoAssemblyService

router = APIRouter()


@router.post("/render", response_model=VideoRenderResultDTO, status_code=status.HTTP_201_CREATED)
async def render_video(
    payload: VideoRenderRequest,
    session: Session = Depends(get_db),
) -> VideoRenderResultDTO:
    service = VideoAssemblyService()
    try:
        video = await service.render_video(
            script_id=payload.script_id,
            client_id=payload.client_id,
            engine_type=payload.engine_type,
            voice_id=payload.voice_id,
            include_subtitles=payload.include_subtitles,
            include_watermark=payload.include_watermark,
            session=session,
        )
        return VideoRenderResultDTO(
            video=RenderedVideoRead.model_validate(video),
            message="Video rendered successfully.",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Video rendering failed: {str(e)}",
        )


@router.get("/{video_id}", response_model=RenderedVideoRead)
def get_video(
    video_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> RenderedVideoRead:
    repo = RenderedVideoRepository(session)
    video = repo.get_by_id(video_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rendered video {video_id} not found.",
        )
    return RenderedVideoRead.model_validate(video)


@router.get("/script/{script_id}", response_model=RenderedVideoRead)
def get_latest_video_by_script(
    script_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> RenderedVideoRead:
    repo = RenderedVideoRepository(session)
    video = repo.get_latest_by_script(script_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No rendered video found for script {script_id}.",
        )
    return RenderedVideoRead.model_validate(video)


@router.get("/", response_model=list[RenderedVideoRead])
def list_videos(
    client_id: uuid.UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    session: Session = Depends(get_db),
) -> Sequence[RenderedVideoRead]:
    repo = RenderedVideoRepository(session)
    videos = repo.list_videos(
        client_id=client_id,
        status=status_filter,
        skip=skip,
        limit=limit,
    )
    return [RenderedVideoRead.model_validate(v) for v in videos]
