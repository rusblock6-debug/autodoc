"""
Edge TTS Service - быстрая онлайн озвучка от Microsoft
"""

import logging
import asyncio
from pathlib import Path
from typing import Optional
import tempfile

logger = logging.getLogger(__name__)


class EdgeTTSService:
    """
    Сервис озвучки через Microsoft Edge TTS.
    Быстро, качественно, но требует интернет.
    """
    
    def __init__(self, voice: str = "ru-RU-DmitryNeural"):
        """
        Args:
            voice: Голос для озвучки (ru-RU-DmitryNeural или ru-RU-SvetlanaNeural)
        """
        self.voice = voice
        logger.info(f"Edge TTS service initialized with voice: {voice}")
    
    async def synthesize(
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
            Путь к MP3 файлу с аудио
        """
        try:
            logger.info(f"Synthesizing TTS for text: {text[:50]}...")
            
            # Определяем путь для сохранения
            if output_path:
                save_path = output_path
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            else:
                temp_file = tempfile.NamedTemporaryFile(
                    suffix='.mp3',
                    delete=False
                )
                save_path = temp_file.name
                temp_file.close()
            
            # Генерируем аудио
            import edge_tts
            communicate = edge_tts.Communicate(text, self.voice)
            await communicate.save(save_path)
            
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
        Создаёт новый event loop для выполнения async операции.
        
        Args:
            text: Текст для озвучки
            output_path: Путь для сохранения файла (опционально)
        
        Returns:
            Путь к MP3 файлу с аудио
        """
        import asyncio
        
        # Создаём новый event loop для синхронного вызова
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            return loop.run_until_complete(self.synthesize(text, output_path))
        finally:
            loop.close()
    
    def get_audio_duration(self, audio_path: str) -> float:
        """
        Получить длительность аудио в секундах.
        """
        try:
            from pydub import AudioSegment
            
            audio = AudioSegment.from_file(audio_path)
            return len(audio) / 1000.0  # миллисекунды в секунды
                
        except Exception as e:
            logger.error(f"Failed to get audio duration: {e}")
            # Примерная оценка: 3 слова в секунду
            word_count = len(text.split()) if 'text' in locals() else 10
            return max(2.0, word_count / 3.0)


# Глобальный экземпляр сервиса
_edge_tts_service = None

def get_edge_tts_service() -> EdgeTTSService:
    """Получить глобальный экземпляр Edge TTS сервиса"""
    global _edge_tts_service
    if _edge_tts_service is None:
        _edge_tts_service = EdgeTTSService()
    return _edge_tts_service
