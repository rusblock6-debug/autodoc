"""
Синхронная версия Shorts Generator для Celery worker.
Работает без asyncio - только subprocess.run().
"""

import logging
import subprocess
import json
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
    output_path: str = ""


@dataclass
class ShortsResult:
    """Результат генерации Shorts."""
    success: bool
    output_path: Optional[str]
    duration_seconds: float
    error: Optional[str] = None
    segments_count: int = 0


class ShortsGeneratorSync:
    """
    Синхронный генератор Shorts для Celery worker.
    Использует только subprocess.run() без asyncio.
    """
    
    def __init__(
        self,
        output_dir: str = "/tmp/autodoc_worker_temp",
        width: int = 1080,
        height: int = 1920,
        fps: int = 30
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.width = width
        self.height = height
        self.fps = fps
    
    def generate_from_steps(
        self,
        steps: List[Dict[str, Any]],
        guide_uuid: str,
        tts_engine: str = "edge"
    ) -> ShortsResult:
        """
        Генерация Shorts из шагов (синхронно).
        
        Args:
            steps: Список шагов с полями:
                - step_number: int
                - screenshot_path: str (полный путь)
                - click_x, click_y: int
                - normalized_text, edited_text: str
            guide_uuid: UUID гайда
            tts_engine: "edge" или "chatterbox"
            
        Returns:
            ShortsResult
        """
        logger.info(f"[SYNC] Generating Shorts for {guide_uuid} with {len(steps)} steps using {tts_engine}")
        
        segments = []
        temp_files = []
        
        # Выбираем TTS сервис
        if tts_engine == "chatterbox":
            logger.info("[SYNC] Trying to use Chatterbox TTS")
            try:
                from app.services.chatterbox_service import ChatterboxService
                tts_service = ChatterboxService()
                logger.info("[SYNC] Chatterbox TTS loaded successfully")
            except ImportError as e:
                logger.warning(f"[SYNC] Chatterbox not available: {e}, falling back to Edge TTS")
                from app.services.edge_tts_service import EdgeTTSService
                tts_service = EdgeTTSService()
        else:
            from app.services.edge_tts_service import EdgeTTSService
            tts_service = EdgeTTSService()
            logger.info("[SYNC] Using Edge TTS")
        
        try:
            # 1. Генерируем TTS для всех шагов
            for i, step in enumerate(steps):
                text = step.get("edited_text") or step.get("normalized_text", "")
                if not text:
                    text = f"Шаг {step.get('step_number', i+1)}"
                
                full_text = f"Шаг {step.get('step_number', i+1)}. {text}"
                
                logger.info(f"[SYNC] Step {i+1}/{len(steps)}: {full_text[:50]}...")
                
                # Генерируем TTS (синхронно)
                tts_audio_path = tts_service.synthesize_sync(text=full_text)
                
                if not tts_audio_path or not Path(tts_audio_path).exists():
                    logger.error(f"[SYNC] TTS failed for step {i+1}")
                    continue
                
                temp_files.append(tts_audio_path)
                
                # Получаем длительность
                duration = tts_service.get_audio_duration(tts_audio_path) or 3.0
                
                segment = ShortsSegment(
                    step_number=step.get('step_number', i+1),
                    screenshot_path=step.get('screenshot_path', ''),
                    marker_x=step.get('click_x', 0),
                    marker_y=step.get('click_y', 0),
                    text=text,
                    tts_audio_path=tts_audio_path,
                    duration_seconds=max(duration, 2.0)
                )
                
                segments.append(segment)
            
            if not segments:
                return ShortsResult(
                    success=False,
                    output_path=None,
                    duration_seconds=0,
                    error="No segments created"
                )
            
            # 2. Создаём видео-сегменты
            segment_videos = []
            
            for i, segment in enumerate(segments):
                logger.info(f"[SYNC] Creating segment video {i+1}/{len(segments)}...")
                
                segment_video = self._create_segment_video(
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
                    error="No video segments created"
                )
            
            # 3. Склеиваем сегменты
            output_path = Path("/data/output") / f"shorts_{guide_uuid}.mp4"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            concat_list = self.output_dir / f"concat_{guide_uuid}.txt"
            
            with open(concat_list, "w") as f:
                for video_path in segment_videos:
                    f.write(f"file '{video_path}'\n")
            
            logger.info(f"[SYNC] Concatenating {len(segment_videos)} segments...")
            
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
                
                logger.info(f"[SYNC] SUCCESS! Shorts: {output_path} ({duration}s)")
                
                return ShortsResult(
                    success=True,
                    output_path=str(output_path),
                    duration_seconds=duration or 0,
                    segments_count=len(segments)
                )
            else:
                error = result.stderr or "Concat failed"
                logger.error(f"[SYNC] Concatenation failed: {error}")
                return ShortsResult(
                    success=False,
                    output_path=None,
                    duration_seconds=0,
                    error=error[:300]
                )
        
        except Exception as e:
            logger.exception(f"[SYNC] Generation failed: {e}")
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
    
    def _create_segment_video(
        self,
        segment: ShortsSegment,
        guide_uuid: str,
        segment_index: int
    ) -> Optional[str]:
        """Создать видео-сегмент из скриншота (синхронно)."""
        output_path = self.output_dir / f"segment_{guide_uuid}_{segment_index:03d}.mp4"
        
        screenshot_path = Path(segment.screenshot_path)
        
        if not screenshot_path.exists():
            logger.error(f"[SYNC] Screenshot not found: {screenshot_path}")
            return None
        
        # Проверяем аудио
        if not segment.tts_audio_path or not Path(segment.tts_audio_path).exists():
            logger.error(f"[SYNC] Audio not found: {segment.tts_audio_path}")
            return None
        
        # Ограничиваем координаты
        marker_x = max(0, min(segment.marker_x, self.width - 1))
        marker_y = max(0, min(segment.marker_y, self.height - 1))
        
        cmd = [
            "ffmpeg",
            "-y",
            "-loop", "1",
            "-t", str(segment.duration_seconds),
            "-i", str(screenshot_path),
            "-i", segment.tts_audio_path,
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
            "-pix_fmt", "yuv420p",
            "-r", str(self.fps),
            "-shortest",
            str(output_path)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0 and output_path.exists():
                logger.info(f"[SYNC] Segment created: {output_path}")
                return str(output_path)
            else:
                logger.error(f"[SYNC] FFmpeg failed: {result.stderr[:200]}")
                return None
                
        except Exception as e:
            logger.error(f"[SYNC] Segment creation error: {e}")
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



def generate_shorts_sync(guide_uuid: str, tts_engine: str = "edge") -> Dict[str, Any]:
    """
    Главная функция для генерации shorts (вызывается из Celery task).
    
    Args:
        guide_uuid: UUID гайда
        tts_engine: "edge" или "chatterbox"
    
    Returns:
        Dict с результатом
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker, selectinload
    from app.config import settings
    from app.models import Guide, GuideStatus
    from datetime import datetime
    
    # Создаём синхронное подключение к БД
    engine = create_engine(settings.sync_database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Получаем гайд
        guide = session.query(Guide).filter(Guide.uuid == guide_uuid).first()
        
        if not guide:
            return {
                "success": False,
                "error": f"Guide not found: {guide_uuid}"
            }
        
        # Получаем шаги
        steps = sorted(guide.steps, key=lambda s: s.step_number)
        
        if not steps:
            return {
                "success": False,
                "error": "No steps in guide"
            }
        
        # Подготавливаем данные шагов
        steps_data = []
        for step in steps:
            # Формируем правильный путь к скриншоту
            if step.screenshot_path:
                # Если путь начинается с /, добавляем /data
                # Если нет, добавляем /data/
                screenshot_path = f"/data/{step.screenshot_path.lstrip('/')}"
            else:
                screenshot_path = ""
            
            steps_data.append({
                "step_number": step.step_number,
                "screenshot_path": screenshot_path,
                "click_x": step.click_x or 540,
                "click_y": step.click_y or 960,
                "normalized_text": step.normalized_text or "",
                "edited_text": step.edited_text or ""
            })
        
        # Генерируем Shorts
        generator = ShortsGeneratorSync()
        result = generator.generate_from_steps(
            steps=steps_data,
            guide_uuid=guide_uuid,
            tts_engine=tts_engine
        )
        
        # Обновляем гайд
        if result.success:
            guide.status = GuideStatus.COMPLETED
            guide.shorts_video_path = result.output_path.replace("/data/", "") if result.output_path else None
            guide.shorts_duration_seconds = result.duration_seconds
            guide.shorts_generated_at = datetime.utcnow()
            guide.error_message = None
        else:
            guide.status = GuideStatus.FAILED
            guide.error_message = result.error
        
        guide.updated_at = datetime.utcnow()
        session.commit()
        
        return {
            "success": result.success,
            "output_path": result.output_path,
            "duration_seconds": result.duration_seconds,
            "segments_count": result.segments_count,
            "error": result.error
        }
        
    except Exception as e:
        logger.exception(f"[SYNC] generate_shorts_sync failed: {e}")
        
        # Обновляем статус на failed
        try:
            guide = session.query(Guide).filter(Guide.uuid == guide_uuid).first()
            if guide:
                guide.status = GuideStatus.FAILED
                guide.error_message = str(e)
                guide.updated_at = datetime.utcnow()
                session.commit()
        except Exception:
            pass
        
        return {
            "success": False,
            "error": str(e)
        }
    
    finally:
        session.close()
