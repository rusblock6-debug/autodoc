"""
API: Export - экспорт гайда в Markdown/HTML/PDF.
GET /guides/{id}/export/markdown
GET /guides/{id}/export/html
GET /guides/{id}/export/pdf
"""

import logging
import base64
from html import escape
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Guide, GuideStatus

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Export"])


@router.get("/export/{guide_id}/markdown")
async def export_markdown(
    guide_id: int,
    include_screenshots: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """
    Экспортировать гайд в Markdown.
    
    Returns:
    - content: Markdown текст
    - file_path: Путь к файлу в хранилище (опционально)
    """
    result = await db.execute(
        select(Guide)
        .options(selectinload(Guide.steps))
        .where(Guide.id == guide_id)
    )
    guide = result.scalar_one_or_none()
    
    if not guide:
        raise HTTPException(status_code=404, detail="Guide not found")
    
    # Сортируем шаги
    steps = sorted(guide.steps, key=lambda s: s.step_number)
    
    # Формируем Markdown
    lines = []
    
    # Заголовок
    lines.append(f"# {guide.title}")
    lines.append("")
    lines.append(f"*Создано: {guide.created_at.strftime('%Y-%m-%d %H:%M')}*")
    lines.append("")
    
    if guide.status == GuideStatus.DRAFT:
        lines.append("⚠️ *Черновик — шаги могут быть изменены*")
        lines.append("")
    
    lines.append("---")
    lines.append("")
    lines.append("## Шаги")
    lines.append("")
    
    # Шаги
    for step in steps:
        lines.append(f"### Шаг {step.step_number}")
        lines.append("")
        
        # Скриншот
        if include_screenshots and step.screenshot_path:
            lines.append(f"![Шаг {step.step_number}]({step.screenshot_path})")
            lines.append("")
        
        # Текст
        final_text = step.final_text
        lines.append(final_text)
        lines.append("")

        lines.append("---")
        lines.append("")
    
    # Метаданные
    lines.append("* * *")
    lines.append("")
    lines.append(f"**Всего шагов:** {len(steps)}")
    lines.append("")
    
    content = "\n".join(lines)
    
    return {
        "guide_id": guide_id,
        "title": guide.title,
        "format": "markdown",
        "content": content,
        "steps_count": len(steps),
        "exported_at": datetime.utcnow().isoformat()
    }


@router.get("/export/{guide_id}/html")
async def export_html(
    guide_id: int,
    include_screenshots: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """
    Экспортировать гайд в HTML.
    
    Returns:
    - content: HTML текст
    - file_path: Путь к файлу в хранилище (опционально)
    """
    # Получаем Markdown
    markdown_response = await export_markdown(guide_id, include_screenshots, db)
    
    markdown_content = markdown_response["content"]
    
    # Конвертируем Markdown в HTML (простая реализация)
    # В продакшене использовать markdown-it или similar
    
    html_content = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{escape(markdown_response['title'])}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
            color: #333;
        }}
        h1 {{
            color: #1a1a1a;
            border-bottom: 2px solid #eee;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #333;
            margin-top: 30px;
        }}
        h3 {{
            color: #555;
            margin-top: 20px;
        }}
        img {{
            max-width: 100%;
            height: auto;
            border: 1px solid #ddd;
            border-radius: 8px;
            margin: 10px 0;
        }}
        .step {{
            margin: 20px 0;
            padding: 15px;
            background: #f9f9f9;
            border-radius: 8px;
        }}
        .meta {{
            color: #666;
            font-size: 0.9em;
        }}
        .marker {{
            color: #f59e0b;
            font-weight: bold;
        }}
    </style>
</head>
<body>
{_convert_simple_markdown(markdown_content)}
</body>
</html>"""
    
    return {
        "guide_id": guide_id,
        "title": markdown_response["title"],
        "format": "html",
        "content": html_content,
        "steps_count": markdown_response["steps_count"],
        "exported_at": datetime.utcnow().isoformat()
    }


@router.get("/export/{guide_id}/pdf")
async def export_pdf(
    guide_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Экспортировать гайд в PDF с красивым дизайном.
    """
    result = await db.execute(
        select(Guide)
        .options(selectinload(Guide.steps))
        .where(Guide.id == guide_id)
    )
    guide = result.scalar_one_or_none()
    
    if not guide:
        raise HTTPException(status_code=404, detail="Guide not found")
    
    # Сортируем шаги
    steps = sorted(guide.steps, key=lambda s: s.step_number)
    
    # Тяжёлая синхронная работа (PIL + weasyprint) — в threadpool,
    # чтобы не блокировать event loop на всё время рендера.
    from starlette.concurrency import run_in_threadpool

    html_content = await run_in_threadpool(_create_pdf_html, guide, steps)

    try:
        pdf_content = await run_in_threadpool(_render_pdf, html_content)

        filename = f"{guide.title.replace(' ', '_').encode('ascii', 'ignore').decode('ascii')}.pdf"
        if not filename.replace('.pdf', ''):
            filename = f"guide_{guide.id}.pdf"
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
        )

    except ImportError:
        # Fallback: если weasyprint не установлен, возвращаем HTML
        logger.warning("weasyprint not installed, returning HTML instead of PDF")
        filename = f"{guide.title.replace(' ', '_').encode('ascii', 'ignore').decode('ascii')}.html"
        if not filename.replace('.html', ''):
            filename = f"guide_{guide.id}.html"
        return Response(
            content=html_content.encode('utf-8'),
            media_type="text/html",
            headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
        )
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")


def _render_pdf(html_content: str) -> bytes:
    """Синхронный рендер PDF через weasyprint (вызывать из threadpool)."""
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration

    font_config = FontConfiguration()
    html_doc = HTML(string=html_content)
    css = CSS(string=_get_pdf_css())
    return html_doc.write_pdf(stylesheets=[css], font_config=font_config)


def _create_pdf_html(guide: Guide, steps: list) -> str:
    """Создает красивый HTML для PDF с дизайном в стиле НИР-Документ."""
    
    steps_html = ""
    for step in steps:
        screenshot_html = ""
        if step.screenshot_path:
            # Получаем изображение с примененными аннотациями как base64
            screenshot_base64 = _get_screenshot_base64(
                step.screenshot_path,
                annotations=step.annotations,
                marker_x=step.click_x,
                marker_y=step.click_y,
                img_width=step.screenshot_width,
                img_height=step.screenshot_height
            )
            if screenshot_base64:
                # Изображение уже содержит overlay, аннотации и маркер
                screenshot_html = f"""
                <div class="screenshot">
                    <img src="data:image/png;base64,{screenshot_base64}" alt="Шаг {step.step_number}" />
                </div>
                """
            else:
                # Fallback: если не удалось загрузить изображение
                screenshot_html = f"""
                <div class="screenshot-placeholder">
                    <p>Скриншот недоступен</p>
                    <p>Шаг {step.step_number}</p>
                </div>
                """
        
        # Блок-легенда: расшифровка подписанных выделений (нумерация = как на скриншоте)
        legend_html = ""
        labeled = [
            (i + 1, a) for i, a in enumerate(step.annotations or [])
            if isinstance(a, dict) and (a.get('label') or '').strip()
        ]
        if labeled:
            items = "".join(
                f'<li>'
                f'<span class="legend-num" style="background:{escape(str(a.get("color") or "#ed8d48"))}">{n}</span>'
                f'<span class="legend-text">{escape(a["label"])}</span>'
                f'</li>'
                for n, a in labeled
            )
            legend_html = f'<div class="legend"><div class="legend-title">Легенда</div><ul>{items}</ul></div>'

        steps_html += f"""
        <div class="step">
            <div class="step-header">
                <div class="step-number">{step.step_number}</div>
                <h3>Шаг {step.step_number}</h3>
            </div>
            {screenshot_html}
            {legend_html}
            <div class="step-text">
                <p>{escape(step.final_text or f'Шаг {step.step_number}')}</p>
            </div>
        </div>
        """
    
    return f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <title>{escape(guide.title)}</title>
    </head>
    <body>
        <div class="document">
            <header class="header">
                <div class="brand">
                    <div class="logo-icon">НД</div>
                    <span class="brand-name">НИР-Документ</span>
                </div>
                <h1 class="doc-title">{escape(guide.title)}</h1>
                <div class="meta">
                    <span>Создано {guide.created_at.strftime('%d.%m.%Y') if guide.created_at else '—'}</span>
                    <span class="dot">·</span>
                    <span>{len(steps)} шагов</span>
                    <span class="dot">·</span>
                    <span>{'Черновик' if guide.status == GuideStatus.DRAFT else 'Готов'}</span>
                </div>
            </header>
            
            <main class="content">
                {steps_html}
            </main>
            
            <footer class="footer">
                <div class="footer-content">
                    <p>Создано с помощью НИР-Документ</p>
                    <p>Экспортировано: {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
                </div>
            </footer>
        </div>
    </body>
    </html>
    """


def _get_pdf_css() -> str:
    """CSS стили для PDF в стиле НИР-Документ."""
    return """
    @page {
        size: A4;
        margin: 2cm 1.5cm;
        @top-center {
            content: "НИР-Документ";
            font-family: 'Montserrat', sans-serif;
            font-size: 10px;
            color: #666;
        }
        @bottom-center {
            content: "Страница " counter(page) " из " counter(pages);
            font-family: 'Roboto', sans-serif;
            font-size: 9px;
            color: #999;
        }
    }
    
    * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
    }
    
    body {
        font-family: 'Roboto', -apple-system, BlinkMacSystemFont, sans-serif;
        line-height: 1.6;
        color: #333;
        background: #fff;
    }
    
    .document {
        max-width: 100%;
    }
    
    .header {
        padding: 0 0 16px;
        border-bottom: 1px solid #ececec;
        margin-bottom: 28px;
    }

    .brand {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 14px;
    }

    .logo-icon {
        width: 26px;
        height: 26px;
        background: #ed8d48;
        color: white;
        border-radius: 6px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: 'Montserrat', sans-serif;
        font-weight: 700;
        font-size: 11px;
    }

    .brand-name {
        font-family: 'Montserrat', sans-serif;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        color: #9a9a9a;
    }

    .doc-title {
        font-family: 'Montserrat', sans-serif;
        font-size: 26px;
        font-weight: 700;
        color: #1a1a1a;
        line-height: 1.2;
        margin-bottom: 10px;
    }

    .meta {
        display: flex;
        gap: 8px;
        align-items: center;
        font-size: 12px;
        color: #888;
    }

    .meta .dot {
        color: #ccc;
    }
    
    .content {
        margin-bottom: 40px;
    }
    
    .step {
        margin-bottom: 40px;
        page-break-inside: avoid;
        break-inside: avoid;
    }
    
    .step-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 16px;
    }
    
    .step-number {
        width: 32px;
        height: 32px;
        background: #ed8d48;
        color: white;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: 'Montserrat', sans-serif;
        font-weight: 600;
        font-size: 14px;
    }
    
    .step-header h3 {
        font-family: 'Montserrat', sans-serif;
        font-size: 16px;
        font-weight: 600;
        color: #333;
    }
    
    .screenshot {
        position: relative;
        margin: 16px 0;
        text-align: center;
    }
    
    .screenshot img {
        max-width: 100%;
        height: auto;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    
    .dark-overlay-base {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.5);
        pointer-events: none;
        border-radius: 8px;
        z-index: 1;
    }
    
    .cutout-window {
        position: absolute;
        background: white;
        opacity: 1;
        pointer-events: none;
        z-index: 2;
        box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.5);
    }
    
    .dark-overlay-simple {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-color: rgba(0, 0, 0, 0.5);
        pointer-events: none;
        border-radius: 8px;
        z-index: 1;
    }
    
    .annotation-rect-with-bg {
        position: absolute;
        border: 3px solid #ed8d48;
        border-radius: 4px;
        background-color: transparent;
        box-sizing: border-box;
        z-index: 2;
        box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.4);
        clip-path: inset(0 0 0 0);
    }
    
    .screenshot-placeholder {
        margin: 16px 0;
        padding: 40px;
        background: #f5f5f5;
        border: 2px dashed #ccc;
        border-radius: 8px;
        text-align: center;
        color: #666;
    }
    
    .screenshot-placeholder p {
        margin: 4px 0;
        font-size: 12px;
    }
    
    .click-marker {
        position: absolute;
        width: 24px;
        height: 24px;
        background: #ed8d48;
        color: white;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 11px;
        font-weight: 600;
        border: 2px solid white;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        transform: translate(-50%, -50%);
    }
    
    .annotation-rect {
        position: absolute;
        border: 3px solid #ed8d48;
        border-radius: 4px;
        background: transparent;
        box-sizing: border-box;
        z-index: 3;
    }
    
    .legend {
        margin-top: 12px;
        padding: 12px 16px;
        background: #fff;
        border: 1px solid #e0e0e0;
        border-radius: 6px;
    }

    .legend-title {
        font-family: 'Montserrat', sans-serif;
        font-size: 10px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: #999;
        margin-bottom: 8px;
    }

    .legend ul {
        list-style: none;
        margin: 0;
        padding: 0;
    }

    .legend li {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 6px;
    }

    .legend-num {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 20px;
        height: 20px;
        border-radius: 10px;
        color: #fff;
        font-family: 'Montserrat', sans-serif;
        font-size: 12px;
        font-weight: 700;
        flex-shrink: 0;
    }

    .legend-text {
        font-size: 13px;
        color: #333;
    }

    .step-text {
        background: #fafafa;
        border: 1px solid #e0e0e0;
        border-radius: 6px;
        padding: 16px;
        margin-top: 16px;
    }
    
    .step-text p {
        font-size: 14px;
        line-height: 1.6;
        color: #333;
    }
    
    .footer {
        border-top: 1px solid #e0e0e0;
        padding-top: 20px;
        margin-top: 40px;
    }
    
    .footer-content {
        text-align: center;
        font-size: 11px;
        color: #999;
    }
    
    .footer-content p {
        margin-bottom: 4px;
    }
    """


def _convert_simple_markdown(md: str) -> str:
    """Простой конвертер Markdown → HTML (базовый)."""
    import re

    # Сначала экранируем HTML: текст шагов пишет пользователь, и без escape
    # `<script>` из шага исполнится в экспортированном HTML (XSS).
    # Markdown-синтаксис (#, *, [, ]) при этом не затрагивается.
    html = escape(md, quote=False)

    # Заголовки
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    
    # Жирный
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    
    # Курсив
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
    
    # Изображения
    html = re.sub(r'!\[(.+?)\]\((.+?)\)', r'<img src="\2" alt="\1">', html)
    
    # Ссылки
    html = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', html)
    
    # Горизонтальная линия
    html = re.sub(r'^---$', '<hr>', html, flags=re.MULTILINE)
    
    # Параграфы (двойные переносы)
    html = re.sub(r'\n\n', '</p><p>', html)
    html = f"<p>{html}</p>"
    
    # Переносы строк
    html = html.replace('\n', '<br>')
    
    return html

def _get_screenshot_base64(screenshot_path: str, annotations: list = None, marker_x: int = None, marker_y: int = None, img_width: int = None, img_height: int = None) -> Optional[str]:
    """Получает скриншот как base64 строку для встраивания в PDF.
    Использует screenshot_processor для обработки аннотаций."""
    try:
        from pathlib import Path
        from app.services.screenshot_processor import process_screenshot_with_annotations, cleanup_processed_screenshot
        import io
        from PIL import Image
        
        # Конвертируем путь в полный путь в /data
        full_path_str = screenshot_path
        
        # Убираем ведущий слэш если есть
        if screenshot_path.startswith("/"):
            full_path_str = screenshot_path[1:]
        
        # Если путь в старом формате (без "screenshots/"), добавляем префикс
        if not full_path_str.startswith("screenshots/"):
            full_path_str = f"screenshots/{full_path_str}"
        
        full_path = Path("/data") / full_path_str
        
        if not full_path.exists():
            logger.warning(f"Screenshot file not found: {full_path}")
            return None
        
        # Обрабатываем скриншот с аннотациями если они есть
        processed_path = None
        if annotations and len(annotations) > 0:
            processed_path = process_screenshot_with_annotations(
                screenshot_path=str(full_path),
                annotations=annotations,
                marker_x=marker_x,
                marker_y=marker_y,
                viewport_width=img_width,
                viewport_height=img_height,
            )
        elif marker_x is not None and marker_y is not None:
            # Только маркер, без аннотаций
            processed_path = process_screenshot_with_annotations(
                screenshot_path=str(full_path),
                annotations=[],
                marker_x=marker_x,
                marker_y=marker_y,
                viewport_width=img_width,
                viewport_height=img_height,
            )
        
        # Используем обработанный скриншот или оригинал
        final_path = processed_path if processed_path else str(full_path)
        
        # Открываем и конвертируем в base64
        img = Image.open(final_path).convert('RGB')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        result = base64.b64encode(buffer.read()).decode('utf-8')
        
        # Удаляем обработанный файл если он был создан
        if processed_path and processed_path != str(full_path):
            cleanup_processed_screenshot(processed_path)
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to get screenshot {screenshot_path}: {e}")
        return None