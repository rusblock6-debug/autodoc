"""
Тесты F5-TTS движка (микросервис f5tts + клиент app/services/f5_tts_service).

Два слоя:
- юнит-тесты клиента — без сети, httpx мокается;
- интеграционные — против живого контейнера f5tts (сами скипаются, если
  сервис не поднят). Первый синтез может быть долгим (загрузка модели).

Запуск внутри контейнера:
    docker compose exec celery-worker python -m pytest tests/test_f5_tts.py -v
"""

import io
import struct
import wave
from pathlib import Path

import pytest

from app.services import f5_tts_service as f5_mod
from app.services.f5_tts_service import (
    BOOTSTRAP_VOICES,
    DEFAULT_VOICE,
    F5TTS_URL,
    F5TTSService,
    get_f5_service,
)


# ---------------------------------------------------------------------------
# Хелперы
# ---------------------------------------------------------------------------

def _make_wav_bytes(duration_sec: float = 1.0, rate: int = 24000) -> bytes:
    """Минимальный валидный WAV (16-bit PCM, mono) заданной длительности."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(struct.pack("<h", 0) * int(rate * duration_sec))
    return buf.getvalue()


class _FakeResponse:
    def __init__(self, status_code=200, content=b""):
        self.status_code = status_code
        self.content = content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


@pytest.fixture
def ready_refs(tmp_path, monkeypatch):
    """Подменяет REFS_DIR на tmp с готовым default-референсом,
    чтобы юнит-тесты не запускали бутстрап через Silero."""
    ref_dir = tmp_path / DEFAULT_VOICE
    ref_dir.mkdir(parents=True)
    (ref_dir / "ref.wav").write_bytes(_make_wav_bytes(0.1))
    (ref_dir / "ref.txt").write_text("тест", encoding="utf-8")
    monkeypatch.setattr(f5_mod, "REFS_DIR", tmp_path)
    return tmp_path


def _service_available() -> bool:
    try:
        import httpx
        return httpx.get(f"{F5TTS_URL}/health", timeout=3).status_code == 200
    except Exception:
        return False


requires_f5 = pytest.mark.skipif(
    not _service_available(), reason="f5tts service is not running"
)

# Первый интеграционный синтез может качать/грузить модель
SYNTH_TIMEOUT = 1800.0


def _synth(text: str, voice: str = DEFAULT_VOICE, speed: float = 1.0):
    import httpx
    return httpx.post(
        f"{F5TTS_URL}/synthesize",
        json={"text": text, "voice": voice, "speed": speed},
        timeout=SYNTH_TIMEOUT,
    )


# ---------------------------------------------------------------------------
# Юнит: препроцессинг текста
# ---------------------------------------------------------------------------

class TestTextPreprocessing:
    def test_numbers_to_words_integer(self):
        from app.services.silero_tts_service import _numbers_to_words

        assert "двадцать пять" in _numbers_to_words("введите число 25")

    def test_numbers_to_words_percent(self):
        from app.services.silero_tts_service import _numbers_to_words

        result = _numbers_to_words("скидка 50%")
        assert "пятьдесят" in result
        assert "процентов" in result


# ---------------------------------------------------------------------------
# Юнит: клиент F5TTSService (httpx мокается)
# ---------------------------------------------------------------------------

class TestF5Client:
    def test_defaults(self):
        svc = get_f5_service()
        assert svc.voice == DEFAULT_VOICE
        assert svc.speed == 1.0

    def test_empty_voice_falls_back_to_default(self):
        svc = get_f5_service(voice="", speed=0)
        assert svc.voice == DEFAULT_VOICE
        assert svc.speed == 1.0

    def test_payload_numbers_converted_latin_preserved(self, ready_refs, monkeypatch, tmp_path):
        """Числа конвертируются в слова, латиница НЕ транслитерируется."""
        captured = {}

        def fake_post(url, json=None, timeout=None):
            captured.update(json)
            return _FakeResponse(200, _make_wav_bytes(0.2))

        import httpx
        monkeypatch.setattr(httpx, "post", fake_post)

        svc = F5TTSService(voice=DEFAULT_VOICE, speed=1.2)
        svc.synthesize_sync("Нажмите Save и введите 25", str(tmp_path / "out.wav"))

        assert "двадцать пять" in captured["text"]
        assert "Save" in captured["text"]  # не «сав»/«с а в»
        assert captured["voice"] == DEFAULT_VOICE
        assert captured["speed"] == 1.2

    def test_output_file_written(self, ready_refs, monkeypatch, tmp_path):
        wav = _make_wav_bytes(0.3)
        import httpx
        monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResponse(200, wav))

        out = tmp_path / "nested" / "audio.wav"
        svc = F5TTSService()
        path = svc.synthesize_sync("тест", str(out))

        assert path == str(out)
        assert out.read_bytes() == wav  # родительская папка создана, байты те же

    def test_404_falls_back_to_default_voice(self, ready_refs, monkeypatch, tmp_path):
        """Несуществующий референс не валит генерацию, а откатывается на default."""
        calls = []

        def fake_post(url, json=None, timeout=None):
            calls.append(json["voice"])
            if json["voice"] != DEFAULT_VOICE:
                return _FakeResponse(404)
            return _FakeResponse(200, _make_wav_bytes(0.2))

        import httpx
        monkeypatch.setattr(httpx, "post", fake_post)

        svc = F5TTSService(voice="ghost_voice")
        svc.synthesize_sync("тест", str(tmp_path / "out.wav"))

        assert calls == ["ghost_voice", DEFAULT_VOICE]

    def test_no_bootstrap_for_custom_voice(self, tmp_path, monkeypatch):
        """Для кастомного голоса бутстрап Silero не запускается."""
        monkeypatch.setattr(f5_mod, "REFS_DIR", tmp_path)
        F5TTSService(voice="someone")._ensure_default_ref()
        assert list(tmp_path.iterdir()) == []  # ничего не создано

    def test_bootstrap_voices_female_and_male(self):
        """Из коробки два авто-голоса: женский (default) и мужской."""
        assert BOOTSTRAP_VOICES.get("default") == "xenia"
        assert BOOTSTRAP_VOICES.get("male") == "eugene"

    def test_get_audio_duration(self, tmp_path):
        p = tmp_path / "one_sec.wav"
        p.write_bytes(_make_wav_bytes(1.0))
        assert F5TTSService().get_audio_duration(str(p)) == pytest.approx(1.0, abs=0.01)

    def test_get_audio_duration_missing_file(self):
        assert F5TTSService().get_audio_duration("/nonexistent.wav") == 0.0


class TestEdgeDurationRegression:
    def test_edge_duration_fallback_returns_zero(self):
        """Регрессия: фолбэк ссылался на несуществующую переменную text."""
        from app.services.edge_tts_service import EdgeTTSService

        assert EdgeTTSService().get_audio_duration("/nonexistent.mp3") == 0.0


# ---------------------------------------------------------------------------
# Интеграция: живой сервис f5tts
# ---------------------------------------------------------------------------

@requires_f5
class TestF5ServiceIntegration:
    def test_health(self):
        import httpx
        data = httpx.get(f"{F5TTS_URL}/health", timeout=5).json()
        assert data["status"] == "ok"

    def test_voices_contains_default(self):
        import httpx
        voices = httpx.get(f"{F5TTS_URL}/voices", timeout=5).json()["voices"]
        assert DEFAULT_VOICE in voices

    def test_empty_text_rejected(self):
        assert _synth("   ").status_code == 400

    def test_unknown_voice_404(self):
        assert _synth("тест", voice="no_such_voice_123").status_code == 404

    def test_synthesize_returns_valid_wav(self):
        r = _synth("Нажмите кнопку Сохранить и нажмите Enter.")
        assert r.status_code == 200

        with wave.open(io.BytesIO(r.content), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2  # 16-bit PCM — требование пайплайна
            assert wf.getframerate() == 24000
            duration = wf.getnframes() / wf.getframerate()
        # ~7 слов: явно дольше секунды, но не минуты
        assert 1.0 < duration < 30.0

    def test_speed_shortens_audio(self):
        text = "Это проверка влияния скорости на длительность озвученной фразы."

        def dur(speed):
            r = _synth(text, speed=speed)
            assert r.status_code == 200
            with wave.open(io.BytesIO(r.content), "rb") as wf:
                return wf.getnframes() / wf.getframerate()

        assert dur(1.4) < dur(1.0) * 0.95

    def test_backend_f5_voices_endpoint(self):
        """Бэкенд проксирует список голосов и репортит доступность."""
        import httpx
        try:
            r = httpx.get("http://autodoc-ai:8000/api/v1/video/f5-voices", timeout=5)
        except Exception:
            pytest.skip("autodoc-ai backend is not reachable from here")
        data = r.json()
        assert data["available"] is True
        assert DEFAULT_VOICE in data["voices"]
        assert "male" in data["voices"]

    def test_male_voice_synthesizes(self):
        r = _synth("Проверка мужского голоса.", voice="male")
        assert r.status_code == 200
        with wave.open(io.BytesIO(r.content), "rb") as wf:
            assert wf.getnframes() > 0
