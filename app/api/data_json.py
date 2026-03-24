"""
API для работы с data.json - экспорт гайдов в документацию.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Guide, GuideStep
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

# Путь к data.json в Docker volume
DATA_JSON_PATH = Path("/data/data.json")

# Путь к скриншотам локально
SCREENSHOTS_DIR = Path("/data/screenshots")


# Pydantic models для запросов
class AddToDescriptiveRequest(BaseModel):
    guide_id: int
    title: str
    subtitle: str
    description: str
    items: list[str]
    image: Optional[str] = None


class AddToInstructionRequest(BaseModel):
    guide_id: int
    title: str
    nav_title: str
    description: str
    items: list[str]
    steps: Optional[list[dict]] = None


class AddToQuickstartRequest(BaseModel):
    guide_id: int
    title: str
    substeps: Optional[list[dict]] = None


class AddToDirectoryRequest(BaseModel):
    guide_id: int
    title: str
    items: list[str]
    image: Optional[str] = None


def read_data_json() -> dict:
    """Прочитать текущий data.json"""
    if not DATA_JSON_PATH.exists():
        # Создаем начальную структуру
        initial_data = {
            "title": "Инструкция пользователя",
            "cards": {
                "quickstart": {
                    "title": "Быстрый старт",
                    "description": "Пошаговое руководство для начала работы с системой",
                    "steps": []
                },
                "descriptive": [],
                "instructions": [],
                "directory": [],
                "about": []
            }
        }
        DATA_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(DATA_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(initial_data, f, ensure_ascii=False, indent=2)
        return initial_data
    
    with open(DATA_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def write_data_json(data: dict):
    """Записать data.json"""
    DATA_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Updated data.json at {DATA_JSON_PATH}")


def copy_screenshots_to_local(guide_id: int, steps: list) -> list:
    """
    Получить локальные пути к скриншотам.
    Теперь скриншоты хранятся локально, копирование не нужно.
    Конвертирует старый формат путей в новый.
    """
    # Создаем папку для скриншотов этого гайда
    guide_screenshot_dir = SCREENSHOTS_DIR / f"guide-{guide_id}"
    guide_screenshot_dir.mkdir(parents=True, exist_ok=True)
    
    local_paths = []
    
    for step in steps:
        if step.screenshot_path:
            # Конвертируем старый формат в новый
            screenshot_path = step.screenshot_path
            if not screenshot_path.startswith("screenshots/"):
                screenshot_path = f"screenshots/{screenshot_path}"
            
            # Проверяем существование
            screenshot_full_path = Path("/data") / screenshot_path
            if screenshot_full_path.exists():
                local_paths.append(screenshot_path)
            else:
                logger.warning(f"Screenshot not found: {screenshot_path}")
                # Возвращаем заглушку
                local_paths.append(f"screenshots/guide-{guide_id}/placeholder.png")
        else:
            local_paths.append(f"screenshots/guide-{guide_id}/placeholder.png")
    
    return local_paths


@router.get("")
async def get_data_json():
    """Получить текущий data.json"""
    try:
        data = read_data_json()
        return data
    except Exception as e:
        logger.error(f"Failed to read data.json: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read data.json: {str(e)}"
        )


@router.post("/add-to-descriptive")
async def add_to_descriptive(
    request: AddToDescriptiveRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Добавить гайд в раздел "Обзор" (cards.descriptive)
    
    - **guide_id**: ID гайда для экспорта
    - **title**: Заголовок (например, "Справочники")
    - **subtitle**: Подзаголовок (например, "Нормативно-справочная информация")
    - **description**: Подробное описание
    - **items**: Список особенностей/возможностей (array of strings)
    - **image**: Путь к скриншоту (опционально)
    """
    try:
        # Получаем гайд с шагами
        query = select(Guide).options(selectinload(Guide.steps)).where(Guide.id == request.guide_id)
        result = await db.execute(query)
        guide = result.scalar_one_or_none()
        
        if not guide:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Guide {request.guide_id} not found"
            )
        
        # Читаем текущий JSON
        data = read_data_json()
        
        # Копируем скриншоты локально
        sorted_steps = sorted(guide.steps, key=lambda s: s.step_number)
        local_screenshots = copy_screenshots_to_local(guide.id, sorted_steps)
        
        # Формируем новую запись
        new_entry = {
            "id": f"guide-{guide.uuid}",
            "title": request.title,
            "subtitle": request.subtitle,
            "description": request.description,
            "items": request.items,
            "image": local_screenshots[0] if local_screenshots else f"screenshots/guide-{guide.id}/overview.png"
        }
        
        # Добавляем в descriptive
        data["cards"]["descriptive"].append(new_entry)
        
        # Записываем обратно
        write_data_json(data)
        
        logger.info(f"Added guide {request.guide_id} to descriptive section")
        
        return {
            "success": True,
            "message": f"Гайд добавлен в раздел 'Обзор'",
            "entry": new_entry
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add to descriptive: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add to descriptive: {str(e)}"
        )


@router.post("/add-to-instruction")
async def add_to_instruction(
    request: AddToInstructionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Добавить гайд в раздел "Пошаговые инструкции" (cards.instructions)
    
    - **guide_id**: ID гайда для экспорта
    - **title**: Полный заголовок инструкции
    - **nav_title**: Короткий заголовок для меню
    - **description**: Описание инструкции
    - **items**: Список шагов (кратко)
    - **steps**: Детальные шаги с картинками (опционально, возьмется из гайда если не указано)
    """
    try:
        # Получаем гайд с шагами
        query = select(Guide).options(selectinload(Guide.steps)).where(Guide.id == request.guide_id)
        result = await db.execute(query)
        guide = result.scalar_one_or_none()
        
        if not guide:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Guide {request.guide_id} not found"
            )
        
        # Читаем текущий JSON
        data = read_data_json()
        
        # Копируем скриншоты локально
        sorted_steps = sorted(guide.steps, key=lambda s: s.step_number)
        local_screenshots = copy_screenshots_to_local(guide.id, sorted_steps)
        
        # Если steps не переданы - берем из гайда с локальными скриншотами
        if request.steps is None:
            steps = []
            for i, step in enumerate(sorted_steps):
                step_data = {
                    "text": step.edited_text or step.normalized_text or f"Шаг {step.step_number}",
                    "images": [local_screenshots[i]] if i < len(local_screenshots) else [],
                    "horizontal": False
                }
                steps.append(step_data)
        else:
            steps = request.steps
        
        # Формируем новую запись
        new_entry = {
            "id": f"guide-{guide.uuid}",
            "title": request.title,
            "navTitle": request.nav_title,
            "description": request.description,
            "items": request.items,
            "steps": steps
        }
        
        # Добавляем в instructions
        data["cards"]["instructions"].append(new_entry)
        
        # Записываем обратно
        write_data_json(data)
        
        logger.info(f"Added guide {request.guide_id} to instructions section")
        
        return {
            "success": True,
            "message": f"Гайд добавлен в раздел 'Пошаговые инструкции'",
            "entry": new_entry
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add to instruction: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add to instruction: {str(e)}"
        )


@router.post("/add-to-quickstart")
async def add_to_quickstart(
    request: AddToQuickstartRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Добавить гайд в раздел "Быстрый старт" (cards.quickstart.steps)
    
    - **guide_id**: ID гайда для экспорта
    - **title**: Заголовок шага
    - **substeps**: Подшаги с деталями (опционально, возьмется из гайда если не указано)
    """
    try:
        # Получаем гайд с шагами
        query = select(Guide).options(selectinload(Guide.steps)).where(Guide.id == request.guide_id)
        result = await db.execute(query)
        guide = result.scalar_one_or_none()
        
        if not guide:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Guide {request.guide_id} not found"
            )
        
        # Читаем текущий JSON
        data = read_data_json()
        
        # Копируем скриншоты локально
        sorted_steps = sorted(guide.steps, key=lambda s: s.step_number)
        local_screenshots = copy_screenshots_to_local(guide.id, sorted_steps)
        
        # Если substeps не переданы - берем из гайда с локальными скриншотами
        if request.substeps is None:
            substeps = []
            for i, step in enumerate(sorted_steps):
                substep = {
                    "text": step.edited_text or step.normalized_text or f"Шаг {step.step_number}",
                    "details": [],
                    "images": [local_screenshots[i]] if i < len(local_screenshots) else []
                }
                if step.click_x is not None and step.click_y is not None:
                    substep["details"].append(f"Координаты клика: X={step.click_x}, Y={step.click_y}")
                substeps.append(substep)
        else:
            substeps = request.substeps
        
        # Формируем новую запись
        new_entry = {
            "title": request.title,
            "substeps": substeps
        }
        
        # Добавляем в quickstart steps
        data["cards"]["quickstart"]["steps"].append(new_entry)
        
        # Записываем обратно
        write_data_json(data)
        
        logger.info(f"Added guide {request.guide_id} to quickstart section")
        
        return {
            "success": True,
            "message": f"Гайд добавлен в раздел 'Быстрый старт'",
            "entry": new_entry
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add to quickstart: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error: {str(e)}"
        )


@router.post("/add-to-directory")
async def add_to_directory(
    request: AddToDirectoryRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Добавить гайд в раздел "Справочники" (cards.directory)
    
    - **guide_id**: ID гайда для экспорта
    - **title**: Название справочника
    - **items**: Параметры справочника (список)
    """
    try:
        # Получаем гайд с шагами
        query = select(Guide).options(selectinload(Guide.steps)).where(Guide.id == request.guide_id)
        result = await db.execute(query)
        guide = result.scalar_one_or_none()
        
        if not guide:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Guide {request.guide_id} not found"
            )
        
        # Читаем текущий JSON
        data = read_data_json()
        
        # Копируем скриншоты локально
        sorted_steps = sorted(guide.steps, key=lambda s: s.step_number)
        local_screenshots = copy_screenshots_to_local(guide.id, sorted_steps)
        
        # Формируем новую запись
        new_entry = {
            "id": f"guide-{guide.uuid}",
            "title": request.title,
            "items": request.items,
            "image": local_screenshots[0] if local_screenshots else f"screenshots/guide-{guide.id}/overview.png"
        }
        
        # Добавляем в directory
        if "directory" not in data["cards"]:
            data["cards"]["directory"] = []
        
        data["cards"]["directory"].append(new_entry)
        
        # Записываем обратно
        write_data_json(data)
        
        logger.info(f"Added guide {request.guide_id} to directory section")
        
        return {
            "success": True,
            "message": f"Гайд добавлен в раздел 'Справочники'",
            "entry": new_entry
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add to directory: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error: {str(e)}"
        )
