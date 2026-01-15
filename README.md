# AutoDoc AI System (MVP)

## Концепция

**AutoDoc AI** — минималистичная платформа, которая превращает запись экрана с голосом и кликами в пошаговый текстовый гайд и короткое вертикальное видео (Shorts). Пользователь говорит и кликает, система сама извлекает скриншоты по кликам, очищает речь до внятных инструкций и предоставляет удобный редактор шагов. Все AI-модели работают локально — никакие данные не покидают вашу инфраструктуру.

## Ключевые возможности (MVP)

Платформа автоматизирует создание обучающих материалов от записи до готового гайда и видео. Расширение для браузера записывает экран, аудио с микрофона и логирует события кликов с точными координатами и таймкодами. Бэкенд автоматически разбивает запись на логические шаги на основе кликов и речевых фрагментов, извлекает скриншоты в моменты взаимодействий и применяет AI для нормализации речи в чёткие инструкции. Готовый результат можно экспортировать как Markdown или HTML, а также сгенерировать Shorts с озвучкой и визуальными маркерами кликов.

| Функционал | Описание |
|------------|----------|
| **Запись экрана** | Chrome-расширение записывает экран, микрофон, логирует клики |
| **Авто-шаги** | Система разбивает сессию на шаги по кликам и речи |
| **Нормализация** | ASR → LLM очищает «эм, ну нужно вот тут нажать» в «Нажмите кнопку „Начать“» |
| **Маркеры кликов** | Жёлтые маркеры на скриншотах в точках кликов |
| **Редактор шагов** | Web UI: скриншот + маркер + текст, можно редактировать |
| **Экспорт** | Markdown или HTML со скриншотами и инструкциями |
| **Озвучка + Shorts** | TTS на русском + сборка вертикального видео с маркерами |
| **Приватность** | Локальные AI-модели, без внешних API |

## Архитектура (MVP)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AutoDoc AI System (MVP)                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │            Chrome Extension (Browser Extension)              │    │
│  │  ┌───────────┐  ┌───────────┐  ┌─────────────────────────┐  │    │
│  │  │  Screen   │  │  Mic &    │  │  Click Logger           │  │    │
│  │  │ Recording │  │  Audio    │  │  (timestamp + coords)   │  │    │
│  │  └───────────┘  └───────────┘  └─────────────────────────┘  │    │
│  │                               │                               │    │
│  │                               ▼                               │    │
│  │                    POST /api/v1/sessions/upload               │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                │                                    │
│                                ▼                                    │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                      FastAPI Backend                         │    │
│  │  ┌─────────────┐  ┌────────────────────────────────────────┐│    │
│  │  │   Session   │  │         Processing Pipeline            ││    │
│  │  │   Storage   │  │  ┌──────────┐  ┌────────────────────┐  ││    │
│  │  │             │  │  │  ASR     │  │  Step Detector      │  ││    │
│  │  │  PostgreSQL │  │  │Whisper   │──│  (clicks + speech)  │  ││    │
│  │  │  (Sessions) │  │  └──────────┘  └────────────────────┘  ││    │
│  │  └─────────────┘  │         │                │              ││    │
│  │                   │         ▼                ▼              ││    │
│  │                   │  ┌──────────┐  ┌────────────────────┐  ││    │
│  │                   │  │   LLM    │  │ Screenshot Extractor│  ││    │
│  │                   │  │ Normalize│  │  (FFmpeg)           │  ││    │
│  │                   │  └──────────┘  └────────────────────┘  ││    │
│  │                   └────────────────────────────────────────┘│    │
│  │                               │                               │    │
│  │         ┌─────────────────────┼─────────────────────┐        │    │
│  │         ▼                     ▼                     ▼        │    │
│  │  ┌─────────────┐      ┌─────────────┐      ┌────────────────┐ │    │
│  │  │  Guide CRUD │      │Step Editor  │      │ Shorts Gen     │ │    │
│  │  │  (REST API) │      │ (Web UI)    │      │ (TTS + Video)  │ │    │
│  │  └─────────────┘      └─────────────┘      └────────────────┘ │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                │                                    │
│         ┌──────────────────────┼──────────────────────┐             │
│         ▼                      ▼                      ▼             │
│  ┌─────────────┐      ┌─────────────┐      ┌────────────────┐      │
│  │ PostgreSQL  │      │    MinIO    │      │   Local AI     │      │
│  │ (Guides)    │      │ (S3 Storage)│      │   Models       │      │
│  └─────────────┘      └─────────────┘      └────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
```

## Технологический стек

### Базовые технологии

Платформа использует современный стек технологий для обеспечения производительности и удобства разработки. FastAPI служит основным веб-фреймворком, обеспечивая высокую скорость работы, автоматическую валидацию данных через Pydantic и встроенную генерацию документации Swagger и OpenAPI. PostgreSQL используется для хранения всех данных о гайдах, шагах и сессиях записи. MinIO предоставляет S3-совместимое объектное хранилище для видео, аудио и извлечённых скриншотов. Redis работает как брокер задач Celery для асинхронной обработки AI-операций.

| Компонент | Технология | Назначение |
|-----------|------------|------------|
| **Backend** | FastAPI + Python 3.10 | REST API, бизнес-логика |
| **Database** | PostgreSQL 15 | Хранение гайдов, шагов, сессий |
| **Queue** | Redis 7 + Celery | Фоновая обработка AI-задач |
| **Storage** | MinIO (S3) | Видео, аудио, скриншоты |
| **Browser Extension** | Chrome Extension | Запись экрана, кликов, аудио |

### AI/ML технологии (локальные)

Все AI-модели работают исключительно локально на вашем GPU. Это обеспечивает полную приватность данных — никакие видео, аудио или тексты не покидают вашу инфраструктуру. Whisper выполняет автоматическое распознавание речи, преобразуя аудиозапись в текст с таймкодами. Локальная LLM через llama-cpp-python нормализует распознанную речь, превращая «эм, ну нужно вот тут нажать на начать» в чёткую инструкцию «Нажмите кнопку „Начать“». TTS генерирует озвучку для Shorts на русском языке.

| Компонент | Модель | Формат | Назначение |
|-----------|--------|--------|------------|
| **ASR** | OpenAI Whisper (medium) | PyTorch CUDA | Распознавание речи → текст + таймкоды |
| **LLM** | Qwen 2.5 7B / Llama 3.1 8B | GGUF (llama-cpp) | Нормализация речи в инструкции |
| **TTS** | Edge TTS / локальный | API / Local | Озвучка шагов для Shorts |
| **Video** | FFmpeg | CUDA | Извлечение скриншотов, сборка Shorts |

### Требования к инфраструктуре

Для запуска MVP требуется Docker с поддержкой GPU NVIDIA. Система протестирована на Ubuntu 22.04 с драйверами NVIDIA версии 535 и выше. Минимальная конфигурация включает 8GB VRAM, 16GB RAM и 100GB SSD.

```
Требования к серверу:
├── Docker Engine >= 24.0
├── Docker Compose >= 2.20
├── NVIDIA Container Toolkit
├── NVIDIA GPU (минимум 8GB VRAM)
├── 16GB RAM (минимум)
└── 100GB SSD storage
```

## Быстрый старт

### Предварительная подготовка

Перед установкой убедитесь, что Docker и NVIDIA Container Toolkit настроены правильно:

```bash
# Проверка Docker
docker --version          # Ожидается: Docker version 24.0+
docker compose version    # Ожидается: Docker Compose version v2.20+

# Проверка NVIDIA GPU (обязательно для AI!)
nvidia-smi
# Ожидается: информация о GPU без ошибок
```

### Запуск системы

```bash
# 1. Клонируйте репозиторий
git clone <repository-url>
cd autodoc_ai

# 2. Создайте директории для данных
mkdir -p data/models data/uploads data/output

# 3. Настройте окружение
cp .env.example .env
# Отредактируйте .env при необходимости

# 4. Запустите все сервисы
docker-compose up -d

# 5. Проверьте статус
docker-compose ps

# 6. Проверьте API
curl http://localhost:8000/health
```

### Проверка работоспособности

После запуска API должен вернуть:

```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "minio": "connected",
  "gpu_available": true
}

Документация API доступна по адресу http://localhost:8000/docs

### Доступ к сервисам

| Сервис | URL | Учётные данные |
|--------|-----|----------------|
| **API** | http://localhost:8000 | — |
| **Swagger Docs** | http://localhost:8000/docs | — |
| **MinIO Console** | http://localhost:9001 | minioadmin / minioadmin |
| **pgAdmin** | http://localhost:5050 | admin@autodoc.local / admin |

## Конфигурация

### Переменные окружения

Создайте файл `.env` в корневой директории проекта:

```env
# =============================================================================
# БАЗОВАЯ КОНФИГУРАЦИЯ
# =============================================================================
APP_NAME=AutoDoc AI System
APP_VERSION=1.0.0
DEBUG=true
ENVIRONMENT=development

# =============================================================================
# POSTGRESQL DATABASE
# =============================================================================
DATABASE_HOST=postgres
DATABASE_PORT=5432
DATABASE_USER=autodoc
DATABASE_PASSWORD=autodoc_secret
DATABASE_NAME=autodoc_db

# =============================================================================
# REDIS QUEUE (Celery Broker)
# =============================================================================
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_URL=redis://redis:6379/0

# =============================================================================
# MINIO S3 STORAGE
# =============================================================================
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_VIDEOS=autodoc-videos
MINIO_BUCKET_SCREENSHOTS=autodoc-screenshots
MINIO_BUCKET_UPLOADS=autodoc-uploads

# =============================================================================
# AI MODELS - ПОЛНОСТЬЮ ЛОКАЛЬНЫЕ (ПРИВАТНОСТЬ!)
# =============================================================================
# ASR: Whisper для распознавания речи
WHISPER_MODEL_SIZE=medium
WHISPER_DEVICE=cuda

# LLM: Локальная модель через llama-cpp-python (GGUF формат)
# Qwen2.5-7B-Instruct-GGUF: 4.7GB, влезает в 8GB VRAM
LLM_MODEL_NAME=Qwen/Qwen2.5-7B-Instruct-GGUF
LLM_MODEL_PATH=/data/models/Qwen2.5-7B-Instruct-Q4_0.gguf
LLM_THREADS=8
LLM_CONTEXT_SIZE=4096
LLM_MAX_TOKENS=2048
LLM_TEMPERATURE=0.7

# Внешние API отключены - всё работает локально!
LLM_API_KEY=

# TTS: Озвучка для Shorts
TTS_ENGINE=edge-tts
EDGE_TTS_VOICE=ru-RU-SvetlanaNeural

# =============================================================================
# GPU КОНФИГУРАЦИЯ
# =============================================================================
GPU_DEVICE_ID=0
GPU_MEMORY_FRACTION=0.8
NVIDIA_VISIBLE_DEVICES=all

# =============================================================================
# ПУТИ
# =============================================================================
WORKER_TEMP_DIR=/tmp/autodoc_worker_temp
```

### Структура томов Docker

```
./data/                    → /data (основные данные)
├── models/                → /data/models (AI модели GGUF)
├── uploads/               → /data/uploads (загруженные сессии)
├── output/                → /data/output (готовые Shorts)
└── screenshots/           → /data/screenshots (извлечённые скриншоты)
```

## API Endpoints

### Сессии записи

Работа с загруженными сессиями записи:

```http
# Загрузить новую сессию (видео + аудио + лог клиентов)
POST /api/v1/sessions/upload
Content-Type: multipart/form-data

file_video: (video.webm)
file_audio: (audio.wav)
file_clicks: (clicks.json)

# Ответ:
{
  "session_id": "uuid-сессии",
  "status": "uploaded",
  "duration_seconds": 120
}

# Список всех сессий
GET /api/v1/sessions?status=all&page=1&page_size=20

# Получить сессию
GET /api/v1/sessions/{session_id}

# Удалить сессию
DELETE /api/v1/sessions/{session_id}
```

### Гайды (CRUD)

Базовые операции с гайдами:

```http
# Создать гайд из сессии
POST /api/v1/guides
Content-Type: application/json

{
  "session_id": "uuid-сессии",
  "title": "Как создать документ",
  "language": "ru"
}

# Список гайдов
GET /api/v1/guides?page=1&page_size=20

# Получить гайд со всеми шагами
GET /api/v1/guides/{guide_id}

# Обновить гайд
PATCH /api/v1/guides/{guide_id}
Content-Type: application/json

{
  "title": "Обновлённое название",
  "is_published": true
}

# Удалить гайд
DELETE /api/v1/guides/{guide_id}
```

### Шаги (редактирование)

Операции с шагами внутри гайда:

```http
# Получить все шаги гайда
GET /api/v1/guides/{guide_id}/steps

# Обновить текст шага (нормализация)
PATCH /api/v1/steps/{step_id}
Content-Type: application/json

{
  "instruction_text": "Нажмите кнопку 'Создать документ'"
}

# Изменить позицию маркера на скриншоте
PATCH /api/v1/steps/{step_id}/marker
Content-Type: application/json

{
  "marker_x": 450,
  "marker_y": 320
}

# Переместить шаг (изменить порядок)
PATCH /api/v1/steps/{step_id}/reorder
Content-Type: application/json

{
  "new_position": 2
}

# Удалить шаг
DELETE /api/v1/steps/{step_id}

# Объединить несколько шагов
POST /api/v1/steps/merge
Content-Type: application/json

{
  "step_ids": [1, 2],
  "merged_instruction": "Нажмите Создать и заполните форму"
}
```

### Экспорт

Генерация готового гайда в текстовом формате:

```http
# Экспорт в Markdown
GET /api/v1/guides/{guide_id}/export/markdown

# Экспорт в HTML
GET /api/v1/guides/{guide_id}/export/html

# Ответ (Markdown):
# # Как создать документ
#
# ## Шаг 1
# ![Screenshot](screenshots/step_1.png)
# Нажмите кнопку "Создать документ"
#
# ## Шаг 2
# ![Screenshot](screenshots/step_2)
# Введите название документа
```

### Генерация Shorts

Создание вертикального видео с озвучкой:

```http
# Запустить генерацию Shorts
POST /api/v1/guides/{guide_id}/shorts/generate
Content-Type: application/json

{
  "tts_voice": "ru-RU-SvetlanaNeural",
  "target_platform": "tiktok",
  "duration_per_step": 5,
  "add_music": false
}

# Ответ:
{
  "task_id": "uuid-задачи",
  "status": "queued",
  "estimated_time": 120
}

# Проверить статус генерации
GET /api/v1/shorts/{task_id}/status

# Скачать готовый Shorts
GET /api/v1/shorts/{task_id}/download
```

## Структура проекта

```
autodoc_ai/
├── app/                              # Основное приложение
│   ├── api/                          # API endpoints (FastAPI Router)
│   │   ├── __init__.py
│   │   ├── sessions.py               # Загрузка сессий
│   │   ├── guides.py                 # CRUD гайдов
│   │   ├── steps.py                  # Редактирование шагов
│   │   ├── export.py                 # Экспорт Markdown/HTML
│   │   └── shorts.py                 # Генерация Shorts
│   ├── core/                         # Конфигурация и безопасность
│   │   ├── config.py                 # Pydantic Settings
│   │   ├── security.py               # JWT (опционально)
│   │   └── database.py               # PostgreSQL подключение
│   ├── models/                       # SQLAlchemy модели
│   │   ├── __init__.py
│   │   ├── session.py                # Модель сессии записи
│   │   ├── guide.py                  # Модель гайда
│   │   └── step.py                   # Модель шага
│   ├── schemas/                      # Pydantic схемы (DTO)
│   │   ├── __init__.py
│   │   ├── session.py
│   │   ├── guide.py
│   │   └── step.py
│   ├── services/                     # Бизнес-логика
│   │   ├── __init__.py
│   │   ├── asr_service.py            # Whisper (ASR)
│   │   ├── llm_service.py            # LLM нормализация
│   │   ├── step_detector.py          # Выделение шагов
│   │   ├── screenshot_service.py     # Извлечение скриншотов
│   │   ├── tts_service.py            # TTS озвучка
│   │   └── shorts_generator.py       # Сборка Shorts
│   ├── tasks.py                      # Celery задачи
│   └── main.py                       # FastAPI приложение
├── extension/                        # Chrome Extension
│   ├── manifest.json
│   ├── background.js
│   ├── content.js
│   ├── popup.html
│   └── popup.js
├── tests/                            # Тесты
│   ├── __init__.py
│   └── test_*.py
├── data/                             # Локальные данные
│   ├── models/                       # AI модели (GGUF)
│   ├── uploads/                      # Загруженные сессии
│   ├── screenshots/                  # Извлечённые скриншоты
│   └── output/                       # Готовые Shorts
├── Dockerfile                        # Docker образ
├── docker-compose.yml                # Docker Compose
├── requirements.txt                  # Python зависимости
├── .env.example                      # Пример конфигурации
└── README.md                         # Этот файл
```

## Поток обработки данных

### Шаг 1: Запись (Browser Extension)

Пользователь устанавливает Chrome-расширение и нажимает «Записать». Расширение захватывает экран через MediaRecorder API, записывает аудио с микрофона и логирует каждый клик с точными координатами и таймкодами. По завершении все данные отправляются на бэкенд.

```javascript
// Пример лога кликов (extension/content.js)
{
  "clicks": [
    {
      "timestamp": 5.234,   // секунды от начала записи
      "x": 450,
      "y": 320,
      "element": "button"
    },
    {
      "timestamp": 12.891,
      "x": 780,
      "y": 450,
      "element": "input"
    }
  ]
}
```

### Шаг 2: Загрузка и хранение

Бэкенд принимает загруженные файлы, сохраняет их в MinIO и создаёт запись сессии в PostgreSQL с метаданными, включая длительность, количество кликов и статус обработки.

### Шаг 3: ASR — распознавание речи

Celery-воркер запускает Whisper для преобразования аудио в текст с таймкодами:

```python
# app/services/asr_service.py
import whisper

def transcribe_with_timestamps(audio_path: str) -> dict:
    model = whisper.load_model("medium")
    result = model.transcribe(audio_path, word_timestamps=True)
    
    # Результат:
    # {
    #   "text": "нужно нажать на кнопку начать...",
    #   "segments": [
    #     {"start": 5.0, "end": 8.0, "text": "нужно нажать"},
    #     {"start": 8.0, "end": 12.0, "text": "на кнопку начать"}
    #   ]
    # }
    return result
```

### Шаг 4: Выделение шагов

Алгоритм разбивает сессию на шаги на основе кликов и ближайших речевых фрагментов:

```python
# app/services/step_detector.py
def detect_steps(clicks: list, transcription: dict) -> list:
    steps = []
    
    for click in clicks:
        # Найти ближайший речевой сегмент к клику
        nearest_segment = find_nearest_segment(click["timestamp"], transcription)
        
        steps.append({
            "click_timestamp": click["timestamp"],
            "click_x": click["x"],
            "click_y": click["y"],
            "raw_speech": nearest_segment["text"],
            "speech_start": nearest_segment["start"],
            "speech_end": nearest_segment["end"]
        })
    
    return steps
```

### Шаг 5: LLM — нормализация речи

Локальная LLM очищает распознанную речь от «эм», «ну», повторов и преобразует в чёткие инструкции:

```python
# app/services/llm_service.py
def normalize_instruction(raw_speech: str) -> str:
    prompt = f"""
Преобразуй речь в краткую чёткую инструкцию.
Убери "эм", "ну", повторы, слова-паразиты.
Говори повелительным тоном на "вы".

Вход: "{raw_speech}"
Выход: "Нажмите кнопку 'Начать'"
"""
    
    result = llm(prompt, max_tokens=100, temperature=0.3)
    return result.strip('"').strip()
```

### Шаг 6: Извлечение скриншотов

FFmpeg извлекает кадры в момент каждого клика:

```bash
# app/services/screenshot_service.py
ffmpeg -i input.webm -ss 00:00:05.234 -vframes 1 \
  -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2" \
  screenshots/step_1.png
```

### Шаг 7: Редактирование (Web UI)

Пользователь открывает Web UI и видит последовательность шагов. Каждый шаг показывает скриншот с жёлтым маркером в точке клика, оригинальную речь и нормализованную инструкцию. Пользователь может редактировать текст, перетаскивать маркеры, менять порядок шагов, удалять или объединять их.

### Шаг 8: Экспорт

После подтверждения пользователь может экспортировать гайд в Markdown или HTML со встроенными скриншотами.

### Шаг 9: Генерация Shorts

Если пользователь хочет видео, система генерирует Shorts:

```python
# app/services/shorts_generator.py
def generate_shorts(guide: Guide, steps: list) -> str:
    """
    Пошаговый процесс:
    1. TTS генерирует аудио для каждого шага
    2. FFmpeg собирает вертикальное видео:
       - Берёт скриншот шага
       - Рисует маркер клика
       - Накладывает озвучку
       - Добавляет заголовок "Шаг N"
    3. Склеивает все шаги в одно видео
    """
    
    for step in steps:
        # Генерация озвучки
        audio_path = tts.generate(f"Шаг {step.order}. {step.instruction}")
        
        # Сборка кадра
        ffmpeg -i step_screenshot.png \
          -i marker_overlay.png \
          -i audio.wav \
          -filter_complex "[0][1]overlay" \
          step_output.mp4
    
    # Склейка всех шагов
    ffmpeg -f concat -i steps_list.txt -c copy shorts_final.mp4
    
    return output_path
```

## AI-модели и производительность

### Оптимальные конфигурации GPU

| GPU VRAM | Whisper | LLM Model | Квантизация | Notes |
|----------|---------|-----------|-------------|-------|
| 8 GB | medium | Qwen 2.5 7B | Q4_0 | Оптимально для MVP |
| 16 GB | medium | Qwen 2.5 7B | Q5_1 | Лучшее качество |
| 24 GB | large-v3 | Llama 3.1 8B | Q4_0 | Максимальное качество |

### Скачивание моделей

Модели скачиваются автоматически при первом запуске:

```bash
# Whisper (автоматически через pip install openai-whisper)
# Qwen 2.5 7B GGUF (~4.7GB)
# Скачивается huggingface-hub в /data/models/

# Проверка моделей
ls -la data/models/
# Ожидается:
# Qwen2.5-7B-Instruct-Q4_0.gguf
```

## Безопасность и приватность

Система спроектирована с учётом максимальной приватности. Все AI-модели работают локально — никакие видео, аудио, тексты или метаданные не передаются во внешние сервисы. Данные хранятся в вашей инфраструктуре под вашим полным контролем. Никаких внешних API, таких как OpenAI или Anthropic, не требуется.

```
ПРИВАТНОСТЬ (всё локально):
├── Whisper (PyTorch CUDA)              Локально
├── Qwen/Llama (llama-cpp-python GGUF)  Локально
├── Edge TTS (опционально)              Требует интернет
├── MinIO (S3)                          Локально
├── PostgreSQL                          Локально
└── Внешние API (OpenAI, Anthropic)     Не используются
```

## Разработка

### Локальный запуск без Docker

```bash
# 1. Создайте виртуальное окружение
python -m venv venv
source venv/bin/activate

# 2. Установите зависимости
pip install -r requirements.txt

# 3. Запустите внешние сервисы (PostgreSQL, Redis, MinIO)
#    или используйте docker-compose для них:
docker-compose up -d postgres redis minio

# 4. Запустите приложение
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 5. Запустите Celery воркер (отдельный терминал)
celery -A app.tasks worker --loglevel=info
```

### Тестирование

```bash
# Запуск тестов
pytest tests/ -v

# Тесты с покрытием
pytest tests/ --cov=app --cov-report=html
```

### Установка Chrome Extension

```bash
# В Chrome:
# 1. Откройте chrome://extensions/
# 2. Включите "Режим разработчика"
# 3. Нажмите "Загрузить распакованное расширение"
# 4. Выберите папку extension/
```

## Мониторинг

```bash
# Проверка здоровья API
curl http://localhost:8000/health

# Логи приложения
docker-compose logs -f autodoc-ai

# Логи Celery
docker-compose logs -f autodoc-celery

# GPU метрики
docker-compose exec autodoc-ai nvidia-smi
```

## Лицензия

MIT License — свободное использование для любых целей, включая коммерческие.

---

**AutoDoc AI System (MVP)** — Превращайте записи экрана в гайды и видео за минуты. С полной приватностью.
