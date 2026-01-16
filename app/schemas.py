"""
Pydantic-схемы для валидации данных API.
Определяют формат входных и выходных данных для всех эндпоинтов.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict, field_validator


# ===================== Enums =====================

class GuideStatusEnum(str, Enum):
    """Статусы гайда."""
    DRAFT = "draft"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


class ContentTypeEnum(str, Enum):
    """Типы генерируемого контента."""
    VIDEO = "video"
    WIKI = "wiki"
    SHORTS = "shorts"
    ALL = "all"


class JobStatusEnum(str, Enum):
    """Статусы задачи обработки."""
    PENDING = "pending"
    STARTED = "started"
    PROGRESS = "progress"
    SUCCESS = "success"
    FAILURE = "failure"


class ActionTypeEnum(str, Enum):
    """Типы действий на экране."""
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    SCROLL = "scroll"
    TYPE = "type"
    DRAG = "drag"
    HOVER = "hover"
    KEY_PRESS = "key_press"


# ===================== Base Models =====================

class BaseModelConfig(BaseModel):
    """Базовая конфигурация для всех моделей."""
    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        use_enum_values=True,
    )


class TimestampMixin(BaseModel):
    """Миксин для полей временных меток."""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ===================== User Schemas =====================

class UserCreate(BaseModel):
    """Схема создания пользователя."""
    email: str = Field(..., description="Электронная почта", min_length=5, max_length=255)
    username: str = Field(..., description="Имя пользователя", min_length=3, max_length=100)
    password: str = Field(..., description="Пароль", min_length=8)
    full_name: Optional[str] = Field(None, description="Полное имя", max_length=200)


class UserLogin(BaseModel):
    """Схема входа пользователя."""
    email: str = Field(..., description="Электронная почта")
    password: str = Field(..., description="Пароль")


class UserResponse(BaseModel):
    """Схема ответа с данными пользователя."""
    id: int
    email: str
    username: str
    full_name: Optional[str] = None
    preferred_language: str = "ru"
    is_active: bool = True
    is_verified: bool = False
    role: str = "user"
    created_at: datetime


class UserWithGuides(UserResponse):
    """Схема пользователя со списком гайдов."""
    guides: List["GuideListResponse"] = []


# ===================== Guide Schemas =====================

class StepCoordinates(BaseModel):
    """Координаты элемента на экране."""
    x: int = Field(..., description="X координата")
    y: int = Field(..., description="Y координата")
    width: int = Field(..., description="Ширина")
    height: int = Field(..., description="Высота")


class ZoomRegion(BaseModel):
    """Область для зума."""
    x: int = Field(..., description="Начальная X координата")
    y: int = Field(..., description="Начальная Y координата")
    width: int = Field(..., description="Ширина области")
    height: int = Field(..., description="Высота области")
    scale: float = Field(..., description="Масштаб увеличения")


class GuideStepBase(BaseModel):
    """Базовая схема шага гайда."""
    step_number: int = Field(..., description="Номер шага", ge=0)
    original_text: str = Field(..., description="Оригинальный текст шага")
    edited_text: Optional[str] = Field(None, description="Отредактированный текст")
    final_text: str = Field(..., description="Финальный текст для озвучки")
    start_time: float = Field(..., description="Начальное время (секунды)", ge=0)
    end_time: float = Field(..., description="Конечное время (секунды)", ge=0)
    action_type: Optional[ActionTypeEnum] = None
    element_description: Optional[str] = Field(None, description="Описание элемента")
    element_coordinates: Optional[StepCoordinates] = None
    zoom_region: Optional[ZoomRegion] = None
    zoom_level: float = Field(default=1.0, ge=1.0, le=5.0)
    audio_path: Optional[str] = None
    audio_duration: Optional[float] = None


class GuideStepCreate(GuideStepBase):
    """Схема создания шага."""
    pass


class GuideStepUpdate(BaseModel):
    """Схема обновления шага."""
    edited_text: Optional[str] = None
    final_text: Optional[str] = None
    zoom_level: Optional[float] = None
    zoom_region: Optional[ZoomRegion] = None


class GuideStepResponse(GuideStepBase, TimestampMixin):
    """Схема ответа с данными шага."""
    id: int
    guide_id: int
    asr_transcript: Optional[str] = None
    asr_confidence: Optional[float] = None
    is_processed: bool = False
    needs_regenerate: bool = False


class AnnotationData(BaseModel):
    """Данные аннотации на скриншоте."""
    type: str = Field(..., description="Тип аннотации (arrow, circle, rect, text)")
    x: int = Field(..., description="X координата")
    y: int = Field(..., description="Y координата")
    width: Optional[int] = None
    height: Optional[int] = None
    color: str = Field(default="#FF0000", description="Цвет аннотации")
    text: Optional[str] = None


class ScreenshotResponse(BaseModel):
    """Схема ответа со скриншотом."""
    id: int
    guide_id: int
    step_id: Optional[int] = None
    file_path: str
    minio_key: str
    width: int
    height: int
    video_timestamp: Optional[float] = None
    annotations: Optional[List[AnnotationData]] = None
    screenshot_type: str = "step_screenshot"
    created_at: datetime


class GuideCreate(BaseModel):
    """Схема создания гайда."""
    title: str = Field(..., description="Название гайда", min_length=3, max_length=500)
    description: Optional[str] = Field(None, description="Описание гайда")
    language: str = Field(default="ru", description="Язык гайда")
    content_type: ContentTypeEnum = Field(
        default=ContentTypeEnum.ALL, 
        description="Тип контента"
    )
    tags: List[str] = Field(default_factory=list, description="Теги")
    asr_model: Optional[str] = Field(None, description="Модель ASR")
    llm_model: Optional[str] = Field(None, description="Модель LLM")
    tts_voice: Optional[str] = Field(None, description="Голос TTS")


class GuideUpdate(BaseModel):
    """Схема обновления гайда."""
    title: Optional[str] = Field(None, min_length=3, max_length=500)
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    is_public: Optional[bool] = None
    status: Optional[GuideStatusEnum] = None


class GuideListResponse(BaseModel):
    """Схема списка гайдов (сокращенная)."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    uuid: str
    title: str
    description: Optional[str] = None
    status: GuideStatusEnum
    language: str = "ru"
    duration_seconds: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    is_public: bool = False
    view_count: int = 0


class GuideDetailResponse(BaseModel):
    """Подробная информация о гайде."""
    id: int
    uuid: str
    title: str
    status: str  # Используем str вместо enum для совместимости
    language: str = "ru"
    
    # TTS настройки
    tts_voice: str = "ru-RU-SvetlanaNeural"
    
    # Файлы
    shorts_video_path: Optional[str] = None
    shorts_duration_seconds: Optional[float] = None
    
    # Временные метки
    created_at: datetime
    updated_at: datetime
    shorts_generated_at: Optional[datetime] = None
    
    # Ошибки
    error_message: Optional[str] = None
    
    # Связанные данные
    steps: List["GuideStepResponseSimple"] = []
    
    model_config = ConfigDict(from_attributes=True)


class GuideStepResponseSimple(BaseModel):
    """Упрощённая схема шага для MVP."""
    id: int
    guide_id: int
    step_number: int
    click_timestamp: float
    click_x: int
    click_y: int
    screenshot_path: str
    screenshot_width: int
    screenshot_height: int
    raw_speech: Optional[str] = None
    normalized_text: str
    edited_text: Optional[str] = None
    tts_audio_path: Optional[str] = None
    tts_duration_seconds: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class GuideProcessingStatus(BaseModel):
    """Статус обработки гайда."""
    guide_id: int
    status: GuideStatusEnum
    current_step: Optional[str] = None
    progress_percent: int = 0
    message: Optional[str] = None
    estimated_time_remaining: Optional[int] = None  # в секундах


# ===================== Processing Job Schemas =====================

class JobCreate(BaseModel):
    """Схема создания задачи обработки."""
    guide_id: int
    job_type: str = Field(..., description="Тип задачи")
    parameters: Optional[Dict[str, Any]] = None
    priority: str = Field(default="normal", description="Приоритет")


class JobResponse(BaseModel):
    """Схема ответа задачи обработки."""
    id: int
    guide_id: int
    celery_task_id: Optional[str] = None
    job_type: str
    status: JobStatusEnum
    progress: int = 0
    progress_message: Optional[str] = None
    priority: str = "normal"
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0


# ===================== Recording Schemas =====================

class RecordingStartRequest(BaseModel):
    """Запрос на начало записи."""
    guide_id: Optional[int] = Field(None, description="ID существующего гайда или None для нового")
    title: Optional[str] = Field(None, description="Название (если guide_id не указан)")
    capture_audio: bool = Field(default=True, description="Записывать аудио с микрофона")
    capture_system_audio: bool = Field(default=False, description="Записывать системный звук")


class RecordingSession(BaseModel):
    """Информация о сессии записи."""
    session_id: str
    guide_id: int
    started_at: datetime
    capture_settings: Dict[str, bool]
    websocket_url: str


class RecordingEvent(BaseModel):
    """Событие, полученное от расширения браузера."""
    event_type: str = Field(..., description="Тип события")
    timestamp: float = Field(..., description="Время события относительно начала записи")
    data: Dict[str, Any] = Field(default_factory=dict)


# ===================== AI Processing Schemas =====================

class AIProcessingRequest(BaseModel):
    """Запрос на AI-обработку."""
    guide_id: int
    regenerate_steps: List[int] = Field(
        default_factory=list, 
        description="ID шагов для перегенерации"
    )
    tts_voice: Optional[str] = None
    smart_align: bool = Field(default=True, description="Включить умную синхронизацию")


class AIProcessingResult(BaseModel):
    """Результат AI-обработки."""
    guide_id: int
    status: str
    processed_steps: int
    total_steps: int
    generated_audio_files: int
    video_regenerated: bool
    wiki_generated: bool
    shorts_generated: bool
    processing_time_seconds: float
    errors: List[str] = []


class TextToSpeechRequest(BaseModel):
    """Запрос на генерацию аудио."""
    text: str = Field(..., description="Текст для озвучки", min_length=1, max_length=5000)
    voice: str = Field(default="ru-RU-SvetlanaNeural", description="Голос")
    output_path: Optional[str] = None
    speed: float = Field(default=1.0, ge=0.5, le=2.0, description="Скорость воспроизведения")
    pitch: float = Field(default=0, ge=-20, le=20, description="Высота тона")


class TextToSpeechResponse(BaseModel):
    """Ответ генерации аудио."""
    success: bool
    audio_path: Optional[str] = None
    duration_seconds: Optional[float] = None
    error: Optional[str] = None


# ===================== Wiki Generation Schemas =====================

class WikiGenerationRequest(BaseModel):
    """Запрос на генерацию Wiki-статьи."""
    guide_id: int
    format: str = Field(default="markdown", description="Формат (markdown, html, pdf)")
    include_annotations: bool = Field(default=True, description="Включать аннотации")
    include_screenshots: bool = Field(default=True, description="Включать скриншоты")
    style: str = Field(default="detailed", description="Стиль (brief, detailed)")


class WikiContentResponse(BaseModel):
    """Сгенерированный Wiki-контент."""
    guide_id: int
    format: str
    title: str
    content: str  # Markdown/HTML content
    metadata: Dict[str, Any]
    file_path: Optional[str] = None
    generated_at: datetime


# ===================== Shorts Generation Schemas =====================

class ShortsGenerationRequest(BaseModel):
    """Запрос на генерацию Shorts/Reels."""
    guide_id: int
    target_platform: str = Field(default="tiktok", description="Платформа (tiktok, instagram, youtube)")
    caption_style: str = Field(default="energetic", description="Стиль заголовков")
    add_music: bool = Field(default=False, description="Добавить фоновую музыку")
    music_source: Optional[str] = None
    aggressive_crop: bool = Field(default=True, description="Агрессивная обрезка пауз")


class ShortsGenerationResponse(BaseModel):
    """Результат генерации Shorts."""
    guide_id: int
    target_platform: str
    video_path: Optional[str] = None
    duration_seconds: Optional[float] = None
    file_size_bytes: Optional[int] = None
    generated_at: datetime
    error: Optional[str] = None


# ===================== Storage Schemas =====================

class PresignedUrlRequest(BaseModel):
    """Запрос на создание presigned URL для загрузки."""
    file_name: str = Field(..., description="Имя файла")
    content_type: str = Field(..., description="MIME-тип файла")
    guide_id: Optional[int] = None
    bucket: str = Field(default="uploads", description="Бакет для загрузки")


class PresignedUrlResponse(BaseModel):
    """Ответ с presigned URL."""
    upload_url: str
    file_key: str
    expires_in: int  # секунды
    method: str = "PUT"


class DownloadUrlResponse(BaseModel):
    """Ответ с URL для скачивания."""
    download_url: str
    expires_in: int  # секунды


# ===================== Pagination =====================

class PaginationParams(BaseModel):
    """Параметры пагинации."""
    page: int = Field(default=1, ge=1, description="Номер страницы")
    page_size: int = Field(default=20, ge=1, le=100, description="Размер страницы")


class PaginatedResponse(BaseModel):
    """Общая схема пагинированного ответа."""
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool


# ===================== Health Check =====================

class HealthCheckResponse(BaseModel):
    """Ответ проверки состояния сервиса."""
    status: str
    version: str
    database: str
    redis: str
    minio: str
    gpu_available: bool
    uptime_seconds: int


# ===================== Error Schemas =====================

class ErrorDetail(BaseModel):
    """Детали ошибки."""
    code: str
    message: str
    field: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Стандартный ответ об ошибке."""
    success: bool = False
    error: str
    details: Optional[List[ErrorDetail]] = None
    request_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Обновление forward references
GuideStepResponse.model_rebuild()
