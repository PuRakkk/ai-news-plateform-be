from typing import Any
from arq.connections import RedisSettings
from app.core.config import settings
from app.core.log import logger


async def startup(ctx: dict[str, Any]) -> None:
    logger.info("ARQ Background Worker initialized.")


async def shutdown(ctx: dict[str, Any]) -> None:
    logger.info("ARQ Background Worker shut down.")


class WorkerSettings:
    """ARQ Worker configuration for background task execution and cron jobs."""

    functions: list[Any] = []
    cron_jobs: list[Any] = []
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD,
        database=settings.REDIS_DB,
    )
