"""
API роуты для работы с хранилищем.
Реализует загрузку, скачивание и управление файлами.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import (
    PresignedUrlRequest,
    PresignedUrlResponse,
    DownloadUrlResponse,
    ErrorResponse,
)
from app.services.storage import storage_service, StorageBucket


logger = logging.getLogger(__name__)


router = APIRouter()


@router.post("/upload/presigned", response_model=PresignedUrlResponse)
async def generate_upload_url(
    request: PresignedUrlRequest,
) -> PresignedUrlResponse:
    """
    Генерация presigned URL для загрузки файла.
    
    Используется для прямой загрузки файлов в MinIO из браузера.
    """
    try:
        bucket = StorageBucket(request.bucket) if request.bucket else StorageBucket.UPLOADS
        
        result = storage_service.get_presigned_upload_url(
            filename=request.file_name,
            bucket=bucket,
            content_type=request.content_type,
            guide_id=request.guide_id,
            expires_in=3600,
        )
        
        return PresignedUrlResponse(
            upload_url=result["upload_url"],
            file_key=result["object_key"],
            expires_in=result["expires_in"],
            method=result["method"],
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid bucket: {e}",
        )
    except Exception as e:
        logger.error(f"Failed to generate upload URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate upload URL",
        )


@router.post("/download/presigned", response_model=DownloadUrlResponse)
async def generate_download_url(
    object_key: str,
    bucket: str = Query(..., description="Бакет хранилища"),
    expires_in: int = Query(3600, ge=1, le=86400, description="Время жизни ссылки в секундах"),
) -> DownloadUrlResponse:
    """
    Генерация presigned URL для скачивания файла.
    """
    try:
        storage_bucket = StorageBucket(bucket)
        
        result = storage_service.get_presigned_download_url(
            object_key=object_key,
            bucket=storage_bucket,
            expires_in=expires_in,
        )
        
        return DownloadUrlResponse(
            download_url=result["download_url"],
            expires_in=result["expires_in"],
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid bucket: {e}",
        )
    except Exception as e:
        logger.error(f"Failed to generate download URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate download URL",
        )


@router.post("/upload/direct")
async def upload_file_direct(
    file: UploadFile = File(...),
    bucket: str = Query("uploads", description="Бакет для загрузки"),
    guide_id: Optional[int] = Query(None, description="ID гайда"),
    subfolder: Optional[str] = Query(None, description="Подпапка"),
):
    """
    Прямая загрузка файла через API.
    
    Для больших файлов используйте presigned URL.
    """
    try:
        storage_bucket = StorageBucket(bucket)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid bucket: {bucket}",
        )
    
    try:
        result = storage_service.upload_file(
            file_data=file.file,
            filename=file.filename,
            bucket=storage_bucket,
            content_type=file.content_type or "application/octet-stream",
            guide_id=guide_id,
            subfolder=subfolder,
        )
        
        return {
            "success": True,
            "file_key": result["object_key"],
            "url": result["url"],
            "size_bytes": result["size_bytes"],
        }
        
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {e}",
        )


@router.delete("/file")
async def delete_file(
    object_key: str,
    bucket: str = Query(..., description="Бакет"),
) -> dict:
    """
    Удаление файла из хранилища.
    """
    try:
        storage_bucket = StorageBucket(bucket)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid bucket: {bucket}",
        )
    
    success = storage_service.delete_file(
        object_key=object_key,
        bucket=storage_bucket,
    )
    
    if success:
        return {"success": True, "message": "File deleted"}
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="File not found or delete failed",
    )


@router.get("/files")
async def list_files(
    bucket: str = Query(..., description="Бакет"),
    prefix: Optional[str] = Query(None, description="Префикс для фильтрации"),
    max_keys: int = Query(100, ge=1, le=1000),
) -> list:
    """
    Получение списка файлов в бакете.
    """
    try:
        storage_bucket = StorageBucket(bucket)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid bucket: {bucket}",
        )
    
    files = storage_service.list_files(
        bucket=storage_bucket,
        prefix=prefix,
        max_keys=max_keys,
    )
    
    return files


@router.get("/file/info")
async def get_file_info(
    object_key: str,
    bucket: str = Query(..., description="Бакет"),
) -> dict:
    """
    Получение информации о файле.
    """
    try:
        storage_bucket = StorageBucket(bucket)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid bucket: {bucket}",
        )
    
    try:
        info = storage_service.get_file_info(
            object_key=object_key,
            bucket=storage_bucket,
        )
        return info
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get file info",
        )


@router.get("/file")
async def get_file(
    path: str = Query(..., description="Путь к файлу (object_key)"),
):
    """
    Получение файла из хранилища.
    Определяет бакет автоматически по пути.
    """
    from fastapi.responses import StreamingResponse
    import io
    
    # Определяем бакет по пути
    bucket = StorageBucket.SCREENSHOTS  # По умолчанию скриншоты
    
    if path.startswith("autodoc-uploads/") or "/uploads/" in path:
        bucket = StorageBucket.UPLOADS
        path = path.replace("autodoc-uploads/", "").replace("/uploads/", "")
    elif path.startswith("autodoc-screenshots/") or "/screenshots/" in path:
        bucket = StorageBucket.SCREENSHOTS
        path = path.replace("autodoc-screenshots/", "").replace("/screenshots/", "")
    elif path.startswith("autodoc-videos/") or "/videos/" in path:
        bucket = StorageBucket.VIDEOS
        path = path.replace("autodoc-videos/", "").replace("/videos/", "")
    elif path.startswith("autodoc-audio/") or "/audio/" in path:
        bucket = StorageBucket.AUDIO
        path = path.replace("autodoc-audio/", "").replace("/audio/", "")
    
    try:
        # Получаем файл из MinIO
        file_data = storage_service.get_file(path, bucket)
        
        if file_data is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found",
            )
        
        # Определяем content-type
        content_type = "application/octet-stream"
        if path.endswith(".png"):
            content_type = "image/png"
        elif path.endswith(".jpg") or path.endswith(".jpeg"):
            content_type = "image/jpeg"
        elif path.endswith(".webm"):
            content_type = "video/webm"
        elif path.endswith(".mp4"):
            content_type = "video/mp4"
        elif path.endswith(".wav"):
            content_type = "audio/wav"
        elif path.endswith(".mp3"):
            content_type = "audio/mpeg"
        
        return StreamingResponse(
            io.BytesIO(file_data),
            media_type=content_type,
            headers={
                "Cache-Control": "public, max-age=86400",
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get file {path}: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {path}",
        )


@router.post("/copy")
async def copy_file(
    source_key: str,
    source_bucket: str,
    dest_key: str,
    dest_bucket: str,
) -> dict:
    """
    Копирование файла внутри хранилища.
    """
    try:
        source = StorageBucket(source_bucket)
        dest = StorageBucket(dest_bucket)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid bucket: {e}",
        )
    
    try:
        result = storage_service.copy_file(
            source_key=source_key,
            source_bucket=source,
            dest_key=dest_key,
            dest_bucket=dest,
        )
        
        return {
            "success": True,
            **result,
        }
        
    except Exception as e:
        logger.error(f"Copy failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Copy failed",
        )


@router.get("/buckets")
async def list_buckets() -> dict:
    """
    Получение списка бакетов и их статуса.
    """
    return {
        "buckets": [
            {
                "name": b.value,
                "description": {
                    StorageBucket.UPLOADS: "Загрузки пользователей",
                    StorageBucket.VIDEOS: "Обработанные видео",
                    StorageBucket.SCREENSHOTS: "Скриншоты для Wiki",
                    StorageBucket.WIKI: "Wiki-статьи",
                    StorageBucket.AUDIO: "Аудио-файлы TTS",
                }.get(b, ""),
            }
            for b in StorageBucket
        ]
    }


@router.get("/status")
async def check_storage_status() -> dict:
    """
    Проверка статуса хранилища.
    """
    return storage_service.check_connection()
