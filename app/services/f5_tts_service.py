"""
F5-TTS Russian — клиент к GPU-микросервису озвучки (контейнер f5tts).

Сам синтез крутится в отдельном контейнере с CUDA (см. f5tts/server.py),
здесь только HTTP-клиент с тем же интерфейсом, что у silero/edge/chatterbox:
    - synthesize_sync(text, output_path) -> путь к WAV
    - get_audio_duration(audio_path) -> секунды

Голос задаётся референс-записью /data/tts_refs/<voice>/ (ref.wav + ref.txt).
Если дефолтного референса нет, он один раз генерится Silero-голосом xenia:
F5 клонирует тембр, но произносит с живой интонацией — офлайн из коробки,
а «настоящий» голос добавляется простым копированием пары файлов в /data.
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

F5TTS_URL = os.environ.get("F5TTS_URL", "http://f5tts:8010")

REFS_DIR = Path("/data/tts_refs")
DEFAULT_VOICE = "default"

# Голоса, которые бутстрапятся автоматически (клон соответствующего
# Silero-голоса). «Настоящий» голос — папка с ref.wav+ref.txt в /data/tts_refs.
BOOTSTRAP_VOICES = {
    "default": "xenia",   # женский
    "male": "eugene",     # мужской
}

# Текст авто-референса (~9 сек речи; ref.txt должен совпадать с ref.wav).
# Подлиннее и со спокойным ритмом: F5 клонирует и ТЕМП референса тоже —
# короткий торопливый референс даёт торопливую озвучку всех шагов.
_DEFAULT_REF_TEXT = (
    "Здравствуйте! В этом видео мы шаг за шагом разберём, как работать "
    "с программой. Не торопитесь, выполняйте каждое действие спокойно "
    "и внимательно. Начнём с самого главного."
)

# Первый запрос может качать модель (~1.4 ГБ) и грузить её на GPU
_FIRST_CALL_TIMEOUT = 1800.0


class F5TTSService:
    """HTTP-клиент к f5tts. Не singleton — состояния нет, модель в контейнере."""

    def __init__(self, voice: str = DEFAULT_VOICE, speed: float = 1.0):
        self.voice = voice or DEFAULT_VOICE
        self.speed = speed or 1.0

    def _ensure_default_ref(self) -> None:
        """Бутстрап авто-референсов (default/male) через Silero (один раз)."""
        speaker = BOOTSTRAP_VOICES.get(self.voice)
        if speaker is None:
            return
        ref_dir = REFS_DIR / self.voice
        if (ref_dir / "ref.wav").exists():
            return

        logger.info(f"No F5 reference voice '{self.voice}', bootstrapping via Silero ({speaker})...")
        from app.services.silero_tts_service import get_silero_service

        ref_dir.mkdir(parents=True, exist_ok=True)
        silero = get_silero_service(speaker=speaker)
        silero.synthesize_sync(text=_DEFAULT_REF_TEXT, output_path=str(ref_dir / "ref.wav"))
        (ref_dir / "ref.txt").write_text(_DEFAULT_REF_TEXT, encoding="utf-8")
        logger.info(f"F5 reference voice '{self.voice}' created in {ref_dir}")

    def synthesize(self, text: str, output_path: Optional[str] = None) -> str:
        """Синтез речи через микросервис. Возвращает путь к WAV (16-bit PCM)."""
        import httpx

        self._ensure_default_ref()

        # Числа -> слова (той же логикой, что у Silero). Латиницу НЕ трогаем:
        # модель училась на смешанном ru-en корпусе и читает английский сама.
        from app.services.silero_tts_service import _numbers_to_words
        normalized = _numbers_to_words(text)

        logger.info(f"Synthesizing (F5/{self.voice}, x{self.speed}): {normalized[:50]}...")
        response = httpx.post(
            f"{F5TTS_URL}/synthesize",
            json={"text": normalized, "voice": self.voice, "speed": self.speed},
            timeout=httpx.Timeout(_FIRST_CALL_TIMEOUT, connect=10.0),
        )
        if response.status_code == 404 and self.voice != DEFAULT_VOICE:
            # Референс выбранного голоса пропал (например, из UI пришло имя
            # silero-голоса) — не валим генерацию, откатываемся на дефолтный
            logger.warning(f"F5 voice '{self.voice}' not found, falling back to '{DEFAULT_VOICE}'")
            self.voice = DEFAULT_VOICE
            return self.synthesize(text=text, output_path=output_path)
        response.raise_for_status()

        if output_path:
            save_path = output_path
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        else:
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            save_path = tmp.name
            tmp.close()

        Path(save_path).write_bytes(response.content)
        logger.info(f"Saved audio to {save_path}")
        return save_path

    def synthesize_sync(self, text: str, output_path: Optional[str] = None) -> str:
        """Синхронный синтез (для Celery)."""
        return self.synthesize(text=text, output_path=output_path)

    def get_audio_duration(self, audio_path: str) -> float:
        """Длительность аудио в секундах."""
        try:
            import wave
            with wave.open(audio_path, "rb") as wf:
                return wf.getnframes() / float(wf.getframerate())
        except Exception as e:
            logger.error(f"Failed to get audio duration: {e}")
            return 0.0


def get_f5_service(voice: str = DEFAULT_VOICE, speed: float = 1.0) -> F5TTSService:
    """Получить клиент F5-TTS с заданным голосом и скоростью."""
    return F5TTSService(voice=voice, speed=speed)
