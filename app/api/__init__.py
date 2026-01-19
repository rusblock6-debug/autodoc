"""
API Router - регистрация всех роутов приложения.
"""

from fastapi import APIRouter

from app.api.guides import router as guides_router
from app.api.processing import router as processing_router
from app.api.storage import router as storage_router
from app.api.auth import router as auth_router
from app.api.sessions import router as sessions_router
from app.api.steps import router as steps_router
from app.api.export import router as export_router
from app.api.shorts import router as shorts_router


api_router = APIRouter()


# Регистрация роутов
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(guides_router, prefix="/guides", tags=["Guides"])
api_router.include_router(processing_router, prefix="/processing", tags=["Processing"])
api_router.include_router(storage_router, prefix="/storage", tags=["Storage"])

# MVP Workflow Routes - Session -> Step -> Shorts
api_router.include_router(sessions_router, prefix="/sessions", tags=["Sessions"])
api_router.include_router(steps_router, prefix="/steps", tags=["Steps"])
api_router.include_router(export_router, tags=["Export"])
api_router.include_router(shorts_router, prefix="/shorts", tags=["Shorts"])
