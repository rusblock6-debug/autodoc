# F5-TTS Russian — GPU-микросервис озвучки.
# Отдельный образ, чтобы CUDA-torch (~5 ГБ) не раздувал основной образ autodoc.
# Сама модель (~1.4 ГБ) в образ НЕ зашита — качается лениво в /data при первом
# синтезе (тот же паттерн, что у Whisper/Silero).

FROM pytorch/pytorch:2.5.1-cuda12.1-cudnn9-runtime

# Кэши HF/torch — в /data (bind-mount), переживают пересоздание контейнера
ENV HF_HOME=/data/hf_cache \
    TORCH_HOME=/data/torch_hub \
    PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir \
    f5-tts \
    ruaccent \
    fastapi \
    "uvicorn[standard]" \
    soundfile

COPY server.py /srv/server.py

EXPOSE 8010

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8010", "--app-dir", "/srv"]
