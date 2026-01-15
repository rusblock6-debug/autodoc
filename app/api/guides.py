"""
API роуты для управления гайдами.
Реализует CRUD операции и расширенный функционал гайдов.
"""

import logging
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Guide, GuideStep, GuideStatus
from app.schemas import (
    GuideCreate,
    GuideUpdate,
    GuideListResponse,
    GuideDetailResponse,
    GuideStepResponse,
    GuideStepUpdate,
    ScreenshotResponse,
    PaginatedResponse,
    ErrorResponse,
)
from app.services.storage import storage_service, StorageBucket


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
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse:
    """
    Получение списка гайдов с пагинацией и фильтрацией.
    """
    # Базовый запрос
    query = select(Guide)
    
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
    query = query.offset(offset).limit(page_size).order_by(Guide.created_at.desc())
    
    # Выполняем запрос
    result = await db.execute(query)
    guides = result.scalars().all()
    
    # Формируем ответ
    items = [GuideListResponse.model_validate(g) for g in guides]
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
            selectinload(Guide.screenshots),
            selectinload(Guide.processing_jobs),
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
            selectinload(Guide.screenshots),
        )
    )
    
    result = await db.execute(query)
    guide = result.scalar_one_or_none()
    
    if not guide:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Guide with uuid {guide_uuid} not found",
        )
    
    # Увеличиваем счетчик просмотров
    guide.view_count += 1
    await db.commit()
    
    return GuideDetailResponse.model_validate(guide)


@router.post("", response_model=GuideDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_guide(
    guide_data: GuideCreate,
    db: AsyncSession = Depends(get_db),
) -> GuideDetailResponse:
    """
    Создание нового гайда.
    """
    guide = Guide(
        uuid=str(uuid4()),
        title=guide_data.title,
        # description=guide_data.description,  # TODO: Not in MVP model
        language=guide_data.language,
        # content_type=ContentType(guide_data.content_type.value) if guide_data.content_type else ContentType.ALL,  # TODO: Not implemented in MVP
        # tags=guide_data.tags or [],  # TODO: Not in MVP model
        # asr_model=guide_data.asr_model or "large-v3",  # TODO: Not in MVP model
        # llm_model=guide_data.llm_model or "Qwen/Qwen2.5-72B-Instruct",  # TODO: Not in MVP model
        tts_voice=guide_data.tts_voice or "ru-RU-SvetlanaNeural",
        status=GuideStatus.DRAFT,
    )
    
    db.add(guide)
    await db.commit()
    await db.refresh(guide)
    
    logger.info(f"Created new guide: {guide.id} - {guide.title}")
    
    return GuideDetailResponse.model_validate(guide)


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
        setattr(guide, field, value)
    
    await db.commit()
    await db.refresh(guide)
    
    logger.info(f"Updated guide: {guide.id}")
    
    return GuideDetailResponse.model_validate(guide)


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
    
    # Удаляем связанные файлы из хранилища
    try:
        if guide.processed_video_path:
            storage_service.delete_file(
                guide.processed_video_path,
                StorageBucket.VIDEOS,
            )
        if guide.wiki_markdown_path:
            storage_service.delete_file(
                guide.wiki_markdown_path,
                StorageBucket.WIKI,
            )
    except Exception as e:
        logger.warning(f"Failed to delete files: {e}")
    
    await db.delete(guide)
    await db.commit()
    
    logger.info(f"Deleted guide: {guide_id}")


# === Шаги гайда ===

@router.get("/{guide_id}/steps", response_model=List[GuideStepResponse])
async def get_guide_steps(
    guide_id: int,
    db: AsyncSession = Depends(get_db),
) -> List[GuideStepResponse]:
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
    
    return [GuideStepResponse.model_validate(s) for s in steps]


@router.get("/{guide_id}/steps/{step_id}", response_model=GuideStepResponse)
async def get_guide_step(
    guide_id: int,
    step_id: int,
    db: AsyncSession = Depends(get_db),
) -> GuideStepResponse:
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
    
    return GuideStepResponse.model_validate(step)


@router.patch("/{guide_id}/steps/{step_id}", response_model=GuideStepResponse)
async def update_guide_step(
    guide_id: int,
    step_id: int,
    step_update: GuideStepUpdate,
    db: AsyncSession = Depends(get_db),
) -> GuideStepResponse:
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
    
    return GuideStepResponse.model_validate(step)


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
            bucket=StorageBucket.SCREENSHOTS,
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
    # await db.commit()
    # await db.refresh(screenshot)
    # 
    # logger.info(f"Added screenshot {screenshot.id} to guide {guide_id}")
    
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
