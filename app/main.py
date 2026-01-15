"""
AutoDoc AI System - Основной файл приложения.

Концепция: Guidde Analog + Extended Features
Функционал: Автоматическая генерация обучающего контента

Основные возможности:
- Захват экрана и действий
- Автоматический зум на клики
- AI-озвучка и транскрипция
- Генерация Wiki-статей и Shorts
- "Магическое редактирование" текста
- Полная приватность (on-premise)
"""

import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text

from app.config import settings, setup_directories
from app.database import init_db, close_db
from app.api import api_router
from app.schemas import HealthCheckResponse


# === Настройка логирования ===
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/tmp/autodoc_ai.log"),
    ],
)

logger = logging.getLogger(__name__)


# === Lifespan контекст ===
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Управление жизненным циклом приложения.
    Выполняет инициализацию при запуске и очистку при завершении.
    """
    # === Запуск ===
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    
    # Создаем необходимые директории
    setup_directories()
    logger.info("Directories created")
    
    # Инициализируем базу данных
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning(f"Database initialization failed: {e}")
    
    # Проверяем соединение с хранилищем
    try:
        from app.services.storage import storage_service
        storage_status = storage_service.check_connection()
        logger.info(f"Storage connection: {storage_status}")
    except Exception as e:
        logger.warning(f"Storage initialization failed: {e}")
    
    logger.info(f"{settings.APP_NAME} started successfully")
    
    yield
    
    # === Завершение ===
    logger.info(f"Shutting down {settings.APP_NAME}")
    
    # Закрываем соединения
    await close_db()
    logger.info("Database connections closed")
    
    logger.info(f"{settings.APP_NAME} shut down complete")


# === Создание FastAPI приложения ===
app = FastAPI(
    title=settings.APP_NAME,
    description="""
# AutoDoc AI System

Автоматическая платформа для генерации обучающего контента.

## Функционал

### Базовый (Must Have)
- **Захват экрана** через веб-расширение
- **Авто-зум** на области кликов с использованием FFmpeg
- **AI-озвучка** с поддержкой Edge TTS и Coqui XTTS
- **Библиотека гайдов** с поиском и тегами

### Расширенный (Innovation)
- **"Магическое редактирование"** - редактирование текста перегенерирует видео
- **Двойная генерация** - Wiki-статья + Video из одной записи
- **Smart Aligner** - интеллектуальная синхронизация с удалением "мёртвого времени"
- **Shorts Generation** - вертикальное видео для соцсетей
- **Полная приватность** - on-premise развертывание

## AI Stack

| Компонент | Технология |
|-----------|------------|
| ASR | OpenAI Whisper Large v3 |
| LLM | Qwen 2.5 (72B) / Llama 3.1 (70B) |
| TTS | Edge TTS / Coqui XTTS v2 |
| Video | FFmpeg |

## Архитектура

- **Backend**: Python (FastAPI)
- **Database**: PostgreSQL
- **Queue**: Redis (Celery)
- **Storage**: MinIO (S3-compatible)
    """,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# === CORS Middleware ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else ["https://autodoc.ai", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === Exception Handlers ===

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, 
    exc: RequestValidationError
) -> JSONResponse:
    """
    Обработчик ошибок валидации.
    """
    errors = []
    for error in exc.errors():
        errors.append({
            "code": "validation_error",
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
        })
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": "Validation error",
            "details": errors,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(
    request: Request, 
    exc: Exception
) -> JSONResponse:
    """
    Общий обработчик исключений.
    """
    logger.exception(f"Unhandled exception: {exc}")
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "Internal server error",
            "details": [{"code": "internal_error", "message": str(exc)}],
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


# === Middleware ===

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """
    Добавление заголовка с временем обработки запроса.
    """
    start_time = datetime.now()
    
    response = await call_next(request)
    
    process_time = (datetime.now() - start_time).total_seconds()
    response.headers["X-Process-Time"] = str(process_time)
    
    return response


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """
    Добавление уникального ID запроса.
    """
    request_id = request.headers.get("X-Request-ID") or str(datetime.now().timestamp())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# === API Routes ===
app.include_router(api_router, prefix="/api/v1")


# === Health Check ===

@app.get("/health", response_model=HealthCheckResponse, tags=["System"])
async def health_check() -> HealthCheckResponse:
    """
    Проверка состояния сервиса.
    
    Возвращает статус всех компонентов системы:
    - Database: Подключение к PostgreSQL
    - Redis: Подключение к Redis
    - MinIO: Подключение к хранилищу
    - GPU: Доступность GPU
    """
    from app.database import engine
    import redis
    
    # Проверка базы данных
    db_status = "healthy"
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            await conn.close()
    except Exception as e:
        db_status = f"unhealthy: {e}"
    
    # Проверка Redis
    redis_status = "healthy"
    try:
        r = redis.from_url(settings.redis_url)
        r.ping()
    except Exception as e:
        redis_status = f"unhealthy: {e}"
    
    # Проверка GPU
    gpu_status = False
    try:
        import torch
        gpu_status = torch.cuda.is_available()
    except ImportError:
        gpu_status = False
    
    # Проверка MinIO
    minio_status = "healthy"
    try:
        from app.services.storage import storage_service
        minio_status = storage_service.check_connection().get("connected", False)
        minio_status = "healthy" if minio_status else "unhealthy"
    except Exception as e:
        minio_status = f"unhealthy: {e}"
    
    return HealthCheckResponse(
        status="healthy" if all([
            db_status == "healthy",
            redis_status == "healthy",
            minio_status == "healthy",
        ]) else "degraded",
        version=settings.APP_VERSION,
        database=db_status,
        redis=redis_status,
        minio=minio_status,
        gpu_available=gpu_status,
        uptime_seconds=0,  # Можно вычислять при старте
    )


@app.get("/", tags=["Root"])
async def root():
    """
    Корневой эндпоинт.
    """
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """
    Заглушка для favicon.
    """
    return {"message": "No favicon"}


# === Запуск приложения ===
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    )
