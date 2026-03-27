"""
Инициализация сервисов AutoDoc AI System.

ВАЖНО: Не импортируем сервисы здесь, чтобы избежать загрузки тяжелых моделей при импорте.
Импортируйте сервисы напрямую из их модулей:
- from app.services.ai_service import ai_service
- from app.services.chatterbox_service import ChatterboxService
- from app.services.video_processor import video_processor
- etc.
"""

__all__ = [
    "VideoProcessor",
    "AIService", 
    "SmartAligner",
    "StorageService",
    "ChatterboxService",
]
