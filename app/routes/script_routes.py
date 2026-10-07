import uuid
from typing import Sequence
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.core.deps import get_db
from app.repositories.script_repo import ScriptRepository
from app.schemas.script import (
    ScriptDetailRead,
    ScriptGenerationRequest,
    ScriptGenerationResultDTO,
    ScriptRead,
)
from app.services.scripting.auditor import FactCheckingAuditorService
from app.services.scripting.pipeline import ScriptingPipeline

router = APIRouter()


@router.post("/generate", response_model=ScriptGenerationResultDTO, status_code=status.HTTP_201_CREATED)
async def generate_script(
    payload: ScriptGenerationRequest,
    session: Session = Depends(get_db),
) -> ScriptGenerationResultDTO:
    pipeline = ScriptingPipeline(session)
    try:
        detail = await pipeline.generate_and_audit(
            article_id=payload.article_id,
            client_id=payload.client_id,
            auto_audit=payload.auto_audit,
            enforce_grounding_revision=payload.enforce_grounding_revision,
        )
        return ScriptGenerationResultDTO(
            script=detail,
            message="Script successfully generated and audited.",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{script_id}", response_model=ScriptDetailRead)
def get_script_detail(
    script_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> ScriptDetailRead:
    pipeline = ScriptingPipeline(session)
    detail = pipeline.get_script_detail(script_id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Script with id {script_id} not found.",
        )
    return detail


@router.get("/", response_model=list[ScriptRead])
def list_scripts(
    client_id: uuid.UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    session: Session = Depends(get_db),
) -> Sequence[ScriptRead]:
    repo = ScriptRepository(session)
    scripts = repo.list_scripts(
        client_id=client_id,
        status=status_filter,
        skip=skip,
        limit=limit,
    )
    return [ScriptRead.model_validate(s) for s in scripts]


@router.post("/{script_id}/audit", response_model=ScriptDetailRead)
async def re_audit_script(
    script_id: uuid.UUID,
    auto_revise: bool = Query(default=True),
    session: Session = Depends(get_db),
) -> ScriptDetailRead:
    auditor = FactCheckingAuditorService(session)
    pipeline = ScriptingPipeline(session)
    try:
        await auditor.audit_script(script_id=script_id, auto_revise=auto_revise)
        detail = pipeline.get_script_detail(script_id)
        if not detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Script with id {script_id} not found.",
            )
        return detail
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
