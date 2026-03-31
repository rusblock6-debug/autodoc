"""
API: Video - генерация видео-гайдов.
POST /guides/{id}/video/generate - запустить генерацию
GET /guides/{id}/video/status/{task_id} - проверить статус задачи
GET /guides/{id}/video/download - скачать результат
"""

import logging
from typing import Optional
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Guide, GuideStep, GuideStatus
from app.services.storage import storage_service
from app.services.shorts_generator import shorts_generator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Video"])


@router.post("/generate/{guide_id}")
async def generate_video(
    guide_id: int,
    body: Optional[dict] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Запустить генерацию видео из гайда.
    
    Request body:
    {
        "tts_engine": "edge" | "chatterbox",
        "tts_voice": "ru-RU-SvetlanaNeural",
        "tts_speed": 1.0,
        "tts_pitch": 0
    }
    
    Returns:
    {
        "success": True,
        "task_id": "uuid",
        "message": "Video generation started"
    }
    """
    body = body or {}
    
    # Получаем гайд
    result = await db.execute(
        select(Guide)
        .options(selectinload(Guide.steps))
        .where(Guide.id == guide_id)
    )
    guide = result.scalar_one_or_none()
    
    if not guide:
        raise HTTPException(status_code=404, detail="Guide not found")
    
    # Проверяем статус
    if guide.status == GuideStatus.DRAFT:
        raise HTTPException(
            status_code=400, 
            detail="Guide is in draft mode. Finalize steps first."
        )
    
    # Проверяем, что есть шаги
    steps = sorted(guide.steps, key=lambda s: s.step_number)
    
    if not steps:
        raise HTTPException(status_code=400, detail="No steps in guide")
    
    # Проверяем, что все шаги имеют скриншоты
    steps_without_screenshots = [s for s in steps if not s.screenshot_path]
    
    if steps_without_screenshots:
        raise HTTPException(
            status_code=400,
            detail=f"{len(steps_without_screenshots)} steps missing screenshots"
        )
    
    # Обновляем статус
    guide.status = GuideStatus.GENERATING
    guide.updated_at = datetime.utcnow()
    await db.commit()
    
    # Извлекаем настройки TTS
    tts_engine = body.get("tts_engine", "edge")
    tts_voice = body.get("tts_voice", "ru-RU-SvetlanaNeural")
    tts_speed = body.get("tts_speed", 1.0)
    tts_pitch = body.get("tts_pitch", 0)
    
    # Запускаем генерацию через Celery
    try:
        from app.celery_tasks import generate_video_task
        
        logger.info(f"Starting video generation for guide {guide.uuid} with {len(steps)} steps")
        
        task = generate_video_task.delay(
            guide_id=guide.id,
            tts_engine=tts_engine,
            tts_voice=tts_voice,
            tts_speed=tts_speed,
            tts_pitch=tts_pitch
        )
        
        logger.info(f"Task created: {task.id}")
        
        if not task.id:
            logger.error("Task ID is None!")
            raise HTTPException(status_code=500, detail="Failed to create task")
        
        return {
            "success": True,
            "task_id": task.id,
            "message": "Video generation started"
        }
        
        if result.success:
            # Сохраняем путь к видео (относительный путь от /data)
            from pathlib import Path
            video_path = Path(result.output_path)
            relative_path = f"output/{video_path.name}"
            
            # Перемещаем файл в постоянное хранилище
            output_dir = Path("/data/output")
            output_dir.mkdir(parents=True, exist_ok=True)
            final_path = output_dir / video_path.name
            
            try:
                import shutil
                shutil.move(str(video_path), str(final_path))
            except Exception as e:
                logger.error(f"Failed to move video file: {e}")
                # Если не удалось переместить, копируем
                shutil.copy2(str(video_path), str(final_path))
            
            # Обновляем гайд
            guide.status = GuideStatus.COMPLETED
            guide.video_path = relative_path
            guide.video_duration_seconds = result.duration_seconds
            guide.video_generated_at = datetime.utcnow()
            guide.updated_at = datetime.utcnow()
            await db.commit()
            
            return {
                "success": True,
                "guide_id": guide_id,
                "video_path": relative_path,
                "duration_seconds": result.duration_seconds,
                "segments_count": result.segments_count,
                "generated_at": guide.video_generated_at.isoformat()
            }
        else:
            guide.status = GuideStatus.READY
            guide.error_message = result.error
            guide.updated_at = datetime.utcnow()
            await db.commit()
            
            raise HTTPException(status_code=500, detail=result.error)
    
    except Exception as e:
        logger.exception(f"Video generation failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/status/{guide_id}/{task_id}")
async def get_video_status(
    guide_id: int,
    task_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Проверить статус генерации видео по task_id.
    
    Returns:
    {
        "task_id": "uuid",
        "task_status": "PENDING" | "STARTED" | "SUCCESS" | "FAILURE",
        "progress": 45,
        "current_step": "Генерация TTS для шага 3/10",
        "error_message": null
    }
    """
    from celery.result import AsyncResult
    from app.celery import celery_app
    
    result = AsyncResult(task_id, app=celery_app)
    
    response = {
        "task_id": task_id,
        "task_status": result.state,
        "progress": 0,
        "current_step": None,
        "error_message": None
    }
    
    if result.state == "PENDING":
        response["current_step"] = "Задача в очереди..."
    elif result.state == "STARTED":
        response["current_step"] = "Генерация началась..."
        response["progress"] = 5
    elif result.state == "PROGRESS":
        # Celery может передавать метаданные о прогрессе
        if result.info:
            response["progress"] = result.info.get("progress", 0)
            response["current_step"] = result.info.get("message", "Обработка...")
    elif result.state == "SUCCESS":
        response["progress"] = 100
        response["current_step"] = "Готово!"
    elif result.state == "FAILURE":
        response["error_message"] = str(result.info) if result.info else "Unknown error"
        response["current_step"] = "Ошибка генерации"
    
    return response


@router.get("/status/{guide_id}")
async def get_guide_video_status(
    guide_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Проверить статус видео гайда.
    """
    result = await db.execute(
        select(Guide).where(Guide.id == guide_id)
    )
    guide = result.scalar_one_or_none()
    
    if not guide:
        raise HTTPException(status_code=404, detail="Guide not found")
    
    return {
        "guide_id": guide_id,
        "status": guide.status,
        "video_path": guide.shorts_video_path,
        "duration_seconds": guide.shorts_duration_seconds,
        "generated_at": guide.shorts_generated_at.isoformat() if guide.shorts_generated_at else None,
        "error_message": guide.error_message
    }


@router.get("/download/{guide_id}")
async def download_video(
    guide_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Скачать сгенерированное видео.
    """
    result = await db.execute(
        select(Guide).where(Guide.id == guide_id)
    )
    guide = result.scalar_one_or_none()
    
    if not guide:
        raise HTTPException(status_code=404, detail="Guide not found")
    
    if not guide.shorts_video_path:
        raise HTTPException(status_code=404, detail="Video not generated yet")
    
    if guide.status != GuideStatus.COMPLETED:
        raise HTTPException(status_code=400, detail=f"Guide status: {guide.status}")
    
    # Возвращаем путь к локальному файлу
    from pathlib import Path
    video_path = Path("/data") / guide.shorts_video_path
    
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    
    from fastapi.responses import FileResponse
    return FileResponse(
        str(video_path),
        media_type="video/mp4",
        filename=f"{guide.title}.mp4"
    )


@router.get("/test-tts/{step_id}")
async def test_tts_for_step(
    step_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    ТЕСТ: Генерация TTS для одного шага.
    Возвращает аудио файл.
    """
    from sqlalchemy import select
    from app.models import GuideStep
    
    result = await db.execute(
        select(GuideStep).where(GuideStep.id == step_id)
    )
    step = result.scalar_one_or_none()
    
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    
    text = step.edited_text or step.normalized_text
    
    logger.info(f"Testing TTS for step {step_id}: {text[:50]}...")
    
    try:
        from app.services.edge_tts_service import get_edge_tts_service
        tts_service = get_edge_tts_service()
        
        # Генерируем аудио (БЕЗ "Шаг N")
        audio_path = await tts_service.synthesize(text=text)
        
        # Возвращаем файл
        from fastapi.responses import FileResponse
        return FileResponse(
            audio_path,
            media_type="audio/mpeg",
            filename=f"step_{step_id}.mp3"
        )
        
    except Exception as e:
        logger.exception(f"TTS test failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/preview/{guide_id}")
async def preview_shorts_segments(
    guide_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Получить превью сегментов Shorts (для UI).
    
    Returns:
    - Список сегментов с информацией о скриншоте, тексте, длительности
    """
    result = await db.execute(
        select(Guide)
        .options(selectinload(Guide.steps))
        .where(Guide.id == guide_id)
    )
    guide = result.scalar_one_or_none()
    
    if not guide:
        raise HTTPException(status_code=404, detail="Guide not found")
    
    steps = sorted(guide.steps, key=lambda s: s.step_number)
    
    segments = []
    for step in steps:
        # Получаем URL скриншота
        screenshot_url = None
        if step.screenshot_path:
            # Используем endpoint для скриншотов
            screenshot_url = f"/api/v1/guides/screenshots{step.screenshot_path}"
        
        # Предварительная длительность TTS
        estimated_duration = _estimate_tts_duration(step.final_text)
        
        segments.append({
            "step_number": step.step_number,
            "screenshot_url": screenshot_url,
            "marker_x": step.click_x,
            "marker_y": step.click_y,
            "text": step.final_text,
            "estimated_duration": estimated_duration,
            "tts_audio_url": step.tts_audio_path  # Если уже сгенерирован
        })
    
    return {
        "guide_id": guide_id,
        "segments": segments,
        "total_estimated_duration": sum(s["estimated_duration"] for s in segments)
    }


async def _get_screenshot_url(key: str) -> str:
    """Получить полный URL скриншота.
    Теперь работает с локальными файлами."""
    if not key:
        return ""
    
    # Если это уже полный URL
    if key.startswith("http"):
        return key
    
    # Для локальных файлов возвращаем URL к API
    # Формат: "/screenshots/{uuid}/filename.png"
    # Используем endpoint /guides/screenshots/{path}
    return f"/api/v1/guides/screenshots{key}"


def _estimate_tts_duration(text: str, words_per_second: float = 3.0) -> float:
    """Оценить длительность TTS в секундах."""
    word_count = len(text.split())
    return max(2.0, word_count / words_per_second)
