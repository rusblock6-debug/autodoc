# Быстрый старт

## Запуск через Docker Compose (рекомендуется)

1. **Запустите все сервисы:**
   ```bash
   docker-compose up -d
   ```

2. **Проверьте статус:**
   ```bash
   docker-compose ps
   ```
   
   Все сервисы должны быть в статусе "Up":
   - autodoc-ai (Backend API)
   - autodoc-frontend (Frontend)
   - autodoc-postgres (Database)
   - autodoc-redis (Task Queue)
   - autodoc-celery (Worker) ← ВАЖНО для генерации видео!

3. **Проверьте логи Celery worker:**
   ```bash
   docker-compose logs -f celery-worker
   ```
   
   Должны увидеть:
   ```
   [tasks]
     . app.celery_tasks.generate_video_task
   
   [2024-XX-XX XX:XX:XX,XXX: INFO/MainProcess] Connected to redis://redis:6379/0
   [2024-XX-XX XX:XX:XX,XXX: INFO/MainProcess] celery@... ready.
   ```

4. **Откройте приложение:**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

## Локальный запуск (для разработки)

### Предварительные требования

- Python 3.10+
- PostgreSQL 15+
- Redis 7+
- FFmpeg

### Шаги

1. **Установите зависимости:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Настройте .env файл:**
   ```bash
   cp .env.example .env
   # Отредактируйте .env с вашими настройками
   ```

3. **Запустите PostgreSQL и Redis:**
   ```bash
   # PostgreSQL (если не запущен)
   sudo systemctl start postgresql
   
   # Redis
   redis-server
   ```

4. **Примените миграции:**
   ```bash
   alembic upgrade head
   ```

5. **Запустите Celery worker (в отдельном терминале):**
   ```bash
   celery -A app.celery worker --loglevel=info
   ```
   
   ⚠️ **ВАЖНО:** Без запущенного worker генерация видео не будет работать!

6. **Запустите FastAPI сервер (в другом терминале):**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

7. **Запустите Frontend (в третьем терминале):**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

## Проверка работоспособности

Запустите диагностический скрипт:

```bash
python test_video_generation.py
```

Все тесты должны пройти успешно (✓ PASS).

## Решение проблем

Если возникла ошибка "Не получен ID задачи", см. [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

### Быстрая проверка

```bash
# Проверка Celery
python check_celery.py

# Проверка Redis
redis-cli ping

# Проверка логов (Docker)
docker-compose logs celery-worker

# Перезапуск worker (Docker)
docker-compose restart celery-worker
```

## Структура проекта

```
autodoc_ai/
├── app/                    # Backend (FastAPI)
│   ├── api/               # API endpoints
│   ├── services/          # Business logic
│   ├── celery.py          # Celery configuration
│   └── celery_tasks.py    # Background tasks
├── frontend/              # Frontend (React)
├── data/                  # Локальное хранилище
│   ├── screenshots/       # Скриншоты
│   ├── audio/            # Аудио файлы
│   ├── videos/           # Исходные видео
│   └── output/           # Сгенерированные видео
├── workers/              # AI subprocess workers
├── docker-compose.yml    # Docker конфигурация
└── requirements.txt      # Python зависимости
```

## Полезные команды

```bash
# Docker Compose
docker-compose up -d              # Запуск всех сервисов
docker-compose down               # Остановка всех сервисов
docker-compose logs -f [service]  # Просмотр логов
docker-compose restart [service]  # Перезапуск сервиса
docker-compose ps                 # Статус сервисов

# Celery
celery -A app.celery worker --loglevel=info    # Запуск worker
celery -A app.celery inspect active            # Активные задачи
celery -A app.celery inspect registered        # Зарегистрированные задачи
celery -A app.celery inspect stats             # Статистика worker

# Database
alembic upgrade head              # Применить миграции
alembic revision --autogenerate   # Создать новую миграцию

# Redis
redis-cli ping                    # Проверка подключения
redis-cli KEYS "autodoc:*"        # Просмотр ключей
redis-cli FLUSHDB                 # Очистка базы (осторожно!)
```
