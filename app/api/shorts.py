"""
API: Shorts - генерация Shorts видео.
POST /guides/{id}/shorts/generate - запустить генерацию
GET /guides/{id}/shorts/status - проверить статус
GET /guides/{id}/shorts/download - скачать результат
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

# Импортируем Celery задачу
try:
    from app.celery_tasks import generate_shorts_task
except ImportError as e:
    logger.warning(f"Failed to import Celery task: {e}")
    generate_shorts_task = None

router = APIRouter(tags=["Shorts"])


@router.post("/generate/{guide_id}")
async def generate_shorts(
    guide_id: int,
    body: Optional[dict] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Запустить генерацию Shorts из гайда (через Celery).
    
    Request body (optional):
    {
        "add_intro": true,
        "intro_text": "Как создать документ",
        "tts_engine": "edge"  // "edge" или "chatterbox"
    }
    
    Returns:
    {
        "success": True,
        "task_id": "celery-task-uuid",
        "guide_uuid": "guide-uuid",
        "status": "queued"
    }
    """
    body = body or {}
    # По умолчанию используем Edge TTS (легковесный, не требует много памяти)
    # Chatterbox требует ~3GB RAM и может убить worker
    tts_engine = body.get("tts_engine", "edge")
    
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
    
    # Запускаем Celery task
    try:
        if not generate_shorts_task:
            raise HTTPException(status_code=500, detail="Celery task not available")
        
        logger.info(f"Queuing Shorts generation for guide {guide.uuid} with {len(steps)} steps")
        
        # Запускаем задачу асинхронно
        task = generate_shorts_task.delay(guide.uuid, tts_engine)
        
        return {
            "success": True,
            "task_id": task.id,
            "guide_uuid": guide.uuid,
            "guide_id": guide_id,
            "status": "queued",
            "tts_engine": tts_engine,
            "steps_count": len(steps)
        }
        
    except Exception as e:
        logger.exception(f"Failed to queue Shorts generation: {e}")
        guide.status = GuideStatus.READY
        guide.error_message = str(e)
        guide.updated_at = datetime.utcnow()
        await db.commit()
        
        raise HTTPException(status_code=500, detail=f"Failed to queue task: {str(e)}")


@router.get("/status/{guide_id}")
async def get_shorts_status(
    guide_id: int,
    task_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Проверить статус генерации Shorts.
    
    Query params:
    - task_id: ID Celery задачи (опционально)
    
    Returns:
    {
        "guide_id": 1,
        "status": "generating",  // draft, ready, generating, completed, failed
        "task_status": "PENDING",  // PENDING, STARTED, SUCCESS, FAILURE (если task_id указан)
        "task_result": {...},  // результат задачи если завершена
        "shorts_path": "output/shorts_xxx.mp4",
        "duration_seconds": 15.5,
        "generated_at": "2024-01-01T00:00:00"
    }
    """
    result = await db.execute(
        select(Guide).where(Guide.id == guide_id)
    )
    guide = result.scalar_one_or_none()
    
    if not guide:
        raise HTTPException(status_code=404, detail="Guide not found")
    
    response = {
        "guide_id": guide_id,
        "guide_uuid": guide.uuid,
        "status": guide.status,
        "shorts_path": guide.shorts_video_path,
        "duration_seconds": guide.shorts_duration_seconds,
        "generated_at": guide.shorts_generated_at.isoformat() if guide.shorts_generated_at else None,
        "error_message": guide.error_message
    }
    
    # Если указан task_id, проверяем статус Celery задачи
    if task_id:
        try:
            from celery.result import AsyncResult
            
            task = AsyncResult(task_id)
            response["task_status"] = task.state
            response["task_id"] = task_id
            
            # Если задача завершена успешно, обновляем гайд
            if task.state == "SUCCESS" and task.result:
                task_result = task.result
                response["task_result"] = task_result
                
                # Обновляем гайд если ещё не обновлён
                if task_result.get("success") and guide.status == GuideStatus.GENERATING:
                    from pathlib import Path
                    
                    output_path = task_result.get("output_path")
                    if output_path:
                        video_path = Path(output_path)
                        relative_path = f"output/{video_path.name}"
                        
                        guide.status = GuideStatus.COMPLETED
                        guide.shorts_video_path = relative_path
                        guide.shorts_duration_seconds = task_result.get("duration_seconds", 0)
                        guide.shorts_generated_at = datetime.utcnow()
                        guide.updated_at = datetime.utcnow()
                        await db.commit()
                        
                        response["status"] = guide.status
                        response["shorts_path"] = relative_path
                        response["duration_seconds"] = guide.shorts_duration_seconds
                        response["generated_at"] = guide.shorts_generated_at.isoformat()
            
            # Если задача провалилась
            elif task.state == "FAILURE":
                if guide.status == GuideStatus.GENERATING:
                    guide.status = GuideStatus.FAILED
                    guide.error_message = str(task.result) if task.result else "Task failed"
                    guide.updated_at = datetime.utcnow()
                    await db.commit()
                    
                    response["status"] = guide.status
                    response["error_message"] = guide.error_message
                
        except Exception as e:
            logger.error(f"Failed to check task status: {e}")
            response["task_error"] = str(e)
    
    return response


@router.get("/download/{guide_id}")
async def download_shorts(
    guide_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Получить presigned URL для скачивания Shorts.
    """
    result = await db.execute(
        select(Guide).where(Guide.id == guide_id)
    )
    guide = result.scalar_one_or_none()
    
    if not guide:
        raise HTTPException(status_code=404, detail="Guide not found")
    
    if not guide.shorts_video_path:
        raise HTTPException(status_code=404, detail="Shorts not generated yet")
    
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
    
    text = step.edited_text or step.normalized_text or f"Шаг {step.step_number}"
    full_text = f"Шаг {step.step_number}. {text}"
    
    logger.info(f"Testing TTS for step {step_id}: {full_text[:50]}...")
    
    try:
        from app.services.edge_tts_service import get_edge_tts_service
        tts_service = get_edge_tts_service()
        
        # Генерируем аудио
        audio_path = await tts_service.synthesize(text=full_text)
        
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
