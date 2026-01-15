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

router = APIRouter(prefix="/api/v1/shorts", tags=["Shorts"])


@router.post("/generate/{guide_id}")
async def generate_shorts(
    guide_id: int,
    body: Optional[dict] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Запустить генерацию Shorts из гайда.
    
    Request body (optional):
    {
        "tts_voice": "ru-RU-SvetlanaNeural",
        "add_intro": true,
        "intro_text": "Как создать документ"
    }
    
    Returns:
    {
        "success": True,
        "task_id": "uuid",
        "status": "queued",
        "estimated_time": 120
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
    
    # Запускаем генерацию
    try:
        result = await shorts_generator.generate_from_steps(
            steps=[
                {
                    "step_number": s.step_number,
                    "screenshot_path": await _get_screenshot_url(s.screenshot_path),
                    "click_x": s.click_x,
                    "click_y": s.click_y,
                    "normalized_text": s.normalized_text,
                    "edited_text": s.edited_text,
                }
                for s in steps
            ],
            guide_uuid=guide.uuid,
            tts_voice=body.get("tts_voice", guide.tts_voice)
        )
        
        if result.success:
            # Загружаем результат в MinIO
            output_key = f"guides/{guide.uuid}/shorts.mp4"
            await storage_service.upload_file_path(
                result.output_path,
                output_key
            )
            
            # Обновляем гайд
            guide.status = GuideStatus.COMPLETED
            guide.shorts_video_path = output_key
            guide.shorts_duration_seconds = result.duration_seconds
            guide.shorts_generated_at = datetime.utcnow()
            guide.updated_at = datetime.utcnow()
            await db.commit()
            
            # Чистим локальный файл
            try:
                from pathlib import Path
                Path(result.output_path).unlink(missing_ok=True)
            except Exception:
                pass
            
            return {
                "success": True,
                "guide_id": guide_id,
                "shorts_path": output_key,
                "duration_seconds": result.duration_seconds,
                "segments_count": result.segments_count,
                "generated_at": guide.shorts_generated_at.isoformat()
            }
        else:
            guide.status = GuideStatus.READY
            guide.error_message = result.error
            guide.updated_at = datetime.utcnow()
            await db.commit()
            
            raise HTTPException(status_code=500, detail=result.error)
    
    except Exception as e:
        logger.exception(f"Shorts generation failed: {e}")
        guide.status = GuideStatus.FAILED
        guide.error_message = str(e)
        guide.updated_at = datetime.utcnow()
        await db.commit()
        
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@router.get("/status/{guide_id}")
async def get_shorts_status(
    guide_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Проверить статус генерации Shorts.
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
        "shorts_path": guide.shorts_video_path,
        "duration_seconds": guide.shorts_duration_seconds,
        "generated_at": guide.shorts_generated_at.isoformat() if guide.shorts_generated_at else None,
        "error_message": guide.error_message
    }


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
    
    # Генерируем presigned URL
    download_url = await storage_service.generate_download_url(
        guide.shorts_video_path,
        expiry_seconds=3600  # 1 час
    )
    
    return {
        "download_url": download_url,
        "expires_in": 3600,
        "filename": f"{guide.title}.mp4"
    }


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
            screenshot_url = await storage_service.generate_download_url(
                step.screenshot_path,
                expiry_seconds=3600
            )
        
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
    """Получить полный URL скриншота."""
    if not key:
        return ""
    
    # Если это уже полный URL
    if key.startswith("http"):
        return key
    
    # Генерируем presigned URL
    return await storage_service.generate_download_url(key, expiry_seconds=3600)


def _estimate_tts_duration(text: str, words_per_second: float = 3.0) -> float:
    """Оценить длительность TTS в секундах."""
    word_count = len(text.split())
    return max(2.0, word_count / words_per_second)
