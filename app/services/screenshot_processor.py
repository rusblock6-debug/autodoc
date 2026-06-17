"""
Утилита для обработки скриншотов с аннотациями.
Создает временные копии скриншотов с примененными overlay и аннотациями.
"""

import logging
import math
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter

logger = logging.getLogger(__name__)

DEFAULT_ANN_COLOR = '#ed8d48'


def _hex_to_rgb(color: str) -> Tuple[int, int, int]:
    """'#ed8d48' → (237, 141, 72). При ошибке возвращает дефолтный оранжевый."""
    try:
        c = (color or DEFAULT_ANN_COLOR).lstrip('#')
        if len(c) == 3:
            c = ''.join(ch * 2 for ch in c)
        return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))
    except Exception:
        return (237, 141, 72)


def _get_font(size: int) -> "ImageFont.FreeTypeFont":
    """Пытается загрузить TrueType-шрифт для номеров; иначе дефолтный bitmap-шрифт."""
    for name in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf", "arial.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _draw_arrow(draw: "ImageDraw.ImageDraw", x1: int, y1: int, x2: int, y2: int,
                color: str, width: int) -> None:
    """Рисует линию со стрелочным наконечником на конце (x2, y2)."""
    draw.line([(x1, y1), (x2, y2)], fill=color, width=width)
    angle = math.atan2(y2 - y1, x2 - x1)
    head = max(10, width * 4)
    phi = math.pi / 7
    left = (x2 - head * math.cos(angle - phi), y2 - head * math.sin(angle - phi))
    right = (x2 - head * math.cos(angle + phi), y2 - head * math.sin(angle + phi))
    draw.polygon([(x2, y2), left, right], fill=color)


def _draw_badge(draw: "ImageDraw.ImageDraw", cx: int, cy: int, number: int,
                color: str, radius: int) -> None:
    """Рисует номерной кружок с белой цифрой по центру (cx, cy)."""
    draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
                 fill=color, outline='white', width=max(2, radius // 6))
    font = _get_font(max(11, int(radius * 1.2)))
    try:
        draw.text((cx, cy), str(number), fill='white', font=font, anchor='mm')
    except TypeError:
        # Старые Pillow без anchor — центрируем вручную
        tw, th = draw.textsize(str(number), font=font)
        draw.text((cx - tw / 2, cy - th / 2), str(number), fill='white', font=font)


def process_screenshot_with_annotations(
    screenshot_path: str,
    annotations: List[Dict[str, Any]],
    marker_x: Optional[int] = None,
    marker_y: Optional[int] = None,
    output_path: Optional[str] = None,
    viewport_width: Optional[int] = None,
    viewport_height: Optional[int] = None,
) -> Optional[str]:
    """
    Создает обработанную версию скриншота с overlay, аннотациями и маркером.

    Args:
        screenshot_path: Путь к оригинальному скриншоту
        annotations: Список аннотаций [{type, x, y, width, height, color}]
        marker_x: X координата маркера (опционально)
        marker_y: Y координата маркера (опционально)
        output_path: Путь для сохранения (если None, создается временный файл)
        viewport_width, viewport_height: размеры вьюпорта в CSS-пикселях. Маркер и
            аннотации редактор хранит в CSS-координатах, а скриншот — в физических
            пикселях (CSS × devicePixelRatio). Без пересчёта на дисплеях с масштабом
            ≠ 100% маркер/рамки уезжают. Если не переданы — масштаб не применяется.

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

        # Коэффициенты CSS → пиксели картинки (учёт devicePixelRatio / масштаба)
        sx = (img_width / viewport_width) if viewport_width else 1.0
        sy = (img_height / viewport_height) if viewport_height else 1.0

        logger.info(f"Processing screenshot {screenshot_path}: {img_width}x{img_height}, {len(annotations)} annotations")
        
        # Если есть аннотации, рисуем выделения (rect/circle/arrow) с режимами
        if annotations and len(annotations) > 0:
            ui_scale = max(1.0, img_width / 1000.0)
            ow = max(3, int(3 * ui_scale))         # толщина рамок/линий
            badge_r = max(12, int(12 * ui_scale))  # радиус номерного кружка

            def _box(ann):
                x = int(ann.get('x', 0) * sx)
                y = int(ann.get('y', 0) * sy)
                w = int(ann.get('width', 100) * sx)
                h = int(ann.get('height', 50) * sy)
                return x, y, w, h

            # 1) Затемнение фона с вырезами — только для spotlight rect/circle
            spotlight = [a for a in annotations
                         if a.get('type') in ('rect', 'circle')
                         and a.get('mode', 'spotlight') == 'spotlight']
            if spotlight:
                mask = Image.new('L', (img_width, img_height), 102)  # 40% затемнение
                mask_draw = ImageDraw.Draw(mask)
                for ann in spotlight:
                    x, y, w, h = _box(ann)
                    if ann.get('type') == 'circle':
                        mask_draw.ellipse([x, y, x + w, y + h], fill=0)
                    else:
                        mask_draw.rectangle([x, y, x + w, y + h], fill=0)
                overlay_with_alpha = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 255))
                overlay_with_alpha.putalpha(mask)
                img = Image.alpha_composite(img, overlay_with_alpha)

            # 2) Свечение (glow) — отдельный размытый слой
            glow_anns = [a for a in annotations if a.get('mode') == 'glow']
            if glow_anns:
                glow_layer = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
                gdraw = ImageDraw.Draw(glow_layer)
                gw = max(6, int(8 * ui_scale))
                for ann in glow_anns:
                    x, y, w, h = _box(ann)
                    rgba = (*_hex_to_rgb(ann.get('color', DEFAULT_ANN_COLOR)), 220)
                    t = ann.get('type')
                    if t == 'circle':
                        gdraw.ellipse([x, y, x + w, y + h], outline=rgba, width=gw)
                    elif t == 'arrow':
                        gdraw.line([(x, y), (x + w, y + h)], fill=rgba, width=gw)
                    else:
                        gdraw.rectangle([x, y, x + w, y + h], outline=rgba, width=gw)
                glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(max(4, int(6 * ui_scale))))
                img = Image.alpha_composite(img, glow_layer)

            # 3) Чёткие фигуры + номерные бейджи
            draw = ImageDraw.Draw(img)
            for idx, ann in enumerate(annotations, start=1):
                x, y, w, h = _box(ann)
                color = ann.get('color', DEFAULT_ANN_COLOR)
                t = ann.get('type')
                if t == 'circle':
                    draw.ellipse([x, y, x + w, y + h], outline=color, width=ow)
                elif t == 'arrow':
                    _draw_arrow(draw, x, y, x + w, y + h, color, ow)
                else:
                    draw.rectangle([x, y, x + w, y + h], outline=color, width=ow)
                # Номерной бейдж в левом-верхнем углу выделения / у начала стрелки
                _draw_badge(draw, x, y, idx, color, badge_r)
        
        # Рисуем маркер если координаты переданы (CSS → пиксели картинки)
        if marker_x is not None and marker_y is not None:
            draw = ImageDraw.Draw(img)
            mx = int(marker_x * sx)
            my = int(marker_y * sy)
            marker_radius = 18

            # Внешний оранжевый круг
            draw.ellipse(
                [mx - marker_radius, my - marker_radius,
                 mx + marker_radius, my + marker_radius],
                outline='#ed8d48',
                width=3
            )
            # Белый средний круг
            inner_radius = 15
            draw.ellipse(
                [mx - inner_radius, my - inner_radius,
                 mx + inner_radius, my + inner_radius],
                fill='white'
            )
            # Оранжевая центральная точка
            center_radius = 5
            draw.ellipse(
                [mx - center_radius, my - center_radius,
                 mx + center_radius, my + center_radius],
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


def _scale_click_to_image(
    click_x: float,
    click_y: float,
    img_w: int,
    img_h: int,
    viewport_width: Optional[int],
    viewport_height: Optional[int],
) -> tuple:
    """
    Пересчитывает координаты клика из CSS-пикселей вьюпорта в пиксели картинки.

    captureVisibleTab сохраняет скриншот в физических пикселях (CSS × DPR), а клик
    приходит в CSS. Масштаб = размер картинки / размер вьюпорта. Если размеры
    вьюпорта неизвестны или совпадают с картинкой — возвращаем координаты как есть.
    """
    sx = (img_w / viewport_width) if viewport_width else 1.0
    sy = (img_h / viewport_height) if viewport_height else 1.0
    return click_x * sx, click_y * sy


def _draw_click_marker(draw: "ImageDraw.ImageDraw", x: int, y: int, scale: float = 1.0) -> None:
    """Рисует маркер клика (оранжевый круг с белой серединой и точкой) в точке (x, y)."""
    marker_radius = int(18 * scale)
    inner_radius = int(15 * scale)
    center_radius = int(5 * scale)
    width = max(2, int(3 * scale))

    draw.ellipse(
        [x - marker_radius, y - marker_radius, x + marker_radius, y + marker_radius],
        outline='#ed8d48', width=width
    )
    draw.ellipse(
        [x - inner_radius, y - inner_radius, x + inner_radius, y + inner_radius],
        fill='white'
    )
    draw.ellipse(
        [x - center_radius, y - center_radius, x + center_radius, y + center_radius],
        fill='#ed8d48'
    )


def render_click_focus(
    screenshot_path: str,
    click_x: int,
    click_y: int,
    crop_size: int = 520,
    zoom: float = 2.0,
    viewport_width: Optional[int] = None,
    viewport_height: Optional[int] = None,
) -> Optional[Dict[str, str]]:
    """
    Готовит изображения для Vision-анализа: место клика становится явно видимым.

    Возвращает два base64-PNG (без data-URI префикса):
    - "full":  полный скриншот с маркером клика (контекст всей страницы)
    - "crop":  увеличенный фрагмент вокруг клика (что именно под маркером)

    Args:
        screenshot_path: путь к оригинальному скриншоту
        click_x, click_y: координаты клика в CSS-пикселях вьюпорта
        crop_size: сторона области вокруг клика, которая вырезается (px оригинала)
        zoom: во сколько раз увеличить вырезанный фрагмент
        viewport_width, viewport_height: размеры вьюпорта в CSS-пикселях на момент
            клика. Нужны, чтобы пересчитать координаты в пиксели картинки:
            captureVisibleTab сохраняет PNG в физических пикселях
            (CSS × devicePixelRatio), а клик приходит в CSS. Без этого маркер
            уезжает на дисплеях с масштабом ≠ 100%.

    Returns:
        dict с ключами "full" и "crop" (base64) или None при ошибке.
    """
    import base64
    import io

    try:
        path_obj = Path(screenshot_path)
        if not path_obj.exists():
            logger.error(f"Screenshot not found for click focus: {screenshot_path}")
            return None

        base_img = Image.open(path_obj).convert('RGB')
        img_w, img_h = base_img.size

        # CSS-координаты → пиксели картинки (учёт devicePixelRatio / масштаба экрана)
        scaled_x, scaled_y = _scale_click_to_image(
            click_x, click_y, img_w, img_h, viewport_width, viewport_height
        )

        # Клик может прийти за пределами картинки — прижимаем к границам
        cx = max(0, min(int(scaled_x), img_w - 1))
        cy = max(0, min(int(scaled_y), img_h - 1))

        # 1) Полный скриншот с маркером
        full_img = base_img.copy()
        _draw_click_marker(ImageDraw.Draw(full_img), cx, cy)

        # 2) Кроп вокруг клика с маркером по центру, затем увеличение
        half = crop_size // 2
        left = max(0, min(cx - half, img_w - crop_size)) if img_w > crop_size else 0
        top = max(0, min(cy - half, img_h - crop_size)) if img_h > crop_size else 0
        right = min(img_w, left + crop_size)
        bottom = min(img_h, top + crop_size)

        crop_img = base_img.crop((left, top, right, bottom))
        # Маркер в координатах кропа
        _draw_click_marker(ImageDraw.Draw(crop_img), cx - left, cy - top)

        if zoom and zoom != 1.0:
            crop_img = crop_img.resize(
                (int(crop_img.width * zoom), int(crop_img.height * zoom)),
                Image.LANCZOS
            )

        def _to_b64(img: "Image.Image") -> str:
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            return base64.b64encode(buf.getvalue()).decode('utf-8')

        return {"full": _to_b64(full_img), "crop": _to_b64(crop_img)}

    except Exception as e:
        logger.error(f"Failed to render click focus for {screenshot_path}: {e}", exc_info=True)
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
