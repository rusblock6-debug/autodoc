"""
Shorts Generator - сборка вертикального видео из шагов.
Итоговый Shorts: скриншот + маркер + TTS озвучка + заголовок "Шаг N".
"""

import logging
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from app.config import settings
from app.services.chatterbox_service import ChatterboxService

logger = logging.getLogger(__name__)


@dataclass
class ShortsSegment:
    """Один сегмент Shorts (один шаг)."""
    step_number: int
    screenshot_path: str
    marker_x: int
    marker_y: int
    text: str
    tts_audio_path: str
    duration_seconds: float
    output_path: str = ""


@dataclass
class ShortsResult:
    """Результат генерации Shorts."""
    success: bool
    output_path: Optional[str]
    duration_seconds: float
    error: Optional[str] = None
    segments_count: int = 0


class ShortsGenerator:
    """
    Генератор Shorts из шагов гайда.
    
    Поток:
    1. Для каждого шага: скриншот + маркер + TTS
    2. Склейка в вертикальное видео 1080x1920
    3. Добавление заголовков "Шаг N"
    """
    
    def __init__(
        self,
        output_dir: str = None,
        width: int = 1080,
        height: int = 1920,
        fps: int = 30
    ):
        """
        Инициализация.
        
        Args:
            output_dir: Директория для сохранения результата
            width: Ширина видео (1080 для Shorts)
            height: Высота видео (1920 для Shorts)
            fps: Кадров в секунду
        """
        self.output_dir = Path(output_dir or settings.WORKER_TEMP_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)  # Создаём директорию если не существует
        self.width = width
        self.height = height
        self.fps = fps
    
    async def generate_from_steps(
        self,
        steps: List[Dict[str, Any]],
        guide_uuid: str,
        intro_text: Optional[str] = None
    ) -> ShortsResult:
        """
        Основной метод: генерация Shorts из шагов.
        
        Args:
            steps: Список шагов (из БД)
            guide_uuid: UUID гайда для именования файлов
            intro_text: Текст интро (опционально)
            
        Returns:
            ShortsResult с путём к видео
        """
        logger.info(f"Generating Shorts for guide {guide_uuid} with {len(steps)} steps")
        
        segments = []
        temp_files = []  # Для очистки
        
        # Инициализируем Edge TTS сервис (быстрый, онлайн)
        from app.services.edge_tts_service import get_edge_tts_service
        tts_service = get_edge_tts_service()
        
        try:
            # 1. Генерируем TTS и подготавливаем сегменты
            for i, step in enumerate(steps):
                text = step.get("edited_text") or step.get("normalized_text", "")
                if not text:
                    text = f"Шаг {step.get('step_number', i+1)}"
                
                # Формируем полный текст для озвучки
                full_text = f"Шаг {step.get('step_number', i+1)}. {text}"
                
                logger.info(f"Processing step {i+1}/{len(steps)}: {full_text[:50]}...")
                logger.info(f"Screenshot path: {step.get('screenshot_path', '')}")
                
                # Генерируем TTS через Edge TTS (асинхронный вызов)
                tts_audio_path = await tts_service.synthesize(text=full_text)
                temp_files.append(tts_audio_path)
                
                # Получаем длительность аудио
                duration = tts_service.get_audio_duration(tts_audio_path) or 3.0
                
                segment = ShortsSegment(
                    step_number=step.get('step_number', i+1),
                    screenshot_path=step.get('screenshot_path', ''),
                    marker_x=step.get('click_x', 0),
                    marker_y=step.get('click_y', 0),
                    text=text,
                    tts_audio_path=tts_audio_path,
                    duration_seconds=max(duration, 2.0)  # Минимум 2 секунды
                )
                
                segments.append(segment)
            
            # 2. Создаём промежуточные видео для каждого сегмента
            segment_videos = []
            
            for i, segment in enumerate(segments):
                if not segment.screenshot_path:
                    logger.warning(f"Missing screenshot for step {i+1}")
                    continue
                
                logger.info(f"Creating segment video {i+1}/{len(segments)}...")
                # Создаём видео из скриншота с маркером и заголовком
                segment_video = await self._create_segment_video(
                    segment=segment,
                    guide_uuid=guide_uuid,
                    segment_index=i
                )
                
                if segment_video:
                    segment_videos.append(segment_video)
                    temp_files.append(segment_video)
                else:
                    logger.error(f"Failed to create segment {i+1}")
            
            if not segment_videos:
                logger.error("No valid segments created")
                return ShortsResult(
                    success=False,
                    output_path=None,
                    duration_seconds=0,
                    error="No valid segments created"
                )
            
            # 3. Склеиваем все сегменты
            output_path = self.output_dir / f"shorts_{guide_uuid}.mp4"
            concat_list = self.output_dir / f"concat_{guide_uuid}.txt"
            
            logger.info(f"Concatenating {len(segment_videos)} segments...")
            
            with open(concat_list, "w") as f:
                for video_path in segment_videos:
                    f.write(f"file '{video_path}'\n")
            
            # FFmpeg concat
            cmd = [
                "ffmpeg",
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_list),
                "-c", "copy",
                "-movflags", "+faststart",
                str(output_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0 and output_path.exists():
                duration = self._get_duration(str(output_path))
                
                logger.info(f"Shorts generated successfully: {output_path} ({duration}s)")
                
                return ShortsResult(
                    success=True,
                    output_path=str(output_path),
                    duration_seconds=duration or 0,
                    segments_count=len(segments)
                )
            else:
                error = result.stderr or "Unknown concat error"
                logger.error(f"Concatenation failed: {error}")
                return ShortsResult(
                    success=False,
                    output_path=None,
                    duration_seconds=0,
                    error=error[:300]
                )
        
        except Exception as e:
            logger.exception(f"Shorts generation failed: {e}")
            return ShortsResult(
                success=False,
                output_path=None,
                duration_seconds=0,
                error=str(e)
            )
        
        finally:
            # Очистка временных файлов
            for f in temp_files:
                try:
                    if f and Path(f).exists():
                        Path(f).unlink()
                except Exception:
                    pass
    
    async def _create_segment_video(
        self,
        segment: ShortsSegment,
        guide_uuid: str,
        segment_index: int
    ) -> Optional[str]:
        """
        Создать видео-сегмент из скриншота.
        
        Фильтры:
        1. Масштабирование до 1080x1920 (letterbox если нужно)
        2. Наложение маркера (жёлтый круг)
        3. Добавление текста "Шаг N"
        """
        # Путь к выходному файлу
        output_path = self.output_dir / f"segment_{guide_uuid}_{segment_index:03d}.mp4"
        
        # Проверяем существует ли файл скриншота
        screenshot_path = Path(segment.screenshot_path)
        
        logger.info(f"Original screenshot path: {segment.screenshot_path}")
        logger.info(f"Current working directory: {Path.cwd()}")
        
        # Если путь относительный (начинается с "screenshots/"), добавляем базовый путь /data
        if not screenshot_path.is_absolute():
            # Основной путь - /data/screenshots/...
            absolute_path = Path("/data") / screenshot_path
            
            logger.info(f"Checking absolute path: {absolute_path}")
            
            if absolute_path.exists():
                logger.info(f"Found screenshot at: {absolute_path}")
                screenshot_path = absolute_path
            else:
                # Пробуем альтернативные варианты
                possible_bases = [
                    Path("./data"),
                    Path.cwd() / "data",
                ]
                
                for base in possible_bases:
                    full_path = base / screenshot_path
                    logger.info(f"Checking alternative path: {full_path}")
                    if full_path.exists():
                        logger.info(f"Found screenshot at: {full_path}")
                        screenshot_path = full_path
                        break
                else:
                    # Если ни один путь не подошел
                    logger.error(f"Screenshot not found: {segment.screenshot_path}")
                    return None
        
        # Конвертируем hex color в FFmpeg формат
        marker_color = "gold"
        
        # Проверяем наличие скриншота
        if not screenshot_path.exists():
            logger.error(f"Screenshot file not found: {screenshot_path}")
            return None
        
        # Проверяем наличие аудио
        audio_input = []
        audio_filter = []
        
        if segment.tts_audio_path and Path(segment.tts_audio_path).exists():
            audio_input = ["-i", segment.tts_audio_path]
            audio_filter = ["-shortest"]
        
        # Ограничиваем координаты маркера допустимыми значениями
        # FFmpeg требует неотрицательные координаты
        marker_x = max(0, min(segment.marker_x, self.width - 1))
        marker_y = max(0, min(segment.marker_y, self.height - 1))
        
        logger.info(f"Marker coordinates: x={marker_x}, y={marker_y} (original: {segment.marker_x}, {segment.marker_y})")
        
        # Формируем команду
        cmd = [
            "ffmpeg",
            "-y",
            "-loop", "1",
            "-i", str(screenshot_path),
            *audio_input,
            "-vf", (
                f"scale={self.width}:{self.height}:"
                f"force_original_aspect_ratio=decrease,"
                f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2,"
                f"drawbox=x={marker_x-25}:y={marker_y-25}:"
                f"w=50:h=50:color=yellow:t=5,"
                f"drawbox=x={marker_x-5}:y={marker_y-5}:"
                f"w=10:h=10:color=yellow:t=-1,"
                f"drawtext=text='Шаг {segment.step_number}':"
                f"fontcolor=white:fontsize=48:x=(w-text_w)/2:y=50:"
                f"bordercolor=black:borderw=3"
            ),
            "-c:v", "libx264",
            "-t", str(segment.duration_seconds),
            "-pix_fmt", "yuv420p",
            "-r", str(self.fps),
            *audio_filter,
            str(output_path)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0 and output_path.exists():
                return str(output_path)
            else:
                logger.error(f"FFmpeg command failed with return code {result.returncode}")
                logger.error(f"FFmpeg stderr: {result.stderr}")
                logger.error(f"FFmpeg stdout: {result.stdout}")
                return None
                
        except Exception as e:
            logger.error(f"Segment creation error: {e}")
            return None
    
    def _get_duration(self, video_path: str) -> float:
        """Получить длительность видео через ffprobe."""
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                return float(result.stdout.strip())
                
        except Exception:
            pass
        
        return 0.0
    
    async def add_intro(
        self,
        video_path: str,
        intro_text: str,
        intro_duration: float = 3.0,
        output_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Добавить интро к готовому Shorts.
        
        Args:
            video_path: Путь к готовому видео
            intro_text: Текст интро
            intro_duration: Длительность интро
            output_path: Путь к результату (автоматически если не указан)
            
        Returns:
            Путь к видео с интро или None
        """
        if output_path is None:
            output_path = str(Path(video_path).with_suffix(".intro.mp4"))
        
        # Генерируем интро-видео с текстом
        intro_video = self.output_dir / "intro_temp.mp4"
        
        # Создаём чёрный фон с текстом
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "lavfi",
            "-i", f"color=c=black:s={self.width}x{self.height}:d={intro_duration}",
            "-vf", (
                f"drawtext=text='{intro_text}':"
                f"fontcolor=white:fontsize=64:x=(w-text_w)/2:y=(h-text_h)/2:"
                f"bordercolor=black:borderw=3"
            ),
            "-c:v", "libx264",
            "-t", str(intro_duration),
            "-pix_fmt", "yuv420p",
            str(intro_video)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            logger.warning(f"Intro creation failed: {result.stderr}")
            return None
        
        # Склеиваем интро + основное видео
        final_output = output_path or str(Path(video_path).with_suffix(".final.mp4"))
        
        concat_cmd = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", f"file='{intro_video}'\nfile='{video_path}'",
            "-c", "copy",
            "-movflags", "+faststart",
            final_output
        ]
        
        final_result = subprocess.run(concat_cmd, capture_output=True, text=True, timeout=300)
        
        # Удаляем временный интро
        try:
            intro_video.unlink()
        except Exception:
            pass
        
        if final_result.returncode == 0:
            return final_output
        
        return None


# Экземпляр для использования
shorts_generator = ShortsGenerator()
