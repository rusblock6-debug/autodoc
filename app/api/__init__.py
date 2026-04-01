"""
API Router - регистрация всех роутов приложения.
"""

from fastapi import APIRouter

from app.api.guides import router as guides_router
from app.api.sessions import router as sessions_router
from app.api.steps import router as steps_router
from app.api.export import router as export_router
from app.api.video import router as video_router
from app.api.data_json import router as data_json_router


api_router = APIRouter()


# Регистрация роутов
api_router.include_router(guides_router, prefix="/guides", tags=["Guides"])

# MVP Workflow Routes - Session -> Step -> Video
api_router.include_router(sessions_router, prefix="/sessions", tags=["Sessions"])
api_router.include_router(steps_router, prefix="/steps", tags=["Steps"])
api_router.include_router(export_router, tags=["Export"])
api_router.include_router(video_router, prefix="/video", tags=["Video"])

# Data JSON Export Routes
api_router.include_router(data_json_router, prefix="/data-json", tags=["Data JSON Export"])
