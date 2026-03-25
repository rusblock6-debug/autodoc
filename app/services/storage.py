"""
Storage Service - локальное файловое хранилище.
Замена MinIO на локальные файлы.
"""

import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List, BinaryIO
from enum import Enum

from app.config import settings


logger = logging.getLogger(__name__)


class StorageType(str, Enum):
    """Типы хранилищ для локальных файлов."""
    UPLOADS = "uploads"
    VIDEOS = "videos"
    SCREENSHOTS = "screenshots"
    WIKI = "wiki"
    AUDIO = "audio"


class StorageError(Exception):
    """Базовый класс для ошибок хранилища."""
    pass


class BucketNotFoundError(StorageError):
    """Бакет не найден."""
    pass


class FileNotFoundError(StorageError):
    """Файл не найден."""
    pass


class UploadError(StorageError):
    """Ошибка загрузки файла."""
    pass


class StorageService:
    """Сервис для работы с локальным файловым хранилищем."""
    
    def __init__(self):
        """Инициализация локального хранилища."""
        self.base_path = Path(settings.STORAGE_BASE_PATH)
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # Создаём подпапки для каждого типа
        self.screenshots_path = self.base_path / "screenshots"
        self.videos_path = self.base_path / "videos"
        self.uploads_path = self.base_path / "uploads"
        self.wiki_path = self.base_path / "wiki"
        self.audio_path = self.base_path / "audio"
        
        for path in [self.screenshots_path, self.videos_path, self.uploads_path, self.wiki_path, self.audio_path]:
            path.mkdir(parents=True, exist_ok=True)
    
    def _get_storage_path(self, storage_type: StorageType) -> Path:
        """Получить путь для типа хранилища."""
        paths = {
            StorageType.SCREENSHOTS: self.screenshots_path,
            StorageType.VIDEOS: self.videos_path,
            StorageType.UPLOADS: self.uploads_path,
            StorageType.WIKI: self.wiki_path,
            StorageType.AUDIO: self.audio_path,
        }
        return paths.get(storage_type, self.uploads_path)
    
    def upload_local_screenshot(
        self,
        file_data: BinaryIO,
        filename: str,
        session_uuid: str
    ) -> Dict[str, Any]:
        """Загрузка скриншота локально (в папку)."""
        # Создаём папку для сессии
        session_folder = self.screenshots_path / session_uuid
        session_folder.mkdir(parents=True, exist_ok=True)
        
        # Сохраняем файл
        file_path = session_folder / filename
        
        # Определяем размер
        file_data.seek(0, 2)
        file_size = file_data.tell()
        file_data.seek(0)
        
        # Сохраняем
        with open(file_path, 'wb') as f:
            f.write(file_data.read())
        
        # Относительный путь для API
        relative_path = f"/screenshots/{session_uuid}/{filename}"
        
        return {
            "success": True,
            "local_path": str(file_path),
            "relative_path": relative_path,
            "size_bytes": file_size,
        }
    
    def upload_file(
        self,
        file_data: BinaryIO,
        filename: str,
        bucket: StorageType,
        content_type: str = "application/octet-stream",
        guide_id: Optional[int] = None,
        subfolder: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Загрузка файла локально."""
        base_path = self._get_storage_path(bucket)
        
        # Создаём подпапку
        if subfolder:
            storage_path = base_path / subfolder
        elif guide_id:
            storage_path = base_path / str(guide_id)
        else:
            storage_path = base_path
        
        storage_path.mkdir(parents=True, exist_ok=True)
        
        # Генерируем уникальное имя файла
        unique_id = uuid.uuid4().hex[:8]
        safe_filename = "".join(c for c in filename if c.isalnum() or c in "._-")
        final_filename = f"{unique_id}_{safe_filename}"
        
        file_path = storage_path / final_filename
        
        # Сохраняем файл
        file_data.seek(0, 2)
        file_size = file_data.tell()
        file_data.seek(0)
        
        with open(file_path, 'wb') as f:
            f.write(file_data.read())
        
        # Относительный путь
        relative_path = f"/{bucket.value}/{storage_path.relative_to(base_path)}/{final_filename}"
        
        return {
            "success": True,
            "local_path": str(file_path),
            "relative_path": relative_path,
            "size_bytes": file_size,
            "content_type": content_type,
        }


# Экземпляр сервиса для использования в приложении
storage_service = StorageService()
