# AutoDoc AI System - PlantUML Diagrams

Документация архитектуры системы в виде PlantUML диаграмм.

## Диаграммы

### 1. Component Diagram (`architecture.puml`)

Архитектура всей системы с компонентами и связями:

```
┌─────────────────────────────────────────────────────────────┐
│                    AutoDoc AI System                        │
├─────────────────────────────────────────────────────────────┤
│ Frontend Layer                                              │
│  ├── Browser Extension (Recording)                          │
│  └── Web Dashboard (React/Vue)                              │
├─────────────────────────────────────────────────────────────┤
│ API Layer - FastAPI                                         │
│  ├── Auth API (JWT, OAuth2)                                 │
│  ├── Guides API (CRUD, Steps)                               │
│  ├── Processing API (AI, Video)                             │
│  └── Storage API (MinIO, URLs)                              │
├─────────────────────────────────────────────────────────────┤
│ Business Logic Services                                     │
│  ├── Video Processor (FFmpeg, Zoom)                         │
│  ├── AI Service (Whisper, LLM)                              │
│  ├── TTS Service (Edge TTS, Coqui)                          │
│  ├── Smart Aligner (Sync, Dead time)                        │
│  └── Storage Service (MinIO Client)                         │
├─────────────────────────────────────────────────────────────┤
│ Task Queue - Celery                                         │
│  ├── Celery Workers (Background Tasks)                      │
│  └── Redis (Message Broker)                                 │
├─────────────────────────────────────────────────────────────┤
│ Data Layer                                                  │
│  ├── PostgreSQL (Guides, Steps, Users)                      │
│  └── MinIO S3 (Videos, Screenshots)                         │
├─────────────────────────────────────────────────────────────┤
│ AI Stack (GPU)                                              │
│  ├── Whisper Large v3 (ASR)                                 │
│  ├── Qwen 2.5 72B (Logic)                                   │
│  ├── Edge TTS (Neural Voices)                               │
│  └── Coqui XTTS v2 (Voice Cloning)                         │
└─────────────────────────────────────────────────────────────┘
```

### 2. Class Diagram (`class_diagram.puml`)

Структура данных системы:

```
┌─────────────────┐         ┌─────────────────┐
│     User        │         │     Guide       │
├─────────────────┤         ├─────────────────┤
│ - id            │         │ - id            │
│ - email         │         │ - uuid          │
│ - username      │ 1    *  │ - title         │
│ - password      │────────▶│ - status        │
│ - preferences   │         │ - content_type  │
└─────────────────┘         │ - tags          │
                            │ - steps (1,*)   │
                            │ - screenshots   │
                            │ - jobs          │
                            └─────────────────┘
                                    │
                                    │ *
                            ┌───────┴───────┐
                            │              │
                    ┌───────────────┐ ┌───────────────┐
                    │  GuideStep    │ │GuideScreenshot│
                    ├───────────────┤ ├───────────────┤
                    │ - step_number │ │ - file_path   │
                    │ - text        │ │ - annotations │
                    │ - timestamps  │ │ - screenshot  │
                    │ - zoom_region │ │   _type       │
                    │ - audio_path  │ └───────────────┘
                    │ - is_processed│
                    └───────────────┘
```

### 3. Sequence Diagram (`magic_edit_sequence.puml`)

Поток "Магического редактирования":

```
1. User edits text
   User → Web: "Нажми кнопку" → "Нажми красную кнопку"
   
2. Update step
   Web → API: PATCH /steps/{id}
   API → DB: Update edited_text
   DB → API: OK
   
3. Trigger magic edit
   User → Web: "Apply Changes"
   Web → API: POST /magic-edit
   
4. Generate new TTS
   API → TTS: Generate audio
   TTS → API: Audio file, duration
   
5. Smart alignment
   API → Aligner: Calculate stretch
   Aligner → API: speed = 0.75
   
6. Render video
   API → Video: FFmpeg processing
   Video → API: New video file
   
7. Upload to storage
   API → Storage: Upload video
   Storage → API: URL
   
8. Update guide
   API → DB: status = COMPLETED
   DB → API: OK
   
9. Show result
   API → Web: new_video_url
   Web → User: Updated video
```

## Использование

Для просмотра диаграмм можно использовать:

1. **PlantUML Server** - онлайн просмотр
2. **VS Code** - расширение PlantUML
3. **IntelliJ IDEA** - плагин PlantUML
4. **Graphviz** - локальная генерация

### Генерация изображений

```bash
# Установка Graphviz (если не установлен)
# Ubuntu/Debian
sudo apt install graphviz

# macOS
brew install graphviz

# Генерация PNG
java -jar plantuml.jar -tsvg architecture.puml
java -jar plantuml.jar -tsvg class_diagram.puml
java -jar plantuml.jar -tsvg magic_edit_sequence.puml

# Или все файлы в директории
java -jar plantuml.jar -tsvg docs/
```

## Ключевые архитектурные решения

| Компонент | Технология | Назначение |
|-----------|------------|------------|
| API Gateway | FastAPI | REST API, валидация, документация |
| AI Processing | Whisper + Qwen | ASR, LLM анализ |
| Video Engine | FFmpeg | Рендеринг, зум, time-stretch |
| TTS | Edge TTS / Coqui | Озвучка, клонирование голоса |
| Storage | MinIO | S3-совместимое хранилище |
| Queue | Redis + Celery | Фоновые задачи |
| Database | PostgreSQL | Персистентное хранение |
