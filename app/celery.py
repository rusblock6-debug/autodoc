"""
Celery Configuration for AutoDoc AI System.
Конфигурация очередей задач с поддержкой Redis Streams и механизмом heartbeat.

Ключевые особенности:
- Redis Streams с Consumer Groups для надёжной доставки (at-least-once)
- Heartbeat мониторинг живых задач
- Consumer Group для распределения задач между воркерами
"""

import os
import logging
import threading
from datetime import datetime
from typing import Optional

import redis
from celery import Celery
from celery.signals import worker_ready, worker_shutdown


logger = logging.getLogger(__name__)


# === Настройки ===
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")

# Настройки Redis из конфига
from app.config import settings

REDIS_HOST = settings.REDIS_HOST
REDIS_PORT = settings.REDIS_PORT
REDIS_DB = settings.REDIS_DB

STREAM_NAME = settings.REDIS_STREAM_NAME
CONSUMER_GROUP = settings.REDIS_CONSUMER_GROUP
VISIBILITY_TIMEOUT = settings.REDIS_VISIBILITY_TIMEOUT
HEARTBEAT_INTERVAL = settings.HEARTBEAT_INTERVAL
HEARTBEAT_PREFIX = settings.HEARTBEAT_PREFIX


# === Celery App ===
celery_app = Celery(
    "autodoc_ai",
    broker=f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}",
    backend=f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}",
)


# === Celery Configuration ===
celery_app.conf.update(
    # Сериализация
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # Часовой пояс
    timezone="UTC",
    enable_utc=True,
    
    # Настройки воркеров
    worker_prefetch_multiplier=1,  # Один таск за раз для потокобезопасности
    worker_concurrency=2,  # 2 воркера (основной + GC)
    
    # Task settings
    task_acks_late=True,  # ACK только после успешного выполнения
    task_reject_on_worker_lost=True,  # Перезапуск задачи при потере воркера
    task_default_retry_delay=60,
    task_max_retries=3,
    
    # Timeouts
    task_soft_time_limit=1800,  # 30 минут soft limit
    task_time_limit=3600,  # 1 час hard limit
    
    # Beat schedule для GC
    beat_schedule={
        "check-stale-tasks-every-5-min": {
            "task": "app.celery_tasks.check_stale_tasks",
            "schedule": 300.0,  # 5 минут
        },
        "cleanup-heartbeats-every-10-min": {
            "task": "app.celery_tasks.cleanup_heartbeats",
            "schedule": 600.0,  # 10 минут
        },
    },
    
    # Result expiration
    result_expires=86400,  # 24 часа
    
    # Отключаем стандартную маршрутизацию для наших специфичных задач
    task_routes={},
)


# === Redis Client для Streams ===
def get_redis_client() -> redis.Redis:
    """
    Получение Redis клиента с оптимальными настройками.
    """
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_keepalive=True,
        retry_on_timeout=True,
    )


# === Heartbeat Manager ===
class HeartbeatManager:
    """
    Менеджер heartbeat для отслеживания живых задач.
    
    Запускает фоновый поток, который обновляет ключи heartbeat
    в Redis для активных задач.
    """
    
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
        self.active_jobs: dict = {}
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._worker_id = f"worker-{os.getpid()}"
    
    def start(self) -> None:
        """Запуск heartbeat монитора."""
        self.redis = get_redis_client()
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True,
            name="HeartbeatMonitor"
        )
        self._thread.start()
        logger.info(f"Heartbeat manager started (worker: {self._worker_id})")
    
    def stop(self) -> None:
        """Остановка heartbeat монитора."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Heartbeat manager stopped")
    
    def register_job(self, job_id: str, stream_id: str) -> None:
        """Регистрация новой задачи для heartbeat."""
        self.active_jobs[job_id] = {
            "stream_id": stream_id,
            "started_at": datetime.utcnow().isoformat(),
            "worker_id": self._worker_id,
        }
        self._update_heartbeat(job_id)
    
    def unregister_job(self, job_id: str) -> None:
        """Удаление задачи из мониторинга."""
        self.active_jobs.pop(job_id, None)
        # Удаляем ключ heartbeat
        if self.redis:
            self.redis.delete(f"{HEARTBEAT_PREFIX}{job_id}")
    
    def _heartbeat_loop(self) -> None:
        """Основной цикл heartbeat."""
        while not self._stop_event.is_set():
            try:
                for job_id in list(self.active_jobs.keys()):
                    self._update_heartbeat(job_id)
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")
            
            # Спим до следующего цикла
            self._stop_event.wait(timeout=HEARTBEAT_INTERVAL)
    
    def _update_heartbeat(self, job_id: str) -> None:
        """Обновление ключа heartbeat в Redis."""
        if not self.redis:
            return
        
        try:
            job_info = self.active_jobs.get(job_id)
            if job_info:
                self.redis.hset(
                    f"{HEARTBEAT_PREFIX}{job_id}",
                    mapping={
                        "worker_id": job_info["worker_id"],
                        "stream_id": job_info["stream_id"],
                        "last_heartbeat": datetime.utcnow().isoformat(),
                        "started_at": job_info["started_at"],
                    }
                )
                # Устанавливаем TTL (2 × HEARTBEAT_INTERVAL)
                self.redis.expire(
                    f"{HEARTBEAT_PREFIX}{job_id}",
                    HEARTBEAT_INTERVAL * 2 + 10
                )
        except Exception as e:
            logger.warning(f"Failed to update heartbeat for {job_id}: {e}")
    
    def get_job_status(self, job_id: str) -> Optional[dict]:
        """Получение статуса задачи из Redis."""
        if not self.redis:
            return None
        
        try:
            data = self.redis.hgetall(f"{HEARTBEAT_PREFIX}{job_id}")
            return data if data else None
        except Exception:
            return None


# Глобальный экземпляр Heartbeat Manager
heartbeat_manager = HeartbeatManager()


# === Worker Signals ===

@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    """Обработчик готовности воркера."""
    logger.info(f"Worker is ready: {sender}")
    
    # Инициализируем Consumer Group в Redis
    redis_client = get_redis_client()
    try:
        redis_client.xgroup_create(
            STREAM_NAME,
            CONSUMER_GROUP,
            id="0",
            mkstream=True
        )
        logger.info(f"Created consumer group: {CONSUMER_GROUP}")
    except redis.ResponseError as e:
        if "BUSYGROUP" in str(e):
            logger.info(f"Consumer group already exists: {CONSUMER_GROUP}")
        else:
            raise
    except Exception as e:
        logger.error(f"Failed to create consumer group: {e}")
    
    # Запускаем heartbeat manager
    heartbeat_manager.start()


@worker_shutdown.connect
def on_worker_shutdown(sender, **kwargs):
    """Обработчик завершения работы воркера."""
    logger.info(f"Worker is shutting down: {sender}")
    heartbeat_manager.stop()


# === Автоматическое обнаружение задач ===
celery_app.autodiscover_tasks([
    "app.celery_tasks",
])


# === Health Check Task ===
@celery_app.task(bind=True, ignore_result=True)
def health_check(self) -> dict:
    """Проверка работоспособности воркера."""
    return {
        "worker_id": self.request.hostname,
        "timestamp": datetime.utcnow().isoformat(),
        "active_jobs": len(heartbeat_manager.active_jobs),
    }
