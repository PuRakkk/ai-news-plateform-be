from fastapi import APIRouter
from app.core.config import settings
from app.core.worker import embedded_worker_manager
from app.schemas.worker import WorkerStatusDTO

router = APIRouter()


@router.get("/status", response_model=WorkerStatusDTO)
def get_worker_status() -> WorkerStatusDTO:
    """Return background worker lifecycle and scheduler status."""
    cron_str = (
        f"{settings.SCHEDULER_CRON_HOUR:02d}:{settings.SCHEDULER_CRON_MINUTE:02d} ({settings.APP_TIMEZONE})"
        if settings.SCHEDULER_ENABLED
        else "disabled"
    )
    return WorkerStatusDTO(
        is_running=embedded_worker_manager.is_running,
        scheduler_enabled=settings.SCHEDULER_ENABLED,
        cron_schedule=cron_str,
        redis_endpoint=f"{settings.REDIS_HOST}:{settings.REDIS_PORT}",
        run_on_startup=settings.SCHEDULER_RUN_ON_STARTUP,
    )
