"""
Step Detector - сервис выделения шагов из записи.
Логика: шаг = клик + ближайший фрагмент речи до клика.
"""

import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ClickEvent:
    """Событие клика из лога расширения."""
    timestamp: float  # Таймкод клика в секундах
    x: int            # Координата X
    y: int            # Координата Y
    element: Optional[str] = None  # Тип элемента (button, input, etc.)


@dataclass
class SpeechSegment:
    """Сегмент речи из ASR."""
    start: float      # Начало в секундах
    end: float        # Конец в секундах
    text: str         # Текст сегмента


@dataclass
class StepCandidate:
    """Кандидат в шаг."""
    click: ClickEvent
    speech: Optional[SpeechSegment]  # Ближайшая речь до клика
    raw_speech_text: str             # Текст для LLM нормализации


class StepDetector:
    """
    Детектор шагов на основе кликов и речи.
    
    Алгоритм:
    1. Для каждого клика находим ближайший сегмент речи ДО клика
    2. Если речь найдена, берём её как "сырой" текст шага
    3. Если речи нет, создаём placeholder
    """
    
    # Сколько секунд речи брать до клика (максимум)
    MAX_SPEECH_SECONDS = 5.0
    
    # Минимальная длительность речи для использования
    MIN_SPEECH_DURATION = 1.0
    
    def detect_steps(
        self,
        clicks: List[ClickEvent],
        speech_segments: List[SpeechSegment]
    ) -> List[StepCandidate]:
        """
        Основной метод: обнаружение шагов.
        
        Args:
            clicks: Список кликов
            speech_segments: Список сегментов речи
            
        Returns:
            Список кандидатов в шаги
        """
        logger.info(f"Detecting steps from {len(clicks)} clicks and {len(speech_segments)} speech segments")
        
        steps = []
        
        for i, click in enumerate(clicks):
            # Находим ближайшую речь до клика
            nearest_speech = self._find_nearest_speech_before(click.timestamp, speech_segments)
            
            # Формируем raw text для LLM
            raw_text = self._extract_raw_text(nearest_speech)
            
            step = StepCandidate(
                click=click,
                speech=nearest_speech,
                raw_speech_text=raw_text
            )
            
            steps.append(step)
            
            logger.debug(f"Step {i+1}: click @ {click.timestamp:.2f}s, speech: '{raw_text[:50]}...'")
        
        logger.info(f"Detected {len(steps)} step candidates")
        return steps
    
    def _find_nearest_speech_before(
        self,
        click_timestamp: float,
        speech_segments: List[SpeechSegment]
    ) -> Optional[SpeechSegment]:
        """
        Найти ближайший сегмент речи перед кликом.
        
        Берем сегмент, который заканчивается ближе всего к клику,
        но не позже чем MAX_SPEECH_SECONDS до клика.
        """
        best_candidate = None
        best_distance = float('inf')
        
        for segment in speech_segments:
            # Сегмент должен заканчиваться до клика
            if segment.end > click_timestamp:
                continue
            
            # Сегмент должен начинаться не раньше, чем MAX_SPEECH_SECONDS до клика
            if segment.end < click_timestamp - self.MAX_SPEECH_SECONDS:
                continue
            
            # Вычисляем расстояние от конца сегмента до клика
            distance = click_timestamp - segment.end
            
            if distance < best_distance:
                best_distance = distance
                best_candidate = segment
        
        return best_candidate
    
    def _extract_raw_text(self, speech: Optional[SpeechSegment]) -> str:
        """Извлечь текст речи для передачи в LLM."""
        if speech is None:
            return ""
        
        return speech.text
    
    def filter_clicks_by_speech(
        self,
        clicks: List[ClickEvent],
        speech_segments: List[SpeechSegment],
        max_gap_seconds: float = 3.0
    ) -> List[ClickEvent]:
        """
        Отфильтровать клики: оставить только те, рядом с которыми есть речь.
        
        Args:
            clicks: Все клики
            speech_segments: Все сегменты речи
            max_gap_seconds: Максимальный промежуток между кликом и речью
            
        Returns:
            Отфильтрованный список кликов
        """
        filtered = []
        
        for click in clicks:
            nearest = self._find_nearest_speech_before(click.timestamp, speech_segments)
            
            if nearest is not None:
                # Проверяем, что речь достаточно близко к клику
                gap = click.timestamp - nearest.end
                if gap <= max_gap_seconds:
                    filtered.append(click)
                else:
                    logger.debug(f"Click @ {click.timestamp:.2f}s skipped: gap {gap:.2f}s > {max_gap_seconds}s")
            else:
                logger.debug(f"Click @ {click.timestamp:.2f}s skipped: no speech nearby")
        
        logger.info(f"Filtered {len(clicks)} clicks -> {len(filtered)} with speech")
        return filtered


def parse_clicks_from_log(clicks_log: Dict[str, Any]) -> List[ClickEvent]:
    """Парсинг лога кликов из JSON формата расширения."""
    clicks = []
    
    raw_clicks = clicks_log.get("clicks", [])
    if isinstance(raw_clicks, list):
        for c in raw_clicks:
            clicks.append(ClickEvent(
                timestamp=c.get("timestamp", 0.0),
                x=c.get("x", 0),
                y=c.get("y", 0),
                element=c.get("element")
            ))
    
    return clicks


def parse_asr_segments(asr_result: Dict[str, Any]) -> List[SpeechSegment]:
    """Парсинг сегментов речи из результата Whisper."""
    segments = []
    
    raw_segments = asr_result.get("segments", [])
    if isinstance(raw_segments, list):
        for s in raw_segments:
            segments.append(SpeechSegment(
                start=s.get("start", 0.0),
                end=s.get("end", 0.0),
                text=s.get("text", "").strip()
            ))
    
    return segments
