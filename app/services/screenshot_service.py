"""
Screenshot Service - извлечение скриншотов из видео.
Использует FFmpeg для захвата кадров в заданные таймкоды.
"""

import logging
import subprocess
import uuid
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ExtractedScreenshot:
    """Результат извлечения скриншота."""
    timestamp: float          # Таймкод
    output_path: str          # Путь к файлу
    width: int                # Ширина изображения
    height: int               # Высота изображения
    success: bool             # Успешно ли
    error: Optional[str] = None  # Ошибка если есть


class ScreenshotExtractor:
    """
    Извлекает скриншоты из видео в заданные таймкоды.
    
    Использует FFmpeg для точного захвата кадра.
    """
    
    def __init__(
        self,
        output_dir: str = None,
        width: int = 1080,
        height: int = 1920
    ):
        """
        Инициализация.
        
        Args:
            output_dir: Директория для сохранения скриншотов
            width: Ширина скриншота (по умолчанию 1080 для Shorts)
            height: Высота скриншота (по умолчанию 1920 для Shorts)
        """
        self.output_dir = Path(output_dir or settings.WORKER_TEMP_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.width = width
        self.height = height
    
    def extract_at_timestamps(
        self,
        video_path: str,
        timestamps: List[float],
        prefix: str = "step"
    ) -> List[ExtractedScreenshot]:
        """
        Извлечь скриншоты в несколько таймкодов.
        
        Args:
            video_path: Путь к видеофайлу
            timestamps: Список таймкодов для захвата
            prefix: Префикс имени файла
            
        Returns:
            Список результатов
        """
        results = []
        
        for i, ts in enumerate(timestamps):
            output_path = self.output_dir / f"{prefix}_{i:03d}_{ts:.2f}.png"
            
            result = self._extract_single(
                video_path=video_path,
                timestamp=ts,
                output_path=str(output_path)
            )
            
            results.append(result)
        
        success_count = sum(1 for r in results if r.success)
        logger.info(f"Extracted {success_count}/{len(results)} screenshots")
        
        return results
    
    def _extract_single(
        self,
        video_path: str,
        timestamp: float,
        output_path: str
    ) -> ExtractedScreenshot:
        """
        Извлечь один скриншот.
        
        FFmpeg command:
        ffmpeg -ss {timestamp} -i input.mp4 -vframes 1 -vf "scale={width}:{height}:force" output.png
        """
        video = Path(video_path)
        output = Path(output_path)
        
        if not video.exists():
            return ExtractedScreenshot(
                timestamp=timestamp,
                output_path="",
                width=0,
                height=0,
                success=False,
                error=f"Video not found: {video_path}"
            )
        
        # Создаем выходную директорию
        output.parent.mkdir(parents=True, exist_ok=True)
        
        # FFmpeg команда
        # -ss: позиция
        # -i: входной файл
        # -vframes 1: один кадр
        # -vf: видеофильтры для масштабирования
        cmd = [
            "ffmpeg",
            "-ss", str(timestamp),
            "-i", str(video),
            "-vframes", "1",
            "-vf", f"scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2",
            "-y",  # Перезаписать если существует
            str(output)
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30  # Таймаут 30 секунд на кадр
            )
            
            if result.returncode == 0 and output.exists():
                # Получаем размеры изображения
                img_info = self._get_image_info(str(output))
                
                return ExtractedScreenshot(
                    timestamp=timestamp,
                    output_path=str(output),
                    width=img_info.get("width", self.width),
                    height=img_info.get("height", self.height),
                    success=True
                )
            else:
                error_msg = result.stderr or "Unknown error"
                logger.error(f"FFmpeg failed for timestamp {timestamp}: {error_msg}")
                
                return ExtractedScreenshot(
                    timestamp=timestamp,
                    output_path="",
                    width=0,
                    height=0,
                    success=False,
                    error=error_msg[:200]
                )
                
        except subprocess.TimeoutExpired:
            return ExtractedScreenshot(
                timestamp=timestamp,
                output_path="",
                width=0,
                height=0,
                success=False,
                error="FFmpeg timeout (30s)"
            )
        except Exception as e:
            logger.exception(f"Screenshot extraction failed: {e}")
            return ExtractedScreenshot(
                timestamp=timestamp,
                output_path="",
                width=0,
                height=0,
                success=False,
                error=str(e)[:200]
            )
    
    def _get_image_info(self, image_path: str) -> Dict[str, int]:
        """Получить размеры изображения через FFprobe."""
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=p=0",
                image_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                parts = result.stdout.strip().split(",")
                if len(parts) == 2:
                    return {
                        "width": int(parts[0]),
                        "height": int(parts[1])
                    }
                    
        except Exception as e:
            logger.warning(f"Failed to get image info: {e}")
        
        return {"width": self.width, "height": self.height}
    
    def extract_sequence(
        self,
        video_path: str,
        start_time: float,
        end_time: float,
        interval: float = 1.0,
        prefix: str = "sequence"
    ) -> List[ExtractedScreenshot]:
        """
        Извлечь последовательность кадров (для превью/анимации).
        
        Args:
            video_path: Путь к видео
            start_time: Начало
            end_time: Конец
            interval: Интервал между кадрами
            prefix: Префикс файла
            
        Returns:
            Список скриншотов
        """
        timestamps = []
        current = start_time
        
        while current <= end_time:
            timestamps.append(current)
            current += interval
        
        return self.extract_at_timestamps(video_path, timestamps, prefix)


def generate_marker_overlay(
    screenshot_path: str,
    output_path: str,
    x: int,
    y: int,
    marker_size: int = 30,
    marker_color: str = "#FFD700",  # Жёлтый цвет
    ring_width: int = 3
) -> bool:
    """
    Наложить маркер на скриншот.
    
    Использует FFmpeg для рисования круга в указанных координатах.
    
    Args:
        screenshot_path: Путь к исходному скриншоту
        output_path: Путь к результату
        x: Координата X центра маркера
        y: Координата Y центра маркера
        marker_size: Радиус маркера
        marker_color: Цвет (hex или color name)
        ring_width: Толщина кольца
        
    Returns:
        True если успешно
    """
    # FFmpeg фильтр для рисования круга
    # drawbox с закруглением через circle filter
    draw_filter = (
        f"drawbox=x={x-marker_size}:y={y-marker_size}:w={marker_size*2}:h={marker_size*2}:"
        f"color={marker_color}:t={ring_width}:round=20,"
        f"drawbox=x={x-5}:y={y-5}:w=10:h=10:color={marker_color}:t=-1"
    )
    
    # Альтернатива: circle filter если доступен
    if marker_color.startswith("#"):
        # Конвертируем hex в FFmpeg формат
        hex_color = marker_color[1:]
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        draw_filter = f"drawcircle=r={marker_size}:c=@0x{r:x}{g:x}{b:x}:t={ring_width}:x={x}:y={y}"
    
    cmd = [
        "ffmpeg",
        "-i", screenshot_path,
        "-vf", draw_filter,
        "-y",
        output_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.returncode == 0 and Path(output_path).exists()
    except Exception as e:
        logger.error(f"Marker overlay failed: {e}")
        return False
