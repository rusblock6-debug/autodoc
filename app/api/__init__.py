"""
API Router - регистрация всех роутов приложения.
"""

from fastapi import APIRouter

from app.api.guides import router as guides_router
# from app.api.storage import router as storage_router  # MinIO removed - using local storage
from app.api.auth import router as auth_router
from app.api.sessions import router as sessions_router
from app.api.steps import router as steps_router
from app.api.export import router as export_router
from app.api.video import router as video_router


api_router = APIRouter()


# Регистрация роутов
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(guides_router, prefix="/guides", tags=["Guides"])
# processing_router удалён: модуль целиком ссылался на несуществующие поля
# моделей (легаси до-MVP версии), все его эндпоинты падали с 500.
# api_router.include_router(storage_router, prefix="/storage", tags=["Storage"])  # MinIO removed

# MVP Workflow Routes - Session -> Step -> Video
api_router.include_router(sessions_router, prefix="/sessions", tags=["Sessions"])
api_router.include_router(steps_router, prefix="/steps", tags=["Steps"])
api_router.include_router(export_router, tags=["Export"])
api_router.include_router(video_router, prefix="/video", tags=["Video"])

# data_json_router удалён: экспорт в data.json (разделы «Обзор»/«Инструкции»
# внешнего сайта документации) — устаревшая фича, файл /data/data.json больше
# не ведётся.
