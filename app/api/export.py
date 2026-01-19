"""
API: Export - экспорт гайда в Markdown/HTML/PDF/JSON.
GET /guides/{id}/export/markdown
GET /guides/{id}/export/html
GET /guides/{id}/export/pdf
GET /guides/{id}/export/json
"""

import logging
import json
import tempfile
import os
import base64
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Response
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Guide, GuideStep, GuideStatus

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
        
        # Координаты маркера (для отладки)
        # lines.append(f"*Маркер: ({step.click_x}, {step.click_y})*")
        # lines.append("")
        
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
    <title>{markdown_response['title']}</title>
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
    
    # Создаем красивый HTML для PDF
    html_content = _create_pdf_html(guide, steps)
    
    try:
        # Используем weasyprint для генерации PDF
        from weasyprint import HTML, CSS
        from weasyprint.text.fonts import FontConfiguration
        
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            # Генерируем PDF
            font_config = FontConfiguration()
            html_doc = HTML(string=html_content)
            css = CSS(string=_get_pdf_css())
            
            html_doc.write_pdf(tmp_file.name, stylesheets=[css], font_config=font_config)
            
            # Читаем содержимое файла
            with open(tmp_file.name, 'rb') as pdf_file:
                pdf_content = pdf_file.read()
            
            # Удаляем временный файл
            os.unlink(tmp_file.name)
            
            # Возвращаем PDF
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


@router.get("/export/{guide_id}/json")
async def export_json(
    guide_id: int,
    include_metadata: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """
    Экспортировать гайд в JSON формате.
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
    
    # Формируем JSON структуру
    json_data = {
        "guide": {
            "id": guide.id,
            "uuid": guide.uuid,
            "title": guide.title,
            "status": guide.status.value if guide.status else "draft",
            "language": guide.language or "ru",
            "created_at": guide.created_at.isoformat() if guide.created_at else None,
            "updated_at": guide.updated_at.isoformat() if guide.updated_at else None,
        },
        "steps": [
            {
                "id": step.id,
                "step_number": step.step_number,
                "text": {
                    "raw_speech": step.raw_speech,
                    "normalized": step.normalized_text,
                    "edited": step.edited_text,
                    "final": step.final_text
                },
                "screenshot": {
                    "path": step.screenshot_path,
                    "width": step.screenshot_width,
                    "height": step.screenshot_height,
                    "click_coordinates": {
                        "x": step.click_x,
                        "y": step.click_y
                    }
                },
                "timing": {
                    "click_timestamp": step.click_timestamp,
                    "speech_start": step.raw_speech_start,
                    "speech_end": step.raw_speech_end,
                    "speech_duration": (step.raw_speech_end - step.raw_speech_start) if step.raw_speech_start and step.raw_speech_end else None
                },
                "tts": {
                    "audio_path": step.tts_audio_path,
                    "duration_seconds": step.tts_duration_seconds
                },
                "created_at": step.created_at.isoformat() if step.created_at else None,
                "updated_at": step.updated_at.isoformat() if step.updated_at else None
            }
            for step in steps
        ],
        "statistics": {
            "total_steps": len(steps),
            "total_duration": sum(
                (step.raw_speech_end - step.raw_speech_start) 
                for step in steps 
                if step.raw_speech_start and step.raw_speech_end
            ) if steps else 0,
            "steps_with_screenshots": len([s for s in steps if s.screenshot_path]),
            "steps_with_text": len([s for s in steps if s.final_text]),
            "steps_with_tts": len([s for s in steps if s.tts_audio_path])
        }
    }
    
    if include_metadata:
        json_data["metadata"] = {
            "export_format": "json",
            "export_version": "1.0",
            "exported_at": datetime.utcnow().isoformat(),
            "exported_by": "НИР-Документ",
            "schema_version": "1.0"
        }
    
    # Возвращаем JSON как файл для скачивания
    json_content = json.dumps(json_data, ensure_ascii=False, indent=2)
    filename = f"{guide.title.replace(' ', '_').encode('ascii', 'ignore').decode('ascii')}.json"
    if not filename.replace('.json', ''):
        filename = f"guide_{guide.id}.json"
    
    return Response(
        content=json_content.encode('utf-8'),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
    )


def _create_pdf_html(guide: Guide, steps: list) -> str:
    """Создает красивый HTML для PDF с дизайном в стиле НИР-Документ."""
    
    steps_html = ""
    for step in steps:
        screenshot_html = ""
        if step.screenshot_path:
            # Получаем изображение как base64 для встраивания в PDF
            screenshot_base64 = _get_screenshot_base64(step.screenshot_path)
            if screenshot_base64:
                screenshot_html = f"""
                <div class="screenshot">
                    <img src="data:image/png;base64,{screenshot_base64}" alt="Шаг {step.step_number}" />
                    {f'<div class="click-marker" style="left: {step.click_x}px; top: {step.click_y}px;"><span>{step.step_number}</span></div>' if step.click_x and step.click_y else ''}
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
        
        steps_html += f"""
        <div class="step">
            <div class="step-header">
                <div class="step-number">{step.step_number}</div>
                <h3>Шаг {step.step_number}</h3>
            </div>
            {screenshot_html}
            <div class="step-text">
                <p>{step.final_text or f'Шаг {step.step_number}'}</p>
            </div>
        </div>
        """
    
    return f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <title>{guide.title}</title>
    </head>
    <body>
        <div class="document">
            <header class="header">
                <div class="logo">
                    <div class="logo-icon">НД</div>
                    <div class="logo-text">НИР-Документ</div>
                </div>
                <div class="guide-info">
                    <h1>{guide.title}</h1>
                    <div class="meta">
                        <span>Создано: {guide.created_at.strftime('%d.%m.%Y %H:%M') if guide.created_at else 'Неизвестно'}</span>
                        <span>Шагов: {len(steps)}</span>
                        <span>Статус: {'Черновик' if guide.status == GuideStatus.DRAFT else 'Готов'}</span>
                    </div>
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
        display: flex;
        align-items: center;
        gap: 20px;
        padding: 20px 0;
        border-bottom: 2px solid #ed8d48;
        margin-bottom: 30px;
    }
    
    .logo {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    .logo-icon {
        width: 40px;
        height: 40px;
        background: #ed8d48;
        color: white;
        border-radius: 6px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: 'Montserrat', sans-serif;
        font-weight: 700;
        font-size: 14px;
    }
    
    .logo-text {
        font-family: 'Montserrat', sans-serif;
        font-size: 16px;
        font-weight: 600;
        color: #333;
    }
    
    .guide-info h1 {
        font-family: 'Montserrat', sans-serif;
        font-size: 24px;
        font-weight: 600;
        color: #333;
        margin-bottom: 8px;
    }
    
    .meta {
        display: flex;
        gap: 20px;
        font-size: 12px;
        color: #666;
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
    
    html = md
    
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

def _get_screenshot_base64(screenshot_path: str) -> Optional[str]:
    """Получает скриншот как base64 строку для встраивания в PDF."""
    try:
        from app.services.storage import storage_service, StorageBucket
        
        # Получаем файл из MinIO (скриншоты хранятся в бакете SCREENSHOTS)
        file_data = storage_service.get_file(screenshot_path, StorageBucket.SCREENSHOTS)
        if file_data:
            # Кодируем в base64
            return base64.b64encode(file_data).decode('utf-8')
        
        logger.warning(f"Screenshot not found: {screenshot_path}")
        return None
        
    except Exception as e:
        logger.error(f"Failed to get screenshot {screenshot_path}: {e}")
        return None