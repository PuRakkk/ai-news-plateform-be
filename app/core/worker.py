import asyncio
import signal
import threading
import zoneinfo
from typing import Any
from arq.connections import ArqRedis, RedisSettings, create_pool
from arq.cron import cron
from arq.worker import Worker, create_worker
from app.core.config import settings
from app.core.log import logger
from app.services.ingestion.pipeline import execute_daily_ingestion_pipeline

# Ensure SIGUSR1 exists on Windows platforms to prevent ARQ shutdown AttributeError
if not hasattr(signal, "SIGUSR1"):
    setattr(signal, "SIGUSR1", getattr(signal, "SIGTERM", 15))


def get_redis_settings() -> RedisSettings:
    """Return ARQ Redis connection settings."""
    return RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD or None,
        database=settings.REDIS_DB,
    )


async def get_redis_pool() -> ArqRedis:
    """Create and return an ARQ Redis connection pool for enqueuing background tasks."""
    return await create_pool(get_redis_settings())


async def run_daily_news_ingestion(ctx: dict[str, Any]) -> dict[str, Any]:
    """ARQ job to run the complete 4-stage ingestion, verification, and scoring pipeline, then fan out scripts to active clients."""
    logger.info("ARQ Worker: Triggering scheduled news ingestion...")
    result = await execute_daily_ingestion_pipeline()
    from app.core.database import get_session
    from app.repositories.client_repo import ClientProfileRepository
    from app.repositories.news_repo import ArticleScoreRepository
    from app.services.scripting.pipeline import ScriptingPipeline

    with get_session() as session:
        client_repo = ClientProfileRepository(session)
        active_clients = list(client_repo.get_active_clients())

    if active_clients:
        for cl in active_clients:
            cl_win_id = result.client_winners.get(str(cl.id))
            if not cl_win_id:
                with get_session() as score_session:
                    score_repo = ArticleScoreRepository(score_session)
                    win_score = score_repo.get_winning_article(client_id=cl.id)
                    if win_score:
                        cl_win_id = win_score.article_id

            if not cl_win_id:
                logger.warning(
                    f"ARQ Worker: No qualifying winning article met relevance threshold for client '{cl.name}' (id={cl.id}). "
                    f"Skipping script generation to prevent off-topic content."
                )
                continue

            logger.info(f"ARQ Worker: Auto-generating script for client: {cl.name} (winning article_id={cl_win_id})")
            try:
                with get_session() as client_session:
                    pipeline = ScriptingPipeline(client_session)
                    await pipeline.generate_and_audit(
                        article_id=cl_win_id,
                        client_id=cl.id,
                        auto_audit=True,
                    )
            except Exception as e:
                logger.error(f"ARQ Worker: Failed to generate script for client {cl.name}: {e}")
    else:
        if result.winning_article_id:
            logger.info("ARQ Worker: No custom clients configured. Generating default executive script.")
            try:
                with get_session() as default_session:
                    pipeline = ScriptingPipeline(default_session)
                    await pipeline.generate_and_audit(
                        article_id=result.winning_article_id,
                        client_id=None,
                        auto_audit=True,
                    )
            except Exception as e:
                logger.error(f"ARQ Worker: Failed to generate default script: {e}")

    return result.model_dump()


async def startup(ctx: dict[str, Any]) -> None:
    from app.core.log import setup_logging
    setup_logging()
    logger.info(
        f"ARQ Background Worker initialized. Scheduled daily at {settings.SCHEDULER_CRON_HOUR:02d}:{settings.SCHEDULER_CRON_MINUTE:02d} ({settings.APP_TIMEZONE})."
    )
    if settings.SCHEDULER_RUN_ON_STARTUP:
        logger.info("SCHEDULER_RUN_ON_STARTUP is enabled. Running ingestion on startup...")
        await run_daily_news_ingestion(ctx)


async def shutdown(ctx: dict[str, Any]) -> None:
    logger.info("ARQ Background Worker shut down.")


cron_schedules: list[Any] = []
if settings.SCHEDULER_ENABLED:
    cron_schedules.append(
        cron(
            run_daily_news_ingestion,
            hour={settings.SCHEDULER_CRON_HOUR},
            minute={settings.SCHEDULER_CRON_MINUTE},
        )
    )


class WorkerSettings:
    """ARQ Worker configuration for background task execution and cron jobs."""

    functions: list[Any] = [run_daily_news_ingestion]
    cron_jobs: list[Any] = cron_schedules
    on_startup = startup
    on_shutdown = shutdown
    timezone = zoneinfo.ZoneInfo(settings.APP_TIMEZONE)
    redis_settings = get_redis_settings()
    job_timeout: int = 900  # 15 minutes to allow multi-stage ingestion & multi-client script generation


class EmbeddedWorkerManager:
    """Manages lifecycle of the in-process ARQ background worker in a dedicated background thread."""

    def __init__(self) -> None:
        self.worker: Worker | None = None
        self.thread: threading.Thread | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.is_running: bool = False

    def _run_worker(self) -> None:
        """Isolated thread entrypoint: creates a dedicated event loop and runs ARQ."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.worker = create_worker(WorkerSettings, handle_signals=False)
            self.loop.run_until_complete(self.worker.async_run())
        except Exception as exc:
            logger.error(f"Embedded ARQ background worker error: {exc}")
        finally:
            try:
                self.loop.close()
            except Exception:
                pass

    async def start(self) -> None:
        """Start the embedded ARQ worker inside a dedicated background thread."""
        if not settings.WORKER_EMBEDDED_ENABLED:
            logger.info("Embedded ARQ background worker is disabled via configuration.")
            return

        if self.is_running:
            logger.warning("Embedded ARQ worker is already running.")
            return

        try:
            logger.info("Initializing embedded ARQ background worker in isolated background thread...")
            self.thread = threading.Thread(
                target=self._run_worker,
                name="arq-embedded-worker",
                daemon=True,
            )
            self.thread.start()
            self.is_running = True
            logger.info(
                f"Embedded ARQ Worker started in isolated background thread (FastAPI event loop is 100% non-blocking). "
                f"Daily cron at {settings.SCHEDULER_CRON_HOUR:02d}:{settings.SCHEDULER_CRON_MINUTE:02d} ({settings.APP_TIMEZONE})."
            )
        except Exception as exc:
            logger.warning(
                f"Could not initialize embedded ARQ worker (is Redis running on {settings.REDIS_HOST}:{settings.REDIS_PORT}?): {exc}. "
                "The web server will continue running without background scheduling."
            )
            self.worker = None
            self.thread = None
            self.loop = None
            self.is_running = False

    async def stop(self) -> None:
        """Gracefully shut down the embedded ARQ worker."""
        if not self.is_running:
            return

        logger.info("Gracefully shutting down embedded ARQ background worker...")
        if self.worker and self.loop and self.loop.is_running():
            try:
                fut = asyncio.run_coroutine_threadsafe(self.worker.close(), self.loop)
                fut.result(timeout=5)
            except Exception as exc:
                logger.warning(f"Error while closing embedded worker: {exc}")

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3.0)

        self.worker = None
        self.thread = None
        self.loop = None
        self.is_running = False
        logger.info("Embedded ARQ background worker shutdown complete.")


embedded_worker_manager = EmbeddedWorkerManager()
