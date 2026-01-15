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
from app.services.tts_service import tts_service

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
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.width = width
        self.height = height
        self.fps = fps
    
    async def generate_from_steps(
        self,
        steps: List[Dict[str, Any]],
        guide_uuid: str,
        tts_voice: str = "ru-RU-SvetlanaNeural",
        intro_text: Optional[str] = None
    ) -> ShortsResult:
        """
        Основной метод: генерация Shorts из шагов.
        
        Args:
            steps: Список шагов (из БД)
            guide_uuid: UUID гайда для именования файлов
            tts_voice: Голос для озвучки
            intro_text: Текст интро (опционально)
            
        Returns:
            ShortsResult с путём к видео
        """
        logger.info(f"Generating Shorts for guide {guide_uuid} with {len(steps)} steps")
        
        segments = []
        temp_files = []  # Для очистки
        
        try:
            # 1. Генерируем TTS и подготавливаем сегменты
            for i, step in enumerate(steps):
                text = step.get("edited_text") or step.get("normalized_text", "")
                if not text:
                    text = f"Шаг {step.get('step_number', i+1)}"
                
                # Формируем полный текст для озвучки
                full_text = f"Шаг {step.get('step_number', i+1)}. {text}"
                
                # Генерируем TTS
                tts_result = await tts_service.generate_audio(
                    text=full_text,
                    voice=tts_voice
                )
                
                if not tts_result.success:
                    logger.warning(f"TTS failed for step {i+1}: {tts_result.error}")
                    # Используем тишину или дефолтный звук
                    tts_audio_path = ""
                    duration = 3.0  # Минимум 3 секунды на шаг
                else:
                    tts_audio_path = tts_result.audio_path
                    duration = tts_result.duration_seconds or 3.0
                    temp_files.append(tts_audio_path)
                
                segment = ShortsSegment(
                    step_number=step.get("step_number", i+1),
                    screenshot_path=step.get("screenshot_path", ""),
                    marker_x=step.get("click_x", 0),
                    marker_y=step.get("click_y", 0),
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
                
                # Создаём видео из скриншота с маркером и заголовком
                segment_video = await self._create_segment_video(
                    segment=segment,
                    guide_uuid=guide_uuid,
                    segment_index=i
                )
                
                if segment_video:
                    segment_videos.append(segment_video)
                    temp_files.append(segment_video)
            
            if not segment_videos:
                return ShortsResult(
                    success=False,
                    output_path=None,
                    duration_seconds=0,
                    error="No valid segments created"
                )
            
            # 3. Склеиваем все сегменты
            output_path = self.output_dir / f"shorts_{guide_uuid}.mp4"
            concat_list = self.output_dir / f"concat_{guide_uuid}.txt"
            
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
                
                logger.info(f"Shorts generated: {output_path} ({duration}s)")
                
                return ShortsResult(
                    success=True,
                    output_path=str(output_path),
                    duration_seconds=duration or 0,
                    segments_count=len(segments)
                )
            else:
                error = result.stderr or "Unknown concat error"
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
        
        # Конвертируем hex color в FFmpeg формат
        marker_color = "gold"  # FFmpeg понимает 'gold', 'red', 'blue', etc.
        
        # FFmpeg фильтры
        # 1. Сначала масштабируем скриншот с соотношением сторон
        # 2. Добавляем padding для достижения 1080x1920
        # 3. Рисуем маркер
        # 4. Добавляем текст "Шаг N"
        
        # Проверяем наличие аудио
        audio_input = []
        audio_filter = []
        
        if segment.tts_audio_path and Path(segment.tts_audio_path).exists():
            audio_input = ["-i", segment.tts_audio_path]
            audio_filter = ["-shortest"]
        
        # Формируем команду
        cmd = [
            "ffmpeg",
            "-y",
            "-loop", "1",
            "-i", segment.screenshot_path,
            *audio_input,
            "-vf", (
                f"scale={self.width}:{self.height}:"
                f"force_original_aspect_ratio=decrease,"
                f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2,"
                f"drawbox=x={segment.marker_x-25}:y={segment.marker_y-25}:"
                f"w=50:h=50:color=yellow:t=5:round=25,"
                f"drawbox=x={segment.marker_x-5}:y={segment.marker_y-5}:"
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
                logger.warning(f"Segment creation failed: {result.stderr[:200]}")
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
