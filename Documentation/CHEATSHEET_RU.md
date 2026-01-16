# 📋 Шпаргалка AutoDoc AI System

## 🚀 Быстрый запуск

```bash
# Клонировать проект
git clone <repo-url> && cd autodoc-ai

# Настроить окружение
cp .env.example .env

# Запустить систему
docker compose up -d

# Проверить статус
curl http://localhost:8000/health
```

## 🌐 URL сервисов

| Сервис | URL | Логин/Пароль |
|--------|-----|--------------|
| Frontend | http://localhost:3000 | — |
| Backend API | http://localhost:8000 | — |
| API Docs | http://localhost:8000/docs | — |
| MinIO Console | http://localhost:9001 | minioadmin / minioadmin |
| pgAdmin | http://localhost:5050 | admin@example.com / admin |

## 🎬 Основной флоу

```
1. Установить Chrome Extension
2. Нажать "Начать запись"
3. Говорить и кликать
4. Остановить запись
5. Открыть http://localhost:3000
6. Отредактировать шаги
7. Создать Shorts
8. Скачать видео
```

## 🐳 Docker команды

```bash
# Запуск
docker compose up -d

# Остановка
docker compose down

# Перезапуск
docker compose restart

# Логи
docker compose logs -f

# Логи конкретного сервиса
docker compose logs -f autodoc-ai

# Статус
docker compose ps

# Пересборка
docker compose build --no-cache

# Полная очистка (⚠️ удалит данные!)
docker compose down -v
```

## 📊 Мониторинг

```bash
# Использование ресурсов
docker stats

# GPU
nvidia-smi

# Место на диске
docker system df

# Очистка
docker system prune -a
```

## 🔧 Отладка

```bash
# Проверка здоровья
curl http://localhost:8000/health

# Подключение к PostgreSQL
docker exec -it autodoc-postgres psql -U autodoc -d autodoc_db

# Подключение к Redis
docker exec -it autodoc-redis redis-cli

# Список бакетов MinIO
docker exec -it autodoc-minio mc ls myminio/

# Логи воркера
docker compose logs -f celery-worker
```

## 🎯 API Endpoints

### Сессии
```bash
# Загрузить запись
POST /api/v1/sessions/upload

# Список сессий
GET /api/v1/sessions

# Получить сессию
GET /api/v1/sessions/{id}
```

### Гайды
```bash
# Создать гайд
POST /api/v1/guides

# Список гайдов
GET /api/v1/guides

# Получить гайд
GET /api/v1/guides/{id}

# Обновить гайд
PATCH /api/v1/guides/{id}
```

### Шаги
```bash
# Список шагов
GET /api/v1/guides/{id}/steps

# Обновить шаг
PATCH /api/v1/steps/{id}

# Удалить шаг
DELETE /api/v1/steps/{id}
```

### Экспорт
```bash
# Markdown
GET /api/v1/guides/{id}/export/markdown

# HTML
GET /api/v1/guides/{id}/export/html
```

### Shorts
```bash
# Генерация
POST /api/v1/guides/{id}/shorts/generate

# Статус
GET /api/v1/shorts/{task_id}/status

# Скачать
GET /api/v1/shorts/{task_id}/download
```

## 🔑 Переменные окружения

```bash
# База данных
DATABASE_HOST=postgres
DATABASE_USER=autodoc
DATABASE_PASSWORD=your_password
DATABASE_NAME=autodoc_db

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=your_password

# AI модели
WHISPER_MODEL_SIZE=medium
WHISPER_DEVICE=cuda
LLM_MODEL_NAME=Qwen/Qwen2.5-7B-Instruct-GGUF
TTS_ENGINE=edge-tts
EDGE_TTS_VOICE=ru-RU-SvetlanaNeural

# GPU
GPU_DEVICE_ID=0
GPU_MEMORY_FRACTION=0.8
```

## 🎨 Горячие клавиши (Web UI)

| Клавиша | Действие |
|---------|----------|
| `Ctrl + S` | Сохранить (автосохранение) |
| `←` | Предыдущий шаг |
| `→` | Следующий шаг |
| `Delete` | Удалить шаг |
| `Ctrl + Z` | Отменить |
| `Ctrl + Y` | Повторить |

## 🐛 Частые проблемы

### Docker не запускается
```bash
sudo systemctl restart docker
```

### GPU не обнаружен
```bash
nvidia-smi
sudo apt install nvidia-container-toolkit
sudo systemctl restart docker
```

### Порты заняты
```bash
sudo lsof -ti:8000 | xargs kill -9
```

### База данных не подключается
```bash
docker compose down -v
docker compose up -d postgres
```

### Модели не скачиваются
```bash
# Проверить место
df -h

# Скачать вручную
mkdir -p data/models
cd data/models
wget <model-url>
```

## 📈 Производительность

### Время обработки (1 минута записи)
- ASR: 30-60 сек
- Step Detection: 10-20 сек
- Screenshots: 10-20 сек
- LLM: 20-40 сек
- **Итого: 1-2 минуты**

### Генерация Shorts (5 шагов)
- TTS: 30-60 сек
- Video: 1-2 мин
- Rendering: 30-60 сек
- **Итого: 2-4 минуты**

## 💡 Советы

### Для качественной записи
- ✅ Говорите чётко
- ✅ Делайте паузы между шагами
- ✅ Кликайте точно на элементы
- ✅ Избегайте фонового шума

### Для лучших Shorts
- ✅ 5-10 шагов оптимально
- ✅ Каждый шаг 3-5 секунд
- ✅ Простые инструкции
- ✅ Контрастные маркеры

## 📚 Документация

- [Установка](INSTALLATION_GUIDE_RU.md)
- [Руководство пользователя](USER_GUIDE_RU.md)
- [Обзор проекта](PROJECT_OVERVIEW_RU.md)
- [API Docs](http://localhost:8000/docs)

---

**Быстрая помощь:** Если что-то не работает, проверьте логи: `docker compose logs -f`
