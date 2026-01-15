# Инструкция по перезапуску после исправлений

## Быстрый перезапуск (рекомендуется)

```bash
# Остановить и удалить контейнеры
docker-compose down

# Запустить заново (код уже смонтирован через volumes)
docker-compose up
```

## Полный перезапуск (если быстрый не помог)

```bash
# Остановить и удалить контейнеры + volumes (ОСТОРОЖНО: удалит данные БД!)
docker-compose down -v

# Пересобрать образы (если меняли Dockerfile)
docker-compose build

# Запустить
docker-compose up
```

## Проверка статуса

```bash
# Посмотреть логи
docker-compose logs -f

# Проверить статус контейнеров
docker-compose ps

# Проверить конкретный контейнер
docker-compose logs autodoc-ai
docker-compose logs celery-worker
```

## Что изменилось

1. ✅ `config.py` перемещен в `app/config.py` - исправлена ошибка `ModuleNotFoundError`
2. ✅ Исправлен email для pgAdmin - исправлена ошибка валидации

## После перезапуска проверьте

1. Контейнер `autodoc-ai` должен запуститься без ошибок
2. Контейнер `celery-worker` должен запуститься без ошибок
3. Приложение должно быть доступно на http://localhost:8000
4. API документация: http://localhost:8000/docs
