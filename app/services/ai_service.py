"""
AI Service - сервис для работы с нейросетями.
Обеспечивает ASR (распознавание речи), LLM (логический анализ) и TTS (озвучка).

AI Stack:
- LLM: OpenRouter API (Llama 3.1, Gemma 2 - бесплатно)
- TTS: Chatterbox TTS (нейронная озвучка с эмоциями)
"""

import asyncio
import logging
import os
import subprocess
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Type
from enum import Enum
from functools import lru_cache

import torch

from app.config import settings


logger = logging.getLogger(__name__)


class AIServiceError(Exception):
    """Базовый класс для ошибок AI-сервиса."""
    pass


class ModelLoadError(AIServiceError):
    """Ошибка загрузки модели."""
    pass


class InferenceError(AIServiceError):
    """Ошибка инференса модели."""
    pass


class UnsupportedLanguageError(AIServiceError):
    """Неподдерживаемый язык."""
    pass


@dataclass
class TranscriptionSegment:
    """Сегмент транскрипции с временными метками."""
    id: int
    start: float
    end: float
    text: str
    confidence: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь."""
        return {
            "id": self.id,
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "confidence": self.confidence,
        }


@dataclass
class TranscriptionResult:
    """Результат транскрипции аудио."""
    text: str
    segments: List[TranscriptionSegment]
    language: str
    duration: float
    confidence_avg: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь."""
        return {
            "text": self.text,
            "segments": [s.to_dict() for s in self.segments],
            "language": self.language,
            "duration": self.duration,
            "confidence_avg": self.confidence_avg,
        }


@dataclass
class LLMResponse:
    """Ответ от LLM."""
    text: str
    tokens_used: int
    model: str
    finish_reason: str
    processing_time: float


@dataclass
class GuideMetadata:
    """Метаданные гайда, сгенерированные AI."""
    title: str
    summary: str
    steps: List[Dict[str, Any]]
    tags: List[str]
    difficulty: str  # easy, medium, hard
    estimated_time: int  # минуты
    language: str


class BaseLLMProvider(ABC):
    """Абстрактный базовый класс для LLM-провайдеров."""
    
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """Генерация текста по промпту."""
        pass
    
    @abstractmethod
    async def analyze_text(self, text: str, analysis_type: str) -> Dict[str, Any]:
        """Анализ текста определенного типа."""
        pass


class LLMWrapper:
    """
    Интерфейс для работы с LLM через OpenRouter API.
    
    Поддерживает:
    - OpenRouter API (Llama 3.1, Gemma 2 и др. - бесплатно)
    - Groq API (быстрый инференс)
    - Локальные модели (fallback через llama-cpp-python)
    """
    
    def __init__(
        self,
        api_base: str = None,
        api_key: str = None,
        model: str = None,
        max_tokens: int = None,
        temperature: float = None,
    ):
        """
        Инициализация LLM.
        
        Args:
            api_base: URL API
            api_key: API ключ
            model: Название модели
            max_tokens: Максимум токенов
            temperature: Температура генерации
        """
        self.api_base = api_base or settings.LLM_API_BASE
        self.api_key = api_key or settings.LLM_API_KEY
        self.model = model or settings.LLM_MODEL
        self.max_tokens = max_tokens or settings.LLM_MAX_TOKENS
        self.temperature = temperature or settings.LLM_TEMPERATURE
        
        self.client = None
        self._init_client()
    
    def _init_client(self) -> None:
        """Инициализация API клиента."""
        if self.api_base and self.api_key:
            try:
                from openai import OpenAI
                base_url = self.api_base.rstrip('/')
                if not base_url.endswith('/v1'):
                    base_url += '/v1'
                self.client = OpenAI(
                    base_url=base_url,
                    api_key=self.api_key,
                )
                logger.info(f"LLM client initialized: {self.api_base}")
                logger.info(f"Using model: {self.model}")
            except Exception as e:
                logger.error(f"Failed to init LLM client: {e}")
                self.client = None
        else:
            logger.warning("No API config for LLM, using mock responses")
            self.client = None
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Генерация текста по промпту.
        
        Args:
            prompt: Основной промпт
            system_prompt: Системный промпт
            max_tokens: Максимум токенов
            temperature: Температура
            
        Returns:
            LLMResponse
        """
        import time
        
        start_time = time.time()
        
        if self.client is None:
            return self._mock_response(prompt, start_time)
        
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens or self.max_tokens,
                temperature=temperature or self.temperature,
            )
            
            processing_time = time.time() - start_time
            
            return LLMResponse(
                text=response.choices[0].message.content,
                tokens_used=response.usage.total_tokens if hasattr(response, 'usage') else 0,
                model=self.model,
                finish_reason=response.choices[0].finish_reason,
                processing_time=processing_time,
            )
            
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return self._mock_response(prompt, start_time, error=str(e))
    
    def _mock_response(
        self,
        prompt: str,
        start_time: float,
        error: Optional[str] = None
    ) -> LLMResponse:
        """Мок-ответ для тестирования без API."""
        import time
        
        processing_time = time.time() - start_time
        
        return LLMResponse(
            text=f"[MOCK] Generated response for: {prompt[:100]}...",
            tokens_used=100,
            model=self.model or "mock",
            finish_reason="mock",
            processing_time=processing_time,
        )
    
    async def generate_guide_title(
        self,
        transcript: str,
        language: str = "ru"
    ) -> str:
        """
        Генерация названия гайда на основе транскрипции.
        """
        system_prompt = """Ты - эксперт по созданию обучающего контента. 
Твоя задача - генерировать короткие, информативные названия для видео-инструкций.
Название должно быть:
- Кратким (не более 80 символов)
- Информативным (понятно о чем видео)
- Привлекательным (хочется посмотреть)
- На языке оригинала"""
        
        user_prompt = f"""Создай название для обучающего видео на основе этого содержания:

{transcript[:2000]}

Язык: {language}

Название:"""
        
        response = await self.generate(user_prompt, system_prompt)
        
        return response.text.strip().strip('"').strip("'")
    
    async def generate_step_descriptions(
        self,
        transcript: str,
        click_events: List[Dict[str, Any]],
        language: str = "ru"
    ) -> List[Dict[str, Any]]:
        """
        Генерация описаний шагов на основе транскрипции и кликов.
        """
        system_prompt = """Ты - AI-ассистент для создания обучающих видео.
Твоя задача - разбить транскрипцию на логические шаги и сопоставить их с действиями на экране.
Каждый шаг должен содержать:
- Описание действия
- Временные рамки
- Ключевые элементы интерфейса"""
        
        click_context = "\n".join([
            f"- Время: {c.get('time', 0):.2f}с, Элемент: {c.get('element', 'unknown')}, Координаты: {c.get('x', 0)}, {c.get('y', 0)}"
            for c in click_events[:20]
        ])
        
        user_prompt = f"""Разбери транскрипцию на логические шаги и сопоставь с действиями на экране.

Транскрипция:
{transcript}

Действия на экране:
{click_context}

Язык: {language}

Для каждого шага укажи:
1. Порядковый номер
2. Текст описания (краткий, понятный)
3. Временные рамки (start, end)
4. Тип действия (click, scroll, type, etc.)

Формат ответа - JSON массив объектов с полями: step_number, text, start_time, end_time, action_type, element_description"""

        response = await self.generate(
            user_prompt, 
            system_prompt,
            temperature=0.3,
        )
        
        import json
        try:
            text = response.text
            json_start = text.find("[")
            json_end = text.rfind("]") + 1
            
            if json_start >= 0 and json_end > json_start:
                json_text = text[json_start:json_end]
                return json.loads(json_text)
            
            return []
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse step descriptions: {e}")
            return []
    
    async def smart_align(
        self,
        transcript_segments: List[Dict[str, Any]],
        click_events: List[Dict[str, Any]],
        language: str = "ru"
    ) -> Dict[str, Any]:
        """
        Умная синхронизация (Smart Aligner).
        """
        system_prompt = """Ты - эксперт по монтажу обучающих видео.
Твоя задача - синхронизировать речь с действиями на экране, убирая "мёртвое время"."""
        
        segments_text = "\n".join([
            f"- {s.get('text', '')} ({(s.get('start', 0)):.2f}-{(s.get('end', 0)):.2f}с)"
            for s in transcript_segments
        ])
        
        clicks_text = "\n".join([
            f"- {c.get('element', 'click')} @ {c.get('time', 0):.2f}с"
            for c in click_events
        ])
        
        user_prompt = f"""Выполни умную синхронизацию.

Сегменты речи:
{segments_text}

Клики на экране:
{clicks_text}

Язык: {language}

Верни JSON объект с полями:
- aligned_steps: массив объектов с полями (original_start, original_end, new_start, new_end, text, action)
- removed_silence_seconds: общее количество удаленных секунд
- explanation: краткое описание что было сделано"""

        response = await self.generate(user_prompt, system_prompt)
        
        try:
            import json
            text = response.text
            json_start = text.find("{")
            json_end = text.rfind("}") + 1
            
            if json_start >= 0 and json_end > json_start:
                return json.loads(text[json_start:json_end])
            
            return {"aligned_steps": [], "removed_silence_seconds": 0}
            
        except (json.JSONDecodeError, ValueError):
            return {"aligned_steps": [], "removed_silence_seconds": 0}
    
    async def generate_wiki_content(
        self,
        steps: List[Dict[str, Any]],
        guide_title: str,
        language: str = "ru"
    ) -> str:
        """
        Генерация Wiki-статьи в Markdown-формате.
        """
        system_prompt = """Ты - технический писатель, создающий документацию.
Твоя задача - генерировать чистые, понятные инструкции в формате Markdown."""
        
        steps_text = "\n".join([
            f"{i+1}. {s.get('text', s.get('description', ''))}"
            for i, s in enumerate(steps[:50])
        ])
        
        user_prompt = f"""Создай Wiki-статью в формате Markdown.

Гайд: {guide_title}
Язык: {language}

Шаги:
{steps_text}

Напиши полноценную статью с объяснениями, советами и примерами где уместно."""

        response = await self.generate(user_prompt, system_prompt, max_tokens=4000)
        
        return response.text
    
    async def extract_tags(
        self,
        guide_content: str,
        max_tags: int = 5
    ) -> List[str]:
        """
        Извлечение тегов из содержания гайда.
        """
        system_prompt = """Ты - специалист по тегированию контента.
Извлеки ключевые слова и теги из обучающего материала."""
        
        user_prompt = f"""Извлеки {max_tags} ключевых тегов из этого содержания:

{guide_content[:1500]}

Верни только список тегов, по одному на строку."""

        response = await self.generate(user_prompt, system_prompt)
        
        tags = [
            line.strip().strip("-").strip()
            for line in response.text.split("\n")
            if line.strip() and len(line.strip()) > 1
        ]
        
        return tags[:max_tags]
    
    async def normalize_instruction(
        self,
        raw_speech: str,
        context: Optional[str] = None,
        language: str = "ru"
    ) -> str:
        """
        Нормализовать "сырую" речь в чистую инструкцию.
        
        Это ключевой метод MVP: превращает "эм, ну надо нажать вот сюда на кнопку начать"
        в "Нажмите кнопку 'Начать'".
        """
        if not raw_speech or raw_speech.strip() == "":
            return ""
        
        system_prompt = """Ты — AI-ассистент, который превращает записанную речь в чёткие инструкции.
Твоя задача — очистить текст от слов-паразитов и сформулировать краткую команду.

ПРАВИЛА:
1. УБИРАЙ: "эм", "ну", "вот", "сюда", "тут", "щас", "ща", "понимаешь", "вот тут"
2. УБИРАЙ повторы слов и фраз
3. ИСПОЛЬЗУЙ повелительный тон на "ВЫ" или "ты" (без вежливых форм типа "нажмите, пожалуйста")
4. НАЗЫВАЙ элементы интерфейса так, как они выглядят: "кнопка 'Начать'", "поле 'Email'", "иконка меню"
5. СОХРАНЯЙ смысл действия
6. БУДЬ кратким — одна короткая фраза

ПРИМЕРЫ:
- "эм, ну надо нажать вот сюда на кнопку начать" → "Нажмите кнопку «Начать»"
- "ну вот тут нажимаем на это меню" → "Нажмите меню"
- "щас вводим сюда email" → "Введите email"
- "нажмите кнопочку сохранить пожалуйста" → "Нажмите «Сохранить»"
- "и вот тут видишь нужно кликнуть на этот файл" → "Кликните файл"

ВХОДНОЙ ТЕКСТ: "{raw_speech}"

ВЫХОД: Только нормализованная инструкция, без объяснений."""

        user_prompt = f"Текст для нормализации:\n\n{raw_speech}"

        if context:
            system_prompt = system_prompt.replace(
                "ВХОДНОЙ ТЕКСТ:",
                f"КОНТЕКСТ: {context}\n\nВХОДНОЙ ТЕКСТ:"
            )

        response = await self.generate(
            user_prompt,
            system_prompt,
            max_tokens=100,
            temperature=0.3
        )

        result = response.text.strip()
        
        if result.startswith('"') and result.endswith('"'):
            result = result[1:-1]
        if result.startswith("«") and result.endswith("»"):
            result = result[1:-1]
        
        logger.debug(f"Normalized: '{raw_speech[:30]}...' → '{result[:30]}...'")
        
        return result


class AIService:
    """
    Центральный сервис для координации AI-компонентов.
    
    Объединяет:
    - LLMWrapper для логического анализа
    - ChatterboxService для нейронной озвучки (отдельный модуль)
    """
    
    def __init__(self):
        """Инициализация AI-сервиса."""
        self.llm = LLMWrapper()
        
        logger.info("AI Service initialized")
    
    async def process_recording(
        self,
        video_path: str,
        audio_path: str,
        click_events: List[Dict[str, Any]],
        language: str = "ru"
    ) -> Dict[str, Any]:
        """
        Полная обработка записи с генерацией метаданных гайда.
        
        Note: Транскрипция аудио отключена (Whisper удален).
        Метод оставлен для совместимости, но не выполняет полную обработку.
        """
        logger.warning("Audio transcription disabled - Whisper removed from project")
        logger.info(f"AI processing requested for: {video_path}")
        
        return {
            "status": "disabled",
            "message": "Whisper transcription removed. Use alternative transcription method if needed.",
        }
    
    async def regenerate_step_audio(
        self,
        text: str,
        voice: str = None,
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Перегенерация аудио для одного шага.
        """
        from app.services.tts_service import tts_service
        
        result = await tts_service.generate_audio(text, voice)
        
        return {
            "success": result.success,
            "audio_path": result.audio_path,
            "duration_seconds": result.duration_seconds,
            "error": result.error,
        }
    
    def analyze_screenshot(
        self,
        screenshot_path: str,
        click_x: Optional[float] = None,
        click_y: Optional[float] = None,
        viewport_width: Optional[int] = None,
        viewport_height: Optional[int] = None,
        element_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Анализ скриншота с помощью Vision AI для генерации инструкции.

        Ключевая идея: место клика делается явно видимым для модели —
        на скриншот наносится маркер, плюс отдельно подаётся увеличенный
        фрагмент вокруг клика. Так модель «смотрит, на что нажали», а не
        описывает страницу в целом.

        Args:
            screenshot_path: Путь к файлу скриншота
            click_x: X координата клика (опционально)
            click_y: Y координата клика (опционально)
            viewport_width: Ширина viewport (опционально)
            viewport_height: Высота viewport (опционально)
            element_hint: Текст/описание элемента из DOM (подпись кнопки,
                alt картинки и т.п.) — подсказка для модели (опционально)

        Returns:
            Dict с ключом 'instruction' содержащим сгенерированную инструкцию
        """
        import base64
        from openai import OpenAI
        from app.config import settings
        from app.services.screenshot_processor import render_click_focus

        logger.info(f"Analyzing screenshot: {screenshot_path} (click={click_x},{click_y})")

        # Без настроенного бэкенда Vision молча падать нельзя — это и есть
        # причина «Нажмите на элемент DIV». Сообщаем явно.
        if not settings.LLM_API_BASE or not settings.LLM_API_KEY:
            msg = "Vision backend is not configured (LLM_API_BASE/LLM_API_KEY empty)"
            logger.error(msg)
            return {"instruction": None, "success": False, "error": msg}

        try:
            content: List[Dict[str, Any]] = []
            has_click = click_x is not None and click_y is not None

            hint_line = ""
            if element_hint and element_hint.strip():
                hint_line = (
                    f'\nПодсказка (что говорил пользователь либо подпись элемента под кликом): '
                    f'"{element_hint.strip()[:120]}". Используй её для названия элемента и цели шага, '
                    f'если она осмысленна.'
                )

            if has_click:
                # Готовим маркированный скрин + увеличенный фрагмент вокруг клика.
                # Размеры вьюпорта нужны, чтобы пересчитать CSS-координаты клика
                # в пиксели картинки (DPR/масштаб экрана) — иначе маркер уезжает.
                focus = render_click_focus(
                    screenshot_path, int(click_x), int(click_y),
                    viewport_width=viewport_width, viewport_height=viewport_height,
                )
                # На 8 ГБ VRAM полный скрин можно отключить (VISION_SEND_FULL_IMAGE),
                # чтобы экономить видео-токены и не словить OOM на тяжёлой модели.
                send_full = settings.VISION_SEND_FULL_IMAGE and focus is not None

                if send_full:
                    images_desc = (
                        "Тебе дано ДВА изображения одного и того же шага:\n"
                        "1) Полный скриншот страницы — место клика отмечено оранжевым круглым маркером.\n"
                        "2) Увеличенный фрагмент вокруг этого же маркера — чтобы рассмотреть элемент."
                    )
                else:
                    images_desc = (
                        "Тебе дан увеличенный фрагмент страницы вокруг места клика — "
                        "оно отмечено оранжевым круглым маркером."
                    )

                prompt = f"""Ты пишешь ОДИН шаг пошаговой инструкции (как Guidde/Scribe, но точнее).

{images_desc}

Смотри ИМЕННО на элемент под оранжевым маркером (а не на страницу в целом).{hint_line}

ШАГ 1. Мысленно определи ТИП элемента под маркером:
- поле ввода / строка поиска
- выпадающий список / селектор / переключатель раздела
- ссылка / вкладка / пункт меню (навигация)
- чекбокс / тумблер / переключатель вкл-выкл
- кнопка действия (с подписью: Сохранить, Создать, Отправить…)
- значок / иконка без подписи (шестерёнка, профиль, плюс, корзина…)

ШАГ 2. Подбери ГЛАГОЛ строго по типу (НЕ начинай всё со слова «Кликните»):
- поле ввода / поиск → «Введите …» или «Укажите …»
- список / селектор / меню → «Откройте …», «Раскройте …» или «Выберите …»
- ссылка / вкладка / пункт меню → «Перейдите в …» или «Откройте раздел …»
- чекбокс / тумблер → «Включите …» или «Отметьте …»
- кнопка действия → «Нажмите «…»»
- значок / иконка → «Нажмите на значок …» (назови, что на значке)

Слово «Кликните» допустимо ТОЛЬКО когда ничего из перечисленного не подходит.

ПРАВИЛА:
- Одно короткое предложение, максимум 10 слов.
- Назови КОНКРЕТНЫЙ элемент и его подпись в кавычках «…».
- Грамотный русский язык, без опечаток и канцелярита.
- Не упоминай скриншот, маркер, теги (DIV/BUTTON) и не описывай страницу в целом.

Примеры ХОРОШИХ инструкций:
✅ "Нажмите «Сохранить» в правом верхнем углу"
✅ "Введите адрес электронной почты в поле «Email»"
✅ "Перейдите в раздел «Настройки» в боковом меню"
✅ "Откройте список «Статус» и выберите значение"
✅ "Включите переключатель «Уведомления»"
✅ "Нажмите на значок профиля"

НЕ делай так:
❌ "На скриншоте изображена страница с кнопкой..."
❌ "Кликните на элемент DIV"
❌ "Пользователь видит интерфейс, где находится..."

Выведи ТОЛЬКО итоговую инструкцию, без пояснений. На русском языке."""

                content.append({"type": "text", "text": prompt})

                if focus:
                    if send_full:
                        content.append({"type": "image_url", "image_url": {
                            "url": f"data:image/png;base64,{focus['full']}"}})
                    content.append({"type": "image_url", "image_url": {
                        "url": f"data:image/png;base64,{focus['crop']}"}})
                else:
                    # Не удалось отрисовать маркер — отправляем хотя бы оригинал
                    with open(screenshot_path, "rb") as f:
                        raw = base64.b64encode(f.read()).decode('utf-8')
                    content.append({"type": "image_url", "image_url": {
                        "url": f"data:image/png;base64,{raw}"}})
            else:
                prompt = f"""Ты создаёшь один шаг пошаговой инструкции.

На скриншоте показан один шаг действия.{hint_line}

Напиши ОДНО короткое предложение (максимум 10 слов):
- Начни с «Откройте», «Перейдите» или «Просмотрите»
- Укажи название страницы или раздела
- Грамотный русский язык, без опечаток
- Не упоминай скриншот и не описывай страницу в целом

Отвечай ТОЛЬКО инструкцией, без лишних слов. На русском языке."""
                with open(screenshot_path, "rb") as f:
                    raw = base64.b64encode(f.read()).decode('utf-8')
                content.append({"type": "text", "text": prompt})
                content.append({"type": "image_url", "image_url": {
                    "url": f"data:image/png;base64,{raw}"}})

            client = OpenAI(
                base_url=settings.LLM_API_BASE,
                api_key=settings.LLM_API_KEY,
            )

            response = client.chat.completions.create(
                model=settings.VISION_MODEL,
                messages=[{"role": "user", "content": content}],
                max_tokens=100,   # Короткие инструкции
                temperature=0.4,  # Чуть выше — чтобы не залипать на «Кликните»
            )

            instruction = response.choices[0].message.content.strip()
            logger.info(f"Generated instruction: {instruction[:100]}...")

            return {
                "instruction": instruction,
                "success": True,
            }

        except Exception as e:
            logger.error(f"Error analyzing screenshot: {e}", exc_info=True)
            return {
                "instruction": None,
                "success": False,
                "error": str(e),
            }
    
    def improve_step_text(
        self,
        base_text: str,
        element_hint: Optional[str] = None,
        language: str = "ru",
    ) -> Dict[str, Any]:
        """
        Улучшить УЖЕ существующий текст шага, не переписывая его с нуля.

        Берёт текст, который написал/наговорил пользователь, как ОСНОВУ и только:
        - исправляет орфографию, пунктуацию и грамматику,
        - убирает слова-паразиты и канцелярит,
        - приводит к формату короткой инструкции (повелительный глагол).
        Смысл и выбранный пользователем элемент сохраняются. Если улучшать
        нечего — текст возвращается почти без изменений. Пустой результат
        не возвращается, чтобы вызывающий код не затёр работу пользователя.

        Returns:
            Dict с ключами 'text' (улучшенный текст), 'success', 'error'.
        """
        from openai import OpenAI

        if not base_text or not base_text.strip():
            return {"text": None, "success": False, "error": "empty base text"}

        if not settings.LLM_API_BASE or not settings.LLM_API_KEY:
            msg = "LLM backend is not configured (LLM_API_BASE/LLM_API_KEY empty)"
            logger.error(msg)
            return {"text": None, "success": False, "error": msg}

        hint_line = ""
        if element_hint and element_hint.strip():
            hint_line = (
                f'\nКонтекст (что говорил пользователь / подпись элемента): '
                f'"{element_hint.strip()[:160]}".'
            )

        system_prompt = """Ты — редактор пошаговых инструкций.
Тебе дают ОДИН шаг, который написал пользователь. Улучши его, НЕ меняя смысл.

ПРАВИЛА:
1. СОХРАНЯЙ действие и элемент, выбранные пользователем. Не выдумывай новые.
2. Исправь орфографию, пунктуацию и грамматику.
3. Убери слова-паразиты, повторы и канцелярит.
4. Приведи к короткой инструкции с повелительным глаголом (Нажмите, Введите, Откройте, Выберите, Перейдите, Включите).
5. Названия элементов — в кавычках «…».
6. Одно короткое предложение, максимум 12 слов.
7. Если текст уже хороший — верни его почти без изменений.

Отвечай ТОЛЬКО улучшенным текстом, без пояснений."""

        user_prompt = f'Текст шага: "{base_text.strip()}"{hint_line}'

        try:
            client = OpenAI(
                base_url=settings.LLM_API_BASE,
                api_key=settings.LLM_API_KEY,
            )
            # Тот же бэкенд, что и Vision — VISION_MODEL гарантированно доступна
            # на этом эндпоинте и нормально справляется с чисто текстовой задачей.
            model = settings.VISION_MODEL

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=80,
                temperature=0.3,
            )

            text = (response.choices[0].message.content or "").strip()

            # Снимаем обрамляющие кавычки, если модель их добавила
            if len(text) >= 2 and text[0] in '"«' and text[-1] in '"»':
                text = text[1:-1].strip()

            if not text:
                return {"text": None, "success": False, "error": "empty result"}

            logger.info(f"Improved step text: '{base_text[:40]}...' -> '{text[:40]}...'")
            return {"text": text, "success": True}

        except Exception as e:
            logger.error(f"Error improving step text: {e}", exc_info=True)
            return {"text": None, "success": False, "error": str(e)}

    def close(self) -> None:
        """Освобождение ресурсов."""
        logger.info("AI Service closed")


# Экземпляр сервиса для использования в приложении
ai_service = AIService()
