#!/bin/bash
# Скрипт для перезапуска Celery worker

echo "🔄 Перезапуск Celery worker..."
docker restart autodoc-celery

echo "⏳ Ждем 3 секунды..."
sleep 3

echo "📋 Показываю последние логи:"
docker logs --tail=50 autodoc-celery

echo ""
echo "✅ Worker перезапущен!"
echo "💡 Для просмотра логов в реальном времени:"
echo "   docker logs -f autodoc-celery"
