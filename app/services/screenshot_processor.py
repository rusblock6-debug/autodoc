"""
Утилита для обработки скриншотов с аннотациями.
Создает временные копии скриншотов с примененными overlay и аннотациями.
"""

import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)


def process_screenshot_with_annotations(
    screenshot_path: str,
    annotations: List[Dict[str, Any]],
    marker_x: Optional[int] = None,
    marker_y: Optional[int] = None,
    output_path: Optional[str] = None
) -> Optional[str]:
    """
    Создает обработанную версию скриншота с overlay, аннотациями и маркером.
    
    Args:
        screenshot_path: Путь к оригинальному скриншоту
        annotations: Список аннотаций [{type, x, y, width, height, color}]
        marker_x: X координата маркера (опционально)
        marker_y: Y координата маркера (опционально)
        output_path: Путь для сохранения (если None, создается временный файл)
    
    Returns:
        Путь к обработанному скриншоту или None при ошибке
    """
    try:
        screenshot_path_obj = Path(screenshot_path)
        
        if not screenshot_path_obj.exists():
            logger.error(f"Screenshot not found: {screenshot_path}")
            return None
        
        # Если нет аннотаций и маркера, возвращаем оригинал
        if not annotations and marker_x is None:
            return str(screenshot_path)
        
        # Открываем изображение
        img = Image.open(screenshot_path_obj).convert('RGBA')
        img_width, img_height = img.size
        
        logger.info(f"Processing screenshot {screenshot_path}: {img_width}x{img_height}, {len(annotations)} annotations")
        
        # Если есть аннотации, применяем overlay с вырезами
        if annotations and len(annotations) > 0:
            # Создаем черный overlay
            overlay = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
            
            # Создаем маску с нужной прозрачностью (102 = 40%)
            # Где маска = 102 → overlay будет виден с прозрачностью 40%
            # Где маска = 0 → overlay будет полностью прозрачен
            mask = Image.new('L', (img_width, img_height), 102)  # 102 = 40% непрозрачности
            mask_draw = ImageDraw.Draw(mask)
            
            # Рисуем черные прямоугольники в маске (вырезы)
            for ann in annotations:
                if ann.get('type') == 'rect':
                    x = int(ann.get('x', 0))
                    y = int(ann.get('y', 0))
                    width = int(ann.get('width', 100))
                    height = int(ann.get('height', 50))
                    
                    # Черный (0) = полностью прозрачный overlay в этой области
                    mask_draw.rectangle([x, y, x + width, y + height], fill=0)
            
            # Создаем overlay с черным цветом и применяем маску как альфа-канал
            overlay_with_alpha = Image.new('RGBA', (img_width, img_height))
            # Заполняем черным цветом
            overlay_draw = ImageDraw.Draw(overlay_with_alpha)
            overlay_draw.rectangle([0, 0, img_width, img_height], fill=(0, 0, 0, 255))
            # Применяем маску как альфа-канал
            overlay_with_alpha.putalpha(mask)
            
            # Накладываем overlay на оригинальное изображение
            img = Image.alpha_composite(img, overlay_with_alpha)
            
            # Рисуем оранжевые рамки аннотаций
            draw = ImageDraw.Draw(img)
            for ann in annotations:
                if ann.get('type') == 'rect':
                    x = int(ann.get('x', 0))
                    y = int(ann.get('y', 0))
                    width = int(ann.get('width', 100))
                    height = int(ann.get('height', 50))
                    color = ann.get('color', '#ed8d48')
                    
                    # Рисуем рамку
                    draw.rectangle([x, y, x + width, y + height], outline=color, width=3)
        
        # Рисуем маркер если координаты переданы
        if marker_x is not None and marker_y is not None:
            draw = ImageDraw.Draw(img)
            marker_radius = 18
            
            # Внешний оранжевый круг
            draw.ellipse(
                [marker_x - marker_radius, marker_y - marker_radius,
                 marker_x + marker_radius, marker_y + marker_radius],
                outline='#ed8d48',
                width=3
            )
            # Белый средний круг
            inner_radius = 15
            draw.ellipse(
                [marker_x - inner_radius, marker_y - inner_radius,
                 marker_x + inner_radius, marker_y + inner_radius],
                fill='white'
            )
            # Оранжевая центральная точка
            center_radius = 5
            draw.ellipse(
                [marker_x - center_radius, marker_y - center_radius,
                 marker_x + center_radius, marker_y + center_radius],
                fill='#ed8d48'
            )
        
        # Определяем путь для сохранения
        if output_path is None:
            # Создаем временный файл рядом с оригиналом
            output_path = str(screenshot_path_obj.parent / f"processed_{screenshot_path_obj.name}")
        
        # Конвертируем в RGB и сохраняем
        img.convert('RGB').save(output_path, 'PNG')
        
        logger.info(f"Processed screenshot saved to: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Failed to process screenshot: {e}", exc_info=True)
        return None


def cleanup_processed_screenshot(screenshot_path: str) -> bool:
    """
    Удаляет обработанный скриншот.
    
    Args:
        screenshot_path: Путь к обработанному скриншоту
    
    Returns:
        True если файл удален, False при ошибке
    """
    try:
        path = Path(screenshot_path)
        if path.exists() and path.name.startswith('processed_'):
            path.unlink()
            logger.info(f"Cleaned up processed screenshot: {screenshot_path}")
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to cleanup screenshot {screenshot_path}: {e}")
        return False
