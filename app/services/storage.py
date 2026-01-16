"""
Storage Service - сервис для работы с объектным хранилищем MinIO (S3-compatible).
Обеспечивает загрузку, скачивание и управление файлами видео и скриншотов.

Storage Stack:
- MinIO (S3-compatible) для видео и скриншотов
- Поддержка presigned URLs для безопасной загрузки
- Инкрементальная загрузка больших файлов
"""

import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List, BinaryIO
from enum import Enum

from minio import Minio
from minio.error import S3Error

from app.config import settings


logger = logging.getLogger(__name__)


class StorageBucket(str, Enum):
    """Доступные бакиеты хранилища."""
    UPLOADS = "autodoc-uploads"
    VIDEOS = "autodoc-videos"
    SCREENSHOTS = "autodoc-screenshots"
    WIKI = "autodoc-wiki"
    AUDIO = "autodoc-audio"


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
    """
    Сервис для работы с MinIO / S3-совместимым хранилищем.
    
    Функции:
    - Загрузка и скачивание файлов
    - Генерация presigned URLs
    - Управление бакетами
    - Работа с большими файлами (multipart upload)
    """
    
    def __init__(
        self,
        endpoint: str = None,
        access_key: str = None,
        secret_key: str = None,
        secure: bool = None,
    ):
        """
        Инициализация сервиса хранилища.
        
        Args:
            endpoint: Адрес MinIO сервера
            access_key: Access key
            secret_key: Secret key
            secure: Использовать HTTPS
        """
        self.endpoint = endpoint or settings.MINIO_ENDPOINT
        self.access_key = access_key or settings.MINIO_ACCESS_KEY
        self.secret_key = secret_key or settings.MINIO_SECRET_KEY
        self.secure = secure or settings.MINIO_SECURE
        
        self._client: Optional[Minio] = None
        self._init_client()
    
    def _init_client(self) -> None:
        """Инициализация MinIO клиента."""
        try:
            self._client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure,
            )
            
            logger.info(f"MinIO client initialized: {self.endpoint}")
            
            # Создаем бакиеты если не существуют
            self._ensure_buckets()
            
        except Exception as e:
            logger.error(f"Failed to initialize MinIO client: {e}")
            # Не падаем - хранилище может быть недоступно в dev-режиме
            self._client = None
    
    def _ensure_buckets(self) -> None:
        """Создание необходимых бакетов."""
        buckets = [
            StorageBucket.UPLOADS.value,
            StorageBucket.VIDEOS.value,
            StorageBucket.SCREENSHOTS.value,
            StorageBucket.WIKI.value,
            StorageBucket.AUDIO.value,
        ]
        
        for bucket_name in buckets:
            try:
                if not self._client.bucket_exists(bucket_name):
                    self._client.make_bucket(bucket_name)
                    logger.info(f"Created bucket: {bucket_name}")
            except S3Error as e:
                logger.warning(f"Could not create bucket {bucket_name}: {e}")
    
    @property
    def client(self) -> Minio:
        """Получение клиента (с проверкой инициализации)."""
        if self._client is None:
            raise StorageError("MinIO client not initialized")
        return self._client
    
    def _generate_object_key(
        self,
        bucket: StorageBucket,
        filename: str,
        guide_id: Optional[int] = None,
        subfolder: Optional[str] = None
    ) -> str:
        """
        Генерация ключа объекта для хранения.
        
        Формат: {guide_id}/{subfolder}/{uuid}_{filename}
        или: {subfolder}/{uuid}_{filename}
        или: {uuid}_{filename}
        
        Args:
            bucket: Бакет (не используется в пути, только для контекста)
            filename: Имя файла
            guide_id: ID гайда (опционально)
            subfolder: Подпапка (опционально)
            
        Returns:
            Ключ объекта
        """
        parts = []
        
        if guide_id:
            parts.append(str(guide_id))
        
        if subfolder:
            parts.append(subfolder)
        
        # Добавляем UUID для уникальности
        unique_id = uuid.uuid4().hex[:8]
        safe_filename = "".join(
            c for c in filename 
            if c.isalnum() or c in "._-"
        )
        parts.append(f"{unique_id}_{safe_filename}")
        
        return "/".join(parts)
    
    def upload_file(
        self,
        file_data: BinaryIO,
        filename: str,
        bucket: StorageBucket,
        content_type: str = "application/octet-stream",
        guide_id: Optional[int] = None,
        subfolder: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Загрузка файла в хранилище.
        
        Args:
            file_data: Файл для загрузки
            filename: Имя файла
            bucket: Бакет
            content_type: MIME-тип
            guide_id: ID гайда
            subfolder: Подпапка
            metadata: Метаданные файла
            
        Returns:
            Словарь с информацией о загруженном файле
        """
        object_key = self._generate_object_key(
            bucket, filename, guide_id, subfolder
        )
        
        try:
            # Определяем размер файла
            file_data.seek(0, 2)
            file_size = file_data.tell()
            file_data.seek(0)
            
            # Загружаем файл
            self.client.put_object(
                bucket_name=bucket.value,
                object_name=object_key,
                data=file_data,
                length=file_size,
                content_type=content_type,
                metadata=metadata,
            )
            
            logger.info(f"Uploaded file: {object_key} ({file_size} bytes)")
            
            return {
                "success": True,
                "object_key": object_key,
                "bucket": bucket.value,
                "size_bytes": file_size,
                "content_type": content_type,
                "url": self._get_object_url(object_key, bucket),
            }
            
        except S3Error as e:
            logger.error(f"Upload failed: {e}")
            raise UploadError(f"Failed to upload file: {e}")
    
    def upload_local_file(
        self,
        file_path: str,
        bucket: StorageBucket,
        guide_id: Optional[int] = None,
        subfolder: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Загрузка локального файла.
        
        Args:
            file_path: Путь к локальному файлу
            bucket: Бакет
            guide_id: ID гайда
            subfolder: Подпапка
            
        Returns:
            Информация о загруженном файле
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        with open(file_path, "rb") as f:
            content_type = self._guess_content_type(path.suffix)
            return self.upload_file(
                file_data=f,
                filename=path.name,
                bucket=bucket,
                content_type=content_type,
                guide_id=guide_id,
                subfolder=subfolder,
            )
    
    def download_file(
        self,
        object_key: str,
        bucket: StorageBucket,
        output_path: Optional[str] = None,
    ) -> bytes:
        """
        Скачивание файла из хранилища.
        
        Args:
            object_key: Ключ объекта
            bucket: Бакет
            output_path: Путь для сохранения (опционально)
            
        Returns:
            Байты файла
        """
        try:
            response = self.client.get_object(
                bucket_name=bucket.value,
                object_name=object_key,
            )
            
            data = response.read()
            response.close()
            response.release_conn()
            
            if output_path:
                with open(output_path, "wb") as f:
                    f.write(data)
            
            return data
            
        except S3Error as e:
            if "NoSuchKey" in str(e):
                raise FileNotFoundError(f"Object not found: {object_key}")
            raise StorageError(f"Download failed: {e}")
    
    def get_file(
        self,
        object_key: str,
        bucket: StorageBucket,
    ) -> Optional[bytes]:
        """
        Получение файла из хранилища (упрощённый метод).
        
        Args:
            object_key: Ключ объекта
            bucket: Бакет
            
        Returns:
            Байты файла или None если не найден
        """
        try:
            return self.download_file(object_key, bucket)
        except (FileNotFoundError, StorageError) as e:
            logger.warning(f"File not found: {object_key} in {bucket.value}: {e}")
            return None
    
    def get_presigned_upload_url(
        self,
        filename: str,
        bucket: StorageBucket,
        content_type: str,
        guide_id: Optional[int] = None,
        subfolder: Optional[str] = None,
        expires_in: int = 3600,
    ) -> Dict[str, Any]:
        """
        Генерация presigned URL для загрузки.
        
        Args:
            filename: Имя файла
            bucket: Бакет
            content_type: MIME-тип
            guide_id: ID гайда
            subfolder: Подпапка
            expires_in: Время жизни ссылки в секундах
            
        Returns:
            Словарь с URL и метаданными
        """
        object_key = self._generate_object_key(
            bucket, filename, guide_id, subfolder
        )
        
        try:
            url = self.client.presigned_put_object(
                bucket_name=bucket.value,
                object_name=object_key,
                expires=timedelta(seconds=expires_in),
            )
            
            return {
                "upload_url": url,
                "object_key": object_key,
                "bucket": bucket.value,
                "expires_in": expires_in,
                "method": "PUT",
            }
            
        except S3Error as e:
            raise StorageError(f"Failed to generate presigned URL: {e}")
    
    def get_presigned_download_url(
        self,
        object_key: str,
        bucket: StorageBucket,
        expires_in: int = 3600,
    ) -> Dict[str, Any]:
        """
        Генерация presigned URL для скачивания.
        
        Args:
            object_key: Ключ объекта
            bucket: Бакет
            expires_in: Время жизни ссылки в секундах
            
        Returns:
            Словарь с URL
        """
        try:
            url = self.client.presigned_get_object(
                bucket_name=bucket.value,
                object_name=object_key,
                expires=timedelta(seconds=expires_in),
            )
            
            return {
                "download_url": url,
                "object_key": object_key,
                "bucket": bucket.value,
                "expires_in": expires_in,
            }
            
        except S3Error as e:
            raise StorageError(f"Failed to generate download URL: {e}")
    
    def delete_file(
        self,
        object_key: str,
        bucket: StorageBucket,
    ) -> bool:
        """
        Удаление файла из хранилища.
        
        Args:
            object_key: Ключ объекта
            bucket: Бакет
            
        Returns:
            True если успешно
        """
        try:
            self.client.remove_object(
                bucket_name=bucket.value,
                object_name=object_key,
            )
            
            logger.info(f"Deleted file: {object_key}")
            return True
            
        except S3Error as e:
            logger.error(f"Delete failed: {e}")
            return False
    
    def delete_files_by_prefix(
        self,
        bucket: StorageBucket,
        prefix: str,
    ) -> int:
        """
        Удаление всех файлов с определенным префиксом.
        
        Args:
            bucket: Бакет
            prefix: Префикс ключа
            
        Returns:
            Количество удаленных файлов
        """
        deleted_count = 0
        
        try:
            objects = self.client.list_objects(
                bucket_name=bucket.value,
                prefix=prefix,
                recursive=True,
            )
            
            for obj in objects:
                self.client.remove_object(
                    bucket_name=bucket.value,
                    object_name=obj.object_name,
                )
                deleted_count += 1
            
            logger.info(f"Deleted {deleted_count} files with prefix: {prefix}")
            return deleted_count
            
        except S3Error as e:
            logger.error(f"Bulk delete failed: {e}")
            return 0
    
    def list_files(
        self,
        bucket: StorageBucket,
        prefix: Optional[str] = None,
        max_keys: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Получение списка файлов в бакете.
        
        Args:
            bucket: Бакет
            prefix: Префикс для фильтрации
            max_keys: Максимальное количество
            
        Returns:
            Список файлов с метаданными
        """
        files = []
        
        try:
            objects = self.client.list_objects(
                bucket_name=bucket.value,
                prefix=prefix,
                recursive=True,
                max_keys=max_keys,
            )
            
            for obj in objects:
                files.append({
                    "object_key": obj.object_name,
                    "size_bytes": obj.size,
                    "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
                    "etag": obj.etag,
                })
            
            return files
            
        except S3Error as e:
            logger.error(f"List files failed: {e}")
            return []
    
    def get_file_info(
        self,
        object_key: str,
        bucket: StorageBucket,
    ) -> Dict[str, Any]:
        """
        Получение информации о файле.
        
        Args:
            object_key: Ключ объекта
            bucket: Бакет
            
        Returns:
            Метаданные файла
        """
        try:
            stat = self.client.stat_object(
                bucket_name=bucket.value,
                object_name=object_key,
            )
            
            return {
                "object_key": object_key,
                "size_bytes": stat.size,
                "content_type": stat.content_type,
                "etag": stat.etag,
                "last_modified": stat.last_modified.isoformat() if stat.last_modified else None,
                "metadata": stat.metadata,
            }
            
        except S3Error as e:
            if "NoSuchKey" in str(e):
                raise FileNotFoundError(f"Object not found: {object_key}")
            raise StorageError(f"Stat failed: {e}")
    
    def copy_file(
        self,
        source_key: str,
        source_bucket: StorageBucket,
        dest_key: str,
        dest_bucket: StorageBucket,
    ) -> Dict[str, Any]:
        """
        Копирование файла внутри хранилища.
        
        Args:
            source_key: Исходный ключ
            source_bucket: Исходный бакет
            dest_key: Целевой ключ
            dest_bucket: Целевой бакет
            
        Returns:
            Информация о скопированном файле
        """
        try:
            source_path = f"{source_bucket.value}/{source_key}"
            
            self.client.copy_object(
                bucket_name=dest_bucket.value,
                object_name=dest_key,
                source=f"/{source_bucket.value}/{source_key}",
            )
            
            logger.info(f"Copied file: {source_path} -> {dest_bucket.value}/{dest_key}")
            
            return {
                "source_key": source_key,
                "dest_key": dest_key,
                "bucket": dest_bucket.value,
            }
            
        except S3Error as e:
            raise StorageError(f"Copy failed: {e}")
    
    def _get_object_url(self, object_key: str, bucket: StorageBucket) -> str:
        """Получение прямого URL объекта."""
        # Для MinIO в режиме без проксирования
        return f"https://{self.endpoint}/{bucket.value}/{object_key}"
    
    def _guess_content_type(self, extension: str) -> str:
        """Определение MIME-типа по расширению."""
        content_types = {
            ".mp4": "video/mp4",
            ".webm": "video/webm",
            ".mov": "video/quicktime",
            ".avi": "video/x-msvideo",
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".ogg": "audio/ogg",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".md": "text/markdown",
            ".html": "text/html",
            ".pdf": "application/pdf",
            ".json": "application/json",
        }
        
        return content_types.get(extension.lower(), "application/octet-stream")
    
    def check_bucket_exists(self, bucket: StorageBucket) -> bool:
        """Проверка существования бакета."""
        try:
            return self.client.bucket_exists(bucket.value)
        except S3Error:
            return False
    
    def check_connection(self) -> Dict[str, Any]:
        """Проверка соединения с хранилищем."""
        status = {
            "connected": False,
            "endpoint": self.endpoint,
            "buckets": [],
            "error": None,
        }
        
        try:
            # Проверяем соединение листом бакетов
            buckets = self.client.list_buckets()
            
            status["connected"] = True
            status["buckets"] = [b.name for b in buckets]
            
        except Exception as e:
            status["error"] = str(e)
        
        return status


# Экземпляр сервиса для использования в приложении
storage_service = StorageService()
