"""
API: Export - экспорт гайда в Markdown/HTML.
GET /guides/{id}/export/markdown
GET /guides/{id}/export/html
"""

import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Guide, GuideStep, GuideStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/export", tags=["Export"])


@router.get("/markdown/{guide_id}")
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


@router.get("/html/{guide_id}")
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


@router.get("/pdf/{guide_id}")
async def export_pdf(
    guide_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Экспортировать гайд в PDF.
    
    Требует установленного wkhtmltopdf или подобного.
    """
    # Получаем HTML
    html_response = await export_html(guide_id, True, db)
    
    # TODO: Конвертация в PDF через wkhtmltopdf или weasyprint
    
    return {
        "success": False,
        "message": "PDF export not implemented",
        "note": "Requires wkhtmltopdf or weasyprint"
    }


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
