# План миграции к Guidde-подобной архитектуре

## Текущая архитектура (FFmpeg-based)
```
Запись → FFmpeg извлечение → ASR → LLM → TTS → FFmpeg склейка
```

## Целевая архитектура (AI-based как Guidde)
```
Запись → Сегментация по кликам → AI обработка каждого сегмента → Генерация видео через AI
```

---

## Файлы требующие изменений

### 🔴 КРИТИЧЕСКИЕ ИЗМЕНЕНИЯ (Core Logic)

#### 1. `app/services/video_processor.py` 
**Текущее:** FFmpeg-based обработка с zoompan, concat, time-stretching
**Новое:** AI-based генерация видео из сегментов
**Изменения:**
- Убрать `generate_video_with_zoom()` - заменить на `generate_video_from_segments()`
- Убрать `_extract_and_zoom_segment()` - заменить на AI inference
- Оставить `extract_screenshot()` - нужен для превью
- Добавить `apply_ai_video_generation()` - вызов AI модели для генерации видео

#### 2. `app/services/shorts_generator.py`
**Текущее:** FFmpeg склейка скриншотов + TTS
**Новое:** AI генерация видео с анимациями
**Изменения:**
- Убрать `_create_segment_video()` с FFmpeg
- Добавить `generate_segment_with_ai()` - AI генерация сегмента
- Оставить TTS логику - она работает хорошо
- Добавить оркестрацию нескольких AI моделей (транскрибация, аудио, видео, наложение)

#### 3. `app/celery_tasks.py`
**Текущее:** Subprocess isolation для FFmpeg
**Новое:** Subprocess isolation для AI inference
**Изменения:**
- Переименовать `process_video()` → `process_video_with_ai()`
- Добавить `ai_video_generation()` task
- Добавить `ai_segment_processing()` для параллельной обработки
- Оставить heartbeat и GC логику - она универсальная

#### 4. `workers/ai_runner.py`
**Текущее:** Запуск AI задач в subprocess
**Новое:** Добавить поддержку video generation моделей
**Изменения:**
- Добавить `load_video_generation_model()` - загрузка модели
- Добавить `run_video_inference()` - inference для видео
- Добавить `orchestrate_multi_model()` - оркестрация нескольких моделей
- Оставить существующую логику для ASR/LLM/TTS

---

### 🟡 СРЕДНИЕ ИЗМЕНЕНИЯ (API & Database)

#### 5. `app/api/processing.py`
**Изменения:**
- Добавить endpoint `/api/v1/processing/ai-video` для AI генерации
- Изменить логику обработки: вместо FFmpeg вызывать AI
- Добавить параметры для выбора AI модели

#### 6. `app/api/shorts.py`
**Изменения:**
- Изменить `/api/v1/shorts/generate` - использовать AI вместо FFmpeg
- Добавить параметры: `use_ai_generation=True`, `model_name="stable-video-diffusion"`

#### 7. `app/models.py`
**Изменения:**
- Добавить поле `generation_method` в таблицу `guides` (ffmpeg | ai)
- Добавить таблицу `ai_generation_metadata` для хранения параметров AI
- Добавить поле `ai_model_used` в таблицу `steps`

#### 8. `app/schemas.py`
**Изменения:**
- Добавить `AIGenerationRequest` schema
- Добавить `AIGenerationResponse` schema
- Расширить `ShortsGenerationRequest` с AI параметрами

---

### 🟢 МИНИМАЛЬНЫЕ ИЗМЕНЕНИЯ (Config & Utils)

#### 9. `app/config.py`
**Изменения:**
- Добавить `AI_VIDEO_MODEL_NAME` - название модели для видео
- Добавить `AI_VIDEO_MODEL_PATH` - путь к весам
- Добавить `USE_AI_GENERATION` - флаг включения AI
- Добавить `OPENROUTER_API_KEY` - для OpenRouter API

#### 10. `requirements.txt`
**Изменения:**
- Добавить `diffusers` - для Stable Video Diffusion
- Добавить `transformers` - для Hugging Face моделей
- Добавить `accelerate` - для оптимизации inference
- Добавить `openai` - для OpenRouter API (опционально)

#### 11. `docker-compose.yml`
**Изменения:**
- Добавить volume для AI моделей: `./data/ai_models:/data/ai_models`
- Увеличить memory limits для AI inference
- Добавить environment variables для AI

---

### 🔵 НОВЫЕ ФАЙЛЫ (Добавить)

#### 12. `app/services/ai_video_service.py` (НОВЫЙ)
**Назначение:** Сервис для AI генерации видео
**Функции:**
- `generate_video_from_image()` - генерация видео из статичного изображения
- `apply_motion_to_segment()` - добавление движения к сегменту
- `orchestrate_video_pipeline()` - оркестрация всего pipeline

#### 13. `app/services/model_manager.py` (НОВЫЙ)
**Назначение:** Управление AI моделями
**Функции:**
- `load_model()` - загрузка модели в память
- `unload_model()` - выгрузка для освобождения VRAM
- `get_available_models()` - список доступных моделей
- `download_model_from_hf()` - скачивание с Hugging Face

#### 14. `app/services/openrouter_client.py` (НОВЫЙ)
**Назначение:** Клиент для OpenRouter API
**Функции:**
- `call_video_generation_api()` - вызов API для генерации видео
- `call_audio_processing_api()` - обработка аудио через API
- `handle_rate_limits()` - обработка rate limits

---

## Функционал который ОСТАЕТСЯ

### ✅ Сохраняем без изменений:

1. **Расширение Chrome** (`extension/*`)
   - Запись экрана работает отлично
   - Логирование кликов - ключевая фича
   - Только меняем API URL для удаленного сервера

2. **Frontend** (`frontend/*`)
   - React UI для редактирования шагов
   - Аннотации и маркеры
   - Экспорт в Markdown/HTML

3. **Database** (`app/database.py`, `app/models.py` - частично)
   - PostgreSQL схема остается
   - Только добавляем новые поля для AI

4. **Storage** (`app/services/storage.py`)
   - MinIO для хранения файлов
   - Bucket структура остается

5. **TTS** (`app/services/tts_service.py`)
   - Edge TTS работает хорошо
   - Оставляем как есть

6. **ASR** (`app/services/ai_service.py` - Whisper часть)
   - Whisper для транскрибации
   - Оставляем без изменений

7. **LLM нормализация** (`app/services/ai_service.py` - LLM часть)
   - Qwen/Llama для очистки текста
   - Оставляем как есть

---

## Функционал который УДАЛЯЕМ

### ❌ Убираем (не используется в guidde-подходе):

1. **FFmpeg video processing** (частично)
   - `generate_video_with_zoom()` - заменяем на AI
   - `_extract_and_zoom_segment()` - заменяем на AI
   - `generate_shorts()` с FFmpeg - заменяем на AI
   - Оставляем только `extract_screenshot()` для превью

2. **Time-stretching логика**
   - `atempo` фильтры FFmpeg
   - `setpts` манипуляции
   - Заменяем на AI-based синхронизацию

3. **Concat логика**
   - `_concatenate_segments()`
   - `_create_concat_list()`
   - AI будет генерировать цельное видео

---

## Итоговая статистика

| Категория | Количество файлов |
|-----------|-------------------|
| 🔴 Критические изменения | 4 файла |
| 🟡 Средние изменения | 5 файлов |
| 🟢 Минимальные изменения | 3 файла |
| 🔵 Новые файлы | 3 файла |
| ✅ Без изменений | ~20 файлов |
| ❌ Удаляем функции | ~10 функций |
| **ИТОГО** | **15 файлов изменений + 3 новых** |

---

## Оценка сложности

- **Время разработки:** 3-5 дней (с тестированием)
- **Риск поломки:** Средний (хорошо изолированная архитектура)
- **Обратная совместимость:** Можно сохранить через флаг `USE_AI_GENERATION`

---

## Рекомендации

1. **Поэтапная миграция:**
   - Сначала добавить AI как опцию (`use_ai=True` параметр)
   - Оставить FFmpeg как fallback
   - Постепенно переключать пользователей

2. **Тестирование:**
   - Создать тестовые сессии с разными типами контента
   - Сравнить качество FFmpeg vs AI
   - Измерить время обработки

3. **Мониторинг:**
   - Логировать какой метод используется
   - Отслеживать ошибки AI inference
   - Мониторить VRAM usage

