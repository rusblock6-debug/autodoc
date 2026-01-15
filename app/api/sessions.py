"""
API: Sessions - загрузка и обработка записей.
POST /sessions/upload - загрузить видео, аудио, лог кликов
GET /sessions/{id} - получить статус и результаты
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.database import get_db
from app.models import RecordingSession, SessionStatus, Guide, GuideStep, GuideStatus
from app.services.storage import storage_service
from app.services.ai_service import WhisperASR, LLMWrapper
from app.services.step_detector import StepDetector, parse_clicks_from_log, parse_asr_segments
from app.services.screenshot_service import ScreenshotExtractor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sessions", tags=["Sessions"])


@router.post("/upload")
async def upload_session(
    video: UploadFile = File(...),
    audio: UploadFile = File(...),
    clicks_log: UploadFile = File(...),
    title: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Загрузить сессию записи.
    
    Принимает:
    - video: видеофайл записи экрана
    - audio: аудиофайл с микрофона
    - clicks_log: JSON лог кликов
    - title: название (опционально)
    
    Returns:
    - session_id: ID сессии для отслеживания
    """
    # Генерируем UUID
    session_uuid = str(uuid4())
    
    try:
        # 1. Сохраняем файлы в MinIO
        logger.info(f"Uploading files for session {session_uuid}")
        
        video_path = await storage_service.upload_file(
            video, 
            f"sessions/{session_uuid}/video.webm"
        )
        
        audio_path = await storage_service.upload_file(
            audio,
            f"sessions/{session_uuid}/audio.wav"
        )
        
        clicks_path = await storage_service.upload_file(
            clicks_log,
            f"sessions/{session_uuid}/clicks.json"
        )
        
        # 2. Создаём запись в БД
        session = RecordingSession(
            uuid=session_uuid,
            title=title or "Без названия",
            status=SessionStatus.UPLOADED,
            video_path=video_path,
            audio_path=audio_path,
            clicks_log_path=clicks_path,
            created_at=datetime.utcnow()
        )
        
        db.add(session)
        await db.commit()
        await db.refresh(session)
        
        logger.info(f"Session {session_uuid} created, starting async processing")
        
        # 3. Запускаем асинхронную обработку
        # Celery task или background task
        await process_session_background(session.id, db)
        
        return {
            "success": True,
            "session_id": session_uuid,
            "status": "uploaded",
            "message": "Сессия загружена, обработка началась"
        }
        
    except Exception as e:
        logger.exception(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


async def process_session_background(session_id: int, db: AsyncSession):
    """
    Фоновая обработка сессии.
    Запускается после загрузки.
    """
    # Получаем сессию
    result = await db.execute(
        select(RecordingSession).where(RecordingSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        return
    
    # Обновляем статус
    session.status = SessionStatus.PROCESSING
    session.processing_started_at = datetime.utcnow()
    await db.commit()
    
    try:
        # 1. Скачиваем лог кликов
        clicks_content = await storage_service.download_file(session.clicks_log_path)
        clicks_log = clicks_content if isinstance(clicks_content, dict) else {}
        
        clicks = parse_clicks_from_log(clicks_log)
        session.click_count = len(clicks)
        
        # 2. Запускаем ASR (Whisper)
        logger.info(f"Starting ASR for session {session.uuid}")
        
        asr = WhisperASR()
        
        # Скачиваем аудио локально для Whisper
        local_audio = await storage_service.download_to_temp(session.audio_path)
        
        transcription = asr.transcribe(str(local_audio), language="ru")
        
        # Сохраняем результаты ASR
        session.asr_text = transcription.text
        session.asr_segments = [s.to_dict() for s in transcription.segments]
        session.duration_seconds = transcription.duration
        
        # Чистим память
        asr.close()
        local_audio.unlink(missing_ok=True)
        
        # 3. Парсим сегменты речи
        speech_segments = parse_asr_segments({"segments": session.asr_segments})
        
        # 4. Детектируем шаги
        detector = StepDetector()
        step_candidates = detector.detect_steps(clicks, speech_segments)
        
        # 5. Извлекаем скриншоты
        local_video = await storage_service.download_to_temp(session.video_path)
        extractor = ScreenshotExtractor()
        
        timestamps = [c.click_timestamp for c in step_candidates]
        screenshots = extractor.extract_at_timestamps(
            str(local_video), 
            timestamps,
            prefix=f"step_{session.uuid}"
        )
        
        # 6. Нормализуем тексты через LLM
        llm = LLMWrapper()
        
        guide = Guide(
            uuid=str(uuid4()),
            session_id=session.id,
            title=session.title or "Без названия",
            language="ru",
            status=SessionStatus.DRAFT,
            created_at=datetime.utcnow()
        )
        db.add(guide)
        
        # Создаём шаги
        for i, candidate in enumerate(step_candidates):
            # Находим соответствующий скриншот
            screenshot = screenshots[i] if i < len(screenshots) else None
            
            if screenshot and screenshot.success:
                # Загружаем скриншот в MinIO
                screenshot_key = f"guides/{guide.uuid}/screenshots/step_{i+1}.png"
                await storage_service.upload_file_path(
                    screenshot.output_path,
                    screenshot_key
                )
                
                # Нормализуем текст через LLM
                normalized = await llm.normalize_instruction(
                    candidate.raw_speech_text,
                    language="ru"
                )
                
                step = GuideStep(
                    guide_id=guide.id,
                    step_number=i + 1,
                    click_timestamp=candidate.click.click_timestamp,
                    click_x=candidate.click.x,
                    click_y=candidate.click.y,
                    screenshot_path=screenshot_key,
                    screenshot_width=screenshot.width,
                    screenshot_height=screenshot.height,
                    raw_speech=candidate.raw_speech_text,
                    raw_speech_start=candidate.speech.start if candidate.speech else None,
                    raw_speech_end=candidate.speech.end if candidate.speech else None,
                    normalized_text=normalized,
                    created_at=datetime.utcnow()
                )
                db.add(step)
            else:
                # Скриншот не удался, создаём шаг без скриншота
                normalized = await llm.normalize_instruction(
                    candidate.raw_speech_text,
                    language="ru"
                )
                
                step = GuideStep(
                    guide_id=guide.id,
                    step_number=i + 1,
                    click_timestamp=candidate.click.click_timestamp,
                    click_x=candidate.click.x,
                    click_y=candidate.click.y,
                    screenshot_path="",
                    screenshot_width=0,
                    screenshot_height=0,
                    raw_speech=candidate.raw_speech_text,
                    normalized_text=normalized,
                    created_at=datetime.utcnow()
                )
                db.add(step)
        
        # 7. Обновляем сессию
        session.status = SessionStatus.COMPLETED
        session.processing_completed_at = datetime.utcnow()
        
        # Связываем гайд с сессией
        session.guide = guide
        
        await db.commit()
        
        # Чистим временные файлы
        local_video.unlink(missing_ok=True)
        
        logger.info(f"Session {session.uuid} processing completed")
        
    except Exception as e:
        logger.exception(f"Session processing failed: {e}")
        session.status = SessionStatus.FAILED
        session.error_message = str(e)
        await db.commit()


@router.get("/{session_id}")
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """
    Получить информацию о сессии.
    """
    result = await db.execute(
        select(RecordingSession).where(RecordingSession.uuid == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "uuid": session.uuid,
        "title": session.title,
        "status": session.status,
        "duration_seconds": session.duration_seconds,
        "click_count": session.click_count,
        "created_at": session.created_at,
        "processing_started_at": session.processing_started_at,
        "processing_completed_at": session.processing_completed_at,
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
    
    # Удаляем файлы из MinIO
    if session.video_path:
        await storage_service.delete_file(session.video_path)
    if session.audio_path:
        await storage_service.delete_file(session.audio_path)
    if session.clicks_log_path:
        await storage_service.delete_file(session.clicks_log_path)
    
    # Удаляем из БД (cascade удалит связанный гайд и шаги)
    await db.delete(session)
    await db.commit()
    
    return {"success": True, "message": "Session deleted"}
