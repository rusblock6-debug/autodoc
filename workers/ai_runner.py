#!/usr/bin/env python3
"""
AI Runner - Изолированный subprocess для выполнения AI задач.

Этот скрипт запускается как отдельный процесс из celery_tasks.py.
Он выполняет тяжелые AI/Video операции без блокировки основного воркера.

Поддерживаемые задачи:
- video_processing: Обработка видео с зумом и синхронизацией
- ai_transcription: Транскрипция аудио (Whisper)
- ai_processing: Полная AI-обработка записи
- tts_generation: Генерация TTS
- smart_alignment: Синхронизация речи и действий
- shorts_generation: Генерация Shorts/Reels
- wiki_generation: Генерация Wiki-статей

Usage:
    python workers/ai_runner.py --input <input.json> --output <output.json>

Input format:
    {
        "task_type": "video_processing",
        "task_id": "abc123",
        "payload": { ... },
        "created_at": "2024-01-01T00:00:00"
    }

Output format:
    {
        "task_id": "abc123",
        "success": true,
        "result": { ... },
        "error": null
    }
"""

import argparse
import json
import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

# Добавляем корень проекта в пути для импортов
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("AI-Runner")


# === Task Handlers ===

class TaskHandler:
    """
    Базовый класс для обработчиков задач.
    """
    
    def __init__(self, payload: Dict[str, Any]):
        self.payload = payload
        self.guide_id = payload.get("guide_id")
        self.task_id = payload.get("task_id", "unknown")
        
    def execute(self) -> Dict[str, Any]:
        """Выполнение задачи. Переопределить в наследниках."""
        raise NotImplementedError
    
    def _update_task_status(self, status: str, progress: int = 0, error: str = None, traceback: str = None) -> None:
        """
        Обновление статуса задачи в базе данных.
        
        CRITICAL: Предотвращает зависание задач в PROCESSING при краше.
        
        Args:
            status: Новый статус (PROCESSING, SUCCESS, FAILED)
            progress: Прогресс в процентах
            error: Текст ошибки (для FAILED)
            traceback: Полный traceback (для FAILED)
        """
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.ext.asyncio import create_async_engine
            from app.config import settings
            from app.models import Guide
            from sqlalchemy.future import select
            import asyncio
            
            if not self.guide_id:
                return
            
            # Используем синхронный движок для subprocess
            engine = create_engine(settings.sync_database_url)
            
            def update_status():
                from sqlalchemy.orm import Session
                with Session(engine) as session:
                    guide = session.query(Guide).filter(Guide.id == self.guide_id).first()
                    if guide:
                        guide.processing_status = status
                        guide.processing_progress = progress
                        if error:
                            guide.error_message = error[:1000]  # Ограничиваем длину
                        if traceback:
                            guide.debug_info = traceback[:2000]
                        session.commit()
                        logger.info(f"Task {self.task_id} status updated to: {status}")
            
            # Запускаем в executor для синхронного SQLAlchemy
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_in_executor(None, update_status)
            finally:
                loop.close()
                
        except Exception as e:
            logger.warning(f"Failed to update task status: {e}")
    
    def download_from_s3(self, s3_key: str, local_path: Path) -> bool:
        """
        Скачивание файла из S3.
        
        Args:
            s3_key: Ключ объекта в S3
            local_path: Локальный путь для сохранения
            
        Returns:
            True если успешно
        """
        try:
            from app.services.storage import storage_service
            
            # Скачиваем в chunks для больших файлов
            storage_service.download_file(
                s3_key=s3_key,
                local_path=str(local_path),
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to download {s3_key}: {e}")
            return False
    
    def upload_to_s3(self, local_path: Path, bucket: str, guide_id: int, subfolder: str = "") -> str:
        """
        Загрузка файла в S3.
        
        Args:
            local_path: Локальный путь к файлу
            bucket: Бакет назначения
            guide_id: ID гайда
            subfolder: Подпапка
            
        Returns:
            S3 ключ загруженного файла
        """
        from app.services.storage import storage_service, StorageBucket
        from app.config import settings
        
        # Конвертируем строковый bucket в enum если нужно
        try:
            bucket_enum = StorageBucket(bucket)
        except ValueError:
            bucket_enum = None
        
        result = storage_service.upload_local_file(
            file_path=str(local_path),
            bucket=bucket_enum or StorageBucket.VIDEOS,
            guide_id=guide_id,
            subfolder=subfolder,
        )
        return result.get("object_key", "")
    
    def cleanup(self, *paths: Path) -> None:
        """Очистка временных файлов."""
        for path in paths:
            try:
                if path and path.exists():
                    if path.is_file():
                        path.unlink()
                    elif path.is_dir():
                        import shutil
                        shutil.rmtree(path)
            except Exception as e:
                logger.warning(f"Failed to cleanup {path}: {e}")


class VideoProcessingHandler(TaskHandler):
    """
    Обработчик задач обработки видео.
    """
    
    def execute(self) -> Dict[str, Any]:
        """Обработка видео с применением зума."""
        from app.services.video_processor import video_processor
        from app.config import settings
        
        video_key = self.payload["video_key"]
        steps = self.payload.get("steps", [])
        options = self.payload.get("options", {})
        output_bucket = self.payload.get("output_bucket", settings.MINIO_BUCKET_VIDEOS)
        
        logger.info(f"Processing video {video_key} for guide {self.guide_id}")
        
        # Скачиваем видео
        video_path = settings.WORKER_TEMP_DIR / f"video_{self.guide_id}.mp4"
        
        if not self.download_from_s3(video_key, video_path):
            raise RuntimeError(f"Failed to download video: {video_key}")
        
        # Создаем сегменты
        segments = []
        for step in steps:
            segment = video_processor.StepSegment(
                start_time=step["start_time"],
                end_time=step["end_time"],
                original_start=step["original_start"],
                original_end=step["original_end"],
                text=step["text"],
                audio_path=step.get("audio_path"),
                zoom_region=step.get("zoom_region"),
                action_type=step.get("action_type"),
            )
            segments.append(segment)
        
        # Формируем выходной путь
        output_path = settings.WORKER_TEMP_DIR / f"processed_{self.guide_id}.mp4"
        
        # Прогресс callback
        def progress_callback(progress_data):
            logger.info(f"Processing progress: {progress_data.progress_percent:.1f}% - {progress_data.message}")
        
        # Выполняем обработку
        success = video_processor.generate_video_with_zoom(
            input_video=str(video_path),
            output_video=str(output_path),
            steps=segments,
            progress_callback=progress_callback,
        )
        
        if not success:
            raise RuntimeError("Video processing failed")
        
        # Загружаем результат
        output_key = self.upload_to_s3(output_path, output_bucket, self.guide_id, "processed")
        
        # Очищаем
        self.cleanup(video_path, output_path)
        
        return {
            "success": True,
            "guide_id": self.guide_id,
            "output_key": output_key,
            "processing_time": "calculated",
        }


class ShortsGenerationHandler(TaskHandler):
    """
    Обработчик генерации Shorts/Reels.
    """
    
    def execute(self) -> Dict[str, Any]:
        """Генерация Shorts."""
        from app.services.video_processor import video_processor
        from app.config import settings
        
        video_key = self.payload["video_key"]
        target_platform = self.payload.get("target_platform", "tiktok")
        options = self.payload.get("options", {})
        output_bucket = self.payload.get("output_bucket", settings.MINIO_BUCKET_VIDEOS)
        
        logger.info(f"Generating shorts for guide {self.guide_id}")
        
        # Скачиваем видео
        video_path = settings.WORKER_TEMP_DIR / f"shorts_src_{self.guide_id}.mp4"
        
        if not self.download_from_s3(video_key, video_path):
            raise RuntimeError(f"Failed to download video: {video_key}")
        
        # Формируем выходной путь
        output_path = settings.WORKER_TEMP_DIR / f"shorts_{self.guide_id}.mp4"
        
        # Генерируем shorts
        success = video_processor.generate_shorts(
            input_video=str(video_path),
            output_video=str(output_path),
            target_platform=target_platform,
        )
        
        if not success:
            raise RuntimeError("Shorts generation failed")
        
        # Удаляем тишину если нужно
        if options.get("aggressive_crop", True):
            no_silence_path = settings.WORKER_TEMP_DIR / f"shorts_no_silence_{self.guide_id}.mp4"
            video_processor.remove_silence(
                input_video=str(output_path),
                output_video=str(no_silence_path),
            )
            output_path = no_silence_path
        
        # Загружаем результат
        output_key = self.upload_to_s3(output_path, output_bucket, self.guide_id, "shorts")
        
        # Очищаем
        self.cleanup(video_path, output_path)
        
        return {
            "success": True,
            "guide_id": self.guide_id,
            "platform": target_platform,
            "output_key": output_key,
        }


class TranscriptionHandler(TaskHandler):
    """
    Обработчик транскрипции аудио.
    """
    
    def execute(self) -> Dict[str, Any]:
        """Транскрипция аудио через Whisper."""
        from app.services.ai_service import ai_service
        from app.config import settings
        
        audio_key = self.payload["audio_key"]
        language = self.payload.get("language", "ru")
        
        logger.info(f"Transcribing audio for guide {self.guide_id}")
        
        # Скачиваем аудио
        audio_path = settings.WORKER_TEMP_DIR / f"audio_{self.guide_id}.wav"
        
        if not self.download_from_s3(audio_key, audio_path):
            raise RuntimeError(f"Failed to download audio: {audio_key}")
        
        # Транскрибируем
        result = ai_service.asr.transcribe(str(audio_path), language=language)
        
        # Очищаем
        self.cleanup(audio_path)
        
        return {
            "success": True,
            "guide_id": self.guide_id,
            "transcription": result.to_dict() if hasattr(result, "to_dict") else result,
        }


class AIProcessingHandler(TaskHandler):
    """
    Обработчик полной AI-обработки записи.
    """
    
    def execute(self) -> Dict[str, Any]:
        """Полная AI-обработка: транскрипция, анализ, генерация метаданных."""
        from app.services.ai_service import ai_service
        from app.config import settings
        
        audio_key = self.payload["audio_key"]
        click_events = self.payload.get("click_events", [])
        language = self.payload.get("language", "ru")
        
        logger.info(f"Full AI processing for guide {self.guide_id}")
        
        # Скачиваем аудио
        audio_path = settings.WORKER_TEMP_DIR / f"ai_audio_{self.guide_id}.wav"
        
        if not self.download_from_s3(audio_key, audio_path):
            raise RuntimeError(f"Failed to download audio: {audio_key}")
        
        # Выполняем обработку
        results = ai_service.process_recording(
            video_path="",  # Видео уже обработано
            audio_path=str(audio_path),
            click_events=click_events,
            language=language,
        )
        
        # Очищаем
        self.cleanup(audio_path)
        
        return {
            "success": True,
            "guide_id": self.guide_id,
            "results": results,
        }


class TTSGenerationHandler(TaskHandler):
    """
    Обработчик генерации TTS.
    """
    
    def execute(self) -> Dict[str, Any]:
        """Генерация озвучки текста."""
        from app.services.tts_service import tts_service
        from app.config import settings
        
        step_id = self.payload["step_id"]
        text = self.payload["text"]
        voice = self.payload.get("voice", settings.EDGE_TTS_VOICE)
        
        logger.info(f"Generating TTS for step {step_id}")
        
        # Формируем путь для вывода
        output_path = settings.WORKER_TEMP_DIR / f"tts_{self.guide_id}_{step_id}.wav"
        
        # Генерируем
        result = tts_service.generate_audio(
            text=text,
            voice=voice,
            output_path=str(output_path),
        )
        
        if not result.success:
            return {
                "success": False,
                "guide_id": self.guide_id,
                "step_id": step_id,
                "error": result.error,
            }
        
        # Загружаем в S3
        output_key = self.upload_to_s3(
            output_path,
            settings.MINIO_BUCKET_VIDEOS,
            self.guide_id,
            "tts",
        )
        
        # Очищаем
        self.cleanup(output_path)
        
        return {
            "success": True,
            "guide_id": self.guide_id,
            "step_id": step_id,
            "audio_key": output_key,
            "duration_seconds": result.duration_seconds,
        }


class SmartAlignmentHandler(TaskHandler):
    """
    Обработчик интеллектуальной синхронизации.
    """
    
    def execute(self) -> Dict[str, Any]:
        """Синхронизация речи и действий на экране."""
        from app.services.aligner import smart_aligner, VoiceSegment, ScreenAction, ActionType
        
        voice_segments = self.payload.get("voice_segments", [])
        screen_actions = self.payload.get("screen_actions", [])
        language = self.payload.get("language", "ru")
        
        logger.info(f"Smart alignment for guide {self.guide_id}")
        
        # Конвертируем в объекты
        segments = [
            VoiceSegment(
                start=s["start"],
                end=s["end"],
                text=s["text"],
                confidence=s.get("confidence", 0.9),
            )
            for s in voice_segments
        ]
        
        actions = [
            ScreenAction(
                action_type=ActionType(a["action_type"]),
                timestamp=a["timestamp"],
                x=a["x"],
                y=a["y"],
                element_description=a.get("element_description"),
            )
            for a in screen_actions
        ]
        
        # Выполняем синхронизацию
        result = smart_aligner.align(segments, actions, language)
        
        return {
            "success": True,
            "guide_id": self.guide_id,
            "alignment": result.to_dict() if hasattr(result, "to_dict") else result,
        }


class WikiGenerationHandler(TaskHandler):
    """
    Обработчик генерации Wiki.
    """
    
    def execute(self) -> Dict[str, Any]:
        """Генерация Wiki-статьи из гайда."""
        from app.services.wiki_generator import wiki_generator
        
        format_type = self.payload.get("format", "markdown")
        include_screenshots = self.payload.get("include_screenshots", True)
        
        logger.info(f"Generating wiki for guide {self.guide_id}")
        
        # Здесь должна быть логика генерации Wiki
        # Пока возвращаем заглушку
        
        return {
            "success": True,
            "guide_id": self.guide_id,
            "format": format_type,
            "content": "Wiki content placeholder",
        }


# === Task Router ===

HANDLERS = {
    "video_processing": VideoProcessingHandler,
    "shorts_generation": ShortsGenerationHandler,
    "ai_transcription": TranscriptionHandler,
    "ai_processing": AIProcessingHandler,
    "tts_generation": TTSGenerationHandler,
    "smart_alignment": SmartAlignmentHandler,
    "wiki_generation": WikiGenerationHandler,
}


def execute_task(task_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Выполнение задачи через соответствующий handler.
    
    Args:
        task_type: Тип задачи
        payload: Данные задачи
        
    Returns:
        Результат выполнения
    """
    handler_class = HANDLERS.get(task_type)
    
    if not handler_class:
        raise ValueError(f"Unknown task type: {task_type}")
    
    handler = handler_class(payload)
    return handler.execute()


# === Main Entry Point ===

def main():
    """Точка входа для AI Runner."""
    parser = argparse.ArgumentParser(
        description="AI Runner - Изолированный subprocess для AI задач"
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Путь к входному JSON файлу"
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Путь к выходному JSON файлу"
    )
    
    args = parser.parse_args()
    
    logger.info(f"AI Runner started. Input: {args.input}, Output: {args.output}")
    
    # Проверяем входной файл
    if not args.input.exists():
        result = {
            "success": False,
            "error": f"Input file not found: {args.input}",
            "task_id": "unknown",
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        sys.exit(1)
    
    # Читаем входные данные
    try:
        with open(args.input, "r", encoding="utf-8") as f:
            input_data = json.load(f)
    except json.JSONDecodeError as e:
        result = {
            "success": False,
            "error": f"Invalid JSON in input file: {e}",
            "task_id": "unknown",
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        sys.exit(1)
    
    task_id = input_data.get("task_id", "unknown")
    task_type = input_data.get("task_type", "unknown")
    payload = input_data.get("payload", {})
    
    logger.info(f"Executing task {task_type}/{task_id}")
    
    # Выполняем задачу
    result = {
        "task_id": task_id,
        "success": False,
        "result": None,
        "error": None,
        "completed_at": datetime.utcnow().isoformat(),
    }
    
    try:
        result["result"] = execute_task(task_type, payload)
        result["success"] = True
        logger.info(f"Task {task_type}/{task_id} completed successfully")
        
    except Exception as e:
        result["error"] = str(e)
        result["traceback"] = traceback.format_exc()
        logger.error(f"Task {task_type}/{task_id} failed: {e}")
        # Записываем результат с ошибкой
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        sys.exit(1)
    
    # Записываем результат
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Result written to {args.output}")
    
    # Выход с кодом ошибки если задача неуспешна
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
