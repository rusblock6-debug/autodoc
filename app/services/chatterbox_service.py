"""
Chatterbox TTS Service - бесплатная нейронная озвучка
https://github.com/resemble-ai/chatterbox
"""

import logging
from pathlib import Path
from typing import Optional
import tempfile
import re

logger = logging.getLogger(__name__)


def transliterate_for_russian_tts(text: str) -> str:
    """
    Транслитерирует английские слова в русские для лучшей озвучки.
    Заменяет распространенные HTML-теги и технические термины.
    """
    replacements = {
        # HTML теги
        r'\bMAIN\b': 'мэйн',
        r'\bDIV\b': 'див',
        r'\bSPAN\b': 'спан',
        r'\bBUTTON\b': 'баттон',
        r'\bINPUT\b': 'инпут',
        r'\bFORM\b': 'форм',
        r'\bHEADER\b': 'хэдер',
        r'\bFOOTER\b': 'футер',
        r'\bNAV\b': 'нав',
        r'\bSECTION\b': 'секшн',
        r'\bARTICLE\b': 'артикл',
        r'\bASIDE\b': 'эсайд',
        r'\bTABLE\b': 'тэйбл',
        r'\bLI\b': 'эл ай',
        r'\bUL\b': 'ю эл',
        r'\bOL\b': 'оу эл',
        r'\bA\b': 'эй',
        r'\bIMG\b': 'имидж',
        r'\bP\b': 'пи',
        r'\bH1\b': 'эйч один',
        r'\bH2\b': 'эйч два',
        r'\bH3\b': 'эйч три',
        
        # Общие слова
        r'\bCLICK\b': 'клик',
        r'\bBACK\b': 'бэк',
        r'\bNEXT\b': 'некст',
        r'\bSUBMIT\b': 'сабмит',
        r'\bCANCEL\b': 'кэнсел',
    }
    
    result = text
    for pattern, replacement in replacements.items():
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    
    return result


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
        """Инициализация модели (только один раз)"""
        if self._model is not None:
            return  # Модель уже загружена
            
        try:
            # Используем MULTILINGUAL модель для поддержки русского языка
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS
            
            logger.info("Loading Chatterbox Multilingual TTS model (first time only)...")
            self._model = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
            logger.info("Chatterbox Multilingual TTS model loaded successfully")
            
        except ImportError as e:
            logger.error(f"Failed to import Chatterbox: {e}")
            raise ImportError(
                "Chatterbox TTS not installed. Run: pip install chatterbox-tts"
            )
        except Exception as e:
            logger.error(f"Failed to load Chatterbox model: {e}")
            raise
    
    def synthesize(
        self,
        text: str,
        output_path: Optional[str] = None
    ) -> str:
        """
        Синтез речи из текста.
        
        Args:
            text: Текст для озвучки
            output_path: Путь для сохранения файла (опционально)
        
        Returns:
            Путь к WAV файлу с аудио
        """
        try:
            logger.info(f"Synthesizing TTS for text: {text[:50]}...")
            
            # Генерируем аудио через метод generate с указанием русского языка
            audio_tensor = self._model.generate(text=text, language_id="ru")
            
            # Конвертируем tensor в numpy array
            import torch
            import numpy as np
            import scipy.io.wavfile as wavfile
            
            # Преобразуем tensor в numpy
            if isinstance(audio_tensor, torch.Tensor):
                audio_np = audio_tensor.cpu().numpy()
            else:
                audio_np = np.array(audio_tensor)
            
            # Убираем лишние размерности (batch, channels)
            audio_np = audio_np.squeeze()
            
            # Нормализуем в диапазон int16
            if audio_np.dtype == np.float32 or audio_np.dtype == np.float64:
                # Нормализуем по максимальному значению
                max_val = np.abs(audio_np).max()
                if max_val > 0:
                    audio_np = audio_np / max_val
                # Конвертируем в int16
                audio_np = (audio_np * 32767).astype(np.int16)
            elif audio_np.dtype != np.int16:
                # Если уже int, но не int16 - конвертируем
                audio_np = audio_np.astype(np.int16)
            
            # Определяем путь для сохранения
            if output_path:
                save_path = output_path
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            else:
                temp_file = tempfile.NamedTemporaryFile(
                    suffix='.wav',
                    delete=False
                )
                save_path = temp_file.name
                temp_file.close()
            
            # Сохраняем как WAV (22050 Hz - стандарт для Chatterbox)
            wavfile.write(save_path, 22050, audio_np)
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
        Синхронная версия synthesize (алиас для совместимости).
        
        Args:
            text: Текст для озвучки
            output_path: Путь для сохранения файла (опционально)
        
        Returns:
            Путь к WAV файлу с аудио
        """
        return self.synthesize(text=text, output_path=output_path)
    
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
