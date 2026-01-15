"""
Tests for AutoDoc AI System.
Базовые тесты для проверки структуры проекта.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch


class TestConfig:
    """Тесты конфигурации."""
    
    def test_settings_loaded(self):
        """Проверка загрузки настроек."""
        from app.config import settings
        
        assert settings.APP_NAME == "AutoDoc AI System"
        assert settings.APP_VERSION == "1.0.0"
    
    def test_database_url(self):
        """Проверка формирования URL базы данных."""
        from app.config import settings
        
        url = settings.async_database_url
        assert "postgresql+asyncpg" in url
        assert settings.DATABASE_HOST in url
    
    def test_redis_url(self):
        """Проверка формирования URL Redis."""
        from app.config import settings
        
        url = settings.redis_url
        assert "redis://" in url
        assert str(settings.REDIS_PORT) in url


class TestModels:
    """Тесты моделей базы данных."""
    
    def test_guide_status_enum(self):
        """Проверка enum статусов гайда."""
        from app.models import GuideStatus
        
        assert GuideStatus.DRAFT.value == "draft"
        assert GuideStatus.PROCESSING.value == "processing"
        assert GuideStatus.COMPLETED.value == "completed"
        assert GuideStatus.FAILED.value == "failed"
    
    def test_content_type_enum(self):
        """Проверка enum типов контента."""
        from app.models import ContentType
        
        assert ContentType.VIDEO.value == "video"
        assert ContentType.WIKI.value == "wiki"
        assert ContentType.SHORTS.value == "shorts"
        assert ContentType.ALL.value == "all"


class TestSchemas:
    """Тесты Pydantic схем."""
    
    def test_guide_create_schema(self):
        """Проверка схемы создания гайда."""
        from app.schemas import GuideCreate
        
        guide = GuideCreate(
            title="Тестовый гайд",
            description="Описание",
            language="ru",
        )
        
        assert guide.title == "Тестовый гайд"
        assert guide.language == "ru"
    
    def test_pagination_response(self):
        """Проверка схемы пагинации."""
        from app.schemas import PaginatedResponse
        
        response = PaginatedResponse(
            items=[],
            total=100,
            page=1,
            page_size=20,
            total_pages=5,
            has_next=True,
            has_previous=False,
        )
        
        assert response.total == 100
        assert response.total_pages == 5


class TestVideoProcessor:
    """Тесты видео-процессора."""
    
    @pytest.mark.asyncio
    async def test_step_segment_creation(self):
        """Проверка создания сегмента шага."""
        from app.services.video_processor import StepSegment
        
        segment = StepSegment(
            start_time=5.0,
            end_time=10.0,
            original_start=5.0,
            original_end=10.0,
            text="Нажмите кнопку",
        )
        
        assert segment.duration == 5.0
        assert segment.original_duration == 5.0
    
    def test_zoom_region_creation(self):
        """Проверка создания области зума."""
        from app.services.video_processor import ZoomRegion
        
        region = ZoomRegion(
            x=100,
            y=200,
            width=300,
            height=100,
            target_width=600,
            target_height=200,
        )
        
        assert region.center_x == 250
        assert region.center_y == 250


class TestTTSService:
    """Тесты TTS сервиса."""
    
    @pytest.mark.asyncio
    async def test_tts_result_creation(self):
        """Проверка создания результата TTS."""
        from app.services.tts_service import TTSResult
        
        result = TTSResult(
            success=True,
            audio_path="/path/to/audio.mp3",
            duration_seconds=5.5,
        )
        
        assert result.success is True
        assert result.audio_path == "/path/to/audio.mp3"
        assert result.duration_seconds == 5.5


class TestSmartAligner:
    """Тесты Smart Aligner."""
    
    def test_voice_segment_creation(self):
        """Проверка создания сегмента голоса."""
        from app.services.aligner import VoiceSegment
        
        segment = VoiceSegment(
            start=0.0,
            end=5.0,
            text="Нажмите кнопку",
            confidence=0.95,
        )
        
        assert segment.start == 0.0
        assert segment.end == 5.0
        assert segment.confidence == 0.95
    
    def test_screen_action_creation(self):
        """Проверка создания действия на экране."""
        from app.services.aligner import ScreenAction, ActionType
        
        action = ScreenAction(
            action_type=ActionType.CLICK,
            timestamp=5.5,
            x=100,
            y=200,
            element_description="Кнопка Отправить",
        )
        
        assert action.action_type == ActionType.CLICK
        assert action.timestamp == 5.5
        assert action.x == 100
    
    def test_action_type_enum(self):
        """Проверка enum типов действий."""
        from app.services.aligner import ActionType
        
        assert ActionType.CLICK.value == "click"
        assert ActionType.SCROLL.value == "scroll"
        assert ActionType.TYPE.value == "type"


class TestStorageService:
    """Тесты хранилища."""
    
    def test_storage_bucket_enum(self):
        """Проверка enum бакетов."""
        from app.services.storage import StorageBucket
        
        assert StorageBucket.VIDEOS.value == "autodoc-videos"
        assert StorageBucket.SCREENSHOTS.value == "autodoc-screenshots"
        assert StorageBucket.WIKI.value == "autodoc-wiki"
    
    def test_tts_result_to_dict(self):
        """Проверка сериализации результата TTS."""
        from app.services.tts_service import TTSResult
        
        result = TTSResult(
            success=True,
            audio_path="/path/to/audio.mp3",
            duration_seconds=3.0,
        )
        
        data = result.to_dict()
        
        assert data["success"] is True
        assert data["audio_path"] == "/path/to/audio.mp3"
        assert data["duration_seconds"] == 3.0


class TestAPIEndpoints:
    """Тесты API эндпоинтов (моки)."""
    
    def test_health_check_response(self):
        """Проверка ответа health check."""
        from app.schemas import HealthCheckResponse
        
        response = HealthCheckResponse(
            status="healthy",
            version="1.0.0",
            database="healthy",
            redis="healthy",
            minio="healthy",
            gpu_available=True,
            uptime_seconds=100,
        )
        
        assert response.status == "healthy"
        assert response.gpu_available is True
    
    def test_error_response(self):
        """Проверка ответа об ошибке."""
        from app.schemas import ErrorResponse
        
        error = ErrorResponse(
            error="Test error",
            details=[{"code": "test", "message": "Test message"}],
        )
        
        assert error.success is False
        assert error.error == "Test error"


class TestMainApp:
    """Тесты главного приложения."""
    
    def test_app_title(self):
        """Проверка заголовка приложения."""
        from app.main import app
        
        assert "AutoDoc AI System" in app.title
    
    def test_app_version(self):
        """Проверка версии приложения."""
        from app.main import app
        
        assert app.version == "1.0.0"
    
    def test_api_router_included(self):
        """Проверка включения API роутера."""
        from app.main import app
        from app.api import api_router
        
        # Проверяем что роутер зарегистрирован
        routes = [r.path for r in app.routes]
        
        assert any("/api/v1/" in path for path in routes)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
