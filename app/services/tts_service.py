"""
TTS Service - сервис для генерации речи из текста.
Поддерживает два движка:
- Edge TTS (Microsoft Edge Neural Voices) - быстрый, качественный
- Coqui XTTS v2 - для клонирования голоса пользователя

TTS Stack:
- Базовый: edge-tts (Microsoft Edge Neural Voices)
- Продвинутый: Coqui XTTS v2 (опционально) - для клонирования голоса
"""

import asyncio
import logging
import os
import subprocess
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any
from enum import Enum

from app.config import settings


logger = logging.getLogger(__name__)


class TTSEngine(str, Enum):
    """Доступные движки TTS."""
    EDGE_TTS = "edge-tts"
    COQUI_XTTS = "coqui-xtts"


@dataclass
class TTSResult:
    """Результат генерации аудио."""
    success: bool
    audio_path: Optional[str] = None
    duration_seconds: Optional[float] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь."""
        return {
            "success": self.success,
            "audio_path": self.audio_path,
            "duration_seconds": self.duration_seconds,
            "error": self.error,
        }


class BaseTTSProvider(ABC):
    """Абстрактный базовый класс для TTS-провайдеров."""
    
    @abstractmethod
    async def generate(
        self,
        text: str,
        output_path: Optional[str] = None,
        voice: Optional[str] = None,
        speed: float = 1.0,
        pitch: float = 0.0,
        **kwargs
    ) -> TTSResult:
        """Генерация аудио из текста."""
        pass
    
    @abstractmethod
    def get_available_voices(self) -> List[Dict[str, str]]:
        """Получение списка доступных голосов."""
        pass


class EdgeTTSProvider(BaseTTSProvider):
    """
    Провайдер Edge TTS на базе Microsoft Edge Neural Voices.
    
    Преимущества:
    - Высокое качество нейронных голосов
    - Поддержка множества языков включая русский
    - Быстрая генерация
    - Бесплатный
    
    Недостатки:
    - Требует интернет-соединения
    - Нет возможности клонирования голоса
    """
    
    def __init__(self):
        """Инициализация провайдера."""
        self.voice = settings.EDGE_TTS_VOICE
        self.output_dir = Path(settings.TEMP_DIR) / "tts_output"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Кэш доступных голосов
        self._voices_cache: Optional[List[Dict[str, str]]] = None
    
    async def generate(
        self,
        text: str,
        output_path: Optional[str] = None,
        voice: Optional[str] = None,
        speed: float = 1.0,
        pitch: float = 0.0,
        **kwargs
    ) -> TTSResult:
        """
        Генерация аудио через Edge TTS.
        
        Args:
            text: Текст для озвучки
            output_path: Путь для сохранения (опционально)
            voice: Голос (опционально)
            speed: Скорость (0.5 - 2.0)
            pitch: Высота тона (-20 - 20)
            
        Returns:
            TTSResult с результатом
        """
        # Проверка входных данных
        if not text or not text.strip():
            return TTSResult(success=False, error="Empty text provided")
        
        # Ограничение длины текста
        if len(text) > 5000:
            text = text[:5000]
            logger.warning("Text truncated to 5000 characters")
        
        voice = voice or self.voice
        output_path = output_path or str(
            self.output_dir / f"tts_{uuid.uuid4().hex}.mp3"
        )
        
        try:
            # Формируем команду для edge-tts
            cmd = [
                "edge-tts",
                "--text", text,
                "--voice", voice,
                "--write-media", output_path,
            ]
            
            # Добавляем скорость если отличается от 1.0
            if speed != 1.0:
                # edge-tts использует формат +N% или -N%
                speed_percent = int((speed - 1.0) * 100)
                rate = f"+{speed_percent}%" if speed_percent >= 0 else f"{speed_percent}%"
                cmd.extend(["--rate", rate + "+50"])  # +50 для коррекции
            
            # Добавляем pitch если отличается от 0
            if pitch != 0:
                pitch_str = f"+{pitch}Hz" if pitch >= 0 else f"{pitch}Hz"
                cmd.extend(["--pitch", pitch_str])
            
            # Выполняем команду
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='ignore')
                logger.error(f"Edge TTS failed: {error_msg}")
                return TTSResult(
                    success=False,
                    error=f"TTS generation failed: {error_msg[:200]}"
                )
            
            # Проверяем что файл создан
            if not Path(output_path).exists():
                return TTSResult(success=False, error="Output file not created")
            
            # Получаем длительность
            duration = self._get_audio_duration(output_path)
            
            logger.info(f"Edge TTS generated: {output_path} ({duration:.2f}s)")
            
            return TTSResult(
                success=True,
                audio_path=output_path,
                duration_seconds=duration,
            )
            
        except FileNotFoundError:
            logger.error("edge-tts not found. Install with: pip install edge-tts")
            return TTSResult(
                success=False,
                error="edge-tts not installed. Run: pip install edge-tts"
            )
        except Exception as e:
            logger.error(f"Edge TTS error: {e}")
            return TTSResult(success=False, error=str(e))
    
    def _get_audio_duration(self, audio_path: str) -> float:
        """Получение длительности аудиофайла через ffprobe."""
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                audio_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return float(result.stdout.strip())
            
        except (ValueError, subprocess.TimeoutExpired):
            return 0.0
    
    def get_available_voices(self) -> List[Dict[str, str]]:
        """Получение списка доступных голосов Edge TTS."""
        if self._voices_cache is not None:
            return self._voices_cache
        
        try:
            # Получаем список голосов через edge-tts
            cmd = ["edge-tts", "--list-voices"]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            voices = []
            for line in result.stdout.split("\n"):
                if line.strip() and ":" in line:
                    key, value = line.split(":", 1)
                    voices.append({
                        "id": key.strip(),
                        "name": value.strip(),
                        "engine": "edge-tts",
                    })
            
            self._voices_cache = voices
            return voices
            
        except Exception as e:
            logger.error(f"Failed to list voices: {e}")
            return []
    
    def get_russian_voices(self) -> List[Dict[str, str]]:
        """Получение русскоязычных голосов."""
        all_voices = self.get_available_voices()
        
        russian_voices = [
            v for v in all_voices 
            if "ru-" in v.get("id", "").lower() or 
               "russian" in v.get("name", "").lower()
        ]
        
        return russian_voices


class CoquiXTTSProvider(BaseTTSProvider):
    """
    Провайдер Coqui XTTS v2 для клонирования голоса.
    
    Преимущества:
    - Возможность клонирования голоса по образцу
    - Работа без интернета (on-premise)
    - Полный контроль над процессом
    
    Недостатки:
    - Требует GPU для быстрой работы
    - Большая модель (~1.5GB)
    - Сложнее в настройке
    """
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Инициализация провайдера Coqui XTTS.
        
        Args:
            model_path: Путь к модели (опционально)
        """
        self.model_path = model_path or settings.COQUI_MODEL_PATH
        self.output_dir = Path(settings.TEMP_DIR) / "coqui_output"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.model = None
        self._init_model()
    
    def _init_model(self) -> None:
        """Инициализация модели Coqui XTTS."""
        try:
            from TTS.api import TTS
            
            logger.info(f"Loading Coqui XTTS model from {self.model_path}")
            
            # Загружаем модель
            self.model = TTS(
                model_path=self.model_path,
                progress_bar=False,
                gpu=True  # Используем GPU если доступен
            )
            
            logger.info("Coqui XTTS model loaded successfully")
            
        except ImportError as e:
            logger.warning(f"Coqui TTS not installed: {e}")
            self.model = None
        except Exception as e:
            logger.error(f"Failed to load Coqui model: {e}")
            self.model = None
    
    async def generate(
        self,
        text: str,
        output_path: Optional[str] = None,
        voice: Optional[str] = None,
        speed: float = 1.0,
        **kwargs
    ) -> TTSResult:
        """
        Генерация аудио через Coqui XTTS.
        
        Args:
            text: Текст для озвучки
            output_path: Путь для сохранения
            voice: Путь к аудио-образцу голоса (для клонирования)
            speed: Скорость
            
        Returns:
            TTSResult с результатом
        """
        if not text or not text.strip():
            return TTSResult(success=False, error="Empty text provided")
        
        if self.model is None:
            return TTSResult(success=False, error="Coqui model not loaded")
        
        output_path = output_path or str(
            self.output_dir / f"coqui_{uuid.uuid4().hex}.wav"
        )
        
        try:
            # Запускаем синхронную генерацию в отдельном потоке
            loop = asyncio.get_event_loop()
            
            await loop.run_in_executor(
                None,
                lambda: self.model.tts_to_file(
                    text=text,
                    file_path=output_path,
                    speaker=voice,  # Путь к референсному аудио
                    speed=speed,
                )
            )
            
            if not Path(output_path).exists():
                return TTSResult(success=False, error="Output file not created")
            
            duration = self._get_audio_duration(output_path)
            
            logger.info(f"Coqui TTS generated: {output_path} ({duration:.2f}s)")
            
            return TTSResult(
                success=True,
                audio_path=output_path,
                duration_seconds=duration,
            )
            
        except Exception as e:
            logger.error(f"Coqui TTS error: {e}")
            return TTSResult(success=False, error=str(e))
    
    def _get_audio_duration(self, audio_path: str) -> float:
        """Получение длительности аудиофайла."""
        try:
            from pydub import AudioSegment
            
            audio = AudioSegment.from_file(audio_path)
            return len(audio) / 1000.0
            
        except Exception:
            return 0.0
    
    def get_available_voices(self) -> List[Dict[str, str]]:
        """Получение списка доступных голосов."""
        # Coqui XTTS не имеет "голосов" в традиционном понимании
        # Голос определяется через аудио-образец
        return [
            {
                "id": "clone_voice",
                "name": "Custom Voice (requires audio sample)",
                "engine": "coqui-xtts",
                "description": "Клонирование голоса из аудио-образца"
            }
        ]
    
    async def clone_voice(
        self,
        reference_audio_path: str,
        text: str,
        output_path: Optional[str] = None
    ) -> TTSResult:
        """
        Клонирование голоса из референсного аудио.
        
        Args:
            reference_audio_path: Путь к референсному аудио
            text: Текст для озвучки
            output_path: Путь для сохранения
            
        Returns:
            TTSResult с результатом
        """
        if not Path(reference_audio_path).exists():
            return TTSResult(
                success=False, 
                error="Reference audio file not found"
            )
        
        return await self.generate(
            text=text,
            output_path=output_path,
            voice=reference_audio_path,
        )


class TTSService:
    """
    Центральный сервис TTS с поддержкой нескольких движков.
    
    Позволяет:
    - Выбирать движок (Edge TTS / Coqui)
    - Переключать голоса
    - Клонировать голос (Coqui)
    - Кэшировать результаты
    """
    
    def __init__(self):
        """Инициализация TTS-сервиса."""
        self.engine_type = TTSEngine(settings.TTS_ENGINE)
        self._init_providers()
    
    def _init_providers(self) -> None:
        """Инициализация провайдеров."""
        self.providers: Dict[TTSEngine, BaseTTSProvider] = {}
        
        # Edge TTS (всегда доступен если установлен)
        try:
            self.providers[TTSEngine.EDGE_TTS] = EdgeTTSProvider()
            logger.info("Edge TTS provider initialized")
        except Exception as e:
            logger.warning(f"Edge TTS not available: {e}")
        
        # Coqui XTTS (опционально)
        if settings.TTS_ENGINE == "coqui-xtts":
            try:
                self.providers[TTSEngine.COQUI_XTTS] = CoquiXTTSProvider()
                logger.info("Coqui XTTS provider initialized")
            except Exception as e:
                logger.warning(f"Coqui XTTS not available: {e}")
    
    def get_provider(self, engine: Optional[TTSEngine] = None) -> BaseTTSProvider:
        """
        Получение провайдера по типу движка.
        
        Args:
            engine: Тип движка (опционально)
            
        Returns:
            Экземпляр провайдера
        """
        engine = engine or self.engine_type
        
        if engine not in self.providers:
            # Пытаемся использовать доступный провайдер
            if self.providers:
                return list(self.providers.values())[0]
            raise ValueError(f"No TTS provider available for engine: {engine}")
        
        return self.providers[engine]
    
    async def generate_audio(
        self,
        text: str,
        voice: Optional[str] = None,
        output_path: Optional[str] = None,
        engine: Optional[TTSEngine] = None,
        speed: float = 1.0,
        pitch: float = 0.0,
        **kwargs
    ) -> TTSResult:
        """
        Генерация аудио из текста.
        
        Args:
            text: Текст для озвучки
            voice: Голос или путь к референсному аудио
            output_path: Путь для сохранения
            engine: Движок TTS
            speed: Скорость
            pitch: Высота тона
            
        Returns:
            TTSResult с результатом
        """
        provider = self.get_provider(engine)
        
        return await provider.generate(
            text=text,
            output_path=output_path,
            voice=voice,
            speed=speed,
            pitch=pitch,
            **kwargs
        )
    
    async def batch_generate(
        self,
        texts: List[str],
        voice: Optional[str] = None,
        engine: Optional[TTSEngine] = None,
        parallel: int = 3
    ) -> List[TTSResult]:
        """
        Пакетная генерация аудио для нескольких текстов.
        
        Args:
            texts: Список текстов
            voice: Голос
            engine: Движок
            parallel: Количество параллельных задач
            
        Returns:
            Список результатов
        """
        semaphore = asyncio.Semaphore(parallel)
        
        async def generate_with_limit(text: str) -> TTSResult:
            async with semaphore:
                return await self.generate_audio(
                    text=text,
                    voice=voice,
                    engine=engine,
                )
        
        results = await asyncio.gather(
            *[generate_with_limit(text) for text in texts]
        )
        
        return results
    
    def get_available_voices(self, engine: Optional[TTSEngine] = None) -> List[Dict[str, str]]:
        """Получение доступных голосов."""
        provider = self.get_provider(engine)
        return provider.get_available_voices()
    
    def get_russian_voices(self) -> List[Dict[str, str]]:
        """Получение русскоязычных голосов."""
        edge_provider = self.providers.get(TTSEngine.EDGE_TTS)
        if edge_provider:
            return edge_provider.get_russian_voices()
        return []
    
    async def estimate_duration(
        self,
        text: str,
        voice: Optional[str] = None,
        engine: Optional[TTSEngine] = None
    ) -> float:
        """
        Оценка длительности аудио до генерации.
        
        Args:
            text: Текст
            voice: Голос
            engine: Движок
            
        Returns:
            Ожидаемая длительность в секундах
        """
        # Средняя скорость речи: ~150 слов в минуту
        word_count = len(text.split())
        estimated_minutes = word_count / 150
        
        return estimated_minutes * 60


# Экземпляр сервиса для использования в приложении
tts_service = TTSService()
