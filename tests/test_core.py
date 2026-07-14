"""
Tests for AutoDoc AI System.
Базовые тесты для проверки структуры проекта.
"""

import pytest


class TestConfig:
    """Тесты конфигурации."""

    def test_settings_loaded(self):
        from app.config import settings

        assert settings.APP_NAME == "AutoDoc AI System"
        assert settings.APP_VERSION == "1.0.0"

    def test_database_url(self):
        from app.config import settings

        url = settings.async_database_url
        assert "postgresql+asyncpg" in url
        assert settings.DATABASE_HOST in url

    def test_redis_url(self):
        from app.config import settings

        url = settings.redis_url
        assert "redis://" in url
        assert str(settings.REDIS_PORT) in url


class TestModels:
    """Тесты моделей базы данных."""

    def test_guide_status_enum(self):
        from app.models import GuideStatus

        assert GuideStatus.DRAFT.value == "draft"
        assert GuideStatus.READY.value == "ready"
        assert GuideStatus.GENERATING.value == "generating"
        assert GuideStatus.COMPLETED.value == "completed"
        assert GuideStatus.FAILED.value == "failed"

    def test_session_status_enum(self):
        from app.models import SessionStatus

        assert SessionStatus.UPLOADED.value == "uploaded"
        assert SessionStatus.PROCESSING.value == "processing"
        assert SessionStatus.COMPLETED.value == "completed"
        assert SessionStatus.FAILED.value == "failed"

    def test_content_type_enum(self):
        from app.schemas import ContentTypeEnum

        assert ContentTypeEnum.VIDEO.value == "video"
        assert ContentTypeEnum.WIKI.value == "wiki"
        assert ContentTypeEnum.SHORTS.value == "shorts"
        assert ContentTypeEnum.ALL.value == "all"


class TestSchemas:
    """Тесты Pydantic схем."""

    def test_guide_create_schema(self):
        from app.schemas import GuideCreate

        guide = GuideCreate(
            title="Тестовый гайд",
            description="Описание",
            language="ru",
        )

        assert guide.title == "Тестовый гайд"
        assert guide.language == "ru"

    def test_pagination_response(self):
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


class TestSileroTTS:
    """Тесты Silero TTS (текущий движок озвучки по умолчанию)."""

    def test_default_speaker(self):
        from app.services.silero_tts_service import DEFAULT_SPEAKER

        assert DEFAULT_SPEAKER == "xenia"

    def test_normalize_transliterates_latin(self):
        from app.services.silero_tts_service import normalize_text_for_silero

        # Латиница транслитерируется, кириллица остаётся
        result = normalize_text_for_silero("Click")
        assert result
        assert not any("a" <= ch.lower() <= "z" for ch in result)

    def test_service_factory(self):
        from app.services.silero_tts_service import get_silero_service, SileroTTSService

        service = get_silero_service()
        assert isinstance(service, SileroTTSService)
        assert service.speaker


class TestStorageService:
    """Тесты хранилища."""

    def test_storage_type_enum(self):
        from app.services.storage import StorageType

        assert StorageType.VIDEOS.value == "videos"
        assert StorageType.SCREENSHOTS.value == "screenshots"
        assert StorageType.WIKI.value == "wiki"


class TestAPIEndpoints:
    """Тесты API схем."""

    def test_health_check_response(self):
        from app.schemas import HealthCheckResponse

        response = HealthCheckResponse(
            status="healthy",
            version="1.0.0",
            database="healthy",
            redis="healthy",
            storage="healthy",
            gpu_available=True,
            uptime_seconds=100,
        )

        assert response.status == "healthy"
        assert response.storage == "healthy"
        assert response.gpu_available is True

    def test_error_response(self):
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
        from app.main import app

        assert "AutoDoc AI System" in app.title

    def test_app_version(self):
        from app.main import app

        assert app.version == "1.0.0"

    def test_api_router_included(self):
        from app.main import app

        # api_router монтируется как под-приложение, поэтому пути не лежат
        # плоско в app.routes — проверяем по канонической OpenAPI-схеме.
        paths = app.openapi()["paths"]
        assert any(p.startswith("/api/v1") for p in paths)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
