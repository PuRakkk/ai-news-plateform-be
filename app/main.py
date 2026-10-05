import time
from contextlib import asynccontextmanager
from cryptography.fernet import Fernet
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.core.log import logger, setup_logging
from app.routes.api_router import api_v1_router
from app.services.admin.admin_setup import setup_admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup logging
    setup_logging()
    logger.info("Initializing AI News Platform Backend...")

    # FastAPICache initialization
    FastAPICache.init(InMemoryBackend(), prefix="ai-news-cache:")

    # Startup validation: validate SECRET_ENCRYPTION_KEY if provided
    if settings.SECRET_ENCRYPTION_KEY:
        try:
            Fernet(settings.SECRET_ENCRYPTION_KEY.encode())
        except Exception as exc:
            raise ValueError(f"Invalid SECRET_ENCRYPTION_KEY Fernet format: {exc}") from exc

    yield

    logger.info("Shutting down AI News Platform Backend...")


app = FastAPI(
    title="AI News Backend",
    version="0.1.0",
    lifespan=lifespan,
)

# Admin Session Middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.ADMIN_AUTH_SECRET,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_performance_logging_middleware(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000
    client_ip = request.client.host if request.client else "unknown"
    logger.info(
        f"{request.method} {request.url.path} - Status: {response.status_code} - "
        f"Duration: {duration_ms:.2f}ms - IP: {client_ip}"
    )
    return response


@app.get("/healthz", tags=["health"])
def healthz() -> dict[str, str]:
    """Health check endpoint returning service status."""
    return {"status": "ok"}


# Mount API Routers
app.include_router(api_v1_router, prefix="/api/v1")

# Mount Starlette Admin
setup_admin(app)
