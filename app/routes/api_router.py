from fastapi import APIRouter
from app.routes.auth_routes import router as auth_router
from app.routes.client_routes import router as client_router
from app.routes.media_routes import router as media_router
from app.routes.news_routes import router as news_router
from app.routes.script_routes import router as script_router
from app.routes.worker_routes import router as worker_router

api_v1_router = APIRouter()
api_v1_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_v1_router.include_router(news_router, prefix="/news", tags=["news"])
api_v1_router.include_router(client_router, prefix="/clients", tags=["clients"])
api_v1_router.include_router(script_router, prefix="/scripts", tags=["scripts"])
api_v1_router.include_router(media_router, prefix="/videos", tags=["videos"])
api_v1_router.include_router(worker_router, prefix="/worker", tags=["worker"])
