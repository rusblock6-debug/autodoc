"""
API: Sessions - загрузка и обработка записей.
POST /sessions/upload - загрузить видео, аудио, лог кликов
GET /sessions/{id} - получить статус и результаты
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc

from app.database import get_db
from app.models import RecordingSession, SessionStatus, Guide, GuideStep, GuideStatus

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Sessions"])


@router.post("/upload")
async def upload_session(
    video: Optional[UploadFile] = File(None),
    audio: Optional[UploadFile] = File(None),
    clicks_log: Optional[UploadFile] = File(None),
    screenshots: List[UploadFile] = File(default=[]),
    title: Optional[str] = Form(None),
    duration_seconds: Optional[float] = Form(None),
    click_count: Optional[int] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Загрузить сессию записи.
    
    Принимает (все опционально):
    - video: видеофайл записи экрана
    - audio: аудиофайл с микрофона
    - clicks_log: JSON лог кликов
    - screenshots: массив скриншотов (PNG)
    - title: название
    - duration_seconds: длительность записи
    - click_count: количество кликов
    
    Returns:
    - session_id: ID сессии для отслеживания
    """
    # Генерируем UUID
    session_uuid = str(uuid4())
    
    try:
        logger.info(f"Creating session {session_uuid}, screenshots: {len(screenshots)}")
        
        # Парсим лог кликов если есть
        clicks_data = []
        if clicks_log:
            try:
                content = await clicks_log.read()
                clicks_json = json.loads(content.decode('utf-8'))
                clicks_data = clicks_json.get('clicks', [])
                
                # Если duration не передан, берём из лога
                if not duration_seconds and 'duration_seconds' in clicks_json:
                    duration_seconds = clicks_json['duration_seconds']
                    
                # Если click_count не передан, считаем
                if not click_count:
                    click_count = len(clicks_data)
                    
                logger.info(f"Parsed {len(clicks_data)} clicks from log")
            except Exception as e:
                logger.warning(f"Could not parse clicks log: {e}")
        
        # Сохраняем файлы если есть
        video_path = None
        audio_path = None
        clicks_path = None
        screenshot_paths = []
        
        try:
            from app.services.storage import storage_service, StorageBucket
            
            if video and video.filename:
                result = storage_service.upload_file(
                    video.file,
                    video.filename,
                    StorageBucket.UPLOADS,
                    content_type=video.content_type or "video/webm",
                    subfolder=session_uuid
                )
                video_path = result.get('object_key')
                logger.info(f"Video uploaded: {video_path}")
            
            if audio and audio.filename:
                result = storage_service.upload_file(
                    audio.file,
                    audio.filename,
                    StorageBucket.UPLOADS,
                    content_type=audio.content_type or "audio/wav",
                    subfolder=session_uuid
                )
                audio_path = result.get('object_key')
                logger.info(f"Audio uploaded: {audio_path}")
            
            # Сохраняем скриншоты
            for i, screenshot in enumerate(screenshots):
                if screenshot and screenshot.filename:
                    result = storage_service.upload_file(
                        screenshot.file,
                        f"screenshot_{i}.png",
                        StorageBucket.SCREENSHOTS,
                        content_type="image/png",
                        subfolder=session_uuid
                    )
                    screenshot_paths.append(result.get('object_key'))
                    logger.info(f"Screenshot {i} uploaded: {result.get('object_key')}")
                
        except Exception as e:
            logger.warning(f"Storage upload failed (continuing without files): {e}")
        
        # Создаём запись в БД
        session = RecordingSession(
            uuid=session_uuid,
            title=title or "Новый гайд",
            status=SessionStatus.UPLOADED,
            video_path=video_path or "",
            audio_path=audio_path or "",
            clicks_log_path=clicks_path or "",
            duration_seconds=duration_seconds,
            click_count=click_count or len(clicks_data),
            created_at=datetime.utcnow()
        )
        
        db.add(session)
        await db.commit()
        await db.refresh(session)
        
        logger.info(f"Session {session_uuid} created with {session.click_count} clicks")
        
        # Создаём гайд сразу (без AI обработки для MVP)
        guide = Guide(
            uuid=str(uuid4()),
            session_id=session.id,
            title=session.title,
            language="ru",
            status=GuideStatus.DRAFT,
            created_at=datetime.utcnow()
        )
        db.add(guide)
        await db.commit()
        await db.refresh(guide)
        
        # Создаём шаги из кликов
        for i, click in enumerate(clicks_data):
            # Получаем путь к скриншоту если есть
            screenshot_path = screenshot_paths[i] if i < len(screenshot_paths) else ""
            
            step = GuideStep(
                guide_id=guide.id,
                step_number=i + 1,
                click_timestamp=click.get('timestamp', 0),
                click_x=click.get('x', 0),
                click_y=click.get('y', 0),
                screenshot_path=screenshot_path,
                screenshot_width=click.get('viewport_width', 1920),
                screenshot_height=click.get('viewport_height', 1080),
                raw_speech=click.get('element_text') or click.get('text') or "",
                normalized_text=f"Шаг {i+1}: Нажмите на элемент {click.get('element') or click.get('tagName') or 'unknown'}",
                created_at=datetime.utcnow()
            )
            db.add(step)
        
        await db.commit()
        
        # Обновляем статус сессии
        session.status = SessionStatus.COMPLETED
        session.processing_completed_at = datetime.utcnow()
        await db.commit()
        
        logger.info(f"Session {session_uuid} completed with guide {guide.uuid}")
        
        return {
            "success": True,
            "session_id": session_uuid,
            "guide_id": guide.uuid,
            "status": "completed",
            "click_count": session.click_count,
            "message": "Сессия создана успешно"
        }
        
    except Exception as e:
        logger.exception(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("")
async def list_sessions(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить список всех сессий.
    """
    from sqlalchemy.orm import selectinload
    
    query = select(RecordingSession).options(selectinload(RecordingSession.guide)).order_by(desc(RecordingSession.created_at))
    
    if status:
        query = query.where(RecordingSession.status == status)
    
    # Пагинация
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    
    result = await db.execute(query)
    sessions = result.scalars().all()
    
    return {
        "items": [
            {
                "uuid": s.uuid,
                "title": s.title,
                "status": s.status.value if hasattr(s.status, 'value') else s.status,
                "duration_seconds": s.duration_seconds,
                "click_count": s.click_count,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "guide_id": s.guide.uuid if s.guide else None
            }
            for s in sessions
        ],
        "page": page,
        "page_size": page_size
    }


@router.get("/{session_id}")
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """
    Получить информацию о сессии.
    """
    from sqlalchemy.orm import selectinload
    
    result = await db.execute(
        select(RecordingSession)
        .options(selectinload(RecordingSession.guide))
        .where(RecordingSession.uuid == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "uuid": session.uuid,
        "title": session.title,
        "status": session.status.value if hasattr(session.status, 'value') else session.status,
        "duration_seconds": session.duration_seconds,
        "click_count": session.click_count,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "processing_started_at": session.processing_started_at.isoformat() if session.processing_started_at else None,
        "processing_completed_at": session.processing_completed_at.isoformat() if session.processing_completed_at else None,
        "error_message": session.error_message,
        "guide_id": session.guide.uuid if session.guide else None
    }


@router.get("/{session_id}/transcription")
async def get_transcription(session_id: str, db: AsyncSession = Depends(get_db)):
    """
    Получить результат ASR (текст + таймкоды).
    """
    result = await db.execute(
        select(RecordingSession).where(RecordingSession.uuid == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session.status != SessionStatus.COMPLETED:
        return {"status": session.status, "message": "Transcription not ready"}
    
    return {
        "text": session.asr_text,
        "segments": session.asr_segments,
        "duration": session.duration_seconds
    }


@router.delete("/{session_id}")
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """
    Удалить сессию и связанные файлы.
    """
    result = await db.execute(
        select(RecordingSession).where(RecordingSession.uuid == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Удаляем файлы из MinIO если есть
    try:
        from app.services.storage import storage_service, StorageBucket
        
        if session.video_path:
            storage_service.delete_file(session.video_path, StorageBucket.UPLOADS)
        if session.audio_path:
            storage_service.delete_file(session.audio_path, StorageBucket.UPLOADS)
        if session.clicks_log_path:
            storage_service.delete_file(session.clicks_log_path, StorageBucket.UPLOADS)
    except Exception as e:
        logger.warning(f"Could not delete files: {e}")
    
    # Удаляем из БД (cascade удалит связанный гайд и шаги)
    await db.delete(session)
    await db.commit()
    
    return {"success": True, "message": "Session deleted"}
