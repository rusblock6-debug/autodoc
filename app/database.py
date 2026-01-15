"""
Подключение к базе данных PostgreSQL.
Использует SQLAlchemy с асинхронным драйвером asyncpg.
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

from app.config import settings


# Создание асинхронного движка базы данных
engine = create_async_engine(
    settings.async_database_url,
    echo=settings.DEBUG,  # Логирование SQL-запросов в режиме отладки
    pool_size=20,  # Максимальное количество соединений в пуле
    max_overflow=10,  # Дополнительные соединения при переполнении пула
    pool_pre_ping=True,  # Проверка соединения перед использованием
    pool_recycle=3600,  # Переиспользование соединений каждый час
)

# Фабрика сессий для создания асинхронных сессий
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Не истекать объекты после коммита
    autocommit=False,
    autoflush=False,
)

# Базовый класс для всех моделей
Base = declarative_base()


async def get_db() -> AsyncSession:
    """
    Зависимость FastAPI для получения сессии базы данных.
    Используется как dependency injection в эндпоинтах.
    
    Пример использования:
        @app.get("/guides")
        async def get_guides(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """
    Инициализация базы данных.
    Создает все таблицы на основе моделей.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """
    Закрытие соединений с базой данных при завершении работы.
    """
    await engine.dispose()
