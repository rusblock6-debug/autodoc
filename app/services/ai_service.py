"""
AI Service - сервис для работы с нейросетями.
Обеспечивает ASR (распознавание речи), LLM (логический анализ) и TTS (озвучка).

AI Stack:
- ASR: OpenAI Whisper (через Groq API или локально)
- LLM: OpenRouter API (Llama 3.1, Gemma 2 - бесплатно)
- TTS: Edge TTS / Coqui XTTS v2
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


class WhisperModelSize(str, Enum):
    """Доступные размеры модели Whisper (для локальной версии)."""
    TINY = "tiny"
    BASE = "base"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large-v3"
    TURBO = "turbo"


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


class WhisperASR:
    """
    Модуль Automatic Speech Recognition на базе OpenAI Whisper.
    
    Поддерживает:
    - Groq API (рекомендуется, быстрее локального)
    - OpenAI API (если есть кредиты)
    - Локальный Whisper (fallback)
    """
    
    def __init__(
        self,
        api_base: str = None,
        api_key: str = None,
        model: str = None,
        device: str = None,
    ):
        """
        Инициализация ASR-модуля.
        
        Args:
            api_base: URL API (Groq или OpenAI)
            api_key: API ключ
            model: Модель Whisper
            device: Устройство для локальной версии (cuda, cpu)
        """
        self.api_base = api_base or settings.WHISPER_API_BASE
        self.api_key = api_key or settings.WHISPER_API_KEY
        self.model = model or settings.WHISPER_MODEL
        self.device = device or getattr(settings, 'WHISPER_DEVICE', 'cpu')
        
        self.client = None
        self._init_client()
    
    def _init_client(self) -> None:
        """Инициализация API клиента."""
        # Если есть API настройки - используем API
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
                logger.info(f"Whisper API client initialized: {self.api_base}")
            except Exception as e:
                logger.error(f"Failed to init API client: {e}")
                self.client = None
        else:
            # Fallback на локальный Whisper
            logger.info("No API config, using local Whisper")
            self._load_local_model()
    
    def _load_local_model(self) -> None:
        """Загрузка локальной модели Whisper."""
        try:
            import whisper
            model_size = getattr(settings, 'WHISPER_MODEL_SIZE', 'medium')
            logger.info(f"Loading local Whisper model '{model_size}' on {self.device}")
            self.model = whisper.load_model(
                model_size,
                device=self.device,
            )
            logger.info("Local Whisper model loaded")
        except Exception as e:
            logger.error(f"Failed to load local Whisper: {e}")
            raise ModelLoadError(f"Whisper model loading failed: {e}")
    
    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        verbose: bool = False,
        initial_prompt: Optional[str] = None,
    ) -> TranscriptionResult:
        """
        Транскрипция аудиофайла в текст.
        
        Args:
            audio_path: Путь к аудиофайлу
            language: Язык аудио (опционально)
            verbose: Подробный вывод
            initial_prompt: Начальный промпт
            
        Returns:
            TranscriptionResult
        """
        if not Path(audio_path).exists():
            raise InferenceError(f"Audio file not found: {audio_path}")
        
        logger.info(f"Starting transcription: {audio_path}")
        
        # Используем API если доступен
        if self.client:
            return self._transcribe_api(audio_path, language)
        else:
            return self._transcribe_local(audio_path, language)
    
    def _transcribe_api(self, audio_path: str, language: Optional[str]) -> TranscriptionResult:
        """Транскрипция через API."""
        try:
            with open(audio_path, "rb") as audio_file:
                response = self.client.audio.transcriptions.create(
                    model=self.model or "whisper-1",
                    file=audio_file,
                    language=language,
                    response_format="verbose_json",
                    timestamp_granularities=["segment", "word"]
                )
            
            # Парсим результат
            segments = []
            text_parts = []
            
            for i, seg in enumerate(response.segments):
                segments.append(TranscriptionSegment(
                    id=i,
                    start=seg.start,
                    end=seg.end,
                    text=seg.text.strip(),
                    confidence=getattr(seg, 'comprehension_score', 0.9) or 0.9,
                ))
                text_parts.append(seg.text)
            
            duration = max((s.end for s in segments), default=0.0)
            
            return TranscriptionResult(
                text=" ".join(text_parts),
                segments=segments,
                language=getattr(response, 'language', None) or language or "ru",
                duration=duration,
                confidence_avg=0.9,
            )
            
        except Exception as e:
            logger.error(f"API transcription failed: {e}")
            raise InferenceError(f"ASR API error: {e}")
    
    def _transcribe_local(self, audio_path: str, language: Optional[str]) -> TranscriptionResult:
        """Транскрипция локальной модели Whisper."""
        import whisper
        
        try:
            options = dict(
                language=language,
                verbose=False,
                best_of=5,
                beam_size=5,
                word_timestamps=True,
                fp16=(self.device == "cuda"),
            )
            
            result = self.model.transcribe(audio_path, **options)
            segments = self._parse_segments(result.get("segments", []))
            
            confidences = [s.confidence for s in segments if s.confidence > 0]
            confidence_avg = sum(confidences) / len(confidences) if confidences else 0.0
            
            detected_language = result.get("language", language or "ru")
            duration = max((s.end for s in segments), default=0.0)
            
            return TranscriptionResult(
                text=result["text"],
                segments=segments,
                language=detected_language,
                duration=duration,
                confidence_avg=confidence_avg,
            )
            
        except Exception as e:
            logger.error(f"Local transcription failed: {e}")
            raise InferenceError(f"ASR local error: {e}")
    
    def _parse_segments(self, whisper_segments: List[Dict]) -> List[TranscriptionSegment]:
        """Парсинг сегментов из результата Whisper."""
        parsed = []
        
        for i, seg in enumerate(whisper_segments):
            if isinstance(seg, dict):
                start = seg.get("start", 0.0)
                end = seg.get("end", 0.0)
                text = seg.get("text", "").strip()
                
                confidence = seg.get("probability", 0.0)
                if confidence == 0.0 and seg.get("words"):
                    word_probs = [w.get("probability", 0.5) for w in seg["words"]]
                    confidence = sum(word_probs) / len(word_probs) if word_probs else 0.5
                
                words = []
                if seg.get("words"):
                    for w in seg["words"]:
                        words.append({
                            "word": w.get("word", ""),
                            "start": w.get("start", 0.0),
                            "end": w.get("end", 0.0),
                            "probability": w.get("probability", 0.5),
                        })
                
                parsed.append(TranscriptionSegment(
                    id=i,
                    start=start,
                    end=end,
                    text=text,
                    confidence=confidence,
                ))
            else:
                try:
                    parsed.append(TranscriptionSegment(
                        id=i,
                        start=seg[0],
                        end=seg[1],
                        text=seg[2].strip(),
                        confidence=0.9,
                    ))
                except (IndexError, TypeError):
                    continue
        
        return parsed
    
    def transcribe_streaming(
        self,
        audio_stream: bytes,
        chunk_size: int = 4096,
        language: Optional[str] = None
    ) -> TranscriptionResult:
        """
        Транскрипция потокового аудио.
        """
        temp_dir = getattr(settings, 'TEMP_DIR', '/tmp')
        Path(temp_dir).mkdir(parents=True, exist_ok=True)
        temp_audio = Path(temp_dir) / f"stream_{uuid.uuid4().hex}.wav"
        
        try:
            with open(temp_audio, "wb") as f:
                f.write(audio_stream)
            
            return self.transcribe(str(temp_audio), language=language)
            
        finally:
            if temp_audio.exists():
                temp_audio.unlink()
    
    def close(self) -> None:
        """Освобождение ресурсов модели."""
        if self.model is not None:
            del self.model
            self.model = None
            
            if torch.cuda.is_available():
                torch.cuda.empty_cache()


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
    - WhisperASR для распознавания речи
    - LLMWrapper для логического анализа
    - TTSService для озвучки (отдельный модуль)
    """
    
    def __init__(self):
        """Инициализация AI-сервиса."""
        self.asr = WhisperASR()
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
        """
        logger.info(f"Starting AI processing for: {video_path}")
        
        results = {}
        
        # 1. Транскрипция аудио
        logger.info("Step 1: Transcribing audio with Whisper...")
        transcription = self.asr.transcribe(audio_path, language=language)
        results["transcription"] = transcription.to_dict()
        
        # 2. Генерация названия гайда
        logger.info("Step 2: Generating guide title...")
        title = await self.llm.generate_guide_title(transcription.text, language)
        results["title"] = title
        
        # 3. Генерация описаний шагов
        logger.info("Step 3: Generating step descriptions...")
        steps = await self.llm.generate_step_descriptions(
            transcription.text,
            click_events,
            language
        )
        results["steps"] = steps
        
        # 4. Умная синхронизация
        logger.info("Step 4: Smart alignment...")
        alignment = await self.llm.smart_align(
            transcription.segments,
            click_events,
            language
        )
        results["alignment"] = alignment
        
        # 5. Генерация Wiki-контента
        logger.info("Step 5: Generating Wiki content...")
        wiki_content = await self.llm.generate_wiki_content(steps, title, language)
        results["wiki_content"] = wiki_content
        
        # 6. Извлечение тегов
        logger.info("Step 6: Extracting tags...")
        tags = await self.llm.extract_tags(transcription.text)
        results["tags"] = tags
        
        return results
    
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
    
    def close(self) -> None:
        """Освобождение ресурсов."""
        if self.asr:
            self.asr.close()
        
        logger.info("AI Service closed")


# Экземпляр сервиса для использования в приложении
ai_service = AIService()
