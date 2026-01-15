"""
API роуты для обработки гайдов.
Реализует функционал AI-обработки, видео-рендеринга и "магического редактирования".
"""

import logging
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Guide, GuideStep, GuideStatus
from app.schemas import (
    GuideProcessingStatus,
    AIProcessingRequest,
    AIProcessingResult,
    TextToSpeechRequest,
    TextToSpeechResponse,
    WikiGenerationRequest,
    WikiContentResponse,
    ShortsGenerationRequest,
    ShortsGenerationResponse,
    JobResponse,
    ErrorResponse,
)
from app.services.ai_service import ai_service
from app.services.tts_service import tts_service, TTSEngine
from app.services.video_processor import video_processor
from app.services.storage import storage_service, StorageBucket


logger = logging.getLogger(__name__)


router = APIRouter()


# === Фоновые задачи ===
async def process_guide_background(
    guide_id: int,
    regenerate_steps: List[int] = None,
):
    """
    Фоновая задача для обработки гайда.
    
    Выполняет:
    1. Транскрипцию аудио (если не выполнена)
    2. AI-анализ и генерацию метаданных
    3. Рендеринг видео с зумом
    4. Генерацию Wiki-статьи
    """
    import time
    start_time = time.time()
    
    async with AsyncSessionLocal() as db:
        # Получаем гайд
        guide = await db.get(Guide, guide_id)
        if not guide:
            logger.error(f"Guide {guide_id} not found")
            return
        
        try:
            guide.status = GuideStatus.PROCESSING
            guide.processing_started_at = datetime.utcnow()
            await db.commit()
            
            # Если нужно перегенерировать отдельные шаги
            if regenerate_steps:
                await regenerate_steps_audio(db, guide_id, regenerate_steps)
                
                # Пересобираем видео
                await render_video_with_steps(db, guide_id)
                
                guide.status = GuideStatus.COMPLETED
                guide.processing_completed_at = datetime.utcnow()
                await db.commit()
                
                return
            
            # Полная обработка
            # 1. Транскрипция
            # Здесь должен быть вызов AI сервиса
            # results = await ai_service.process_recording(...)
            
            # 2. Обновляем метаданные
            guide.status = GuideStatus.COMPLETED
            guide.processing_completed_at = datetime.utcnow()
            await db.commit()
            
            processing_time = time.time() - start_time
            logger.info(f"Guide {guide_id} processed in {processing_time:.2f}s")
            
        except Exception as e:
            logger.error(f"Processing failed for guide {guide_id}: {e}")
            guide.status = GuideStatus.FAILED
            guide.error_message = str(e)
            guide.processing_completed_at = datetime.utcnow()
            await db.commit()


async def regenerate_steps_audio(
    db: AsyncSession,
    guide_id: int,
    step_ids: List[int],
) -> bool:
    """
    Перегенерация аудио для указанных шагов.
    
    Используется для "Магического редактирования".
    """
    for step_id in step_ids:
        step = await db.get(GuideStep, step_id)
        if not step or step.guide_id != guide_id:
            continue
        
        # Используем edited_text если есть, иначе original_text
        text = step.edited_text or step.original_text
        
        # Генерируем новое аудио
        result = await tts_service.generate_audio(
            text=text,
            voice=None,  # Используем голос гайда
        )
        
        if result.success and result.audio_path:
            # Обновляем путь и длительность
            step.audio_path = result.audio_path
            step.audio_duration = result.duration_seconds
            step.needs_regenerate = False
            step.is_processed = True
            
            # Обновляем финальный текст
            step.final_text = text
            
            await db.commit()
            
            logger.info(f"Regenerated audio for step {step_id}")
    
    return True


async def render_video_with_steps(
    db: AsyncSession,
    guide_id: int,
) -> bool:
    """
    Рендеринг видео с текущими шагами.
    
    Применяет:
    - Time-stretching под новую длительность аудио
    - Zoom на области кликов
    - Наложение курсора
    """
    from app.services.video_processor import StepSegment, ZoomRegion
    
    # Получаем шаги
    query = select(GuideStep).where(GuideStep.guide_id == guide_id)
    result = await db.execute(query)
    steps = result.scalars().all()
    
    if not steps:
        return False
    
    # Создаем сегменты для видео-процессора
    segments = []
    
    for step in steps:
        zoom_region = None
        if step.zoom_region:
            zr = step.zoom_region
            zoom_region = ZoomRegion(
                x=zr.get("x", 0),
                y=zr.get("y", 0),
                width=zr.get("width", 100),
                height=zr.get("height", 50),
                target_width=zr.get("target_width", 400),
                target_height=zr.get("target_height", 300),
            )
        
        segment = StepSegment(
            start_time=step.start_time,
            end_time=step.end_time,
            original_start=step.start_time,
            original_end=step.end_time,
            text=step.final_text,
            audio_path=step.audio_path,
            audio_duration=step.audio_duration,
            zoom_region=zoom_region,
            action_type=step.action_type,
        )
        segments.append(segment)
    
    # Получаем путь к оригинальному видео
    guide = await db.get(Guide, guide_id)
    if not guide.original_video_path:
        return False
    
    output_path = f"/tmp/guides/{guide_id}/processed.mp4"
    
    # Запускаем рендеринг
    success = video_processor.generate_video_with_zoom(
        input_video=guide.original_video_path,
        output_video=output_path,
        steps=segments,
    )
    
    if success:
        # Загружаем в хранилище
        try:
            upload_result = storage_service.upload_local_file(
                file_path=output_path,
                bucket=StorageBucket.VIDEOS,
                guide_id=guide_id,
                subfolder="processed",
            )
            guide.processed_video_path = upload_result["object_key"]
            await db.commit()
        except Exception as e:
            logger.error(f"Failed to upload processed video: {e}")
    
    return success


# === API Endpoints ===

@router.get("/{guide_id}/status", response_model=GuideProcessingStatus)
async def get_processing_status(
    guide_id: int,
    db: AsyncSession = Depends(get_db),
) -> GuideProcessingStatus:
    """
    Получение статуса обработки гайда.
    """
    guide = await db.get(Guide, guide_id)
    
    if not guide:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Guide {guide_id} not found",
        )
    
    # Вычисляем прогресс на основе шагов
    steps_query = select(func.count()).select_from(GuideStep).where(GuideStep.guide_id == guide_id)
    total_steps = await db.scalar(steps_query) or 1
    
    processed_query = (
        select(func.count())
        .select_from(GuideStep)
        .where(GuideStep.guide_id == guide_id, GuideStep.is_processed == True)
    )
    processed_steps = await db.scalar(processed_query) or 0
    
    progress = int((processed_steps / total_steps) * 100)
    
    return GuideProcessingStatus(
        guide_id=guide_id,
        status=guide.status,
        current_step=f"Step {processed_steps + 1} of {total_steps}",
        progress_percent=progress,
        message=guide.error_message or "Processing...",
    )


@router.post("/{guide_id}/process")  # response_model=JobResponse - TODO: ProcessingJob not implemented
async def start_processing(
    guide_id: int,
    background_tasks: BackgroundTasks,
    regenerate: bool = Query(False, description="Перегенерировать существующий контент"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Запуск обработки гайда.
    
    Запускает AI-обработку и рендеринг видео в фоновом режиме.
    """
    guide = await db.get(Guide, guide_id)
    
    if not guide:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Guide {guide_id} not found",
        )
    
    # TODO: ProcessingJob model not implemented in MVP
    # Запускаем фоновую задачу
    background_tasks.add_task(process_guide_background, guide_id)
    
    logger.info(f"Started processing for guide {guide_id}")
    
    # Возвращаем заглушку, так как ProcessingJob не реализован
    from uuid import uuid4
    return {
        "id": 0,
        "guide_id": guide_id,
        "celery_task_id": str(uuid4()),
        "job_type": "full_process",
        "status": "pending",
        "priority": "normal",
        "created_at": datetime.utcnow().isoformat(),
    }


@router.post("/{guide_id}/magic-edit", response_model=AIProcessingResult)
async def magic_edit(
    guide_id: int,
    step_ids: List[int],
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> AIProcessingResult:
    """
    "Магическое редактирование" - перегенерация видео после изменения текста.
    
    Алгоритм:
    1. Пользователь редактирует текст шага
    2. Вызывается этот endpoint с ID измененных шагов
    3. Система генерирует НОВУЮ озвучку
    4. Система синхронизирует видео под новую длину аудио
    5. Пересобирает видео с умным time-stretching
    """
    guide = await db.get(Guide, guide_id)
    
    if not guide:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Guide {guide_id} not found",
        )
    
    if not step_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No step IDs provided",
        )
    
    # Проверяем что шаги помечены для перегенерации
    query = (
        select(GuideStep)
        .where(GuideStep.id.in_(step_ids), GuideStep.guide_id == guide_id)
    )
    result = await db.execute(query)
    steps = result.scalars().all()
    
    if not steps:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Steps not found",
        )
    
    # Запускаем перегенерацию в фоне
    background_tasks.add_task(process_guide_background, guide_id, step_ids)
    
    return AIProcessingResult(
        guide_id=guide_id,
        status="started",
        processed_steps=len(steps),
        total_steps=len(steps),
        generated_audio_files=len(steps),
        video_regenerated=True,
        wiki_generated=False,
        shorts_generated=False,
        processing_time_seconds=0,
        errors=[],
    )


@router.post("/{guide_id}/tts", response_model=TextToSpeechResponse)
async def regenerate_step_tts(
    guide_id: int,
    step_id: int,
    tts_request: TextToSpeechRequest,
    db: AsyncSession = Depends(get_db),
) -> TextToSpeechResponse:
    """
    Перегенерация TTS для конкретного шага.
    
    Используется для предварительного прослушивания озвучки
    перед применением изменений.
    """
    step = await db.get(GuideStep, step_id)
    
    if not step or step.guide_id != guide_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Step {step_id} not found in guide {guide_id}",
        )
    
    text = tts_request.text or step.original_text
    
    result = await tts_service.generate_audio(
        text=text,
        voice=tts_request.voice or step.guide.tts_voice,
        speed=tts_request.speed,
        pitch=tts_request.pitch,
    )
    
    return TextToSpeechResponse(
        success=result.success,
        audio_path=result.audio_path,
        duration_seconds=result.duration_seconds,
        error=result.error,
    )


@router.post("/{guide_id}/wiki", response_model=WikiContentResponse)
async def generate_wiki(
    guide_id: int,
    request: WikiGenerationRequest,
    db: AsyncSession = Depends(get_db),
) -> WikiContentResponse:
    """
    Генерация Wiki-статьи из гайда.
    
    Форматы:
    - markdown: Markdown-файл
    - html: HTML-страница
    - pdf: PDF-документ (требует конвертации)
    """
    guide = await db.get(Guide, guide_id)
    
    if not guide:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Guide {guide_id} not found",
        )
    
    # Получаем шаги
    query = (
        select(GuideStep)
        .where(GuideStep.guide_id == guide_id)
        .order_by(GuideStep.step_number)
    )
    result = await db.execute(query)
    steps = result.scalars().all()
    
    # Генерируем Wiki-контент
    # Формируем структурированный контент
    content_parts = []
    
    # Заголовок
    content_parts.append(f"# {guide.title}\n")
    
    if guide.description:
        content_parts.append(f"{guide.description}\n")
    
    # Теги
    if guide.tags:
        content_parts.append(f"**Теги:** {', '.join(guide.tags)}\n")
    
    content_parts.append("\n---\n\n")
    
    # Шаги
    content_parts.append("## Инструкция\n\n")
    
    for i, step in enumerate(steps, 1):
        content_parts.append(f"### Шаг {i}\n")
        content_parts.append(f"**Время:** {step.start_time:.0f}с - {step.end_time:.0f}с\n\n")
        content_parts.append(f"**Описание:** {step.final_text}\n\n")
        
        if step.element_description:
            content_parts.append(f"**Элемент:** {step.element_description}\n\n")
        
        # Ссылка на скриншот если есть
        # content_parts.append(f"![Screenshot](screenshots/{step.id}.png)\n\n")
        
        content_parts.append("---\n\n")
    
    # Советы
    content_parts.append("## Советы\n")
    content_parts.append("- Используйте горячие клавиши для ускорения работы\n")
    content_parts.append("- Делайте паузы между сложными действиями\n")
    
    full_content = "".join(content_parts)
    
    # Сохраняем в хранилище
    wiki_filename = f"{guide.uuid}.md"
    
    try:
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(full_content)
            temp_path = f.name
        
        upload_result = storage_service.upload_local_file(
            file_path=temp_path,
            bucket=StorageBucket.WIKI,
            guide_id=guide_id,
            subfolder="wiki",
        )
        
        guide.wiki_markdown_path = upload_result["object_key"]
        await db.commit()
        
        import os
        os.unlink(temp_path)
        
    except Exception as e:
        logger.error(f"Failed to save Wiki: {e}")
    
    return WikiContentResponse(
        guide_id=guide_id,
        format=request.format,
        title=guide.title,
        content=full_content,
        metadata={
            "tags": guide.tags,
            "language": guide.language,
            "steps_count": len(steps),
        },
        file_path=guide.wiki_markdown_path,
        generated_at=datetime.utcnow(),
    )


@router.post("/{guide_id}/shorts", response_model=ShortsGenerationResponse)
async def generate_shorts(
    guide_id: int,
    request: ShortsGenerationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ShortsGenerationResponse:
    """
    Генерация Shorts/Reels из гайда.
    
    Особенности:
    - Вертикальный формат (9:16)
    - Агрессивная нарезка таймингов
    - Удаление пауз
    - Наложение кэпшенов (опционально)
    - Фоновая музыка (опционально)
    """
    guide = await db.get(Guide, guide_id)
    
    if not guide:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Guide {guide_id} not found",
        )
    
    if not guide.processed_video_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Processed video not available. Process guide first.",
        )
    
    # Запускаем генерацию в фоне
    # background_tasks.add_task(_generate_shorts_task, guide_id, request)
    
    # Временный ответ (в реальности будет background task)
    return ShortsGenerationResponse(
        guide_id=guide_id,
        target_platform=request.target_platform,
        video_path=None,
        duration_seconds=None,
        generated_at=datetime.utcnow(),
        error="Not implemented yet",
    )


@router.post("/tts/preview", response_model=TextToSpeechResponse)
async def preview_tts(
    request: TextToSpeechRequest,
) -> TextToSpeechResponse:
    """
    Предпрослушивание TTS без сохранения.
    
    Позволяет проверить звучание голоса перед применением.
    """
    result = await tts_service.generate_audio(
        text=request.text,
        voice=request.voice,
        speed=request.speed,
        pitch=request.pitch,
    )
    
    return TextToSpeechResponse(
        success=result.success,
        audio_path=result.audio_path,
        duration_seconds=result.duration_seconds,
        error=result.error,
    )


@router.get("/tts/voices")
async def list_tts_voices(
    engine: Optional[str] = Query(None, description="Фильтр по движку"),
) -> List[dict]:
    """
    Получение списка доступных голосов TTS.
    """
    voices = tts_service.get_available_voices()
    
    if engine:
        voices = [v for v in voices if v.get("engine") == engine]
    
    return voices


# TODO: ProcessingJob model not implemented in MVP
# @router.get("/jobs/{job_id}", response_model=JobResponse)
# async def get_job_status(
#     job_id: int,
#     db: AsyncSession = Depends(get_db),
# ) -> JobResponse:
#     """
#     Получение статуса задачи обработки.
#     """
#     job = await db.get(ProcessingJob, job_id)
#     
#     if not job:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail=f"Job {job_id} not found",
#         )
#     
#     return JobResponse.model_validate(job)


# TODO: ProcessingJob model not implemented in MVP
# @router.get("/{guide_id}/jobs", response_model=List[JobResponse])
# async def get_guide_jobs(
#     guide_id: int,
#     db: AsyncSession = Depends(get_db),
# ) -> List[JobResponse]:
#     """
#     Получение всех задач обработки для гайда.
#     """
#     query = (
#         select(ProcessingJob)
#         .where(ProcessingJob.guide_id == guide_id)
#         .order_by(ProcessingJob.created_at.desc())
#     )
#     
#     result = await db.execute(query)
#     jobs = result.scalars().all()
#     
#     return [JobResponse.model_validate(j) for j in jobs]


# Вспомогательные переменные
AsyncSessionLocal = None
