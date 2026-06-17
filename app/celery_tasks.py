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

from app.celery import celery_app, heartbeat_manager
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
        # output_bucket удалён - используется локальное хранилище
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
        # output_bucket удалён - используется локальное хранилище
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
    
    @celery_app.task(
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


# === Shorts Generation Task ===

@celery_app.task(
    bind=True,
    name="app.celery_tasks.generate_shorts_task",
    soft_time_limit=1800,
    max_retries=2,
    acks_late=True,
)
def generate_shorts_task(self, guide_uuid: str, tts_engine: str = "edge"):
    """
    Celery task для генерации shorts видео.
    
    Args:
        guide_uuid: UUID гайда
        tts_engine: "edge" или "chatterbox"
    
    Returns:
        Dict с результатом генерации
    """
    task_id = self.request.id or f"shorts_{uuid.uuid4().hex[:8]}"
    logger.info(f"Starting shorts generation task {task_id} for guide {guide_uuid} with {tts_engine}")
    
    try:
        # Регистрируем в heartbeat
        heartbeat_manager.register_job(task_id, f"celery:generate_shorts")
        
        # Импортируем здесь чтобы избежать циклических зависимостей
        from app.services.shorts_generator_sync import generate_shorts_sync
        
        # Вызываем синхронную версию генератора
        result = generate_shorts_sync(guide_uuid, tts_engine)
        
        # Удаляем из heartbeat
        heartbeat_manager.unregister_job(task_id)
        
        logger.info(f"Shorts generation completed: {result}")
        return result
        
    except Exception as e:
        heartbeat_manager.unregister_job(task_id)
        logger.error(f"Shorts generation failed: {e}", exc_info=True)
        raise self.retry(exc=e)


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


# === Video Generation Task (NEW) ===

@celery_app.task(
    bind=True,
    name="app.celery_tasks.generate_video_task",
    soft_time_limit=1800,
    max_retries=2,
    acks_late=True,
)
def generate_video_task(
    self,
    guide_id: int,
    tts_engine: str = "edge",
    tts_voice: str = "ru-RU-SvetlanaNeural",
    tts_speed: float = 1.0,
    tts_pitch: float = 0
):
    """
    Celery task для генерации видео с прогрессом.
    
    Args:
        guide_id: ID гайда
        tts_engine: "edge" или "chatterbox"
        tts_voice: Голос для TTS
        tts_speed: Скорость речи (0.5-2.0)
        tts_pitch: Тембр голоса (-20 до 20)
    
    Returns:
        Dict с результатом генерации
    """
    task_id = self.request.id or f"video_{uuid.uuid4().hex[:8]}"
    logger.info(f"Starting video generation task {task_id} for guide {guide_id}")
    
    try:
        # Регистрируем в heartbeat
        heartbeat_manager.register_job(task_id, f"celery:generate_video")
        
        # Обновляем прогресс
        self.update_state(
            state='PROGRESS',
            meta={'progress': 5, 'message': 'Загрузка данных гайда...'}
        )
        
        # Импортируем здесь чтобы избежать циклических зависимостей
        import asyncio
        from app.database import get_db_sync
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from app.models import Guide, GuideStatus
        
        # Получаем гайд
        db = next(get_db_sync())
        guide = db.execute(
            select(Guide)
            .options(selectinload(Guide.steps))
            .where(Guide.id == guide_id)
        ).scalar_one_or_none()
        
        if not guide:
            raise ValueError(f"Guide {guide_id} not found")
        
        steps = sorted(guide.steps, key=lambda s: s.step_number)
        total_steps = len(steps)
        
        self.update_state(
            state='PROGRESS',
            meta={'progress': 10, 'message': f'Найдено {total_steps} шагов'}
        )
        
        # Генерируем TTS для каждого шага
        from app.services.edge_tts_service import EdgeTTSService
        from app.services.chatterbox_service import get_chatterbox_service
        
        # Создаем TTS сервис с нужными параметрами
        if tts_engine == "edge":
            # Форматируем параметры для Edge TTS
            rate_str = f"{int((tts_speed - 1.0) * 100):+d}%"
            pitch_str = f"{int(tts_pitch):+d}Hz"
            tts_service = EdgeTTSService(voice=tts_voice, rate=rate_str, pitch=pitch_str)
        else:
            tts_service = get_chatterbox_service()
        
        audio_files = []
        for idx, step in enumerate(steps):
            progress = 10 + int((idx / total_steps) * 40)  # 10-50%
            self.update_state(
                state='PROGRESS',
                meta={
                    'progress': progress,
                    'message': f'Генерация TTS для шага {idx + 1}/{total_steps}'
                }
            )
            
            text = step.edited_text or step.normalized_text
            
            # Генерируем аудио (БЕЗ "Шаг N")
            # Используем синхронный метод для Celery
            if tts_engine == "edge":
                audio_path = tts_service.synthesize_sync(text=text)
            else:
                audio_path = tts_service.synthesize_sync(text=text)
            
            audio_files.append({
                "step_number": step.step_number,
                "audio_path": audio_path,
                "screenshot_path": f"/data/{step.screenshot_path}",
                "click_x": step.click_x,
                "click_y": step.click_y,
                "annotations": step.annotations or []
            })
        
        self.update_state(
            state='PROGRESS',
            meta={'progress': 50, 'message': 'Сборка видео...'}
        )
        
        # Генерируем видео
        from app.services.shorts_generator_sync import generate_video_from_steps
        
        result = generate_video_from_steps(
            steps=audio_files,
            guide_uuid=guide.uuid,
            progress_callback=lambda p, msg: self.update_state(
                state='PROGRESS',
                meta={'progress': 50 + int(p * 0.5), 'message': msg}
            )
        )
        
        if result["success"]:
            # Обновляем гайд
            from pathlib import Path
            video_path = Path(result["output_path"])
            relative_path = f"output/{video_path.name}"
            
            # Перемещаем файл
            output_dir = Path("/data/output")
            output_dir.mkdir(parents=True, exist_ok=True)
            final_path = output_dir / video_path.name
            
            import shutil
            shutil.move(str(video_path), str(final_path))
            
            # Обновляем БД
            guide.status = GuideStatus.COMPLETED
            guide.shorts_video_path = relative_path
            guide.shorts_duration_seconds = result.get("duration_seconds")
            guide.shorts_generated_at = datetime.utcnow()
            guide.updated_at = datetime.utcnow()
            db.commit()
            
            self.update_state(
                state='SUCCESS',
                meta={'progress': 100, 'message': 'Видео готово!'}
            )
            
            heartbeat_manager.unregister_job(task_id)
            
            return {
                "success": True,
                "video_path": relative_path,
                "duration_seconds": result.get("duration_seconds")
            }
        else:
            raise Exception(result.get("error", "Unknown error"))
        
    except Exception as e:
        heartbeat_manager.unregister_job(task_id)
        logger.error(f"Video generation failed: {e}", exc_info=True)
        
        # Обновляем статус гайда
        try:
            from app.database import get_db_sync
            from sqlalchemy import select
            from app.models import Guide, GuideStatus
            
            db = next(get_db_sync())
            guide = db.execute(select(Guide).where(Guide.id == guide_id)).scalar_one_or_none()
            if guide:
                guide.status = GuideStatus.FAILED
                guide.error_message = str(e)
                guide.updated_at = datetime.utcnow()
                db.commit()
        except:
            pass
        
        raise self.retry(exc=e)



@celery_app.task(name="app.celery_tasks.enhance_guide_with_ai_task", bind=True)
def enhance_guide_with_ai_task(self, guide_id: int) -> Dict[str, Any]:
    """
    Улучшение текста шагов гайда с помощью Vision AI.
    
    Для каждого шага:
    1. Читает скриншот
    2. Отправляет в Vision AI с координатами клика
    3. Получает улучшенный текст инструкции
    4. Обновляет normalized_text в БД
    
    Args:
        guide_id: ID гайда для обработки
        
    Returns:
        Результат обработки
    """
    import redis
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    logger.info(f"[AI Enhancement] Starting for guide {guide_id}")
    
    # Подключаемся к Redis для прогресса
    redis_client = redis.from_url(settings.redis_url)
    
    # Ключи для хранения прогресса
    progress_key = f"ai_enhancement:{guide_id}:progress"
    status_key = f"ai_enhancement:{guide_id}:status"
    message_key = f"ai_enhancement:{guide_id}:message"
    
    try:
        # Создаем синхронное подключение к БД
        engine = create_engine(settings.sync_database_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Получаем гайд и его шаги
        from app.models import Guide, GuideStep
        
        guide = session.query(Guide).filter(Guide.id == guide_id).first()
        if not guide:
            raise ValueError(f"Guide {guide_id} not found")
        
        steps = session.query(GuideStep).filter(
            GuideStep.guide_id == guide_id
        ).order_by(GuideStep.step_number).all()
        
        total_steps = len(steps)
        logger.info(f"[AI Enhancement] Found {total_steps} steps to process")
        
        # Устанавливаем начальный статус
        redis_client.set(status_key, "processing", ex=3600)
        redis_client.set(progress_key, f"0/{total_steps}", ex=3600)
        redis_client.set(message_key, "Начинаем обработку...", ex=3600)
        
        # Импортируем AI сервис
        from app.services.ai_service import ai_service

        succeeded = 0
        failed = 0
        last_error = None

        # Обрабатываем каждый шаг
        for i, step in enumerate(steps, 1):
            logger.info(f"[AI Enhancement] Processing step {i}/{total_steps} (ID: {step.id})")

            # Обновляем прогресс
            redis_client.set(progress_key, f"{i-1}/{total_steps}", ex=3600)
            redis_client.set(message_key, f"Анализируем шаг {i} из {total_steps}...", ex=3600)

            # Проверяем наличие скриншота
            if not step.screenshot_path:
                logger.warning(f"[AI Enhancement] Step {step.id} has no screenshot, skipping")
                failed += 1
                last_error = "no screenshot"
                continue

            # Полный путь к скриншоту
            screenshot_path = f"/data/{step.screenshot_path}"

            if not os.path.exists(screenshot_path):
                logger.warning(f"[AI Enhancement] Screenshot not found: {screenshot_path}")
                failed += 1
                last_error = "screenshot file missing"
                continue

            try:
                # Вызываем Vision AI. Текст элемента (raw_speech) — подсказка модели.
                result = ai_service.analyze_screenshot(
                    screenshot_path=screenshot_path,
                    click_x=step.click_x,
                    click_y=step.click_y,
                    viewport_width=step.screenshot_width,
                    viewport_height=step.screenshot_height,
                    element_hint=step.raw_speech,
                )

                # Обновляем текст шага
                if result and result.get('instruction'):
                    step.normalized_text = result['instruction']
                    session.commit()
                    succeeded += 1
                    logger.info(f"[AI Enhancement] Step {step.id} updated: {result['instruction'][:50]}...")
                else:
                    failed += 1
                    last_error = (result or {}).get('error') or "no instruction returned"
                    logger.warning(f"[AI Enhancement] Step {step.id} not updated: {last_error}")

            except Exception as e:
                logger.error(f"[AI Enhancement] Error processing step {step.id}: {e}")
                failed += 1
                last_error = str(e)
                # Продолжаем обработку остальных шагов
                continue

        # Финальный статус
        redis_client.set(progress_key, f"{total_steps}/{total_steps}", ex=3600)
        if succeeded == 0 and failed > 0:
            # Ни один шаг не улучшен — это ошибка конфигурации, а не успех
            redis_client.set(status_key, "error", ex=3600)
            redis_client.set(message_key, f"Не удалось улучшить ни одного шага. Причина: {last_error}", ex=3600)
        else:
            redis_client.set(status_key, "completed", ex=3600)
            done_msg = f"Готово: обновлено {succeeded} из {total_steps}"
            if failed:
                done_msg += f" (пропущено {failed}: {last_error})"
            redis_client.set(message_key, done_msg, ex=3600)
        
        session.close()
        
        logger.info(f"[AI Enhancement] Completed for guide {guide_id}")
        
        return {
            "success": succeeded > 0,
            "guide_id": guide_id,
            "total_steps": total_steps,
            "updated_steps": succeeded,
            "failed_steps": failed,
            "last_error": last_error,
            "message": "AI enhancement completed",
        }
        
    except Exception as e:
        logger.exception(f"[AI Enhancement] Failed for guide {guide_id}: {e}")
        
        # Устанавливаем статус ошибки
        redis_client.set(status_key, "error", ex=3600)
        redis_client.set(message_key, f"Ошибка: {str(e)}", ex=3600)
        
        return {
            "success": False,
            "guide_id": guide_id,
            "error": str(e),
        }
