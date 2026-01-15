# Frontend Setup - Notion Style

Фронтенд полностью переработан в стиле Notion на основе примеров из папки `example/`.

## Что было сделано

### 1. Стили
- ✅ Скопированы все стили из `example/css/styles.css` → `frontend/src/styles-notion.css`
- ✅ Скопированы компоненты из `example/css/components.css` → `frontend/src/components-notion.css`
- ✅ Подключены Google Fonts (Inter) и Font Awesome
- ✅ Обновлен `frontend/src/index.css` для импорта всех стилей

### 2. Страницы
- ✅ **Home.jsx** - главная страница с карточками гайдов (на основе `example/index.html`)
- ✅ **GuideEditor.jsx** - редактор с drag-and-drop маркерами (на основе `example/editor.html`)
- ✅ **CreateGuide.jsx** - создание нового гайда
- ✅ **ExportGuide.jsx** - экспорт в Markdown/HTML/PDF
- ✅ **ShortsGenerator.jsx** - генерация вертикального видео

### 3. Компоненты
- Sidebar с навигацией
- Top bar с поиском и кнопками
- Модальные окна
- Карточки гайдов
- Drag-and-drop маркеры
- Список шагов
- Прогресс-бары

## Запуск

```bash
cd frontend
npm install
npm run dev
```

Фронтенд будет доступен на http://localhost:5173

## Структура

```
frontend/src/
├── pages/
│   ├── Home.jsx              # Главная страница (dashboard)
│   ├── GuideEditor.jsx       # Редактор гайдов
│   ├── CreateGuide.jsx       # Создание гайда
│   ├── ExportGuide.jsx       # Экспорт
│   └── ShortsGenerator.jsx   # Генерация шортс
├── services/
│   └── api.js                # API клиент
├── styles-notion.css         # Основные стили Notion
├── components-notion.css     # Дополнительные компоненты
├── index.css                 # Глобальные стили + импорты
├── App.jsx                   # Роутинг
└── main.jsx                  # Entry point
```

## Особенности

### Notion Style Design System
- Минималистичный дизайн
- Цветовая палитра Notion
- Плавные анимации
- Адаптивная верстка
- Drag-and-drop интерфейс

### Интерактивность
- Перетаскивание маркеров на скриншотах
- Модальные окна для экспорта и предпросмотра
- Переключение между видами (галерея/список)
- Поиск по гайдам
- Прогресс-бары для загрузки

### API Integration
- Полная интеграция с backend API
- Загрузка файлов с прогрессом
- Обработка ошибок
- Автосохранение изменений

## Отличия от примера

1. **React вместо vanilla JS** - все компоненты переписаны на React
2. **React Router** - для навигации между страницами
3. **API интеграция** - подключение к backend через axios
4. **State management** - использование React hooks (useState, useEffect)
5. **Модульность** - разделение на компоненты и страницы

## Следующие шаги

1. Подключить backend API (убедиться что он запущен на http://localhost:8000)
2. Протестировать все функции
3. Добавить обработку ошибок
4. Оптимизировать производительность
