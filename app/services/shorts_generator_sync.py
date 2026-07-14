"""
Синхронная версия Shorts Generator для Celery worker.
Работает без asyncio - только subprocess.run().
"""

import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

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
    annotations: List[Dict[str, Any]] = None
    output_path: str = ""
    # CSS-размеры вьюпорта — для пересчёта координат маркера/аннотаций в пиксели
    # картинки (скриншот в физических пикселях, координаты — в CSS).
    viewport_width: Optional[int] = None
    viewport_height: Optional[int] = None
    
    def __post_init__(self):
        """Инициализация аннотаций."""
        if self.annotations is None:
            self.annotations = []


class ShortsGeneratorSync:
    """
    Синхронный генератор Shorts для Celery worker.
    Использует только subprocess.run() без asyncio.
    """
    
    def __init__(
        self,
        output_dir: str = "/tmp/autodoc_worker_temp",
        width: Optional[int] = None,
        height: Optional[int] = None,
        fps: int = 30
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.width = width  # Может быть None - определим из первого скриншота
        self.height = height
        self.fps = fps
    
    def _get_image_size(self, image_path: str) -> tuple[int, int]:
        """Получить размер изображения (округляет до четных чисел для H.264)."""
        try:
            from PIL import Image
            with Image.open(image_path) as img:
                # H.264 требует четные размеры - округляем вверх
                width = img.width + (img.width % 2)
                height = img.height + (img.height % 2)
                return width, height
        except Exception as e:
            logger.error(f"Failed to get image size: {e}")
            return 1920, 1080  # Fallback
    
    def _create_segment_video(
        self,
        segment: ShortsSegment,
        guide_uuid: str,
        segment_index: int
    ) -> Optional[str]:
        """Создать видео-сегмент из скриншота (синхронно)."""
        from app.services.screenshot_processor import process_screenshot_with_annotations, cleanup_processed_screenshot
        
        output_path = self.output_dir / f"segment_{guide_uuid}_{segment_index:03d}.mp4"
        
        screenshot_path = Path(segment.screenshot_path)
        
        if not screenshot_path.exists():
            logger.error(f"[SYNC] Screenshot not found: {screenshot_path}")
            return None
        
        # Проверяем аудио
        if not segment.tts_audio_path or not Path(segment.tts_audio_path).exists():
            logger.error(f"[SYNC] Audio not found: {segment.tts_audio_path}")
            return None
        
        # Ограничиваем координаты маркера
        marker_x = max(0, min(segment.marker_x, self.width - 1))
        marker_y = max(0, min(segment.marker_y, self.height - 1))
        
        logger.info(f"[SYNC] Segment {segment_index}: annotations count = {len(segment.annotations) if segment.annotations else 0}")
        
        # Обрабатываем скриншот с аннотациями и маркером
        processed_screenshot = None
        if segment.annotations and len(segment.annotations) > 0:
            # Создаем обработанную версию с overlay, аннотациями и маркером
            processed_screenshot = process_screenshot_with_annotations(
                screenshot_path=str(screenshot_path),
                annotations=segment.annotations,
                marker_x=marker_x,
                marker_y=marker_y,
                viewport_width=segment.viewport_width,
                viewport_height=segment.viewport_height,
            )
            
            if processed_screenshot:
                logger.info(f"[SYNC] Using processed screenshot with {len(segment.annotations)} annotations and marker")
            else:
                logger.warning(f"[SYNC] Failed to process screenshot, using original")
                processed_screenshot = str(screenshot_path)
        else:
            # Нет аннотаций, но рисуем маркер
            processed_screenshot = process_screenshot_with_annotations(
                screenshot_path=str(screenshot_path),
                annotations=[],
                marker_x=marker_x,
                marker_y=marker_y,
                viewport_width=segment.viewport_width,
                viewport_height=segment.viewport_height,
            )
            
            if not processed_screenshot:
                processed_screenshot = str(screenshot_path)
        
        # Паузы вокруг озвучки: без них шаги в склейке звучат встык,
        # одной сплошной фразой. Тишина до/после + сегмент длиннее аудио.
        pad_before = 0.4  # сек тишины перед голосом шага
        pad_after = 0.7   # сек тишины после (пауза между шагами)
        total_duration = segment.duration_seconds + pad_before + pad_after

        # Генерируем видео из обработанного скриншота
        cmd = [
            "ffmpeg",
            "-y",
            "-loop", "1",
            "-t", f"{total_duration:.3f}",
            "-i", processed_screenshot,
            "-i", segment.tts_audio_path,
            "-vf", f"scale={self.width}:{self.height}",
            "-af", f"adelay={int(pad_before * 1000)}:all=1,apad=pad_dur={pad_after}",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-r", str(self.fps),
            str(output_path)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            # Удаляем обработанный скриншот если он был создан
            if processed_screenshot != str(screenshot_path):
                cleanup_processed_screenshot(processed_screenshot)
            
            if result.returncode == 0 and output_path.exists():
                logger.info(f"[SYNC] Segment created: {output_path}")
                return str(output_path)
            else:
                logger.error(f"[SYNC] FFmpeg failed with code {result.returncode}")
                logger.error(f"[SYNC] FFmpeg stderr: {result.stderr}")
                logger.error(f"[SYNC] FFmpeg stdout: {result.stdout}")
                return None
                
        except Exception as e:
            logger.error(f"[SYNC] Segment creation error: {e}")
            # Удаляем обработанный скриншот в случае ошибки
            if processed_screenshot and processed_screenshot != str(screenshot_path):
                cleanup_processed_screenshot(processed_screenshot)
            return None
    
    def _get_duration(self, video_path: str) -> float:
        """Получить длительность видео."""
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



def generate_video_from_steps(
    steps: List[Dict[str, Any]],
    guide_uuid: str,
    progress_callback=None
) -> Dict[str, Any]:
    """
    Генерация видео из шагов с прогрессом (для Celery task).
    
    Args:
        steps: Список шагов с полями:
            - step_number: int
            - audio_path: str (путь к TTS аудио)
            - screenshot_path: str (полный путь)
            - click_x, click_y: int
        guide_uuid: UUID гайда
        progress_callback: Функция для обновления прогресса (progress, message)
    
    Returns:
        Dict с результатом
    """
    logger.info(f"[VIDEO] Generating video for {guide_uuid} with {len(steps)} steps")
    
    generator = ShortsGeneratorSync()
    temp_files = []
    segment_videos = []
    
    # Определяем размер из первого скриншота
    if steps and steps[0].get('screenshot_path'):
        first_screenshot = steps[0]['screenshot_path']
        generator.width, generator.height = generator._get_image_size(first_screenshot)
        logger.info(f"[VIDEO] Detected video size: {generator.width}x{generator.height}")
    
    try:
        # 1. Создаём видео-сегменты
        for i, step in enumerate(steps):
            if progress_callback:
                progress = int((i / len(steps)) * 100)
                progress_callback(progress, f'Обработка шага {i+1}/{len(steps)}')
            
            logger.info(f"[VIDEO] Creating segment {i+1}/{len(steps)}...")
            
            segment = ShortsSegment(
                step_number=step.get('step_number', i+1),
                screenshot_path=step.get('screenshot_path', ''),
                marker_x=step.get('click_x', 0),
                marker_y=step.get('click_y', 0),
                text='',  # Текст уже в аудио
                tts_audio_path=step.get('audio_path', ''),
                duration_seconds=generator._get_duration(step.get('audio_path', '')) or 3.0,
                annotations=step.get('annotations', []),
                viewport_width=step.get('screenshot_width'),
                viewport_height=step.get('screenshot_height'),
            )
            
            segment_video = generator._create_segment_video(
                segment=segment,
                guide_uuid=guide_uuid,
                segment_index=i
            )
            
            if segment_video:
                segment_videos.append(segment_video)
                temp_files.append(segment_video)
        
        if not segment_videos:
            return {
                "success": False,
                "error": "No video segments created"
            }
        
        if progress_callback:
            progress_callback(80, 'Склеивание видео...')
        
        # 2. Склеиваем сегменты
        output_path = Path("/data/output") / f"video_{guide_uuid}.mp4"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        concat_list = generator.output_dir / f"concat_{guide_uuid}.txt"
        
        with open(concat_list, "w") as f:
            for video_path in segment_videos:
                f.write(f"file '{video_path}'\n")
        
        logger.info(f"[VIDEO] Concatenating {len(segment_videos)} segments...")
        
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
            duration = generator._get_duration(str(output_path))
            
            if progress_callback:
                progress_callback(100, 'Готово!')
            
            logger.info(f"[VIDEO] SUCCESS! Video: {output_path} ({duration}s)")
            
            return {
                "success": True,
                "output_path": str(output_path),
                "duration_seconds": duration or 0,
                "segments_count": len(segment_videos)
            }
        else:
            error = result.stderr or "Concat failed"
            logger.error(f"[VIDEO] Concatenation failed: {error}")
            return {
                "success": False,
                "error": error[:300]
            }
    
    except Exception as e:
        logger.exception(f"[VIDEO] Generation failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }
    
    finally:
        # Очистка временных файлов
        for f in temp_files:
            try:
                if f and Path(f).exists():
                    Path(f).unlink()
            except Exception:
                pass
