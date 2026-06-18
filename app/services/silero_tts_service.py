"""
Silero TTS Service - бесплатная нейронная озвучка на русском (модель v5_5_ru).

Самый свежий русский Silero, локально на CPU, очень быстро (RTF ~0.03-0.12).
Ударения и ё-фикацию ставит сама модель, дополнительной разметки не требует.

Интерфейс совместим с EdgeTTSService/ChatterboxService:
    - synthesize_sync(text, output_path) -> путь к WAV
    - get_audio_duration(audio_path) -> секунды
"""

import logging
import os
import re
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Модель кладём в /data (bind-mount ./data), чтобы переживала пересоздание контейнера
MODEL_URL = "https://models.silero.ai/models/tts/ru/v5_5_ru.pt"
MODELS_DIR = "/data/torch_hub/models"
MODEL_PATH = os.path.join(MODELS_DIR, "v5_5_ru.pt")

DEFAULT_SPEAKER = "xenia"
SAMPLE_RATE = 48000


# --- Препроцессинг текста для естественной русской озвучки ---

# HTML-теги и технические термины -> кириллица
_HTML_REPLACEMENTS = {
    r'\bMAIN\b': 'мэйн', r'\bDIV\b': 'див', r'\bSPAN\b': 'спан',
    r'\bBUTTON\b': 'баттон', r'\bINPUT\b': 'инпут', r'\bFORM\b': 'форм',
    r'\bHEADER\b': 'хэдер', r'\bFOOTER\b': 'футер', r'\bNAV\b': 'нав',
    r'\bSECTION\b': 'секшн', r'\bARTICLE\b': 'артикл', r'\bASIDE\b': 'эсайд',
    r'\bTABLE\b': 'тэйбл', r'\bLI\b': 'эл ай', r'\bUL\b': 'ю эл',
    r'\bIMG\b': 'имидж', r'\bH1\b': 'эйч один', r'\bH2\b': 'эйч два',
    r'\bH3\b': 'эйч три',
    # Распространённые англ. слова из UI
    r'\bENTER\b': 'энтер', r'\bCLICK\b': 'клик', r'\bBACK\b': 'бэк',
    r'\bNEXT\b': 'некст', r'\bSUBMIT\b': 'сабмит', r'\bCANCEL\b': 'кэнсел',
    r'\bSAVE\b': 'сэйв', r'\bDELETE\b': 'делит', r'\bEDIT\b': 'эдит',
    r'\bOK\b': 'окей', r'\bLOGIN\b': 'логин', r'\bLOGOUT\b': 'логаут',
    r'\bMENU\b': 'меню', r'\bSEARCH\b': 'сёрч',
}

# Посимвольная транслитерация оставшейся латиницы (грубо, но читаемо)
_TRANSLIT = {
    'a': 'а', 'b': 'б', 'c': 'к', 'd': 'д', 'e': 'е', 'f': 'ф', 'g': 'г',
    'h': 'х', 'i': 'и', 'j': 'дж', 'k': 'к', 'l': 'л', 'm': 'м', 'n': 'н',
    'o': 'о', 'p': 'п', 'q': 'к', 'r': 'р', 's': 'с', 't': 'т', 'u': 'у',
    'v': 'в', 'w': 'в', 'x': 'кс', 'y': 'й', 'z': 'з',
}


def _transliterate_word(word: str) -> str:
    return ''.join(_TRANSLIT.get(ch, _TRANSLIT.get(ch.lower(), ch)) for ch in word)


def _numbers_to_words(text: str) -> str:
    """Числа -> слова (2 -> два, 50% -> пятьдесят процентов)."""
    try:
        from num2words import num2words
    except ImportError:
        logger.warning("num2words not installed — числа читаются как есть")
        return text

    def repl(match):
        num = match.group(0)
        try:
            return num2words(int(num), lang='ru')
        except Exception:
            return num

    text = re.sub(r'\b\d+\b', repl, text)
    text = text.replace('%', ' процентов')
    return text


def normalize_text_for_silero(text: str) -> str:
    """Готовит текст: теги/числа/латиница -> произносимый русский."""
    result = text
    for pattern, replacement in _HTML_REPLACEMENTS.items():
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

    result = _numbers_to_words(result)

    # Оставшиеся латинские слова транслитерируем посимвольно
    result = re.sub(r'[A-Za-z]+', lambda m: _transliterate_word(m.group(0)), result)

    logger.debug(f"Silero normalized: '{text}' -> '{result}'")
    return result


class SileroTTSService:
    """
    Нейронная озвучка Silero v5_5_ru. Singleton — модель грузится один раз.
    """

    _instance = None
    _model = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, speaker: str = DEFAULT_SPEAKER):
        self.speaker = speaker or DEFAULT_SPEAKER
        if self._model is not None:
            return  # Уже загружена

        try:
            import torch

            os.makedirs(MODELS_DIR, exist_ok=True)
            if not os.path.exists(MODEL_PATH):
                logger.info(f"Downloading Silero model from {MODEL_URL} ...")
                urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
                logger.info(f"Silero model downloaded ({os.path.getsize(MODEL_PATH)/1e6:.0f} MB)")

            logger.info("Loading Silero v5_5_ru model (first time only)...")
            model = torch.package.PackageImporter(MODEL_PATH).load_pickle("tts_models", "model")
            model.to(torch.device("cpu"))
            torch.set_num_threads(os.cpu_count() or 4)
            SileroTTSService._model = model
            logger.info(f"Silero loaded. Speakers: {model.speakers}")

        except Exception as e:
            logger.error(f"Failed to load Silero model: {e}")
            raise

    def synthesize(self, text: str, output_path: Optional[str] = None,
                   speaker: Optional[str] = None) -> str:
        """Синтез речи. Возвращает путь к WAV."""
        import torchaudio

        voice = speaker or self.speaker
        if self._model is not None and voice not in self._model.speakers:
            logger.warning(f"Speaker '{voice}' not in model, falling back to '{DEFAULT_SPEAKER}'")
            voice = DEFAULT_SPEAKER

        normalized = normalize_text_for_silero(text)
        logger.info(f"Synthesizing (Silero/{voice}): {normalized[:50]}...")

        audio = self._model.apply_tts(
            text=normalized,
            speaker=voice,
            sample_rate=SAMPLE_RATE,
            put_accent=True,
            put_yo=True,
        )

        if output_path:
            save_path = output_path
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        else:
            tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            save_path = tmp.name
            tmp.close()

        # 16-bit PCM — совместимо с wave, pydub и ffmpeg (float-WAV ломает их)
        torchaudio.save(
            save_path, audio.unsqueeze(0), SAMPLE_RATE,
            encoding="PCM_S", bits_per_sample=16,
        )
        logger.info(f"Saved audio to {save_path}")
        return save_path

    def synthesize_sync(self, text: str, output_path: Optional[str] = None) -> str:
        """Синхронный синтез (для Celery)."""
        return self.synthesize(text=text, output_path=output_path)

    def get_audio_duration(self, audio_path: str) -> float:
        """Длительность аудио в секундах."""
        try:
            import wave
            with wave.open(audio_path, 'rb') as wf:
                return wf.getnframes() / float(wf.getframerate())
        except Exception as e:
            logger.error(f"Failed to get audio duration: {e}")
            return 0.0


_silero_service = None


def get_silero_service(speaker: str = DEFAULT_SPEAKER) -> SileroTTSService:
    """Получить глобальный экземпляр Silero сервиса."""
    global _silero_service
    if _silero_service is None:
        _silero_service = SileroTTSService(speaker=speaker)
    else:
        _silero_service.speaker = speaker or DEFAULT_SPEAKER
    return _silero_service
