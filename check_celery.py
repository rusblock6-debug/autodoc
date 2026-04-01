#!/usr/bin/env python3
"""
Скрипт для проверки состояния Celery worker.
"""

import sys
from pathlib import Path

# Добавляем корень проекта в пути
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.celery import celery_app

def check_celery():
    """Проверка доступности Celery worker."""
    print("Проверка Celery worker...")
    
    try:
        # Проверяем активные воркеры
        inspect = celery_app.control.inspect()
        
        # Получаем список активных воркеров
        active = inspect.active()
        stats = inspect.stats()
        
        if not active and not stats:
            print("❌ Celery worker не запущен!")
            print("\nДля запуска выполните:")
            print("  celery -A app.celery worker --loglevel=info")
            return False
        
        print("✅ Celery worker запущен!")
        
        if stats:
            print(f"\nАктивные воркеры: {len(stats)}")
            for worker_name, worker_stats in stats.items():
                print(f"  - {worker_name}")
        
        if active:
            total_tasks = sum(len(tasks) for tasks in active.values())
            print(f"\nАктивные задачи: {total_tasks}")
        
        # Проверяем зарегистрированные задачи
        registered = inspect.registered()
        if registered:
            print(f"\nЗарегистрированные задачи:")
            for worker_name, tasks in registered.items():
                print(f"  Воркер: {worker_name}")
                for task in tasks:
                    if 'generate_video' in task or 'generate_shorts' in task:
                        print(f"    ✓ {task}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при проверке Celery: {e}")
        print("\nВозможные причины:")
        print("  1. Redis не запущен")
        print("  2. Celery worker не запущен")
        print("  3. Неверная конфигурация в .env")
        return False

if __name__ == "__main__":
    success = check_celery()
    sys.exit(0 if success else 1)
