from pydantic import BaseModel


class WorkerStatusDTO(BaseModel):
    is_running: bool
    scheduler_enabled: bool
    cron_schedule: str
    redis_endpoint: str
    run_on_startup: bool
