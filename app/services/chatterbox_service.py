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
    """
    
    def __init__(self):
        """Инициализация модели"""
        try:
            from chatterbox.tts import ChatterboxTTS
            
            logger.info("Loading Chatterbox TTS model...")
            # from_pretrained принимает только device, модель загружается автоматически
            self.model = ChatterboxTTS.from_pretrained(device="cpu")
            logger.info("Chatterbox TTS model loaded successfully")
            
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
            
            # Генерируем аудио через метод generate (не synthesize!)
            audio = self.model.generate(text=text)
            
            # Сохраняем в файл
            if output_path:
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'wb') as f:
                    f.write(audio)
                logger.info(f"Saved audio to {output_path}")
                return output_path
            else:
                # Временный файл
                temp_file = tempfile.NamedTemporaryFile(
                    suffix='.wav',
                    delete=False
                )
                temp_file.write(audio)
                temp_file.close()
                return temp_file.name
                
        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            raise
    
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
