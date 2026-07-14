"""
Celery Tasks для AutoDoc AI System.

Фоновые задачи воркера: генерация видео из шагов (generate_video_task) и
AI-доработка гайдов (enhance_guide_with_ai_task). Тяжёлые операции выполняются
прямо в воркере; heartbeat в Redis отслеживает живые джобы, а beat-задачи
подчищают зависшие consumer'ы и осиротевшие heartbeat-ключи.
"""

import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict

from app.celery import celery_app, heartbeat_manager
from app.config import settings


logger = logging.getLogger(__name__)


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


# === Video Generation Task ===

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
        from app.services.silero_tts_service import get_silero_service, DEFAULT_SPEAKER

        # Создаем TTS сервис с нужными параметрами
        if tts_engine == "edge":
            # Форматируем параметры для Edge TTS
            rate_str = f"{int((tts_speed - 1.0) * 100):+d}%"
            pitch_str = f"{int(tts_pitch):+d}Hz"
            tts_service = EdgeTTSService(voice=tts_voice, rate=rate_str, pitch=pitch_str)
        elif tts_engine == "silero":
            # Для Silero tts_voice — это имя голоса (xenia/baya/eugene/...)
            speaker = tts_voice if tts_voice in ("aidar", "baya", "kseniya", "eugene", "xenia") else DEFAULT_SPEAKER
            tts_service = get_silero_service(speaker=speaker)
        elif tts_engine == "f5":
            # F5-TTS (GPU-микросервис): tts_voice — имя референса из /data/tts_refs
            from app.services.f5_tts_service import get_f5_service
            tts_service = get_f5_service(voice=tts_voice, speed=tts_speed)
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
def enhance_guide_with_ai_task(self, guide_id: int, mode: str = "regenerate") -> Dict[str, Any]:
    """
    Обработка текста шагов гайда с помощью AI. Два режима:

    - mode="regenerate": генерация текста С НУЛЯ по скриншоту (Vision AI).
      Для каждого шага читает скриншот, отправляет в Vision AI с координатами
      клика и записывает результат в normalized_text.

    - mode="improve": УЛУЧШЕНИЕ существующего текста. Берёт то, что написал
      пользователь (edited_text/normalized_text, либо raw_speech), как ОСНОВУ
      и только правит орфографию/формулировку. Пустой результат не пишется,
      чтобы не затереть работу пользователя.

    Args:
        guide_id: ID гайда для обработки
        mode: "regenerate" (с нуля по картинке) или "improve" (полировка текста)

    Returns:
        Результат обработки
    """
    mode = mode if mode in ("regenerate", "improve") else "regenerate"
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
    cancel_key = f"ai_enhancement:{guide_id}:cancel"

    # Свежий запуск — снимаем возможный флаг отмены от прошлой задачи
    redis_client.delete(cancel_key)

    engine = None
    session = None
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

        def _improve_step(step) -> dict:
            """Полирует существующий текст шага (без скриншота).

            Возвращает {'ok': bool, 'text': str, 'error': str}. Сам пишет
            результат в нужное поле шага, но commit оставляет вызывающему.
            """
            base_text = (step.edited_text or step.normalized_text or "").strip()
            if not base_text:
                base_text = (step.raw_speech or "").strip()
            if not base_text:
                return {"ok": False, "error": "no text to improve"}

            res = ai_service.improve_step_text(
                base_text=base_text,
                element_hint=step.raw_speech,
            )
            if res and res.get("text"):
                # Пишем в то же поле, что реально показывается пользователю
                # (edited_text имеет приоритет в final_text).
                if step.edited_text:
                    step.edited_text = res["text"]
                else:
                    step.normalized_text = res["text"]
                return {"ok": True, "text": res["text"]}
            return {"ok": False, "error": (res or {}).get("error") or "no text returned"}

        action_word = "Улучшаем" if mode == "improve" else "Анализируем"

        # Обрабатываем каждый шаг
        for i, step in enumerate(steps, 1):
            # Отмена пользователем — останавливаемся на границе шага.
            # (Зависший внутри шага вызов прерывает revoke(terminate=True) из API.)
            if redis_client.get(cancel_key):
                logger.info(f"[AI Enhancement] Cancelled by user at step {i}/{total_steps}")
                redis_client.set(status_key, "cancelled", ex=3600)
                redis_client.set(
                    message_key,
                    f"Отменено. Обновлено {succeeded} из {total_steps}.",
                    ex=3600,
                )
                redis_client.delete(cancel_key)
                session.close()
                return {
                    "success": False,
                    "guide_id": guide_id,
                    "total_steps": total_steps,
                    "updated_steps": succeeded,
                    "cancelled": True,
                    "message": "AI enhancement cancelled",
                }

            logger.info(f"[AI Enhancement] Processing step {i}/{total_steps} (ID: {step.id}, mode={mode})")

            # Обновляем прогресс
            redis_client.set(progress_key, f"{i-1}/{total_steps}", ex=3600)
            redis_client.set(message_key, f"{action_word} шаг {i} из {total_steps}...", ex=3600)

            try:
                if mode == "improve":
                    # Берём текст пользователя как ОСНОВУ и только полируем его.
                    r = _improve_step(step)
                    if r["ok"]:
                        session.commit()
                        succeeded += 1
                        logger.info(f"[AI Enhancement] Step {step.id} improved: {r['text'][:50]}...")
                    else:
                        failed += 1
                        last_error = r["error"]
                        logger.warning(f"[AI Enhancement] Step {step.id} not improved: {last_error}")
                    continue

                # mode == "regenerate": генерация по скриншоту (Vision AI).
                # Если скриншота нет (или файл потерян) — это не ошибка: откатываемся
                # на полировку существующего текста, чтобы шаг всё равно улучшился.
                screenshot_path = f"/data/{step.screenshot_path}" if step.screenshot_path else None

                if not screenshot_path or not os.path.exists(screenshot_path):
                    logger.info(
                        f"[AI Enhancement] Step {step.id} has no screenshot, "
                        f"falling back to text improvement"
                    )
                    r = _improve_step(step)
                    if r["ok"]:
                        session.commit()
                        succeeded += 1
                        logger.info(f"[AI Enhancement] Step {step.id} improved (no screenshot): {r['text'][:50]}...")
                    else:
                        failed += 1
                        last_error = r["error"]
                        logger.warning(f"[AI Enhancement] Step {step.id} not improved: {last_error}")
                    continue

                # Вызываем Vision AI. Текст элемента (raw_speech) — подсказка модели,
                # тип действия (click/select/drag/input) задаёт глагол инструкции.
                result = ai_service.analyze_screenshot(
                    screenshot_path=screenshot_path,
                    click_x=step.click_x,
                    click_y=step.click_y,
                    viewport_width=step.screenshot_width,
                    viewport_height=step.screenshot_height,
                    element_hint=step.raw_speech,
                    action=getattr(step, "action", None) or "click",
                )

                # Обновляем текст шага
                if result and result.get('instruction'):
                    step.normalized_text = result['instruction']
                    session.commit()
                    succeeded += 1
                    logger.info(f"[AI Enhancement] Step {step.id} updated: {result['instruction'][:50]}...")
                else:
                    # Vision не дал результат — пробуем хотя бы отполировать текст.
                    logger.warning(
                        f"[AI Enhancement] Step {step.id} vision returned nothing, "
                        f"falling back to text improvement"
                    )
                    r = _improve_step(step)
                    if r["ok"]:
                        session.commit()
                        succeeded += 1
                        logger.info(f"[AI Enhancement] Step {step.id} improved (vision fallback): {r['text'][:50]}...")
                    else:
                        failed += 1
                        last_error = (result or {}).get('error') or r["error"]
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
    finally:
        # Движок создаётся на каждый запуск задачи: без dispose() пул держал
        # соединения к postgres до конца жизни воркера (утечка соединений)
        if session is not None:
            session.close()
        if engine is not None:
            engine.dispose()
