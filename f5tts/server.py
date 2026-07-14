"""
F5-TTS Russian — GPU-микросервис озвучки (файнтюн Misha24-10/F5-TTS_RUSSIAN).

Отдельный контейнер (по аналогии с ollama): основной образ autodoc не тянет
CUDA-зависимости, а модель живёт в /data и переживает пересоздание контейнера.

Модель работает через клонирование голоса: тембр задаётся референс-записью
/data/tts_refs/<voice>/ref.wav + ref.txt (текст, который звучит в записи).
Дефолтный референс бутстрапит основной бэкенд через Silero (см.
app/services/f5_tts_service.py); свой голос — положить пару файлов в новую
папку /data/tts_refs/<имя>/.

API:
    GET  /health              — статус (model_loaded)
    GET  /voices              — список голосов (папки с ref.wav)
    POST /synthesize          — {text, voice, speed} -> WAV (16-bit PCM, 24 кГц)
"""

import io
import logging
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("f5tts")

# Самый свежий чекпоинт репозитория (июль 2026) + vocab от базовой версии
MODEL_REPO = "Misha24-10/F5-TTS_RUSSIAN"
CKPT_FILE = "F5TTS_v1_Base_v4_winter/model_212000.safetensors"
VOCAB_FILE = "F5TTS_v1_Base/vocab.txt"

# Всё в /data (bind-mount ./data) — переживает пересоздание контейнера
MODELS_DIR = Path("/data/torch_hub/f5tts")
RUACCENT_DIR = Path("/data/ruaccent")
REFS_DIR = Path("/data/tts_refs")

app = FastAPI(title="F5-TTS Russian")

_lock = threading.Lock()  # модель не потокобезопасна, синтез строго по одному
_tts = None
_accentizer = None
_accentizer_failed = False


def _get_tts():
    """Ленивая загрузка модели: качается с HF при первом синтезе (~1.4 ГБ)."""
    global _tts
    if _tts is None:
        import torch
        from huggingface_hub import hf_hub_download
        from f5_tts.api import F5TTS

        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        logger.info("Fetching F5-TTS_RUSSIAN checkpoint (cached in /data)...")
        ckpt = hf_hub_download(MODEL_REPO, CKPT_FILE, local_dir=str(MODELS_DIR))
        vocab = hf_hub_download(MODEL_REPO, VOCAB_FILE, local_dir=str(MODELS_DIR))

        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Loading F5-TTS on {device}...")
        _tts = F5TTS(model="F5TTS_v1_Base", ckpt_file=ckpt, vocab_file=vocab, device=device)
        logger.info("F5-TTS loaded")
    return _tts


def _accentuate(text: str) -> str:
    """Расстановка ударений через RUAccent ('+' перед ударной гласной —
    именно такую разметку понимает F5-TTS_RUSSIAN). При недоступности
    RUAccent синтезируем без ударений — модель справляется, но чуть хуже."""
    global _accentizer, _accentizer_failed
    if _accentizer_failed:
        return text
    if _accentizer is None:
        try:
            from ruaccent import RUAccent
            acc = RUAccent()
            try:
                acc.load(omograph_model_size="turbo3.1", use_dictionary=True,
                         workdir=str(RUACCENT_DIR))
            except TypeError:
                # старые версии ruaccent без параметра workdir
                acc.load(omograph_model_size="turbo3.1", use_dictionary=True)
            _accentizer = acc
            logger.info("RUAccent loaded")
        except Exception as e:
            logger.warning(f"RUAccent unavailable, synthesizing without accents: {e}")
            _accentizer_failed = True
            return text
    try:
        return _accentizer.process_all(text)
    except Exception as e:
        logger.warning(f"RUAccent failed on text, using raw: {e}")
        return text


class SynthesizeRequest(BaseModel):
    text: str
    voice: str = "default"
    speed: float = 1.0


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": _tts is not None}


@app.get("/voices")
def voices():
    if not REFS_DIR.exists():
        return {"voices": []}
    names = sorted(d.name for d in REFS_DIR.iterdir()
                   if d.is_dir() and (d / "ref.wav").exists())
    return {"voices": names}


@app.post("/synthesize")
def synthesize(req: SynthesizeRequest):
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty text")

    ref_wav = REFS_DIR / req.voice / "ref.wav"
    ref_txt = REFS_DIR / req.voice / "ref.txt"
    if not ref_wav.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Voice '{req.voice}' not found: put ref.wav + ref.txt into {REFS_DIR / req.voice}",
        )
    ref_text = ref_txt.read_text(encoding="utf-8").strip() if ref_txt.exists() else ""

    # F5 интонирует по знакам препинания — фраза без точки звучит оборванно
    if text[-1] not in ".!?…":
        text += "."
    text = _accentuate(text)

    with _lock:
        tts = _get_tts()
        logger.info(f"Synthesizing (voice={req.voice}, speed={req.speed}): {text[:60]}...")
        # Фиксированный seed: одинаковая манера речи во всех шагах одного видео
        wav, sr, _ = tts.infer(
            ref_file=str(ref_wav),
            ref_text=ref_text,
            gen_text=text,
            speed=req.speed,
            remove_silence=False,
            seed=42,
        )

    import soundfile as sf
    buf = io.BytesIO()
    # 16-bit PCM — дальше по пайплайну wave/pydub/ffmpeg (float-WAV они не едят)
    sf.write(buf, wav, sr, format="WAV", subtype="PCM_16")
    return Response(content=buf.getvalue(), media_type="audio/wav")
