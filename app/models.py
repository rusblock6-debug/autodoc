"""
Модели данных для AutoDoc AI System (MVP).
Структура оптимизирована под сценарий: Запись → Шаги → Редактирование → Shorts
"""

from datetime import datetime
from typing import List, Optional
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, 
    Text, ForeignKey, JSON, Enum as SQLEnum, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.database import Base


class SessionStatus(str, Enum):
    """Статус сессии записи."""
    UPLOADED = "uploaded"      # Загружена, ожидает обработки
    PROCESSING = "processing"  # Идёт обработка (ASR, скриншоты, LLM)
    COMPLETED = "completed"    # Шаги созданы, готов к редактированию
    FAILED = "failed"          # Ошибка обработки


class GuideStatus(str, Enum):
    """Статус гайда."""
    DRAFT = "draft"            # Черновик, идёт редактирование
    READY = "ready"            # Текст готов, можно генерировать Shorts
    GENERATING = "generating"  # Генерация Shorts
    COMPLETED = "completed"    # Всё готово
    FAILED = "failed"          # Ошибка


class RecordingSession(Base):
    """
    Сессия записи.
    Хранит загруженные файлы: видео, аудио, лог кликов.
    """
    __tablename__ = "recording_sessions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    
    # Статус
    status: Mapped[SessionStatus] = mapped_column(
        SQLEnum(SessionStatus),
        default=SessionStatus.UPLOADED,
        nullable=False,
        index=True
    )
    
    # Метаданные записи
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    click_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Пути к файлам (MinIO keys)
    video_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    audio_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    clicks_log_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    
    # Результаты ASR
    asr_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    asr_segments: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    
    # Ошибки
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Временные метки
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    processing_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    processing_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Связи
    guide: Mapped[Optional["Guide"]] = relationship("Guide", back_populates="session", uselist=False)
    
    __table_args__ = (
        Index("idx_sessions_status", "status"),
    )


class Guide(Base):
    """
    Гайд.
    Содержит шаги со скриншотами и маркерами.
    """
    __tablename__ = "guides"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    
    # Ссылка на сессию
    session_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("recording_sessions.id", ondelete="SET NULL"), 
        nullable=True
    )
    
    # Основная информация
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="ru", nullable=False)
    
    # Статус
    status: Mapped[GuideStatus] = mapped_column(
        SQLEnum(GuideStatus),
        default=GuideStatus.DRAFT,
        nullable=False,
        index=True
    )
    
    # TTS настройки
    tts_voice: Mapped[str] = mapped_column(String(100), default="ru-RU-SvetlanaNeural")
    
    # Результаты
    shorts_video_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    shorts_duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Временные метки
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    shorts_generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Ошибки
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Связи
    session: Mapped[Optional["RecordingSession"]] = relationship("RecordingSession", back_populates="guide")
    steps: Mapped[List["GuideStep"]] = relationship(
        "GuideStep",
        back_populates="guide",
        cascade="all, delete-orphan",
        order_by="GuideStep.step_number"
    )
    
    __table_args__ = (
        Index("idx_guides_status", "status"),
    )


class GuideStep(Base):
    """
    Шаг гайда.
    Содержит: номер шага, скриншот, маркер клика, нормализованный текст.
    """
    __tablename__ = "guide_steps"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    guide_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("guides.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Номер шага (для сортировки)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # === ДАННЫЕ КЛИКА ===
    click_timestamp: Mapped[float] = mapped_column(Float, nullable=False)  # Таймкод клика в секундах
    click_x: Mapped[int] = mapped_column(Integer, nullable=False)          # Координата X маркера
    click_y: Mapped[int] = mapped_column(Integer, nullable=False)          # Координата Y маркера
    
    # === СКРИНШОТ ===
    screenshot_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    screenshot_width: Mapped[int] = mapped_column(Integer, nullable=False)
    screenshot_height: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # === ТЕКСТ ===
    # Оригинальная речь (что сказали до клика)
    raw_speech: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_speech_start: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    raw_speech_end: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Нормализованный текст (результат LLM)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Текст после ручной правки (если пользователь изменил)
    edited_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Финальный текст для озвучки и экспорта
    @property
    def final_text(self) -> str:
        """Финальный текст: edited_text или normalized_text."""
        return self.edited_text or self.normalized_text
    
    # === TTS ===
    tts_audio_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    tts_duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # === ВРЕМЕННЫЕ МЕТКИ ===
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Связь с гайдом
    guide: Mapped["Guide"] = relationship("Guide", back_populates="steps")
    
    # Индексы
    __table_args__ = (
        UniqueConstraint("guide_id", "step_number", name="uq_guide_step_number"),
        Index("idx_steps_guide_number", "guide_id", "step_number"),
    )


class User(Base):
    """
    Пользователь системы (опционально, для MVP можно упростить).
    """
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(500), nullable=False)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="user", nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Связи убраны для MVP - нет user_id в Guide
    
    __table_args__ = (
        Index("idx_users_role", "role"),
    )
