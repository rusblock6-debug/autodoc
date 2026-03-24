# Экспорт в data.json

## 📋 Обзор

Функция экспорта созданных гайдов AutoDoc в файл `data.json` - единый источник данных для документации системы.

## 🎯 Назначение

Каждый созданный в AutoDoc гайд можно экспортировать в один из трёх разделов `data.json`:

1. **📘 В БЫСТРЫЙ СТАРТ** → `cards.quickstart.steps[]`
2. **📖 В ОБЗОР** → `cards.descriptive[]`
3. **📝 В ИНСТРУКЦИИ** → `cards.instructions[]`

## 🔧 Архитектура

### Backend (FastAPI)

**Файл:** `app/api/data_json.py`

#### Endpoints:

```python
GET /api/v1/data-json
# Получить текущий data.json

POST /api/v1/data-json/add-to-descriptive
# Добавить в раздел "Обзор"
# Параметры: guide_id, title, subtitle, description, items, image

POST /api/v1/data-json/add-to-instruction  
# Добавить в раздел "Пошаговые инструкции"
# Параметры: guide_id, title, nav_title, description, items, steps

POST /api/v1/data-json/add-to-quickstart
# Добавить в раздел "Быстрый старт"
# Параметры: guide_id, title, substeps
```

#### Логика работы:

1. **Чтение**: `read_data_json()` читает `/data/data.json`
2. **Валидация**: Проверка существования гайда в БД
3. **Маппинг**: Преобразование данных гайда в формат data.json
4. **Добавление**: Append-only (только добавление новых записей)
5. **Запись**: `write_data_json()` сохраняет изменения

### Frontend (React)

**Файл:** `frontend/src/pages/StepEditor.jsx`

#### Кнопки экспорта:

Расположены в верхней части редактора шагов:

```jsx
[← Назад] [PDF] [JSON] | [⚡ В БЫСТРЫЙ СТАРТ] [📖 В ОБЗОР] [📝 В ИНСТРУКЦИИ] [Shorts →]
```

#### Модальные окна:

При нажатии на кнопку открывается серия `prompt`:

**Для "В ОБЗОР":**
1. Заголовок (например, "Справочники")
2. Подзаголовок (например, "Нормативно-справочная информация")
3. Подробное описание
4. Список особенностей (каждый с новой строки)

**Для "В ИНСТРУКЦИИ":**
1. Полный заголовок инструкции
2. Короткий заголовок для меню
3. Описание инструкции
4. Список шагов (кратко)

**Для "В БЫСТРЫЙ СТАРТ":**
1. Заголовок шага

### Docker Volume

**Файл:** `docker-compose.yml`

```yaml
volumes:
  - ./data:/data  # Маунт папки с данными
```

**Пути:**
- В контейнере: `/data/`
  - `/data/data.json` — основной JSON файл
  - `/data/screenshots/` — 📸 **локальные скриншоты**
- На хост-машине: `C:\Projects\autodoc — копия\data\`
  - `data\data.json`
  - `data\screenshots\guide-X\` — скриншоты для гайда X

### Почему локально?

**Преимущества:**
- ✅ **Работает без интернета** — не зависит от MinIO/S3
- ✅ **Быстрый доступ** — скриншоты в той же папке что и JSON
- ✅ **Надёжность** — при пересоздании контейнера данные сохраняются в volume
- ✅ **Простота** — admin.html открывает скриншоты по относительному пути

**Структура после экспорта:**
```
data/
├── data.json
└── screenshots/
    ├── guide-1/
    │   ├── step_1.png
    │   ├── step_2.png
    │   └── ...
    ├── guide-2/
    │   └── ...
    └── guide-X/
        └── ...
```

## 📊 Структура data.json

```json
{
  "title": "Инструкция пользователя",
  "cards": {
    "quickstart": {
      "title": "Быстрый старт",
      "description": "Пошаговое руководство...",
      "steps": [
        {
          "title": "Название шага",
          "substeps": [
            {
              "text": "Описание подшага",
              "details": [],
              "images": ["screenshots/guide-1/step_1.png"]  🔹 ЛОКАЛЬНЫЙ ПУТЬ
            }
          ]
        }
      ]
    },
    "descriptive": [
      {
        "id": "guide-uuid",
        "title": "Справочники",
        "subtitle": "Нормативно-справочная информация",
        "description": "Подробное описание",
        "items": ["Особенность 1", "Особенность 2"],
        "image": "screenshots/guide-1/step_1.png"  🔹 ЛОКАЛЬНЫЙ ПУТЬ
      }
    ],
    "instructions": [
      {
        "id": "guide-uuid",
        "title": "Как запланировать взрывные работы?",
        "navTitle": "Планирование взрывных работ",
        "description": "Описание инструкции",
        "items": ["Шаг 1", "Шаг 2"],
        "steps": [
          {
            "text": "Текст шага",
            "images": ["screenshots/guide-1/step_1.png"],  🔹 ЛОКАЛЬНЫЙ ПУТЬ
            "horizontal": false
          }
        ]
      }
    ],
    "about": []
  }
}
```

## 🚀 Использование

### 1. Создайте гайд в AutoDoc

- Запишите сессию через Chrome Extension
- Дождитесь обработки AI
- Откройте редактор шагов

### 2. Отредактируйте шаги

- Исправьте текст шагов
- Добавьте аннотации при необходимости
- Сохраните изменения

### 3. Экспортируйте в data.json

1. Нажмите одну из кнопок:
   - ⚡ **В БЫСТРЫЙ СТАРТ**
   - 📖 **В ОБЗОР**
   - 📝 **В ИНСТРУКЦИИ**

2. Заполните поля в модальных окнах

3. Получите подтверждение: `✅ Гайд добавлен в раздел '...'`

### 4. Проверьте data.json

Файл обновится по пути: `C:\Projects\autodoc — копия\data\data.json`

## 🔐 Append-Only логика

**Важно:** Функция только **добавляет** новые записи, никогда не перезаписывает существующие.

```python
# Добавление в массив
data["cards"]["descriptive"].append(new_entry)
data["cards"]["instructions"].append(new_entry)
data["cards"]["quickstart"]["steps"].append(new_entry)
```

Это обеспечивает:
- ✅ Сохранение всех предыдущих записей
- ✅ Возможность отката изменений
- ✅ Конфликтоустойчивость при одновременной работе

## 🛠️ API Примеры

### Получить текущий data.json

```bash
curl http://localhost:8888/api/v1/data-json
```

### Добавить в Обзор

```bash
curl -X POST "http://localhost:8888/api/v1/data-json/add-to-descriptive?guide_id=1" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Справочники",
    "subtitle": "Нормативно-справочная информация",
    "description": "Раздел содержит справочную информацию",
    "items": ["Возможность 1", "Возможность 2"]
  }'
```

### Добавить в Инструкции

```bash
curl -X POST "http://localhost:8888/api/v1/data-json/add-to-instruction?guide_id=1" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Как создать проект?",
    "nav_title": "Создание проекта",
    "description": "Пошаговая инструкция",
    "items": ["Шаг 1", "Шаг 2"]
  }'
```

### Добавить в Быстрый старт

```bash
curl -X POST "http://localhost:8888/api/v1/data-json/add-to-quickstart?guide_id=1" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Первые шаги в системе"
  }'
```

## 📝 Обработка ошибок

### Ошибка 404: Guide not found

```json
{
  "detail": "Guide 999 not found"
}
```

**Решение:** Проверьте что гайд существует в БД

### Ошибка 500: Failed to read/write data.json

```json
{
  "detail": "Failed to read data.json: [Errno 2] No such file or directory"
}
```

**Решение:** Проверьте что volume замаунчен и файл доступен

## 🔄 Перезапуск контейнера

При пересоздании контейнера данные **сохраняются** благодаря volume:

```bash
docker compose down
docker compose up -d
# data.json останется на месте
```

## 🎨 Стилизация кнопок

```jsx
// В БЫСТРЫЙ СТАРТ - Зеленый (#10b981)
backgroundColor: '#10b981'

// В ОБЗОР - Фиолетовый (#8b5cf6)
backgroundColor: '#8b5cf6'

// В ИНСТРУКЦИИ - Оранжевый (#ed8d48)
backgroundColor: '#ed8d48'
```

## 📌 Ограничения

- ❌ Нет удаления записей из data.json
- ❌ Нет редактирования существующих записей
- ❌ Нет проверки на дубликаты
- ✅ Все изменения применяются сразу
- ✅ Steps автоматически берутся из гайда если не указаны

## 🔮 Future Enhancements

Возможные улучшения:

1. Админка для управления data.json
2. Превью перед экспортом
3. Проверка на дубликаты
4. Откат изменений (undo)
5. Экспорт нескольких гайдов разом
6. Валидация структуры JSON
