"""
Инициализация сервисов AutoDoc AI System.
"""

from app.services.video_processor import VideoProcessor
from app.services.ai_service import AIService
from app.services.aligner import SmartAligner
from app.services.storage import StorageService
from app.services.tts_service import TTSService

__all__ = [
    "VideoProcessor",
    "AIService", 
    "SmartAligner",
    "StorageService",
    "TTSService",
]
