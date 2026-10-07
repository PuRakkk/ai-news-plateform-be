import uuid
from datetime import datetime, timezone
from typing import Any, Sequence
from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlmodel import Session
from app.core.deps import get_db
from app.core.log import logger
from app.models.news import Article
from app.repositories.news_repo import (
    ArticleRepository,
    ArticleScoreRepository,
    ArticleVerificationRepository,
    NewsSourceRepository,
)
from app.schemas.news import (
    ArticleDetailRead,
    ArticleRead,
    ArticleScoreRead,
    ArticleVerificationRead,
    IngestionSummaryDTO,
    NewsSourceRead,
)
from app.services.ingestion.pipeline import (
    IngestionPipeline,
    execute_daily_ingestion_pipeline,
)

router = APIRouter()

# In-memory status tracker for FastAPI BackgroundTasks
_ingestion_state: dict[str, Any] = {
    "is_running": False,
    "last_run_at": None,
    "last_result": None,
    "error": None,
}


async def run_background_ingestion(client_id: uuid.UUID | None = None) -> None:
    """Non-blocking background runner triggered via FastAPI BackgroundTasks."""
    global _ingestion_state
    if _ingestion_state["is_running"]:
        logger.warning("FastAPI BackgroundTasks: Ingestion is already in progress. Skipping concurrent run.")
        return

    _ingestion_state["is_running"] = True
    _ingestion_state["error"] = None
    try:
        logger.info(f"FastAPI BackgroundTasks: Starting ingestion (client_id={client_id})...")
        result = await execute_daily_ingestion_pipeline(client_id=client_id)
        _ingestion_state["last_run_at"] = datetime.now(timezone.utc).isoformat()
        _ingestion_state["last_result"] = result.model_dump()
        logger.info("FastAPI BackgroundTasks: Ingestion finished successfully.")
    except Exception as exc:
        logger.error(f"FastAPI BackgroundTasks: Ingestion error: {exc}")
        _ingestion_state["error"] = str(exc)
    finally:
        _ingestion_state["is_running"] = False


@router.get("/sources", response_model=list[NewsSourceRead])
def list_news_sources(
    session: Session = Depends(get_db),
) -> Sequence[NewsSourceRead]:
    repo = NewsSourceRepository(session)
    repo.seed_default_sources()
    sources = repo.get_active_sources()
    return [NewsSourceRead.model_validate(s) for s in sources]


@router.get("/articles", response_model=list[ArticleRead])
def list_articles(
    limit: int = Query(default=30, ge=1, le=100),
    session: Session = Depends(get_db),
) -> Sequence[ArticleRead]:
    repo = ArticleRepository(session)
    articles = repo.get_recent_articles(limit=limit)
    return [ArticleRead.model_validate(a) for a in articles]


@router.get("/articles/winner", response_model=ArticleDetailRead | None)
def get_daily_winner(
    client_id: uuid.UUID | None = Query(default=None),
    session: Session = Depends(get_db),
) -> ArticleDetailRead | None:
    score_repo = ArticleScoreRepository(session)
    article_repo = ArticleRepository(session)
    verif_repo = ArticleVerificationRepository(session)

    # Find the winning article where is_selected == True (optionally filtered by client_id)
    from sqlmodel import select
    from app.models.news import Article, ArticleScore

    statement = (
        select(ArticleScore)
        .where(ArticleScore.is_selected == True)  # noqa: E712
    )
    if client_id:
        statement = statement.where(ArticleScore.client_id == client_id)
    statement = statement.order_by(ArticleScore.composite_score.desc())

    score = session.exec(statement).first()
    if score:
        article = article_repo.get_by_id(score.article_id)
    else:
        article = session.exec(
            select(Article).where(Article.status == "selected").order_by(Article.created_at.desc())
        ).first()

    if not article:
        return None

    verif = verif_repo.get_by_article_id(article.id)

    return ArticleDetailRead(
        id=article.id,
        source_id=article.source_id,
        url=article.url,
        title=article.title,
        summary=article.summary,
        full_text=article.full_text,
        content_hash=article.content_hash,
        published_at=article.published_at,
        status=article.status,
        created_at=article.created_at,
        verification=ArticleVerificationRead.model_validate(verif) if verif else None,
        score=ArticleScoreRead.model_validate(score) if score else None,
    )


@router.get("/ingest/status")
def get_ingestion_status() -> dict[str, Any]:
    """Check the real-time execution status and latest results of the background ingestion task."""
    return _ingestion_state


@router.post("/ingest", response_model=IngestionSummaryDTO | dict[str, Any])
async def trigger_ingestion(
    background_tasks: BackgroundTasks,
    client_id: uuid.UUID | None = Query(default=None),
    background: bool = Query(
        default=True,
        description="Run ingestion asynchronously in background using FastAPI BackgroundTasks without blocking the app",
    ),
    session: Session = Depends(get_db),
) -> IngestionSummaryDTO | dict[str, Any]:
    if background:
        background_tasks.add_task(run_background_ingestion, client_id)
        return {
            "status": "queued",
            "message": "News ingestion and verification pipeline started in background via FastAPI BackgroundTasks.",
            "client_id": str(client_id) if client_id else "auto",
        }

    # Synchronous execution (for unit tests or direct CLI scripts)
    pipeline = IngestionPipeline(session)
    return await pipeline.run(client_id=client_id)
