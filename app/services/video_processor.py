"""
Video Processor Service - основной сервис обработки видео.
Отвечает за монтаж, наложение зума, синхронизацию и генерацию выходных файлов.

Главный вызов проекта: стабильный Time-Stretching видео при изменении аудио.
Требование: FFmpeg фильтры atempo или setpts на коротких фрагментах (1-3 секунды).
"""

import asyncio
import logging
import os
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.config import settings


logger = logging.getLogger(__name__)


class VideoProcessError(Exception):
    """Базовый класс для ошибок обработки видео."""
    pass


class FFmpegNotFoundError(VideoProcessError):
    """FFmpeg не найден в системе."""
    pass


class InvalidInputError(VideoProcessError):
    """Невалидные входные данные."""
    pass


class ProcessingTimeoutError(VideoProcessError):
    """Превышено время обработки."""
    pass


class ZoomTransition(Enum):
    """Типы переходов для зума."""
    LINEAR = "linear"
    EASE_IN = "ease_in"
    EASE_OUT = "ease_out"
    EASE_IN_OUT = "ease_in_out"


@dataclass
class ZoomRegion:
    """Область для зума с параметрами анимации."""
    x: int
    y: int
    width: int
    height: int
    target_width: int = 0
    target_height: int = 0
    center_x: Optional[int] = None
    center_y: Optional[int] = None
    
    def __post_init__(self):
        """Вычисление центра области и целевых размеров."""
        self.center_x = self.x + self.width // 2
        self.center_y = self.y + self.height // 2
        
        if self.target_width == 0:
            self.target_width = self.width
        if self.target_height == 0:
            self.target_height = self.height


@dataclass
class StepSegment:
    """Видео-сегмент соответствующий одному шагу гайда."""
    start_time: float
    end_time: float
    original_start: float
    original_end: float
    text: str
    audio_path: Optional[str] = None
    zoom_region: Optional[ZoomRegion] = None
    action_type: Optional[str] = None
    audio_duration: Optional[float] = None
    
    @property
    def duration(self) -> float:
        """Длительность сегмента."""
        return self.end_time - self.start_time
    
    @property
    def original_duration(self) -> float:
        """Оригинальная длительность до растягивания."""
        return self.original_end - self.original_start


@dataclass
class ProcessingProgress:
    """Прогресс обработки видео."""
    current_step: int
    total_steps: int
    progress_percent: float
    message: str
    stage: str  # extraction, rendering, encoding, mixing


class VideoProcessor:
    """
    Основной класс для обработки видео.
    Использует FFmpeg через subprocess для максимальной совместимости.
    
    Ключевые возможности:
    - Автоматический зум на области кликов
    - Наложение курсора мыши
    - Time-stretching для синхронизации с аудио
    - Генерация Shorts/Reels формата
    - Экстракция скриншотов
    """
    
    def __init__(self, ffmpeg_path: str = "ffmpeg", ffprobe_path: str = "ffprobe"):
        """
        Инициализация процессора видео.
        
        Args:
            ffmpeg_path: Путь к исполняемому файлу FFmpeg
            ffprobe_path: Путь к исполняемому файлу FFprobe
        """
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path
        self._check_ffmpeg_installed()
        
        # Настройки по умолчанию
        self.default_width = settings.VIDEO_OUTPUT_WIDTH
        self.default_height = settings.VIDEO_OUTPUT_HEIGHT
        self.default_fps = settings.VIDEO_FPS
        
        # Кэш для оптимизации
        self._frame_cache: Dict[str, np.ndarray] = {}
        self._font_cache: Dict[str, ImageFont.ImageFont] = {}
    
    def _check_ffmpeg_installed(self) -> None:
        """Проверка наличия FFmpeg в системе."""
        try:
            subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
                timeout=10
            )
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            raise FFmpegNotFoundError(
                f"FFmpeg not found or not accessible: {e}. "
                "Please install FFmpeg and add it to PATH."
            )
    
    def get_video_info(self, video_path: str) -> Dict[str, Any]:
        """
        Получение информации о видеофайле.
        
        Args:
            video_path: Путь к видеофайлу
            
        Returns:
            Словарь с информацией о видео
        """
        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            video_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            raise VideoProcessError(f"Failed to probe video: {result.stderr}")
        
        import json
        data = json.loads(result.stdout)
        
        # Поиск видео и аудио потоков
        video_stream = None
        audio_stream = None
        
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video" and video_stream is None:
                video_stream = stream
            elif stream.get("codec_type") == "audio" and audio_stream is None:
                audio_stream = stream
        
        if video_stream is None:
            raise InvalidInputError("No video stream found in the file")
        
        # Парсинг информации
        info = {
            "duration": float(data["format"].get("duration", 0)),
            "format_name": data["format"].get("format_name", ""),
            "size_bytes": int(data["format"].get("size", 0)),
            "bit_rate": int(data["format"].get("bit_rate", 0)),
            "video": {
                "codec": video_stream.get("codec_name", ""),
                "width": int(video_stream.get("width", 0)),
                "height": int(video_stream.get("height", 0)),
                "fps": self._parse_fps(video_stream.get("r_frame_rate", "30/1")),
                "duration": float(video_stream.get("duration", 0)),
                "pix_fmt": video_stream.get("pix_fmt", ""),
            }
        }
        
        if audio_stream:
            info["audio"] = {
                "codec": audio_stream.get("codec_name", ""),
                "channels": int(audio_stream.get("channels", 0)),
                "sample_rate": int(audio_stream.get("sample_rate", 0)),
                "duration": float(audio_stream.get("duration", 0)),
            }
        
        return info
    
    def _parse_fps(self, frame_rate: str) -> float:
        """Парсинг FPS из строки формата '30/1' или '30000/1001'."""
        try:
            num, den = frame_rate.split("/")
            return float(num) / float(den)
        except (ValueError, ZeroDivisionError):
            return 30.0
    
    def extract_frames(
        self,
        video_path: str,
        timestamps: List[float],
        width: int = 320,
        height: int = 180,
        output_dir: Optional[str] = None
    ) -> List[str]:
        """
        Извлечение кадров из видео в указанные моменты времени.
        
        Args:
            video_path: Путь к видеофайлу
            timestamps: Список временных меток для извлечения
            width: Ширина извлекаемых кадров
            height: Высота извлекаемых кадров
            output_dir: Директория для сохранения кадров
            
        Returns:
            Список путей к извлеченным кадрам
        """
        if output_dir is None:
            output_dir = Path(settings.TEMP_DIR) / "frames"
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        output_paths = []
        
        for i, ts in enumerate(timestamps):
            output_path = Path(output_dir) / f"frame_{i:06d}_{ts:.3f}.jpg"
            output_paths.append(str(output_path))
            
            cmd = [
                self.ffmpeg_path,
                "-ss", str(ts),
                "-i", video_path,
                "-vframes", "1",
                "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease",
                "-q:v", "2",
                "-y",  # Перезаписать существующие файлы
                str(output_path)
            ]
            
            try:
                subprocess.run(cmd, capture_output=True, timeout=30)
            except subprocess.TimeoutExpired:
                logger.warning(f"Timeout extracting frame at {ts}s")
                continue
        
        return output_paths
    
    def extract_screenshot(
        self,
        video_path: str,
        timestamp: float,
        output_path: str,
        width: Optional[int] = None,
        height: Optional[int] = None
    ) -> bool:
        """
        Извлечение одного скриншота из видео.
        
        Args:
            video_path: Путь к видеофайлу
            timestamp: Временная метка скриншота
            output_path: Путь для сохранения
            width: Желаемая ширина (None - оригинальная)
            height: Желаемая высота (None - оригинальная)
            
        Returns:
            True если успешно, False иначе
        """
        filters = []
        if width and height:
            filters.append(f"scale={width}:{height}")
        
        vf_string = ",".join(filters) if filters else "null"
        
        cmd = [
            self.ffmpeg_path,
            "-ss", str(timestamp),
            "-i", video_path,
            "-vframes", "1",
        ]
        
        if vf_string != "null":
            cmd.extend(["-vf", vf_string])
        
        cmd.extend([
            "-q:v", "2",
            "-y",
            output_path
        ])
        
        try:
            subprocess.run(cmd, capture_output=True, timeout=30)
            return Path(output_path).exists()
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout extracting screenshot at {timestamp}s")
            return False
    
    def add_annotations_to_image(
        self,
        image_path: str,
        output_path: str,
        annotations: List[Dict[str, Any]]
    ) -> bool:
        """
        Добавление аннотаций к изображению (стрелки, выделения, текст).
        
        Args:
            image_path: Путь к исходному изображению
            output_path: Путь для сохранения результата
            annotations: Список аннотаций
            
        Returns:
            True если успешно
        """
        try:
            img = Image.open(image_path)
            draw = ImageDraw.Draw(img)
            
            for ann in annotations:
                ann_type = ann.get("type", "rect")
                color = ann.get("color", "#FF0000")
                x = ann.get("x", 0)
                y = ann.get("y", 0)
                
                if ann_type == "rect":
                    width = ann.get("width", 100)
                    height = ann.get("height", 30)
                    draw.rectangle([x, y, x + width, y + height], outline=color, width=3)
                
                elif ann_type == "arrow":
                    # Рисуем стрелку
                    end_x = ann.get("end_x", x + 100)
                    end_y = ann.get("end_y", y)
                    self._draw_arrow(draw, x, y, end_x, end_y, color)
                
                elif ann_type == "text":
                    text = ann.get("text", "")
                    font_size = ann.get("font_size", 24)
                    text_color = ann.get("text_color", "#FFFFFF")
                    self._draw_text_with_background(
                        draw, text, x, y, font_size, color, text_color
                    )
                
                elif ann_type == "circle":
                    radius = ann.get("radius", 20)
                    draw.ellipse(
                        [x - radius, y - radius, x + radius, y + radius],
                        outline=color, width=3
                    )
            
            img.save(output_path, quality=95)
            return True
            
        except Exception as e:
            logger.error(f"Failed to add annotations: {e}")
            return False
    
    def _draw_arrow(
        self,
        draw: ImageDraw.ImageDraw,
        x1: int, y1: int,
        x2: int, y2: int,
        color: str
    ) -> None:
        """Рисование стрелки на изображении."""
        draw.line([(x1, y1), (x2, y2)], fill=color, width=3)
        
        # Рисуем наконечник
        angle = np.arctan2(y2 - y1, x2 - x1)
        arrow_length = 15
        arrow_angle = np.pi / 6
        
        x3 = x2 - arrow_length * np.cos(angle - arrow_angle)
        y3 = y2 - arrow_length * np.sin(angle - arrow_angle)
        x4 = x2 - arrow_length * np.cos(angle + arrow_angle)
        y4 = y2 - arrow_length * np.sin(angle + arrow_angle)
        
        draw.line([(x2, y2), (x3, y3)], fill=color, width=3)
        draw.line([(x2, y2), (x4, y4)], fill=color, width=3)
    
    def _draw_text_with_background(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        x: int,
        y: int,
        font_size: int,
        bg_color: str,
        text_color: str
    ) -> None:
        """Рисование текста с фоном."""
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
        except:
            font = ImageFont.load_default()
        
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        padding = 5
        bg_x1 = x - padding
        bg_y1 = y - padding
        bg_x2 = x + text_width + padding * 2
        bg_y2 = y + text_height + padding * 2
        
        draw.rectangle([bg_x1, bg_y1, bg_x2, bg_y2], fill=bg_color)
        draw.text((x + padding, y), text, fill=text_color, font=font)
    
    def generate_video_with_zoom(
        self,
        input_video: str,
        output_video: str,
        steps: List[StepSegment],
        progress_callback: Optional[callable] = None
    ) -> bool:
        """
        Генерация видео с автоматическим зумом на клики.
        
        Это основной метод, который создает видео с умным зумом.
        
        Args:
            input_video: Путь к исходному видео
            output_video: Путь для сохранения результата
            steps: Список сегментов с информацией о шагах
            progress_callback: Функция обратного вызова для прогресса
            
        Returns:
            True если успешно
        """
        logger.info(f"Starting video generation with zoom: {input_video} -> {output_video}")
        
        if not steps:
            # Если шагов нет, просто копируем видео
            return self._copy_video(input_video, output_video)
        
        # Получаем информацию о видео
        video_info = self.get_video_info(input_video)
        original_width = video_info["video"]["width"]
        original_height = video_info["video"]["height"]
        duration = video_info["duration"]
        
        # Создаем временную директорию
        temp_dir = Path(settings.TEMP_DIR) / f"render_{uuid.uuid4().hex[:8]}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Обрабатываем каждый сегмент
            segment_files = []
            
            for i, step in enumerate(steps):
                if progress_callback:
                    progress_callback(ProcessingProgress(
                        current_step=i + 1,
                        total_steps=len(steps),
                        progress_percent=((i + 1) / len(steps)) * 100,
                        message=f"Processing step {i + 1}/{len(steps)}",
                        stage="rendering"
                    ))
                
                # Извлекаем сегмент видео
                segment_file = temp_dir / f"segment_{i:04d}.mp4"
                segment_files.append(str(segment_file))
                
                if not self._extract_and_zoom_segment(
                    input_video,
                    str(segment_file),
                    step,
                    original_width,
                    original_height
                ):
                    logger.error(f"Failed to process segment {i}")
                    return False
            
            # Объединяем сегменты
            if progress_callback:
                progress_callback(ProcessingProgress(
                    current_step=len(steps),
                    total_steps=len(steps),
                    progress_percent=95,
                    message="Concatenating segments",
                    stage="encoding"
                ))
            
            concat_file = temp_dir / "concat.txt"
            self._create_concat_list(concat_file, segment_files)
            
            if not self._concatenate_segments(str(concat_file), output_video):
                return False
            
            # Добавляем финальную озвучку если нужно
            if progress_callback:
                progress_callback(ProcessingProgress(
                    current_step=100,
                    total_steps=100,
                    progress_percent=100,
                    message="Complete",
                    stage="complete"
                ))
            
            return Path(output_video).exists()
            
        finally:
            # Очищаем временные файлы
            import shutil
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
    
    def _extract_and_zoom_segment(
        self,
        input_video: str,
        output_video: str,
        step: StepSegment,
        original_width: int,
        original_height: int
    ) -> bool:
        """
        Извлечение сегмента с применением зума.
        
        Ключевой момент: Time-stretching видео под новую длину аудио.
        """
        # Вычисляем параметры зума
        zoom_factor = step.zoom_level if step.zoom_region else 1.0
        
        # Фильтры видео
        video_filters = []
        
        # Применяем зум если нужно
        if step.zoom_region and zoom_factor > 1.0:
            zr = step.zoom_region
            
            # Вычисляем область для зума
            new_width = int(original_width / zoom_factor)
            new_height = int(original_height / zoom_factor)
            
            # Центрируем область
            new_x = max(0, min(zr.center_x - new_width // 2, original_width - new_width))
            new_y = max(0, min(zr.center_y - new_height // 2, original_height - new_height))
            
            # Фильтр zoompan для плавного зума
            # format=yuv420p, scale для совместимости
            zoom_filter = (
                f"zoompan=z='if(lte(zoom,{zoom_factor}),{zoom_factor},"
                f"min(zoom+0.0015,{zoom_factor}))':"
                f"x='iw/2-(iw/zoom/2)+({zr.center_x}-iw/2)*(zoom-{zoom_factor})':"
                f"y='ih/2-(ih/zoom/2)+({zr.center_y}-ih/2)*(zoom-{zoom_factor})':"
                f"d={int(step.duration * 30)}:"  # Длительность в кадрах
                f"s={original_width}x{original_height}:"
                f"fps=30"
            )
            video_filters.append(zoom_filter)
        
        # Добавляем масштабирование если нужно
        if self.default_width != original_width or self.default_height != original_height:
            scale_filter = f"scale={self.default_width}:{self.default_height}"
            video_filters.append(scale_filter)
        
        # Добавляем наложение курсора (опционально)
        # video_filters.append("hwupload")  # Для аппаратного ускорения
        
        vf_string = ",".join(video_filters) if video_filters else "null"
        
        # Вычисляем speed factor для time-stretching
        original_duration = step.original_duration
        new_duration = step.duration
        
        if original_duration > 0:
            speed_factor = original_duration / new_duration
        else:
            speed_factor = 1.0
        
        # Ограничиваем speed_factor для стабильности
        speed_factor = max(0.5, min(2.0, speed_factor))
        
        # Команда FFmpeg
        cmd = [
            self.ffmpeg_path,
            "-ss", str(step.original_start),
            "-t", str(min(step.original_duration, original_duration)),
            "-i", input_video,
        ]
        
        # Добавляем аудио если есть
        if step.audio_path and Path(step.audio_path).exists():
            cmd.extend([
                "-i", step.audio_path,
                "-filter_complex", f"[0:v]{vf_string}[v];[1:a]atempo={speed_factor}[a]",
                "-map", "[v]",
                "-map", "[a]",
            ])
        else:
            # Без аудио или с оригинальной аудио и time-stretching
            if speed_factor != 1.0:
                cmd.extend([
                    "-filter_complex", f"[0:v]{vf_string}[v];[0:a]atempo={speed_factor}[a]",
                    "-map", "[v]",
                    "-map", "[a]",
                ])
            else:
                cmd.extend([
                    "-vf", vf_string,
                ])
        
        cmd.extend([
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-y",
            output_video
        ])
        
        logger.debug(f"FFmpeg command: {' '.join(cmd[:10])}...")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 минут максимум
            )
            
            if result.returncode != 0:
                logger.error(f"FFmpeg error: {result.stderr}")
                return False
            
            return Path(output_video).exists()
            
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout processing segment")
            return False
    
    def _copy_video(self, input_video: str, output_video: str) -> bool:
        """Простое копирование видео без обработки."""
        cmd = [
            self.ffmpeg_path,
            "-i", input_video,
            "-c", "copy",
            "-y",
            output_video
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, timeout=60)
            return Path(output_video).exists()
        except subprocess.TimeoutExpired:
            return False
    
    def _create_concat_list(self, output_file: Path, files: List[str]) -> None:
        """Создание файла списка для конкатенации."""
        with open(output_file, "w") as f:
            for file_path in files:
                f.write(f"file '{file_path}'\n")
    
    def _concatenate_segments(self, concat_file: str, output_video: str) -> bool:
        """Объединение сегментов в одно видео."""
        cmd = [
            self.ffmpeg_path,
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            "-y",
            output_video
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            
            if result.returncode != 0:
                logger.error(f"Concatenation error: {result.stderr}")
                # Попробуем с перекодированием если copy не работает
                return self._reencode_concat(concat_file, output_video)
            
            return Path(output_video).exists()
            
        except subprocess.TimeoutExpired:
            return False
    
    def _reencode_concat(self, concat_file: str, output_video: str) -> bool:
        """Перекодирование при конкатенации (если видео разных форматов)."""
        cmd = [
            self.ffmpeg_path,
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-y",
            output_video
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=300)
            return result.returncode == 0 and Path(output_video).exists()
        except subprocess.TimeoutExpired:
            return False
    
    def generate_shorts(
        self,
        input_video: str,
        output_video: str,
        target_platform: str = "tiktok",
        progress_callback: Optional[callable] = None
    ) -> bool:
        """
        Генерация вертикального видео для Shorts/Reels.
        
        Args:
            input_video: Путь к исходному видео
            output_video: Путь для сохранения результата
            target_platform: Целевая платформа (tiktok, instagram, youtube)
            progress_callback: Callback для прогресса
            
        Returns:
            True если успешно
        """
        # Параметры для разных платформ
        platform_params = {
            "tiktok": {"width": 1080, "height": 1920, "fps": 60},
            "instagram": {"width": 1080, "height": 1920, "fps": 30},
            "youtube": {"width": 1080, "height": 1920, "fps": 60},
        }
        
        params = platform_params.get(target_platform, platform_params["tiktok"])
        
        if progress_callback:
            progress_callback(ProcessingProgress(
                current_step=1,
                total_steps=3,
                progress_percent=10,
                message="Cropping to vertical format",
                stage="rendering"
            ))
        
        # Команда FFmpeg для обрезки и масштабирования
        cmd = [
            self.ffmpeg_path,
            "-i", input_video,
            "-vf", (
                f"scale={params['width']}:{params['height']}:"
                f"force_original_aspect_ratio=decrease,"
                f"crop={params['width']}:{params['height']},"
                f"pad={params['width']}:{params['height']}:"
                f"(ow-iw)/2:(oh-ih)/2"
            ),
            "-r", str(params["fps"]),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-y",
            output_video
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=300)
            
            if result.returncode != 0:
                logger.error(f"Shorts generation error: {result.stderr}")
                return False
            
            if progress_callback:
                progress_callback(ProcessingProgress(
                    current_step=3,
                    total_steps=3,
                    progress_percent=100,
                    message="Complete",
                    stage="complete"
                ))
            
            return Path(output_video).exists()
            
        except subprocess.TimeoutExpired:
            logger.error("Shorts generation timeout")
            return False
    
    def remove_silence(
        self,
        input_video: str,
        output_video: str,
        silence_threshold: float = -30.0,
        min_silence_duration: float = 0.5,
        progress_callback: Optional[callable] = None
    ) -> bool:
        """
        Удаление тишины из видео (для Shorts).
        
        Args:
            input_video: Путь к исходному видео
            output_video: Путь для сохранения результата
            silence_threshold: Порог тишины в dB
            min_silence_duration: Минимальная длительность тишины для удаления
            progress_callback: Callback для прогресса
        """
        if progress_callback:
            progress_callback(ProcessingProgress(
                current_step=1,
                total_steps=2,
                progress_percent=20,
                message="Analyzing audio for silence",
                stage="analysis"
            ))
        
        # Используем silenceremove фильтр
        cmd = [
            self.ffmpeg_path,
            "-i", input_video,
            "-af", (
                f"silenceremove=start_threshold={silence_threshold}:"
                f"stop_threshold={silence_threshold}:"
                f"start_duration={min_silence_duration}:"
                f"stop_duration=0.1"
            ),
            "-c:v", "copy",
            "-c:a", "aac",
            "-y",
            output_video
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=300)
            
            if progress_callback:
                progress_callback(ProcessingProgress(
                    current_step=2,
                    total_steps=2,
                    progress_percent=100,
                    message="Complete",
                    stage="complete"
                ))
            
            return result.returncode == 0 and Path(output_video).exists()
            
        except subprocess.TimeoutExpired:
            return False
    
    def add_music_overlay(
        self,
        input_video: str,
        output_video: str,
        music_path: str,
        volume: float = 0.3,
        fade_in: float = 1.0,
        fade_out: float = 2.0,
        progress_callback: Optional[callable] = None
    ) -> bool:
        """
        Добавление фоновой музыки к видео.
        
        Args:
            input_video: Путь к видео
            output_video: Путь для сохранения
            music_path: Путь к музыкальному файлу
            volume: Громкость музыки (0.0 - 1.0)
            fade_in: Затухание в начале
            fade_out: Затухание в конце
        """
        cmd = [
            self.ffmpeg_path,
            "-i", input_video,
            "-i", music_path,
            "-filter_complex", (
                f"[0:a][1:a]amix=inputs=2:duration=first:"
                f"weights=1 {volume}[a];"
                f"[a]afade=t=in:st=0:d={fade_in},"
                f"afade=t=out:st=ndura:d={fade_out}[aout]"
            ),
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-y",
            output_video
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=300)
            return result.returncode == 0 and Path(output_video).exists()
        except subprocess.TimeoutExpired:
            return False
    
    def add_captions_to_video(
        self,
        input_video: str,
        output_video: str,
        captions: List[Dict[str, Any]],
        font_path: Optional[str] = None,
        font_size: int = 48,
        text_color: str = "white",
        bg_color: str = "black@0.5",
        progress_callback: Optional[callable] = None
    ) -> bool:
        """
        Добавление субтитров/кэпшенов к видео.
        
        Args:
            input_video: Путь к видео
            output_video: Путь для сохранения
            captions: Список субтитров с полями: start, end, text
            font_path: Путь к шрифту
            font_size: Размер шрифта
            text_color: Цвет текста
            bg_color: Цвет фона
        """
        # Создаем файл субтитров
        subtitles_file = Path(settings.TEMP_DIR) / f"subs_{uuid.uuid4().hex[:8]}.srt"
        
        with open(subtitles_file, "w", encoding="utf-8") as f:
            for i, cap in enumerate(captions, 1):
                start = self._format_srt_time(cap["start"])
                end = self._format_srt_time(cap["end"])
                text = cap["text"].replace("\n", " ")
                f.write(f"{i}\n{start} --> {end}\n{text}\n\n")
        
        cmd = [
            self.ffmpeg_path,
            "-i", input_video,
            "-vf", (
                f"subtitles={subtitles_file}:"
                f"force_style='Fontsize={font_size},"
                f"PrimaryColour=&H{text_color},"
                f"BackColour=&H{bg_color}'"
            ),
            "-c:a", "copy",
            "-y",
            output_video
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=300)
            
            # Удаляем временный файл
            subtitles_file.unlink(missing_ok=True)
            
            return result.returncode == 0 and Path(output_video).exists()
        except subprocess.TimeoutExpired:
            return False
    
    def _format_srt_time(self, seconds: float) -> str:
        """Форматирование времени для формата SRT."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    def apply_time_stretch(
        self,
        input_video: str,
        output_video: str,
        target_duration: float,
        progress_callback: Optional[callable] = None
    ) -> bool:
        """
        Применение time-stretching к видео для достижения целевой длительности.
        
        Это критически важный метод для "Магического редактирования".
        
        Args:
            input_video: Путь к исходному видео
            output_video: Путь для сохранения результата
            target_duration: Желаемая длительность в секундах
            progress_callback: Callback для прогресса
        """
        # Получаем информацию о видео
        info = self.get_video_info(input_video)
        original_duration = info["duration"]
        
        if original_duration <= 0:
            return False
        
        # Вычисляем коэффициент скорости
        speed_factor = original_duration / target_duration
        
        # Ограничиваем для стабильности
        # При больших изменениях лучше использовать несколько этапов
        if speed_factor > 2.0:
            # Разбиваем на несколько этапов
            intermediate = Path(settings.TEMP_DIR) / f"stretch_{uuid.uuid4().hex[:8]}.mp4"
            success = self._apply_single_stretch(input_video, str(intermediate), 2.0)
            if not success:
                return False
            success = self.apply_time_stretch(str(intermediate), output_video, target_duration / 2.0)
            intermediate.unlink(missing_ok=True)
            return success
        
        return self._apply_single_stretch(input_video, output_video, speed_factor)
    
    def _apply_single_stretch(
        self,
        input_video: str,
        output_video: str,
        speed_factor: float
    ) -> bool:
        """Применение одного этапа time-stretching."""
        # atempo фильтр работает в диапазоне 0.5 - 2.0
        atempo_values = []
        
        if speed_factor >= 0.5 and speed_factor <= 2.0:
            atempo_values.append(f"atempo={speed_factor}")
        elif speed_factor < 0.5:
            # Каскад atempo для замедления
            current = speed_factor
            while current < 0.5:
                atempo_values.append("atempo=0.5")
                current /= 0.5
        else:
            # Каскад atempo для ускорения
            current = speed_factor
            while current > 2.0:
                atempo_values.append("atempo=2.0")
                current /= 2.0
            if current > 0.5:
                atempo_values.append(f"atempo={current}")
        
        filter_complex = ",".join(atempo_values)
        
        cmd = [
            self.ffmpeg_path,
            "-i", input_video,
            "-filter_complex", filter_complex,
            "-c:v", "copy",  # Копируем видео без перекодирования
            "-c:a", "aac",
            "-b:a", "192k",
            "-y",
            output_video
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=300)
            return result.returncode == 0 and Path(output_video).exists()
        except subprocess.TimeoutExpired:
            return False


# Экземпляр процессора для использования в приложении
video_processor = VideoProcessor()
