"""
API Router - регистрация всех роутов приложения.
"""

from fastapi import APIRouter

from app.api.guides import router as guides_router
from app.api.auth import router as auth_router
from app.api.sessions import router as sessions_router
from app.api.steps import router as steps_router
from app.api.export import router as export_router
from app.api.video import router as video_router

# Историческая справка (роутеров нет намеренно):
# - storage_router — хранилище перевели с MinIO на локальные файлы;
# - processing_router — легаси до-MVP, ссылался на несуществующие поля моделей;
# - data_json_router — экспорт в /data/data.json, фича больше не поддерживается.


api_router = APIRouter()


# Регистрация роутов
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(guides_router, prefix="/guides", tags=["Guides"])

# MVP Workflow Routes: Session -> Step -> Video
api_router.include_router(sessions_router, prefix="/sessions", tags=["Sessions"])
api_router.include_router(steps_router, prefix="/steps", tags=["Steps"])
api_router.include_router(export_router, tags=["Export"])
api_router.include_router(video_router, prefix="/video", tags=["Video"])
