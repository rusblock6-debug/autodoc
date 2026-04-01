# Troubleshooting - Решение проблем

## Ошибка "Не получен ID задачи"

Эта ошибка возникает, когда Celery worker не может создать задачу. Обычно это означает, что Celery worker не запущен или не может подключиться к Redis.

### Диагностика

1. **Проверьте статус Celery worker:**
   ```bash
   python check_celery.py
   ```

2. **Проверьте, что Redis запущен:**
   ```bash
   redis-cli ping
   ```
   Должен вернуть: `PONG`

3. **Проверьте логи Celery worker:**
   ```bash
   # Если worker запущен в отдельном терминале, проверьте его вывод
   # Или проверьте логи Docker контейнера:
   docker-compose logs celery
   ```

### Решение

#### Вариант 1: Запуск через Docker Compose (рекомендуется)

```bash
# Запустите все сервисы
docker-compose up -d

# Проверьте статус
docker-compose ps

# Проверьте логи worker
docker-compose logs -f celery
```

#### Вариант 2: Локальный запуск

1. **Запустите Redis:**
   ```bash
   # Linux/Mac
   redis-server
   
   # Windows (через WSL или установленный Redis)
   redis-server.exe
   ```

2. **Запустите Celery worker:**
   ```bash
   # В отдельном терминале
   celery -A app.celery worker --loglevel=info
   ```

3. **Запустите FastAPI сервер:**
   ```bash
   # В другом терминале
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

### Проверка конфигурации

Убедитесь, что в файле `.env` правильно указаны настройки Redis:

```env
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

Если используете Docker:
```env
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
```

### Дополнительные проверки

1. **Проверьте подключение к Redis из Python:**
   ```python
   from app.celery import get_redis_client
   
   redis_client = get_redis_client()
   print(redis_client.ping())  # Должно вернуть True
   ```

2. **Проверьте, что задача зарегистрирована:**
   ```bash
   celery -A app.celery inspect registered
   ```
   
   В списке должна быть задача: `app.celery_tasks.generate_video_task`

### Частые причины проблемы

1. **Redis не запущен** - запустите Redis сервер
2. **Celery worker не запущен** - запустите worker командой выше
3. **Неверный REDIS_HOST** - проверьте .env файл
4. **Порт Redis занят** - проверьте, что Redis слушает на правильном порту
5. **Firewall блокирует подключение** - проверьте настройки firewall

### Логи для отладки

При обращении в поддержку предоставьте:

1. Вывод `python check_celery.py`
2. Логи Celery worker
3. Логи FastAPI сервера
4. Содержимое `.env` файла (без паролей!)

## Другие проблемы

### Видео не генерируется (задача зависла)

1. Проверьте логи worker:
   ```bash
   docker-compose logs -f celery
   ```

2. Проверьте статус задачи в Redis:
   ```bash
   redis-cli
   > KEYS autodoc:*
   ```

3. Перезапустите worker:
   ```bash
   docker-compose restart celery
   ```

### Ошибки TTS (озвучка)

Проверьте, что установлены зависимости:
```bash
pip install edge-tts
```

### Ошибки обработки видео

Проверьте, что установлен FFmpeg:
```bash
ffmpeg -version
```

Если не установлен:
```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# Mac
brew install ffmpeg

# Windows
# Скачайте с https://ffmpeg.org/download.html
```
