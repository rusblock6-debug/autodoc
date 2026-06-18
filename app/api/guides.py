"""
API роуты для управления гайдами.
Реализует CRUD операции и расширенный функционал гайдов.
"""

import copy
import logging
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status, Response, Header
from fastapi.responses import FileResponse
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Guide, GuideStep, GuideStatus
from app.schemas import (
    GuideCreate,
    GuideUpdate,
    GuideListResponse,
    GuideDetailResponse,
    GuideStepResponseSimple,
    GuideStepUpdate,
    ScreenshotResponse,
    PaginatedResponse,
    ErrorResponse,
)
from app.services.storage import storage_service, StorageType


logger = logging.getLogger(__name__)


router = APIRouter()


@router.get("", response_model=PaginatedResponse)
async def list_guides(
    page: int = Query(1, ge=1, description="Номер страницы"),
    page_size: int = Query(20, ge=1, le=100, description="Размер страницы"),
    status_filter: Optional[str] = Query(None, description="Фильтр по статусу"),
    content_type: Optional[str] = Query(None, description="Фильтр по типу контента"),
    search: Optional[str] = Query(None, description="Поиск по названию"),
    user_id: Optional[int] = Query(None, description="Фильтр по пользователю"),
    owner_token: Optional[str] = Header(None, alias="X-Owner-Token"),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse:
    """
    Получение списка гайдов с пагинацией и фильтрацией.

    Приватность: черновики (status=draft) видны только своему владельцу
    (по анонимному owner_token из заголовка X-Owner-Token). Готовые гайды
    видны всем — это общий каталог.
    """
    # Базовый запрос
    query = select(Guide)

    # Черновики приватны: показываем чужие/анонимные черновики только владельцу.
    if owner_token:
        query = query.where(
            or_(Guide.status != GuideStatus.DRAFT, Guide.owner_token == owner_token)
        )
    else:
        # Токена нет — никаких черновиков, только общий каталог.
        query = query.where(Guide.status != GuideStatus.DRAFT)

    # Применяем фильтры
    if status_filter:
        try:
            query = query.where(Guide.status == GuideStatus(status_filter))
        except ValueError:
            pass
    
    # TODO: content_type filtering not implemented in MVP
    # if content_type:
    #     try:
    #         query = query.where(Guide.content_type == ContentType(content_type))
    #     except ValueError:
    #         pass
    
    if search:
        search_term = f"%{search}%"
        query = query.where(Guide.title.ilike(search_term))
    
    if user_id:
        query = query.where(Guide.user_id == user_id)
    
    # Получаем общее количество
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0
    
    # Пагинация
    offset = (page - 1) * page_size
    # Подгружаем шаги, чтобы отдать превью (первый скриншот) и счётчик шагов
    query = (
        query.options(selectinload(Guide.steps))
        .offset(offset)
        .limit(page_size)
        .order_by(Guide.created_at.desc())
    )

    # Выполняем запрос
    result = await db.execute(query)
    guides = result.scalars().all()

    # Формируем ответ
    items = []
    for g in guides:
        item = GuideListResponse.model_validate(g)
        steps = g.steps or []
        item.step_count = len(steps)
        # Первый шаг со скриншотом → превью карточки
        item.thumbnail = next(
            (s.screenshot_path for s in steps if s.screenshot_path), None
        )
        items.append(item)
    total_pages = (total + page_size - 1) // page_size
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1,
    )


@router.get("/screenshots/{screenshot_path:path}")
async def get_screenshot(screenshot_path: str):
    """
    Отдача скриншота по пути вида {session_uuid}/{filename}.
    Путь может прийти с префиксом screenshots/ или без него.
    """
    from pathlib import Path

    # Нормализуем: убираем ведущий слэш и дублирующий префикс screenshots/
    rel = screenshot_path.lstrip("/")
    if rel.startswith("screenshots/"):
        rel = rel[len("screenshots/"):]

    base = Path("/data/screenshots").resolve()
    file_path = (base / rel).resolve()

    # Защита от path traversal: итоговый путь обязан лежать внутри base.
    try:
        file_path.relative_to(base)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid screenshot path")

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Screenshot not found")

    return FileResponse(
        str(file_path),
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=31536000",
        }
    )


@router.get("/{guide_id}", response_model=GuideDetailResponse)
async def get_guide(
    guide_id: int,
    db: AsyncSession = Depends(get_db),
) -> GuideDetailResponse:
    """
    Получение детальной информации о гайде.
    """
    query = (
        select(Guide)
        .where(Guide.id == guide_id)
        .options(
            selectinload(Guide.steps),
        )
    )
    
    result = await db.execute(query)
    guide = result.scalar_one_or_none()
    
    if not guide:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Guide with id {guide_id} not found",
        )
    
    return GuideDetailResponse.model_validate(guide)


@router.get("/uuid/{guide_uuid}", response_model=GuideDetailResponse)
async def get_guide_by_uuid(
    guide_uuid: str,
    db: AsyncSession = Depends(get_db),
) -> GuideDetailResponse:
    """
    Получение гайда по UUID (публичный доступ).
    """
    query = (
        select(Guide)
        .where(Guide.uuid == guide_uuid)
        .options(
            selectinload(Guide.steps),
        )
    )
    
    result = await db.execute(query)
    guide = result.scalar_one_or_none()
    
    if not guide:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Guide with uuid {guide_uuid} not found",
        )
    
    return GuideDetailResponse.model_validate(guide)


@router.post("", response_model=GuideDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_guide(
    guide_data: GuideCreate,
    owner_token: Optional[str] = Header(None, alias="X-Owner-Token"),
    db: AsyncSession = Depends(get_db),
) -> GuideDetailResponse:
    """
    Создание нового гайда.
    """
    guide = Guide(
        uuid=str(uuid4()),
        owner_token=owner_token,
        title=guide_data.title,
        language=guide_data.language,
        status=GuideStatus.DRAFT,
    )
    
    db.add(guide)
    await db.commit()
    await db.refresh(guide)
    
    logger.info(f"Created new guide: {guide.id} - {guide.title}")

    return GuideDetailResponse.model_validate(guide)


@router.post("/{guide_id}/duplicate", response_model=GuideDetailResponse, status_code=status.HTTP_201_CREATED)
async def duplicate_guide(
    guide_id: int,
    owner_token: Optional[str] = Header(None, alias="X-Owner-Token"),
    db: AsyncSession = Depends(get_db),
) -> GuideDetailResponse:
    """
    Дублирование гайда вместе со всеми шагами.

    Скриншоты переиспользуются (тот же screenshot_path) — файлы общие и не
    копируются: удаление гайда не трогает файлы на диске, поэтому удаление копии
    не затронет оригинал. TTS-аудио не копируется (переозвучивается по требованию).
    """
    query = (
        select(Guide)
        .where(Guide.id == guide_id)
        .options(selectinload(Guide.steps))
    )
    result = await db.execute(query)
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Guide with id {guide_id} not found",
        )

    # title в модели — String(500); не даём превысить лимит после добавления суффикса.
    suffix = " (копия)"
    new_title = (source.title or "")[: 500 - len(suffix)] + suffix

    new_guide = Guide(
        uuid=str(uuid4()),
        owner_token=owner_token,
        title=new_title,
        language=source.language,
        tts_voice=source.tts_voice,
        status=GuideStatus.DRAFT,
    )
    db.add(new_guide)
    await db.flush()  # получаем new_guide.id для шагов

    for step in source.steps:
        db.add(GuideStep(
            guide_id=new_guide.id,
            step_number=step.step_number,
            click_timestamp=step.click_timestamp,
            click_x=step.click_x,
            click_y=step.click_y,
            screenshot_path=step.screenshot_path,
            screenshot_width=step.screenshot_width,
            screenshot_height=step.screenshot_height,
            annotations=copy.deepcopy(step.annotations) if step.annotations else [],
            raw_speech=step.raw_speech,
            raw_speech_start=step.raw_speech_start,
            raw_speech_end=step.raw_speech_end,
            normalized_text=step.normalized_text,
            edited_text=step.edited_text,
        ))

    await db.commit()

    # Перечитываем с шагами для корректного ответа.
    result = await db.execute(
        select(Guide).where(Guide.id == new_guide.id).options(selectinload(Guide.steps))
    )
    new_guide = result.scalar_one()

    logger.info(f"Duplicated guide {guide_id} -> {new_guide.id} ({len(source.steps)} steps)")

    return GuideDetailResponse.model_validate(new_guide)


@router.patch("/{guide_id}", response_model=GuideDetailResponse)
async def update_guide(
    guide_id: int,
    guide_update: GuideUpdate,
    db: AsyncSession = Depends(get_db),
) -> GuideDetailResponse:
    """
    Обновление информации о гайде.
    """
    query = select(Guide).where(Guide.id == guide_id)
    result = await db.execute(query)
    guide = result.scalar_one_or_none()
    
    if not guide:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Guide with id {guide_id} not found",
        )
    
    # Обновляем только измененные поля
    update_data = guide_update.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        # Конвертируем status из строки в enum
        if field == "status" and isinstance(value, str):
            value = GuideStatus(value)
        setattr(guide, field, value)
    
    await db.commit()
    await db.refresh(guide)
    
    logger.info(f"Updated guide: {guide.id}")
    
    # Загружаем шаги отдельно для ответа
    steps_query = (
        select(GuideStep)
        .where(GuideStep.guide_id == guide.id)
        .order_by(GuideStep.step_number)
    )
    steps_result = await db.execute(steps_query)
    steps = steps_result.scalars().all()
    
    # Создаем ответ вручную
    response_data = {
        "id": guide.id,
        "uuid": guide.uuid,
        "title": guide.title,
        "status": guide.status.value if hasattr(guide.status, 'value') else str(guide.status),
        "language": guide.language,
        # "tts_voice": guide.tts_voice,  # Удалено - Chatterbox не требует выбора голоса
        "shorts_video_path": guide.shorts_video_path,
        "shorts_duration_seconds": guide.shorts_duration_seconds,
        "created_at": guide.created_at,
        "updated_at": guide.updated_at,
        "shorts_generated_at": guide.shorts_generated_at,
        "error_message": guide.error_message,
        "steps": [
            {
                "id": step.id,
                "guide_id": step.guide_id,
                "step_number": step.step_number,
                "click_timestamp": step.click_timestamp,
                "click_x": step.click_x,
                "click_y": step.click_y,
                "screenshot_path": step.screenshot_path,
                "screenshot_width": step.screenshot_width,
                "screenshot_height": step.screenshot_height,
                "raw_speech": step.raw_speech,
                "normalized_text": step.normalized_text,
                "edited_text": step.edited_text,
                "created_at": step.created_at,
                "updated_at": step.updated_at,
            }
            for step in steps
        ]
    }
    
    return response_data


@router.delete("/{guide_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_guide(
    guide_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Удаление гайда.
    """
    query = select(Guide).where(Guide.id == guide_id)
    result = await db.execute(query)
    guide = result.scalar_one_or_none()
    
    if not guide:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Guide with id {guide_id} not found",
        )
    
    await db.delete(guide)
    await db.commit()
    
    logger.info(f"Deleted guide: {guide_id}")


# === Шаги гайда ===

@router.get("/{guide_id}/steps", response_model=List[GuideStepResponseSimple])
async def get_guide_steps(
    guide_id: int,
    db: AsyncSession = Depends(get_db),
) -> List[GuideStepResponseSimple]:
    """
    Получение всех шагов гайда.
    """
    query = (
        select(GuideStep)
        .where(GuideStep.guide_id == guide_id)
        .order_by(GuideStep.step_number)
    )
    
    result = await db.execute(query)
    steps = result.scalars().all()
    
    return [GuideStepResponseSimple.model_validate(s) for s in steps]


@router.get("/{guide_id}/steps/{step_id}", response_model=GuideStepResponseSimple)
async def get_guide_step(
    guide_id: int,
    step_id: int,
    db: AsyncSession = Depends(get_db),
) -> GuideStepResponseSimple:
    """
    Получение конкретного шага гайда.
    """
    query = (
        select(GuideStep)
        .where(GuideStep.id == step_id, GuideStep.guide_id == guide_id)
    )
    
    result = await db.execute(query)
    step = result.scalar_one_or_none()
    
    if not step:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Step {step_id} not found in guide {guide_id}",
        )
    
    return GuideStepResponseSimple.model_validate(step)


@router.patch("/{guide_id}/steps/{step_id}", response_model=GuideStepResponseSimple)
async def update_guide_step(
    guide_id: int,
    step_id: int,
    step_update: GuideStepUpdate,
    db: AsyncSession = Depends(get_db),
) -> GuideStepResponseSimple:
    """
    Обновление шага гайда.
    
    Важно: При изменении edited_text устанавливается флаг needs_regenerate,
    что запускает перегенерацию видео и озвучки.
    """
    query = (
        select(GuideStep)
        .where(GuideStep.id == step_id, GuideStep.guide_id == guide_id)
    )
    
    result = await db.execute(query)
    step = result.scalar_one_or_none()
    
    if not step:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Step {step_id} not found in guide {guide_id}",
        )
    
    # Обновляем поля
    update_data = step_update.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(step, field, value)
    
    # Если изменился edited_text - помечаем на перегенерацию
    if step_update.edited_text is not None:
        step.needs_regenerate = True
        step.edited_text = step_update.edited_text
        step.final_text = step_update.edited_text
    
    await db.commit()
    await db.refresh(step)
    
    logger.info(f"Updated step {step_id} in guide {guide_id}")
    
    return GuideStepResponseSimple.model_validate(step)


# === Скриншоты ===

# TODO: GuideScreenshot model not implemented in MVP - screenshots are in GuideStep
# @router.get("/{guide_id}/screenshots", response_model=List[ScreenshotResponse])
# async def get_guide_screenshots(
#     guide_id: int,
#     db: AsyncSession = Depends(get_db),
# ) -> List[ScreenshotResponse]:
#     """
#     Получение скриншотов гайда.
#     """
#     query = (
#         select(GuideScreenshot)
#         .where(GuideScreenshot.guide_id == guide_id)
#         .order_by(GuideScreenshot.video_timestamp)
#     )
#     
#     result = await db.execute(query)
#     screenshots = result.scalars().all()
#     
#     return [ScreenshotResponse.model_validate(s) for s in screenshots]


# TODO: GuideScreenshot model not implemented in MVP
# @router.get("/{guide_id}/screenshots/{screenshot_id}", response_model=ScreenshotResponse)
# async def get_screenshot(...):
#     ...


@router.post("/{guide_id}/screenshots", response_model=ScreenshotResponse, status_code=status.HTTP_201_CREATED)
async def add_screenshot(
    guide_id: int,
    file_path: str,
    video_timestamp: float,
    screenshot_type: str = "step_screenshot",
    annotations: Optional[List[dict]] = None,
    db: AsyncSession = Depends(get_db),
) -> ScreenshotResponse:
    """
    Добавление скриншота к гайду.
    """
    # Проверяем существование гайда
    guide = await db.get(Guide, guide_id)
    if not guide:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Guide {guide_id} not found",
        )
    
    # Загружаем скриншот в хранилище
    try:
        upload_result = storage_service.upload_local_file(
            file_path=file_path,
            bucket=StorageType.SCREENSHOTS,
            guide_id=guide_id,
            subfolder="screenshots",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to upload screenshot: {e}",
        )
    
    # TODO: GuideScreenshot model not implemented in MVP - use GuideStep instead
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Screenshot management not implemented in MVP. Use GuideStep.screenshot_path instead."
    )
    # # Создаем запись в БД
    # screenshot = GuideScreenshot(
    #     guide_id=guide_id,
    #     file_path=upload_result["url"],
    #     minio_key=upload_result["object_key"],
    #     width=1920,  # Можно получить из изображения
    #     height=1080,
    #     video_timestamp=video_timestamp,
    #     screenshot_type=screenshot_type,
    #     annotations=annotations,
    # )
    # 
    # db.add(screenshot)
    return ScreenshotResponse.model_validate(screenshot)


# === Публичный доступ ===

@router.post("/{guide_id}/share")
async def generate_share_link(
    guide_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Генерация ссылки для публичного доступа к гайду.
    """
    query = select(Guide).where(Guide.id == guide_id)
    result = await db.execute(query)
    guide = result.scalar_one_or_none()
    
    if not guide:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Guide {guide_id} not found",
        )
    
    # Генерируем share_token если нет
    if not guide.share_token:
        guide.share_token = str(uuid4())[:12]
        guide.is_public = True
        await db.commit()
    
    share_url = f"/shared/{guide.uuid}/{guide.share_token}"
    
    return {
        "share_url": share_url,
        "share_token": guide.share_token,
        "is_public": guide.is_public,
    }


@router.get("/shared/{uuid}/{token}")
async def access_shared_guide(
    uuid: str,
    token: str,
    db: AsyncSession = Depends(get_db),
) -> GuideDetailResponse:
    """
    Доступ к гайду по ссылке шеринга.
    """
    query = (
        select(Guide)
        .where(Guide.uuid == uuid, Guide.share_token == token)
        .options(
            selectinload(Guide.steps),
            selectinload(Guide.screenshots),
        )
    )
    
    result = await db.execute(query)
    guide = result.scalar_one_or_none()
    
    if not guide:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guide not found or link expired",
        )
    
    if not guide.is_public:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guide is not public",
        )
    
    # Увеличиваем счетчик просмотров
    guide.view_count += 1
    await db.commit()
    
    return GuideDetailResponse.model_validate(guide)


# === Статистика ===

@router.get("/stats/summary")
async def get_guides_stats(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Получение статистики по гайдам.
    """
    # Общее количество
    total_query = select(func.count()).select_from(Guide)
    total = await db.scalar(total_query) or 0
    
    # По статусам
    status_query = (
        select(Guide.status, func.count())
        .group_by(Guide.status)
    )
    result = await db.execute(status_query)
    status_counts = {str(row[0]): row[1] for row in result.fetchall()}
    
    # По типам контента
    content_query = (
        select(Guide.content_type, func.count())
        .group_by(Guide.content_type)
    )
    result = await db.execute(content_query)
    content_counts = {str(row[0]): row[1] for row in result.fetchall()}
    
    return {
        "total_guides": total,
        "by_status": status_counts,
        "by_content_type": content_counts,
    }


# === AI Enhancement ===

@router.post("/{guide_id}/enhance-with-ai")
async def enhance_guide_with_ai(
    guide_id: int,
    mode: str = "regenerate",
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Запуск AI обработки текста шагов гайда.

    mode="regenerate" — генерация с нуля по скриншотам (Vision AI).
    mode="improve"    — улучшение существующего текста пользователя
                         (орфография/формулировка, текст берётся за основу).
    """
    mode = mode if mode in ("regenerate", "improve") else "regenerate"
    # Проверяем существование гайда
    query = select(Guide).where(Guide.id == guide_id)
    result = await db.execute(query)
    guide = result.scalar_one_or_none()
    
    if not guide:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Guide {guide_id} not found",
        )
    
    # Проверяем есть ли шаги
    steps_query = select(func.count()).select_from(GuideStep).where(GuideStep.guide_id == guide_id)
    steps_count = await db.scalar(steps_query) or 0
    
    if steps_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Guide has no steps to enhance",
        )
    
    # Запускаем Celery задачу
    from app.celery_tasks import enhance_guide_with_ai_task
    task = enhance_guide_with_ai_task.delay(guide_id, mode)

    # Сохраняем task_id, чтобы можно было отменить задачу из UI.
    # Заодно снимаем флаг отмены от предыдущего запуска.
    from app.celery import celery_app
    import redis as _redis
    _rc = _redis.from_url(celery_app.conf.broker_url)
    _rc.set(f"ai_enhancement:{guide_id}:task_id", task.id, ex=3600)
    _rc.delete(f"ai_enhancement:{guide_id}:cancel")

    logger.info(f"Started AI enhancement for guide {guide_id}, mode={mode}, task_id: {task.id}")

    return {
        "success": True,
        "task_id": task.id,
        "guide_id": guide_id,
        "mode": mode,
        "total_steps": steps_count,
        "message": "AI enhancement started",
    }


@router.get("/{guide_id}/ai-status")
async def get_ai_enhancement_status(
    guide_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Получение статуса AI обработки гайда.
    Возвращает прогресс обработки шагов.
    """
    # Проверяем существование гайда
    query = select(Guide).where(Guide.id == guide_id)
    result = await db.execute(query)
    guide = result.scalar_one_or_none()
    
    if not guide:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Guide {guide_id} not found",
        )
    
    # Получаем статус из Redis
    from app.celery import celery_app
    import redis
    
    redis_client = redis.from_url(celery_app.conf.broker_url)
    
    # Ключ для хранения прогресса
    progress_key = f"ai_enhancement:{guide_id}:progress"
    status_key = f"ai_enhancement:{guide_id}:status"
    message_key = f"ai_enhancement:{guide_id}:message"
    
    progress_data = redis_client.get(progress_key)
    status_data = redis_client.get(status_key)
    message_data = redis_client.get(message_key)
    
    if not progress_data:
        # Нет активной задачи
        return {
            "status": "idle",
            "current": 0,
            "total": 0,
            "message": "No active AI enhancement",
        }
    
    # Парсим прогресс (формат: "2/4")
    progress_str = progress_data.decode('utf-8')
    current, total = map(int, progress_str.split('/'))
    
    status = status_data.decode('utf-8') if status_data else "processing"
    message = message_data.decode('utf-8') if message_data else f"Анализируем шаг {current} из {total}..."
    
    return {
        "status": status,
        "current": current,
        "total": total,
        "progress_percent": int((current / total) * 100) if total > 0 else 0,
        "message": message,
    }


@router.post("/{guide_id}/cancel-ai")
async def cancel_ai_enhancement(
    guide_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Отмена выполняющейся AI обработки гайда.

    Прерывает задачу двумя способами:
    1) revoke(terminate=True) — убивает процесс воркера, чтобы оборвать даже
       зависший внутри шага вызов модели (например, медленный Vision на CPU);
    2) флаг отмены в Redis — на случай, если задача между шагами, останавливает
       её на ближайшей границе (кооперативно, без потери уже сделанной работы).
    """
    from app.celery import celery_app
    import redis

    redis_client = redis.from_url(celery_app.conf.broker_url)

    task_id_key = f"ai_enhancement:{guide_id}:task_id"
    status_key = f"ai_enhancement:{guide_id}:status"
    message_key = f"ai_enhancement:{guide_id}:message"
    cancel_key = f"ai_enhancement:{guide_id}:cancel"

    # Кооперативный флаг — задача сама остановится на границе шага
    redis_client.set(cancel_key, "1", ex=3600)

    # Жёсткое прерывание зависшего шага
    task_id = redis_client.get(task_id_key)
    if task_id:
        task_id = task_id.decode("utf-8")
        celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")
        logger.info(f"Revoked AI enhancement task {task_id} for guide {guide_id}")

    # Отражаем отмену в статусе сразу (на случай, если воркер убит до записи)
    redis_client.set(status_key, "cancelled", ex=3600)
    redis_client.set(message_key, "Обработка отменена", ex=3600)

    return {
        "success": True,
        "guide_id": guide_id,
        "message": "AI enhancement cancelled",
    }
