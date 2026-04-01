"""
Celery Tasks для AutoDoc AI System.
Фоновые задачи для генерации видео.
"""

import logging
import uuid
from datetime import datetime
from pathlib import Path

from app.celery import celery_app, heartbeat_manager
from app.models import Guide, GuideStatus


logger = logging.getLogger(__name__)


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
        from app.database import get_db_sync
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        
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
