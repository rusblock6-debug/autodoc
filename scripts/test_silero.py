"""
Тест Silero TTS (v5_5_ru — самый свежий русский) — генерирует текст шага
доступными голосами, чтобы послушать и выбрать самый естественный.

Запуск внутри контейнера:
    docker compose exec celery-worker python scripts/test_silero.py

Результат: /data/silero_samples/<voice>.wav  (на хосте — ./data/silero_samples/)
"""

import os
import time
import shutil
import urllib.request
import torch

MODEL_URL = "https://models.silero.ai/models/tts/ru/v5_5_ru.pt"
MODELS_DIR = "/data/torch_hub/models"
MODEL_PATH = os.path.join(MODELS_DIR, "v5_5_ru.pt")

OUT_DIR = "/data/silero_samples"
SAMPLE_RATE = 48000

# Текст шага. Числа и латиница — намеренно, чтобы увидеть как модель их читает.
TEXT = (
    "Нажмите на кнопку «Сохранить» в правом верхнем углу экрана. "
    "После этого откроется форма с настройками профиля. "
    "Введите имя пользователя и подтвердите действие, затем нажмите Enter."
)


def main():
    # Чистим старые сэмплы (v4)
    if os.path.isdir(OUT_DIR):
        shutil.rmtree(OUT_DIR)
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(MODELS_DIR, exist_ok=True)

    # Скачиваем модель один раз
    if not os.path.exists(MODEL_PATH):
        print(f"Скачивание {MODEL_URL} ...")
        t0 = time.time()
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print(f"Скачано за {time.time() - t0:.1f}с ({os.path.getsize(MODEL_PATH)/1e6:.0f} МБ)\n")

    print("Загрузка модели v5_5_ru...")
    t0 = time.time()
    device = torch.device("cpu")
    model = torch.package.PackageImporter(MODEL_PATH).load_pickle("tts_models", "model")
    model.to(device)
    torch.set_num_threads(os.cpu_count() or 4)
    print(f"Модель загружена за {time.time() - t0:.1f}с")

    speakers = [s for s in model.speakers if not s.startswith("random")]
    print(f"Доступные голоса: {model.speakers}\n")

    for voice in speakers:
        try:
            t0 = time.time()
            path = os.path.join(OUT_DIR, f"{voice}.wav")
            audio = model.apply_tts(
                text=TEXT,
                speaker=voice,
                sample_rate=SAMPLE_RATE,
                put_accent=True,
                put_yo=True,
            )
            _save(path, audio, SAMPLE_RATE)
            dur = audio.shape[-1] / SAMPLE_RATE
            gen = time.time() - t0
            print(f"[{voice}] -> {path}  ({dur:.1f}с аудио / {gen:.1f}с генерация, RTF={gen/dur:.2f})")
        except Exception as e:
            print(f"[{voice}] FAILED: {e}")

    print(f"\nГотово. Файлы на хосте: ./data/silero_samples/")


def _save(path, audio_tensor, sample_rate):
    import torchaudio
    torchaudio.save(path, audio_tensor.unsqueeze(0), sample_rate)


if __name__ == "__main__":
    main()
