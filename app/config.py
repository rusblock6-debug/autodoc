"""
Конфигурация приложения AutoDoc AI System.
Загружает настройки из переменных окружения и файла .env.

Включает расширенные настройки для:
- Redis Streams с Consumer Groups (надёжная очередь)
- Heartbeat механизм для отслеживания живых задач
- Subprocess isolation для AI/Video операций
- GPU конфигурация для ML-моделей
"""

import os
from pathlib import Path
from typing import Optional
from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """
    Центральные настройки приложения.
    Все параметры конфигурируются через переменные окружения.
    """
    
    # === Базовые настройки приложения ===
    APP_NAME: str = "AutoDoc AI System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False, description="Режим отладки")
    ENVIRONMENT: str = Field(default="development", description="Среда выполнения")
    
    # === Настройки базы данных PostgreSQL ===
    DATABASE_HOST: str = Field(default="localhost", description="Хост базы данных")
    DATABASE_PORT: int = Field(default=5432, description="Порт базы данных")
    DATABASE_USER: str = Field(default="autodoc", description="Пользователь базы данных")
    DATABASE_PASSWORD: str = Field(default="autodoc_secret", description="Пароль базы данных")
    DATABASE_NAME: str = Field(default="autodoc_db", description="Имя базы данных")
    DATABASE_URL: Optional[str] = None  # Формируется автоматически
    
    @property
    def async_database_url(self) -> str:
        """Асинхронный URL для SQLAlchemy (asyncpg)."""
        return (
            f"postgresql+asyncpg://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}"
            f"@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
        )
    
    @property
    def sync_database_url(self) -> str:
        """Синхронный URL для SQLAlchemy (psycopg2)."""
        return (
            f"postgresql+psycopg2://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}"
            f"@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
        )
    
    # === Настройки Redis для очередей задач ===
    REDIS_HOST: str = Field(default="localhost", description="Хост Redis")
    REDIS_PORT: int = Field(default=6379, description="Порт Redis")
    REDIS_DB: int = Field(default=0, description="Номер базы данных Redis")
    REDIS_URL: Optional[str] = None  # Формируется автоматически
    
    # === Redis Streams Configuration (Надёжная очередь) ===
    REDIS_STREAM_NAME: str = Field(default="autodoc:tasks", description="Имя Redis Stream")
    REDIS_CONSUMER_GROUP: str = Field(default="autodoc:workers", description="Имя Consumer Group")
    REDIS_VISIBILITY_TIMEOUT: int = Field(
        default=3600, 
        description="Visibility timeout в секундах (1 час для тяжёлых AI задач)"
    )
    REDIS_BLOCK_TIMEOUT: int = Field(default=5000, description="BLOCK timeout для XREADGROUP в мс")
    
    @property
    def redis_url(self) -> str:
        """Полный URL для подключения к Redis."""
        if self.REDIS_URL:
            return self.REDIS_URL
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    # === Heartbeat Configuration ===
    HEARTBEAT_INTERVAL: int = Field(
        default=10, 
        description="Интервал обновления heartbeat в секундах"
    )
    STALE_TASK_THRESHOLD: int = Field(
        default=60, 
        description="Порог зависшей задачи в секундах (без heartbeat)"
    )
    HEARTBEAT_PREFIX: str = Field(
        default="autodoc:heartbeat:", 
        description="Префикс ключей для хранения heartbeat"
    )
    
    # === Task Retry Configuration ===
    MAX_RETRIES: int = Field(default=3, description="Максимальное количество попыток")
    RETRY_DELAY_INITIAL: int = Field(default=60, description="Начальная задержка retry в секундах")
    RETRY_BACKOFF_MULTIPLIER: float = Field(
        default=2.0, 
        description="Множитель экспоненциальной задержки"
    )
    RETRY_MAX_DELAY: int = Field(
        default=600, 
        description="Максимальная задержка retry в секундах"
    )
    
    # === AI Process Configuration ===
    AI_PROCESS_TIMEOUT: int = Field(
        default=3600, 
        description="Hard timeout для subprocess AI в секундах (1 час)"
    )
    GPU_DEVICE_ID: int = Field(default=0, description="ID GPU устройства для CUDA")
    GPU_MEMORY_FRACTION: float = Field(
        default=0.8, 
        description="Максимальная доля GPU памяти (0.0-1.0)"
    )
    
    # === Настройки MinIO (S3-совместимое хранилище) ===
    MINIO_ENDPOINT: str = Field(default="localhost:9000", description="Эндпоинт MinIO")
    MINIO_ACCESS_KEY: str = Field(default="minioadmin", description="Access key MinIO")
    MINIO_SECRET_KEY: str = Field(default="minioadmin", description="Secret key MinIO")
    MINIO_BUCKET_VIDEOS: str = Field(default="autodoc-videos", description="Бакет для видео")
    MINIO_BUCKET_SCREENSHOTS: str = Field(default="autodoc-screenshots", description="Бакет для скриншотов")
    MINIO_BUCKET_WIKI: str = Field(default="autodoc-wiki", description="Бакет для Wiki")
    MINIO_BUCKET_UPLOADS: str = Field(default="autodoc-uploads", description="Бакет для загрузок")
    MINIO_SECURE: bool = Field(default=False, description="Использовать HTTPS")
    MINIO_PRESIGNED_URL_EXPIRY: int = Field(
        default=3600, 
        description="Срок действия presigned URL в секундах"
    )
    
    # === Настройки AI-моделей ===
    # 
    # Поддержка внешних API для AI-моделей (бесплатные лимиты):
    # - OpenRouter: LLM (Llama 3.1, Gemma 2 - бесплатно)
    # - Groq: Whisper ASR (быстрее локального)
    
    # LLM (Logic & Analysis) - через OpenRouter API
    LLM_API_BASE: str = Field(
        default="https://openrouter.ai/api/v1",
        description="URL для LLM API (OpenRouter или Groq)"
    )
    LLM_API_KEY: str = Field(
        default="",
        description="API ключ для LLM"
    )
    LLM_MODEL: str = Field(
        default="meta-llama/llama-3.1-8b-instruct",
        description="Название модели для LLM (OpenRouter)"
    )
    
    # Параметры генерации LLM
    LLM_MAX_TOKENS: int = Field(default=2048, description="Максимальное количество токенов")
    LLM_TEMPERATURE: float = Field(default=0.3, description="Температура генерации")
    LLM_TOP_P: float = Field(default=0.9, description="Top-p sampling")
    
    # === Настройки Whisper (ASR) ===
    WHISPER_API_BASE: str = Field(
        default="https://api.groq.com/openai/v1",
        description="URL для Whisper API (Groq или OpenAI)"
    )
    WHISPER_API_KEY: str = Field(
        default="",
        description="API ключ для Whisper"
    )
    WHISPER_MODEL: str = Field(
        default="whisper-large-v3",
        description="Модель Whisper (для API: whisper-1 или whisper-large-v3)"
    )
    WHISPER_MODEL_SIZE: str = Field(
        default="medium",
        description="Размер локальной модели Whisper: tiny/base/small/medium/large-v3"
    )
    WHISPER_DEVICE: str = Field(
        default="cpu",
        description="Устройство для локального Whisper (cuda/cpu)"
    )
    
    # Локальная LLM (fallback через llama-cpp-python)
    LLM_MODEL_NAME: str = Field(
        default="Qwen/Qwen2.5-7B-Instruct-GGUF", 
        description="Название локальной LLM модели на Hugging Face"
    )
    LLM_MODEL_PATH: str = Field(
        default="/data/models/Qwen2.5-7B-Instruct-Q4_0.gguf",
        description="Путь к GGUF файлу локальной модели"
    )
    LLM_THREADS: int = Field(default=8, description="Количество CPU потоков для llama.cpp")
    LLM_CONTEXT_SIZE: int = Field(default=4096, description="Контекстное окно локальной LLM")
    LLM_BATCH_SIZE: int = Field(default=512, description="Размер батча для локального инференса")
    
    # TTS (Text-to-Speech)
    TTS_ENGINE: str = Field(default="edge-tts", description="Движок TTS (edge-tts/coqui)")
    EDGE_TTS_VOICE: str = Field(default="ru-RU-SvetlanaNeural", description="Голос для Edge TTS")
    COQUI_MODEL_PATH: Optional[str] = Field(default=None, description="Путь к модели Coqui XTTS")
    
    # === Настройки видеообработки ===
    VIDEO_OUTPUT_WIDTH: int = Field(default=1920, description="Ширина выходного видео")
    VIDEO_OUTPUT_HEIGHT: int = Field(default=1080, description="Высота выходного видео")
    VIDEO_FPS: int = Field(default=30, description="Кадров в секунду")
    VIDEO_QUALITY: str = Field(default="high", description="Качество видео (low/medium/high)")
    
    # Настройки для Shorts/Reels
    SHORTS_WIDTH: int = Field(default=1080, description="Ширина для Shorts")
    SHORTS_HEIGHT: int = Field(default=1920, description="Высота для Shorts")
    SHORTS_FPS: int = Field(default=60, description="Кадров в секунду для Shorts")
    
    # === Настройки путей ===
    WORKER_TEMP_DIR: Path = Field(
        default=Path("/tmp/autodoc_worker_temp"), 
        description="Временная директория для воркера"
    )
    SUBPROCESS_SCRIPT_PATH: Path = Field(
        default=Path("workers/ai_runner.py"), 
        description="Путь к скрипту AI Runner (относительно проекта)"
    )
    
    @field_validator("WORKER_TEMP_DIR", "SUBPROCESS_SCRIPT_PATH")
    @classmethod
    def validate_paths(cls, v: Path) -> Path:
        """Валидация путей. Не создаёт директории для SUBPROCESS_SCRIPT_PATH."""
        return v
    
    def get_subprocess_script_path(self) -> Path:
        """
        Получение абсолютного пути к скрипту AI Runner.
        Поддерживает как абсолютные пути, так и относительные от PROJECT_ROOT.
        """
        if self.SUBPROCESS_SCRIPT_PATH.is_absolute():
            return self.SUBPROCESS_SCRIPT_PATH
        
        # Вычисляем относительно директории app (теперь config.py в app/)
        # Нужно подняться на уровень выше для project root
        app_dir = Path(__file__).parent
        project_root = app_dir.parent
        return project_root / self.SUBPROCESS_SCRIPT_PATH


@lru_cache()
def get_settings() -> Settings:
    """
    Получение экземпляра настроек.
    Использует lru_cache для кэширования и предотвращения повторной загрузки.
    """
    return Settings()


# Создаем глобальный экземпляр настроек
settings = get_settings()


def setup_directories() -> None:
    """
    Создание необходимых директорий при запуске приложения.
    """
    directories = [
        settings.WORKER_TEMP_DIR,
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        directory.chmod(0o755)
