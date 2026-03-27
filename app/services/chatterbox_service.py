"""
Chatterbox TTS Service - бесплатная нейронная озвучка
https://github.com/resemble-ai/chatterbox
"""

import logging
from pathlib import Path
from typing import Optional
import tempfile

logger = logging.getLogger(__name__)


class ChatterboxService:
    """
    Сервис нейронной озвучки на основе Chatterbox TTS.
    Бесплатный, локальный, с поддержкой русского языка.
    
    Singleton - модель загружается один раз.
    """
    
    _instance = None
    _model = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Инициализация (модель загружается при первом использовании)"""
        pass
    
    def _ensure_model_loaded(self):
        """Загрузка модели при первом использовании (ленивая загрузка)"""
        if self._model is not None:
            return  # Модель уже загружена
            
        try:
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS
            import torch
            import os
            
            logger.info("Loading Chatterbox Multilingual TTS model (first time only)...")
            
            # Патчим torch.load чтобы всегда загружать на CPU
            original_load = torch.load
            def load_to_cpu(*args, **kwargs):
                kwargs['map_location'] = torch.device('cpu')
                kwargs['weights_only'] = False
                return original_load(*args, **kwargs)
            
            torch.load = load_to_cpu
            
            try:
                # Используем мультиязычную модель для русского
                self._model = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
                logger.info("Chatterbox Multilingual TTS model loaded successfully")
            finally:
                # Восстанавливаем оригинальный torch.load
                torch.load = original_load
            
        except ImportError as e:
            logger.error(f"Failed to import Chatterbox: {e}")
            raise ImportError(
                "Chatterbox TTS not installed. Run: pip install chatterbox-tts"
            )
        except Exception as e:
            logger.error(f"Failed to load Chatterbox model: {e}")
            raise
    
    def _synthesize_sync(
        self,
        text: str,
        output_path: Optional[str] = None
    ) -> str:
        """
        Синтез речи из текста (синхронный метод).
        
        Args:
            text: Текст для озвучки
            output_path: Путь для сохранения файла (опционально)
        
        Returns:
            Путь к WAV файлу с аудио
        """
        try:
            logger.info(f"Synthesizing TTS for text: {text[:50]}...")
            
            # Загружаем модель если ещё не загружена
            self._ensure_model_loaded()
            
            # Генерируем аудио с указанием русского языка
            wav = self._model.generate(text=text, language_id="ru")
            
            # Определяем путь для сохранения
            if output_path:
                save_path = output_path
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            else:
                # Сохраняем в /data/audio/ с уникальным именем
                import uuid
                audio_dir = Path("/data/audio")
                audio_dir.mkdir(parents=True, exist_ok=True)
                save_path = str(audio_dir / f"tts_{uuid.uuid4().hex[:8]}.wav")
            
            # Сохраняем через torchaudio (как в документации)
            import torchaudio as ta
            ta.save(save_path, wav, self._model.sr)
            
            logger.info(f"Saved audio to {save_path}")
            return save_path
                
        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            raise
    
    def synthesize_sync(
        self,
        text: str,
        output_path: Optional[str] = None
    ) -> str:
        """
        Синхронный метод синтеза речи (для Celery).
        
        Args:
            text: Текст для озвучки
            output_path: Путь для сохранения файла (опционально)
        
        Returns:
            Путь к WAV файлу с аудио
        """
        return self._synthesize_sync(text, output_path)
    
    async def synthesize(
        self,
        text: str,
        output_path: Optional[str] = None
    ) -> str:
        """
        Асинхронная обёртка для синтеза речи.
        Запускает синхронный метод в отдельном потоке.
        
        Args:
            text: Текст для озвучки
            output_path: Путь для сохранения файла (опционально)
        
        Returns:
            Путь к WAV файлу с аудио
        """
        import asyncio
        return await asyncio.to_thread(self._synthesize_sync, text, output_path)
    
    def get_audio_duration(self, audio_path: str) -> float:
        """
        Получить длительность аудио в секундах.
        """
        try:
            import wave
            
            with wave.open(audio_path, 'rb') as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                return frames / float(rate)
                
        except Exception as e:
            logger.error(f"Failed to get audio duration: {e}")
            return 0.0


# Глобальный экземпляр сервиса (загружается при первом использовании)
_chatterbox_service = None

def get_chatterbox_service() -> ChatterboxService:
    """Получить глобальный экземпляр Chatterbox сервиса"""
    global _chatterbox_service
    if _chatterbox_service is None:
        _chatterbox_service = ChatterboxService()
    return _chatterbox_service
