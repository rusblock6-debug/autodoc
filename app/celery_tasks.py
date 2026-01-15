"""
Celery Tasks для AutoDoc AI System.
Фоновые задачи с Subprocess Isolation паттерном.

Ключевые принципы:
- Тяжелые AI/Video операции выполняются в изолированных subprocess
- Родительский процесс не блокируется (asyncio-friendly)
- Краш subprocess не ломает воркер
- Heartbeat мониторинг через Redis
"""

import json
import logging
import os
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Добавляем корень проекта в пути
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.celery import heartbeat_manager
from app.config import settings


logger = logging.getLogger(__name__)


# === Subprocess Runner ===

def run_ai_subprocess(
    task_type: str,
    task_id: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Запуск AI задачи в изолированном subprocess.
    
    Args:
        task_type: Тип задачи (video_processing, ai_transcription, tts_generation, etc.)
        task_id: Уникальный ID задачи
        payload: Данные задачи
        
    Returns:
        Результат выполнения
    """
    # Формируем команду
    script_path = settings.get_subprocess_script_path()
    if not script_path.exists():
        raise FileNotFoundError(f"AI Runner script not found: {script_path}")
    
    # Создаем временный файл с входными данными
    input_file = settings.WORKER_TEMP_DIR / f"input_{task_id}.json"
    output_file = settings.WORKER_TEMP_DIR / f"output_{task_id}.json"
    
    # Записываем входные данные
    input_data = {
        "task_type": task_type,
        "task_id": task_id,
        "payload": payload,
        "created_at": datetime.utcnow().isoformat(),
    }
    
    with open(input_file, "w", encoding="utf-8") as f:
        json.dump(input_data, f, ensure_ascii=False, indent=2)
    
    # Формируем команду
    cmd = [
        sys.executable,  # Текущий Python интерпретатор
        str(script_path),
        "--input", str(input_file),
        "--output", str(output_file),
    ]
    
    logger.info(f"Starting subprocess for task {task_type}/{task_id}")
    
    # Запускаем subprocess
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(PROJECT_ROOT),
        )
        
        # Регистрируем в heartbeat
        heartbeat_manager.register_job(task_id, f"subprocess:{task_type}")
        
        # Ждем завершения
        stdout, stderr = process.communicate(timeout=settings.AI_PROCESS_TIMEOUT)
        
        # Удаляем из heartbeat
        heartbeat_manager.unregister_job(task_id)
        
        # Читаем результат
        if output_file.exists():
            with open(output_file, "r", encoding="utf-8") as f:
                result = json.load(f)
            
            # Чистим временные файлы
            input_file.unlink(missing_ok=True)
            output_file.unlink(missing_ok=True)
            
            return result
        else:
            raise RuntimeError(f"Subprocess completed but no output file: {output_file}")
    
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        heartbeat_manager.unregister_job(task_id)
        raise TimeoutError(f"AI subprocess timeout after {settings.AI_PROCESS_TIMEOUT}s")
    
    except Exception as e:
        heartbeat_manager.unregister_job(task_id)
        # Чистим временные файлы
        input_file.unlink(missing_ok=True)
        output_file.unlink(missing_ok=True)
        raise


# === Task Definitions (Lightweight Wrappers) ===

def process_video(
    guide_id: int,
    video_key: str,
    steps_data: List[Dict[str, Any]],
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Обработка видео с применением зума и синхронизации.
    
    Args:
        guide_id: ID гайда
        video_key: S3 ключ видеофайла
        steps_data: Данные о шагах
        options: Дополнительные опции
        
    Returns:
        Результат обработки
    """
    task_id = f"video_{guide_id}_{uuid.uuid4().hex[:8]}"
    
    payload = {
        "guide_id": guide_id,
        "video_key": video_key,
        "steps": steps_data,
        "options": options or {},
        "output_bucket": settings.MINIO_BUCKET_VIDEOS,
    }
    
    return run_ai_subprocess("video_processing", task_id, payload)


def generate_shorts(
    guide_id: int,
    video_key: str,
    target_platform: str = "tiktok",
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Генерация Shorts/Reels из обработанного видео.
    """
    task_id = f"shorts_{guide_id}_{uuid.uuid4().hex[:8]}"
    
    payload = {
        "guide_id": guide_id,
        "video_key": video_key,
        "target_platform": target_platform,
        "options": options or {},
        "output_bucket": settings.MINIO_BUCKET_VIDEOS,
    }
    
    return run_ai_subprocess("shorts_generation", task_id, payload)


def ai_transcription(
    guide_id: int,
    audio_key: str,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Транскрипция аудио в текст с использованием Whisper.
    """
    task_id = f"transcribe_{guide_id}_{uuid.uuid4().hex[:8]}"
    
    payload = {
        "guide_id": guide_id,
        "audio_key": audio_key,
        "language": language or "ru",
    }
    
    return run_ai_subprocess("ai_transcription", task_id, payload)


def ai_process_recording(
    guide_id: int,
    audio_key: str,
    click_events: List[Dict[str, Any]],
    language: str = "ru",
) -> Dict[str, Any]:
    """
    Полная AI-обработка записи: транскрипция, анализ, генерация метаданных.
    """
    task_id = f"ai_process_{guide_id}_{uuid.uuid4().hex[:8]}"
    
    payload = {
        "guide_id": guide_id,
        "audio_key": audio_key,
        "click_events": click_events,
        "language": language,
    }
    
    return run_ai_subprocess("ai_processing", task_id, payload)


def generate_tts(
    guide_id: int,
    step_id: int,
    text: str,
    voice: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Генерация TTS для конкретного шага.
    """
    task_id = f"tts_{guide_id}_{step_id}_{uuid.uuid4().hex[:8]}"
    
    payload = {
        "guide_id": guide_id,
        "step_id": step_id,
        "text": text,
        "voice": voice or settings.EDGE_TTS_VOICE,
    }
    
    return run_ai_subprocess("tts_generation", task_id, payload)


def smart_align(
    guide_id: int,
    voice_segments: List[Dict[str, Any]],
    screen_actions: List[Dict[str, Any]],
    language: str = "ru",
) -> Dict[str, Any]:
    """
    Интеллектуальная синхронизация речи и действий.
    """
    task_id = f"align_{guide_id}_{uuid.uuid4().hex[:8]}"
    
    payload = {
        "guide_id": guide_id,
        "voice_segments": voice_segments,
        "screen_actions": screen_actions,
        "language": language,
    }
    
    return run_ai_subprocess("smart_alignment", task_id, payload)


def generate_wiki(
    guide_id: int,
    format: str = "markdown",
    include_screenshots: bool = True,
) -> Dict[str, Any]:
    """
    Генерация Wiki-статьи из гайда.
    """
    task_id = f"wiki_{guide_id}_{uuid.uuid4().hex[:8]}"
    
    payload = {
        "guide_id": guide_id,
        "format": format,
        "include_screenshots": include_screenshots,
    }
    
    return run_ai_subprocess("wiki_generation", task_id, payload)


# === Celery Task Wrappers (For backwards compatibility) ===

def create_celery_task_wrapper(task_func, task_name: str):
    """
    Создание Celery task wrapper для обратной совместимости.
    """
    from celery import shared_task
    
    @shared_task(
        bind=True,
        name=f"app.celery_tasks.{task_name}",
        soft_time_limit=3600,
        max_retries=2,
        acks_late=True,
    )
    def wrapper(self, *args, **kwargs):
        task_id = self.request.id or f"celery_{uuid.uuid4().hex[:8]}"
        logger.info(f"Starting Celery task: {task_name} (id={task_id})")
        
        try:
            # Регистрируем в heartbeat
            heartbeat_manager.register_job(task_id, f"celery:{task_name}")
            
            # Выполняем задачу
            result = task_func(*args, **kwargs)
            
            # Удаляем из heartbeat
            heartbeat_manager.unregister_job(task_id)
            
            return result
            
        except Exception as e:
            heartbeat_manager.unregister_job(task_id)
            logger.error(f"Task {task_name} failed: {e}")
            raise self.retry(exc=e)
    
    return wrapper


# === Garbage Collection Tasks ===

def check_stale_tasks() -> Dict[str, Any]:
    """
    Проверка зависших задач (без heartbeat).
    
    Returns:
        Статистика GC
    """
    from app.celery import get_redis_client, STREAM_NAME, CONSUMER_GROUP
    from app.config import settings
    
    redis_client = get_redis_client()
    stale_count = 0
    reclaimed_count = 0
    
    try:
        # Получаем информацию о потоке
        stream_info = redis_client.xinfo_stream(STREAM_NAME)
        if not stream_info:
            return {"stale_count": 0, "reclaimed_count": 0}
        
        # Проверяем задачи в consumer group
        consumers = redis_client.xinfo_consumers(STREAM_NAME, CONSUMER_GROUP)
        
        current_time = datetime.utcnow()
        
        for consumer in consumers:
            consumer_name = consumer.get("name", "")
            last_seen = consumer.get("pending", 0)
            
            if last_seen == 0:
                continue
            
            # Проверяем idle время
            idle_time = 0
            if isinstance(last_seen, int):
                # Redis streams используют milliseconds
                idle_time = last_seen / 1000
            
            if idle_time > settings.STALE_TASK_THRESHOLD:
                stale_count += 1
                
                # CLAIM задачи
                try:
                    # Получаем pending сообщения
                    pending = redis_client.xpending_range(
                        STREAM_NAME,
                        CONSUMER_GROUP,
                        consumer_name,
                        consumer_name,
                        count=100,
                    )
                    
                    for msg in pending:
                        msg_id = msg.get("message_id")
                        if msg_id:
                            # Переназначаем сообщение
                            redis_client.xclaim(
                                STREAM_NAME,
                                CONSUMER_GROUP,
                                msg_id,
                                min_idle_time=int(settings.STALE_TASK_THRESHOLD * 1000),
                                message=None,  # Переоткрываем для других
                            )
                            reclaimed_count += 1
                            
                except Exception as e:
                    logger.warning(f"Failed to claim stale tasks: {e}")
        
        logger.info(f"GC: Found {stale_count} stale consumers, reclaimed {reclaimed_count} tasks")
        
    except Exception as e:
        logger.error(f"Stale task check failed: {e}")
    
    return {
        "stale_count": stale_count,
        "reclaimed_count": reclaimed_count,
        "timestamp": current_time.isoformat(),
    }


def cleanup_heartbeats() -> Dict[str, Any]:
    """
    Очистка устаревших heartbeat ключей.
    
    Returns:
        Количество удаленных ключей
    """
    from app.celery import get_redis_client
    from app.config import settings
    
    redis_client = get_redis_client()
    deleted_count = 0
    
    try:
        # Ищем все heartbeat ключи
        pattern = f"{settings.HEARTBEAT_PREFIX}*"
        cursor = 0
        
        while True:
            cursor, keys = redis_client.scan(
                cursor=cursor,
                match=pattern,
                count=100,
            )
            
            for key in keys:
                # Проверяем TTL
                ttl = redis_client.ttl(key)
                if ttl == -1:  # Ключ без TTL
                    redis_client.delete(key)
                    deleted_count += 1
            
            if cursor == 0:
                break
        
        logger.info(f"Cleaned up {deleted_count} orphaned heartbeat keys")
        
    except Exception as e:
        logger.error(f"Heartbeat cleanup failed: {e}")
    
    return {
        "deleted_count": deleted_count,
        "timestamp": datetime.utcnow().isoformat(),
    }


# === Cleanup Tasks ===

def cleanup_temp_files(max_age_hours: int = 24) -> Dict[str, Any]:
    """
    Очистка временных файлов.
    """
    from pathlib import Path
    from datetime import datetime, timedelta
    import shutil
    
    temp_dir = settings.WORKER_TEMP_DIR
    
    if not temp_dir.exists():
        return {"deleted_files": 0, "cutoff_time": None}
    
    cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
    deleted_count = 0
    
    for item in temp_dir.iterdir():
        try:
            mtime = datetime.fromtimestamp(item.stat().st_mtime)
            
            if mtime < cutoff_time:
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
                deleted_count += 1
                
        except Exception:
            pass
    
    logger.info(f"Cleaned up {deleted_count} temporary files")
    
    return {
        "deleted_files": deleted_count,
        "cutoff_time": cutoff_time.isoformat(),
    }
