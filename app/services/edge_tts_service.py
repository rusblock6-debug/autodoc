"""
Edge TTS Service - быстрая онлайн озвучка от Microsoft
"""

import logging
import asyncio
import re
from pathlib import Path
from typing import Optional
import tempfile

logger = logging.getLogger(__name__)


def normalize_text_for_edge_tts(text: str) -> str:
    """
    Нормализует текст для Edge TTS, чтобы избежать ошибок синтеза.
    
    Проблемы Edge TTS:
    - Не может озвучить английские слова в ALL CAPS (например "MARKDOWN-ACCESSIBLITY-TABLE")
    - Плохо работает с техническими терминами и HTML тегами
    
    Решение:
    - Заменяем ALL CAPS английские слова на русскую транслитерацию
    - Добавляем пробелы между буквами в сложных случаях
    
    Args:
        text: Исходный текст
        
    Returns:
        Нормализованный текст для Edge TTS
    """
    # Словарь замен для распространенных HTML тегов и технических терминов
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
        r'\bTBODY\b': 'ти боди',
        r'\bTHEAD\b': 'ти хэд',
        r'\bTR\b': 'ти ар',
        r'\bTD\b': 'ти ди',
        r'\bTH\b': 'ти эйч',
        r'\bLI\b': 'эл ай',
        r'\bUL\b': 'ю эл',
        r'\bOL\b': 'оу эл',
        r'\bA\b': 'эй',
        r'\bIMG\b': 'имидж',
        r'\bP\b': 'пи',
        r'\bH1\b': 'эйч один',
        r'\bH2\b': 'эйч два',
        r'\bH3\b': 'эйч три',
        r'\bH4\b': 'эйч четыре',
        r'\bH5\b': 'эйч пять',
        r'\bH6\b': 'эйч шесть',
        r'\bPRE\b': 'при',
        r'\bCODE\b': 'код',
        r'\bBLOCKQUOTE\b': 'блоккуот',
        
        # Markdown и технические термины
        r'\bMARKDOWN\b': 'маркдаун',
        r'\bACCESSIBILITY\b': 'аксессибилити',
        r'\bACCESSIBLITY\b': 'аксессибилити',  # Опечатка в слове (без второй I)
        r'\bACCESSIBLE\b': 'аксессибл',
        
        # Общие слова
        r'\bCLICK\b': 'клик',
        r'\bBACK\b': 'бэк',
        r'\bNEXT\b': 'некст',
        r'\bSUBMIT\b': 'сабмит',
        r'\bCANCEL\b': 'кэнсел',
        r'\bSAVE\b': 'сэйв',
        r'\bDELETE\b': 'делит',
        r'\bEDIT\b': 'эдит',
    }
    
    result = text
    
    # Применяем известные замены
    for pattern, replacement in replacements.items():
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    
    # Обрабатываем оставшиеся ALL CAPS английские слова с дефисами
    # Например: "MARKDOWN-ACCESSIBLITY-TABLE" -> "маркдаун аксессибилити тэйбл"
    def replace_caps_with_hyphens(match):
        word = match.group(0)
        # Разбиваем по дефисам
        parts = word.split('-')
        # Конвертируем каждую часть в lowercase и добавляем пробелы между буквами
        normalized_parts = []
        for part in parts:
            if len(part) <= 3:
                # Короткие слова - произносим по буквам
                normalized_parts.append(' '.join(part.lower()))
            else:
                # Длинные слова - просто lowercase
                normalized_parts.append(part.lower())
        return ' '.join(normalized_parts)
    
    # Паттерн для ALL CAPS слов с дефисами (минимум 2 буквы)
    result = re.sub(r'\b[A-Z]{2,}(?:-[A-Z]{2,})+\b', replace_caps_with_hyphens, result)
    
    # Обрабатываем оставшиеся одиночные ALL CAPS слова (минимум 2 буквы)
    def replace_single_caps(match):
        word = match.group(0)
        if len(word) <= 3:
            # Короткие слова (H3, PRE, DIV) - произносим по буквам
            return ' '.join(word.lower())
        else:
            # Длинные слова - просто lowercase
            return word.lower()
    
    result = re.sub(r'\b[A-Z]{2,}\b', replace_single_caps, result)
    
    # Заменяем оставшиеся дефисы между словами на пробелы
    # Например: "маркдаун-аксессибилити-тэйбл" -> "маркдаун аксессибилити тэйбл"
    result = re.sub(r'([а-яёa-z]+)-([а-яёa-z]+)', r'\1 \2', result, flags=re.IGNORECASE)
    # Повторяем для множественных дефисов
    result = re.sub(r'([а-яёa-z]+)-([а-яёa-z]+)', r'\1 \2', result, flags=re.IGNORECASE)
    
    logger.debug(f"Text normalized: '{text}' -> '{result}'")
    return result


class EdgeTTSService:
    """
    Сервис озвучки через Microsoft Edge TTS.
    Быстро, качественно, но требует интернет.
    """
    
    def __init__(self, voice: str = "ru-RU-DmitryNeural", rate: str = "+20%", pitch: str = "+0Hz"):
        """
        Args:
            voice: Голос для озвучки (ru-RU-DmitryNeural или ru-RU-SvetlanaNeural)
            rate: Скорость речи (например "+50%" или "-25%"), по умолчанию +20% для более быстрой речи
            pitch: Тембр голоса (например "+10Hz" или "-5Hz")
        """
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        logger.info(f"Edge TTS service initialized with voice: {voice}, rate: {rate}, pitch: {pitch}")
    
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
            
            # Нормализуем текст для Edge TTS
            normalized_text = normalize_text_for_edge_tts(text)
            
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
            
            # Генерируем аудио с нормализованным текстом
            import edge_tts
            communicate = edge_tts.Communicate(normalized_text, self.voice, rate=self.rate, pitch=self.pitch)
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
