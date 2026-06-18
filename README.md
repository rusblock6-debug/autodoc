# AutoDoc AI System (MVP)

Автоматическая платформа для генерации обучающего контента из записей экрана.
Пользователь говорит и кликает — система извлекает скриншоты по кликам, расшифровывает
речь, превращает её в чёткие инструкции и собирает пошаговый гайд и короткое
вертикальное видео (Shorts). Все AI-модели работают локально.

## Быстрый старт

1. Запустите систему:

   ```bash
   docker compose up -d
   ```

   При первом запуске сервис `ollama-init` один раз скачает модели в volume
   (`qwen2.5:3b` и `qwen2.5vl:3b`) — это требует интернета только на первом `up`.

2. Установите расширение Chrome:
   - Откройте `chrome://extensions/`
   - Включите «Режим разработчика»
   - Нажмите «Загрузить распакованное расширение»
   - Выберите папку `extension/`

3. Создайте первый гайд:
   - Нажмите на иконку расширения
   - Введите название записи
   - Нажмите «Начать запись», разрешите захват экрана
   - ОБЯЗАТЕЛЬНО делайте клики по элементам страницы (по ним строятся шаги)
   - Нажмите «Остановить» — система откроет редактор

4. Доступ к системе (хост-порты по умолчанию из `.env`):
   - Frontend: http://localhost:3001
   - API: http://localhost:8888
   - API Docs (Swagger): http://localhost:8888/docs

## AI / Vision — описания шагов

Тексты шагов («Нажмите кнопку …») генерирует ollama, который запускается
ВНУТРИ docker-стека (сервис `ollama`), поэтому «улучшить шаг» работает из коробки
без ручного старта ollama на хосте.

Используются две модели:

| Режим | Модель | Назначение |
|-------|--------|------------|
| Regenerate (по скриншоту) | `qwen2.5vl:3b` (vision) | смотрит на скриншот клика и описывает действие |
| Улучшить шаг | `qwen2.5:3b` (text) | полировка грамматики и формулировок, работает мгновенно |

Модели и адрес ollama настраиваются в `.env`:

```env
LLM_API_BASE=http://ollama:11434/v1   # OpenAI-совместимый эндпоинт ollama внутри сети
LLM_API_KEY=ollama                     # любое непустое значение (ollama его игнорирует)
VISION_MODEL=qwen2.5vl:3b              # на сервере с мощным GPU — 7b/32b точнее
TEXT_MODEL=qwen2.5:3b
VISION_SEND_FULL_IMAGE=true            # false = слать только кроп вокруг клика (экономит VRAM)
```

В редакторе гайда:
- «Улучшить с помощью AI» — полировка текста шага (text-модель).
- «Перегенерировать» — анализ скриншота заново (vision-модель видит маркер клика
  и увеличенный фрагмент вокруг него). Прогресс виден в UI.

Проверка, что ollama доступна из контейнера:

```bash
docker exec autodoc-celery printenv LLM_API_BASE VISION_MODEL TEXT_MODEL
docker exec autodoc-ollama ollama list   # должны быть qwen2.5:3b и qwen2.5vl:3b
```

## Если что-то не работает

Смотрите подробную диагностику в [Documentation/EXTENSION_DEBUG_GUIDE.md](Documentation/EXTENSION_DEBUG_GUIDE.md).

## Концепция

AutoDoc AI — минималистичная платформа, которая превращает запись экрана с голосом и
кликами в пошаговый текстовый гайд и короткое вертикальное видео. Расширение для браузера
записывает экран, аудио с микрофона и логирует клики с точными координатами и таймкодами.
Бэкенд разбивает запись на логические шаги по кликам и речевым фрагментам, извлекает
скриншоты в моменты взаимодействий и применяет AI для нормализации речи в чёткие инструкции.
Готовый результат можно экспортировать как Markdown или HTML, а также сгенерировать Shorts
с озвучкой и визуальными маркерами кликов. Все AI-модели работают локально — данные не
покидают вашу инфраструктуру.

## Ключевые возможности (MVP)

| Функционал | Описание |
|------------|----------|
| Запись экрана | Chrome-расширение записывает экран, микрофон, логирует клики |
| Авто-шаги | Система разбивает сессию на шаги по кликам и речи |
| Нормализация | ASR + LLM очищают «эм, ну нужно вот тут нажать» в «Нажмите кнопку „Начать"» |
| Vision-описания | Vision-модель описывает действие по скриншоту клика |
| Маркеры кликов | Жёлтые маркеры на скриншотах в точках кликов |
| Редактор шагов | Web UI: скриншот + маркер + текст, можно редактировать |
| Экспорт | Markdown или HTML со скриншотами и инструкциями |
| Озвучка + Shorts | TTS на русском + сборка вертикального видео с маркерами |
| Приватность | Локальные AI-модели, без внешних API |

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
│  │                          │                                   │    │
│  │                          ▼  POST /api/v1/sessions/upload     │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                │                                    │
│                                ▼                                    │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                      FastAPI Backend                         │    │
│  │   ASR (Whisper) → Step Detector (clicks + speech) →          │    │
│  │   LLM Normalize (ollama) + Screenshot Extractor (FFmpeg)     │    │
│  │   → Guide CRUD / Step Editor / Shorts Gen (TTS + Video)      │    │
│  └─────────────────────────────────────────────────────────────┘    │
│         │                  │                  │            │         │
│         ▼                  ▼                  ▼            ▼         │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐  ┌──────────┐   │
│  │ PostgreSQL │    │  Local FS  │    │   ollama   │  │  React   │   │
│  │ (Guides)   │    │  (/data)   │    │ (LLM/Vis.) │  │ Frontend │   │
│  └────────────┘    └────────────┘    └────────────┘  └──────────┘   │
│        Celery worker + Redis — фоновая обработка AI-задач            │
└─────────────────────────────────────────────────────────────────────┘
```

## Технологический стек

### Базовые технологии

| Компонент | Технология | Назначение |
|-----------|------------|------------|
| Backend | FastAPI + Python 3.10 | REST API, бизнес-логика |
| Frontend | React + Vite + Tailwind CSS | Web UI редактора гайдов |
| Database | PostgreSQL 15 | Хранение гайдов, шагов, сессий |
| Queue | Redis 7 + Celery | Фоновая обработка AI-задач |
| Storage | Local File System | Видео, аудио, скриншоты в `/data` |
| Browser Extension | Chrome Extension | Запись экрана, кликов, аудио |

### AI/ML технологии (локальные)

Все AI-модели работают локально. Whisper расшифровывает речь в текст с таймкодами.
ollama (внутри docker-стека) выполняет нормализацию речи и vision-описания по скриншотам.
TTS генерирует озвучку для Shorts на русском.

| Компонент | Модель / движок | Назначение |
|-----------|-----------------|------------|
| ASR | OpenAI Whisper (medium) | Распознавание речи → текст + таймкоды |
| LLM (текст) | ollama `qwen2.5:3b` | Нормализация речи, полировка шагов |
| Vision | ollama `qwen2.5vl:3b` | Описание действия по скриншоту клика |
| TTS | Silero (по умолчанию) / Edge-TTS / Chatterbox | Озвучка шагов для Shorts |
| Video | FFmpeg | Извлечение скриншотов, сборка Shorts |

TTS-движок выбирается параметром `tts_engine` при генерации Shorts:
- `silero` — офлайн, русские голоса (`xenia`, `baya`, `aidar`, `eugene`, `kseniya`),
  модель хранится локально, интернет не нужен.
- `edge` — Microsoft Edge TTS, требует интернет, голос `ru-RU-SvetlanaNeural` и др.
- `chatterbox` — нейронная озвучка с эмоциональной окраской.

### Требования к инфраструктуре

```
├── Docker Engine >= 24.0
├── Docker Compose >= 2.20
├── ~16 GB RAM
└── GPU NVIDIA опционально — ускоряет ollama и Whisper.
    Dev-образ работает на CPU (WHISPER_DEVICE=cpu); для CUDA используйте
    docker-compose.gpu.yml и настройте NVIDIA Container Toolkit.
```

## Конфигурация

Все настройки задаются в файле `.env` в корне проекта. Ключевые блоки:

```env
# === Хост-порты (вынесены, чтобы не конфликтовать с другими проектами) ===
API_PORT=8888              # http://localhost:8888 → контейнер :8000
FRONTEND_PORT=3001
POSTGRES_HOST_PORT=15432

# === PostgreSQL ===
DATABASE_HOST=postgres
DATABASE_USER=autodoc
DATABASE_PASSWORD=autodoc_secret
DATABASE_NAME=autodoc_db

# === Redis ===
REDIS_HOST=redis
REDIS_PORT=6379

# === ASR (Whisper) ===
WHISPER_MODEL_SIZE=medium
WHISPER_DEVICE=cpu          # cuda или cpu (dev-образ без CUDA → cpu)

# === LLM / Vision (ollama внутри стека) ===
LLM_API_BASE=http://ollama:11434/v1
LLM_API_KEY=ollama
VISION_MODEL=qwen2.5vl:3b
TEXT_MODEL=qwen2.5:3b
VISION_SEND_FULL_IMAGE=true

# === TTS ===
TTS_ENGINE=silero           # silero / edge-tts / chatterbox
EDGE_TTS_VOICE=ru-RU-SvetlanaNeural

# === Video ===
SHORTS_WIDTH=1080
SHORTS_HEIGHT=1920
SHORTS_FPS=60
```

### Docker-сервисы

| Сервис | Контейнер | Назначение |
|--------|-----------|------------|
| autodoc-ai | autodoc-ai | FastAPI backend |
| autodoc-frontend | autodoc-frontend | React + Vite UI |
| postgres | autodoc-postgres | База данных |
| redis | autodoc-redis | Брокер задач Celery |
| ollama | autodoc-ollama | Локальный LLM / Vision бэкенд |
| ollama-init | autodoc-ollama-init | One-shot: скачивает модели в volume |
| celery-worker | autodoc-celery | Фоновая обработка AI-задач |

### Структура данных (`./data`)

```
./data/                    → /data (основные данные)
├── models/                AI-модели
├── torch_hub/             кэш Silero TTS (в .gitignore, не коммитится)
├── uploads/               загруженные сессии
├── screenshots/           извлечённые скриншоты
├── audio/                 сгенерированная озвучка
└── output/                готовые Shorts
```

## API Endpoints

### Сессии записи

```http
POST   /api/v1/sessions/upload        # Загрузить сессию (видео + аудио + лог кликов)
GET    /api/v1/sessions               # Список сессий
GET    /api/v1/sessions/{session_id}  # Получить сессию
DELETE /api/v1/sessions/{session_id}  # Удалить сессию
```

### Гайды (CRUD)

```http
POST   /api/v1/guides                 # Создать гайд из сессии
GET    /api/v1/guides                 # Список гайдов
GET    /api/v1/guides/{guide_id}      # Гайд со всеми шагами
PATCH  /api/v1/guides/{guide_id}      # Обновить гайд
DELETE /api/v1/guides/{guide_id}      # Удалить гайд
```

### Шаги (редактирование)

```http
GET    /api/v1/guides/{guide_id}/steps    # Все шаги гайда
PATCH  /api/v1/steps/{step_id}            # Обновить текст шага
PATCH  /api/v1/steps/{step_id}/marker     # Сдвинуть маркер на скриншоте
PATCH  /api/v1/steps/{step_id}/reorder    # Изменить порядок
DELETE /api/v1/steps/{step_id}            # Удалить шаг
POST   /api/v1/steps/merge                # Объединить шаги
```

### Экспорт

```http
GET    /api/v1/guides/{guide_id}/export/markdown
GET    /api/v1/guides/{guide_id}/export/html
```

### Генерация Shorts

```http
POST   /api/v1/guides/{guide_id}/shorts/generate   # Запустить генерацию
GET    /api/v1/shorts/{task_id}/status             # Статус генерации
GET    /api/v1/shorts/{task_id}/download           # Скачать готовый Shorts
```

Полная интерактивная документация — в Swagger: http://localhost:8888/docs.

## Поток обработки данных

1. Запись (Chrome Extension) — захват экрана через MediaRecorder API, аудио с микрофона,
   лог кликов с координатами и таймкодами. По завершении всё отправляется на бэкенд.
2. Загрузка и хранение — бэкенд сохраняет файлы в `/data` и создаёт запись сессии в PostgreSQL.
3. ASR — Celery-воркер запускает Whisper, получает текст с таймкодами.
4. Выделение шагов — алгоритм разбивает сессию на шаги по кликам и ближайшим речевым сегментам.
5. Нормализация (LLM) — ollama (`qwen2.5:3b`) превращает сырую речь в чёткие инструкции;
   vision-модель (`qwen2.5vl:3b`) при необходимости описывает действие по скриншоту.
6. Извлечение скриншотов — FFmpeg достаёт кадры в момент каждого клика и рисует маркер.
7. Редактирование (Web UI) — пользователь правит текст, двигает маркеры, меняет порядок,
   удаляет или объединяет шаги.
8. Экспорт — Markdown или HTML со встроенными скриншотами.
9. Генерация Shorts — TTS озвучивает шаги, FFmpeg собирает вертикальное видео с маркерами.

## Разработка

### Запуск и логи

```bash
# Поднять весь стек
docker compose up -d

# Статус сервисов
docker compose ps

# Логи бэкенда / воркера
docker compose logs -f autodoc-ai
docker compose logs -f celery-worker

# Health-check API
curl http://localhost:8888/health
```

### Локальный запуск backend без Docker

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Поднять зависимости в Docker
docker compose up -d postgres redis ollama

# Backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Celery-воркер (отдельный терминал)
celery -A app.celery worker --loglevel=info
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Тестирование

```bash
pytest tests/ -v
pytest tests/ --cov=app --cov-report=html
```

### Установка Chrome Extension

```
1. Откройте chrome://extensions/
2. Включите «Режим разработчика»
3. Нажмите «Загрузить распакованное расширение»
4. Выберите папку extension/
```

## Безопасность и приватность

Все AI-модели (Whisper, ollama, TTS) работают локально. Видео, аудио, тексты и метаданные
не передаются во внешние сервисы (исключение — движок `edge-tts`, который обращается к
Microsoft; для полностью офлайн-озвучки используйте `silero`). Данные хранятся в вашей
инфраструктуре под вашим контролем.

## Лицензия

MIT License — свободное использование для любых целей, включая коммерческие.
