"""
API: Steps - редактирование шагов.
PATCH /steps/{id}/text - изменить текст
PATCH /steps/{id}/marker - переместить маркер
POST /steps/reorder - изменить порядок
POST /steps/merge - объединить шаги
DELETE /steps/{id} - удалить шаг
"""

import logging
from typing import List, Dict, Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Guide, GuideStep, GuideStatus
from app.services.storage import storage_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/steps", tags=["Steps"])


class StepUpdate:
    """Схема обновления текста шага."""
    def __init__(self, edited_text: str):
        self.edited_text = edited_text


class MarkerUpdate:
    """Схема обновления позиции маркера."""
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y


class ReorderRequest:
    """Схема изменения порядка шагов."""
    def __init__(self, step_ids: List[int], from_index: int, to_index: int):
        self.step_ids = step_ids
        self.from_index = from_index
        self.to_index = to_index


class MergeRequest:
    """Схема объединения шагов."""
    def __init__(self, step_ids: List[int], merged_text: str):
        self.step_ids = step_ids
        self.merged_text = merged_text


@router.patch("/{step_id}/text")
async def update_step_text(
    step_id: int,
    body: Dict[str, str],
    db: AsyncSession = Depends(get_db)
):
    """
    Изменить текст шага (edited_text).
    
    Request body:
    {"edited_text": "Новый текст инструкции"}
    
    Returns:
    {"success": True, "step_id": 1, "edited_text": "..."}
    """
    result = await db.execute(
        select(GuideStep).where(GuideStep.id == step_id)
    )
    step = result.scalar_one_or_none()
    
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    
    edited_text = body.get("edited_text", "").strip()
    step.edited_text = edited_text
    step.updated_at = __import__("datetime").datetime.utcnow()
    
    await db.commit()
    
    logger.info(f"Step {step_id} text updated: '{edited_text[:50]}...'")
    
    return {
        "success": True,
        "step_id": step_id,
        "edited_text": edited_text,
        "final_text": step.final_text
    }


@router.patch("/{step_id}/marker")
async def update_marker_position(
    step_id: int,
    body: Dict[str, int],
    db: AsyncSession = Depends(get_db)
):
    """
    Переместить маркер на скриншоте.
    
    Request body:
    {"x": 450, "y": 320}
    
    Returns:
    {"success": True, "step_id": 1, "x": 450, "y": 320}
    """
    result = await db.execute(
        select(GuideStep).where(GuideStep.id == step_id)
    )
    step = result.scalar_one_or_none()
    
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    
    x = body.get("x", 0)
    y = body.get("y", 0)
    
    if x < 0 or y < 0:
        raise HTTPException(status_code=400, detail="Invalid coordinates")
    
    step.click_x = x
    step.click_y = y
    step.updated_at = __import__("datetime").datetime.utcnow()
    
    await db.commit()
    
    logger.info(f"Step {step_id} marker moved to ({x}, {y})")
    
    return {
        "success": True,
        "step_id": step_id,
        "x": x,
        "y": y
    }


@router.post("/reorder")
async def reorder_steps(
    guide_id: int,
    body: Dict[str, Any],
    db: AsyncSession = Depends(get_db)
):
    """
    Изменить порядок шагов.
    
    Request body:
    {
        "step_ids": [3, 1, 2, 4, 5]  // новый порядок ID
    }
    
    Returns:
    {"success": True, "guide_id": 1, "steps_reordered": 5}
    """
    # Получаем гайд
    result = await db.execute(
        select(Guide)
        .options(selectinload(Guide.steps))
        .where(Guide.id == guide_id)
    )
    guide = result.scalar_one_or_none()
    
    if not guide:
        raise HTTPException(status_code=404, detail="Guide not found")
    
    new_order = body.get("step_ids", [])
    
    if not new_order:
        raise HTTPException(status_code=400, detail="step_ids required")
    
    # Обновляем step_number для каждого шага
    updated_count = 0
    
    for new_number, step_id in enumerate(new_order, start=1):
        step = next((s for s in guide.steps if s.id == step_id), None)
        if step:
            step.step_number = new_number
            updated_count += 1
    
    guide.updated_at = __import__("datetime").datetime.utcnow()
    await db.commit()
    
    logger.info(f"Guide {guide_id} reordered: {updated_count} steps")
    
    return {
        "success": True,
        "guide_id": guide_id,
        "steps_reordered": updated_count
    }


@router.post("/merge")
async def merge_steps(
    guide_id: int,
    body: Dict[str, Any],
    db: AsyncSession = Depends(get_db)
):
    """
    Объединить несколько шагов в один.
    
    Request body:
    {
        "step_ids": [2, 3],           // какие шаги объединяем
        "merged_text": "Нажмите Создать и заполните форму"  // текст результата
    }
    
    Первый шаг сохраняется, остальные удаляются.
    """
    # Получаем гайд
    result = await db.execute(
        select(Guide)
        .options(selectinload(Guide.steps))
        .where(Guide.id == guide_id)
    )
    guide = result.scalar_one_or_none()
    
    if not guide:
        raise HTTPException(status_code=404, detail="Guide not found")
    
    step_ids = body.get("step_ids", [])
    merged_text = body.get("merged_text", "").strip()
    
    if len(step_ids) < 2:
        raise HTTPException(status_code=400, detail="At least 2 steps required")
    
    # Находим шаги
    steps_to_merge = [s for s in guide.steps if s.id in step_ids]
    
    if len(steps_to_merge) < 2:
        raise HTTPException(status_code=404, detail="Steps not found")
    
    # Сортируем по номеру
    steps_to_merge.sort(key=lambda s: s.step_number)
    
    # Первый шаг - результат объединения
    first_step = steps_to_merge[0]
    first_step.edited_text = merged_text
    first_step.updated_at = __import__("datetime").datetime.utcnow()
    
    # Удаляем остальные шаги
    steps_to_delete = steps_to_merge[1:]
    for step in steps_to_delete:
        # Удаляем скриншот из хранилища
        if step.screenshot_path:
            try:
                await storage_service.delete_file(step.screenshot_path)
            except Exception:
                pass
        
        await db.delete(step)
    
    # Перенумеровываем оставшиеся шаги
    remaining_steps = [s for s in guide.steps if s.id not in step_ids]
    remaining_steps.sort(key=lambda s: s.step_number)
    
    for i, step in enumerate(remaining_steps, start=1):
        step.step_number = i
    
    guide.updated_at = __import__("datetime").datetime.utcnow()
    await db.commit()
    
    logger.info(f"Guide {guide_id}: merged {len(steps_to_merge)} steps into one")
    
    return {
        "success": True,
        "guide_id": guide_id,
        "merged_step_id": first_step.id,
        "deleted_step_ids": [s.id for s in steps_to_delete],
        "remaining_steps_count": len(remaining_steps)
    }


@router.delete("/{step_id}")
async def delete_step(
    step_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Удалить шаг.
    """
    result = await db.execute(
        select(GuideStep).where(GuideStep.id == step_id)
    )
    step = result.scalar_one_or_none()
    
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    
    guide_id = step.guide_id
    
    # Удаляем скриншот
    if step.screenshot_path:
        try:
            await storage_service.delete_file(step.screenshot_path)
        except Exception:
            pass
    
    await db.delete(step)
    
    # Перенумеровываем шаги в гайде
    guide_result = await db.execute(
        select(Guide)
        .options(selectinload(Guide.steps))
        .where(Guide.id == guide_id)
    )
    guide = guide_result.scalar_one_or_none()
    
    if guide:
        guide.steps.sort(key=lambda s: s.step_number)
        for i, s in enumerate(guide.steps, start=1):
            s.step_number = i
        guide.updated_at = __import__("datetime").datetime.utcnow()
    
    await db.commit()
    
    logger.info(f"Step {step_id} deleted")
    
    return {
        "success": True,
        "step_id": step_id,
        "guide_id": guide_id
    }


@router.post("/{step_id}/regenerate_marker")
async def regenerate_marker(
    step_id: int,
    body: Dict[str, Any],
    db: AsyncSession = Depends(get_db)
):
    """
    Автоматически переместить маркер на основе нового текста.
    Использует LLM для определения, куда должен указывать маркер.
    
    Request body:
    {"new_text": "Нажмите кнопку 'Сохранить'"}
    
    Returns:
    {"success": True, "x": 450, "y": 320, "reason": "Found 'Сохранить' button at bottom-right"}
    """
    # TODO: Реализовать с помощью LLM
    # LLM анализирует текст + скриншот (OCR?) → предлагает координаты
    
    return {
        "success": False,
        "message": "Feature not implemented yet",
        "note": "Requires OCR integration"
    }
