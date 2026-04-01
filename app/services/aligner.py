"""
Smart Aligner Service - сервис интеллектуальной синхронизации.
Реализует алгоритмы сопоставления речи с действиями на экране.

Ключевая особенность:
Система должна уметь сопоставлять фразу сказанную в 00:05 с кликом, 
произошедшим в 00:15 (если между ними была пауза-раздумье), 
и вырезать это "мёртвое время".

Отличие от Guidde: контекстная синхронизация вместо линейной.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
from difflib import SequenceMatcher

import numpy as np

from app.config import settings


logger = logging.getLogger(__name__)


class ActionType(str, Enum):
    """Типы действий на экране."""
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    SCROLL = "scroll"
    TYPE = "type"
    DRAG = "drag"
    HOVER = "hover"
    KEY_PRESS = "key_press"


@dataclass
class ScreenAction:
    """Действие на экране."""
    action_type: ActionType
    timestamp: float
    x: int
    y: int
    element_description: Optional[str] = None
    element_tag: Optional[str] = None
    element_text: Optional[str] = None
    scroll_direction: Optional[str] = None  # up, down
    scroll_amount: Optional[int] = None
    key_code: Optional[int] = None
    typed_text: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь."""
        return {
            "action_type": self.action_type.value,
            "timestamp": self.timestamp,
            "x": self.x,
            "y": self.y,
            "element_description": self.element_description,
            "scroll_direction": self.scroll_direction,
            "scroll_amount": self.scroll_amount,
            "typed_text": self.typed_text,
        }


@dataclass
class VoiceSegment:
    """Сегмент речи из транскрипции."""
    start: float
    end: float
    text: str
    confidence: float = 0.9
    words: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь."""
        return {
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "confidence": self.confidence,
            "words": self.words,
        }


@dataclass
class AlignedStep:
    """Синхронизированный шаг."""
    step_number: int
    original_start: float
    original_end: float
    aligned_start: float
    aligned_end: float
    text: str
    action: ScreenAction
    silence_removed: float = 0.0
    confidence: float = 0.9
    
    @property
    def duration(self) -> float:
        """Длительность шага."""
        return self.aligned_end - self.aligned_start
    
    @property
    def original_duration(self) -> float:
        """Оригинальная длительность."""
        return self.original_end - self.original_start
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь."""
        return {
            "step_number": self.step_number,
            "original_start": self.original_start,
            "original_end": self.original_end,
            "aligned_start": self.aligned_start,
            "aligned_end": self.aligned_end,
            "text": self.text,
            "action": self.action.to_dict(),
            "silence_removed": self.silence_removed,
            "confidence": self.confidence,
        }


@dataclass
class AlignmentResult:
    """Результат синхронизации."""
    steps: List[AlignedStep]
    total_original_duration: float
    total_aligned_duration: float
    total_silence_removed: float
    compression_ratio: float
    alignment_quality: float  # 0.0 - 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь."""
        return {
            "steps": [s.to_dict() for s in self.steps],
            "total_original_duration": self.total_original_duration,
            "total_aligned_duration": self.total_aligned_duration,
            "total_silence_removed": self.total_silence_removed,
            "compression_ratio": self.compression_ratio,
            "alignment_quality": self.alignment_quality,
        }


class SmartAligner:
    """
    Интеллектуальный синхронизатор речи и действий.
    
    Алгоритм работы:
    1. Анализ паттернов речи (паузы, раздумья, слова-маркеры)
    2. Сопоставление с действиями на экране
    3. Вырезание "мёртвого времени"
    4. Оптимизация таймингов
    
    Ключевые слова-маркеры для сопоставления:
    - "нажми" -> click
    - "кликни" -> click
    - "наведи" -> hover
    - "пролистай" -> scroll
    - "введи" -> type
    """
    
    # Паттерны для сопоставления речи с действиями
    ACTION_PATTERNS = {
        ActionType.CLICK: [
            r"нажми",
            r"кликни",
            r"щелкни",
            r"ткни",
            r"нажать",
            r"кликнуть",
            r"выбери",
            r"выбрать",
            r"открой",
            r"открыть",
            r"нажмите",
            r"кликните",
            # English
            r"click",
            r"press",
            r"tap",
        ],
        ActionType.SCROLL: [
            r"пролистай",
            r"прокрути",
            r"скролл",
            r"опусти",
            r"подними",
            r"листай",
            r"двинь",
            # English
            r"scroll",
            r"swipe",
        ],
        ActionType.TYPE: [
            r"введи",
            r"напечатай",
            r"напиши",
            r"ввести",
            r"напечатать",
            r"ввод",
            # English
            r"type",
            r"enter",
            r"input",
        ],
        ActionType.HOVER: [
            r"наведи",
            r"наведи курсор",
            r"подведи",
            r"наведите",
            # English
            r"hover",
            r"move",
        ],
    }
    
    # Паттерны пауз и раздумий
    PAUSE_PATTERNS = [
        r"эээ",
        r"ммм",
        r"ну",
        r"вот",
        r"значит",
        r"понимаешь",
        r"как бы",
        r"в общем",
        r"допустим",
    ]
    
    def __init__(
        self,
        max_gap_threshold: float = 5.0,
        min_speech_gap: float = 0.3,
        pause_word_threshold: float = 0.5,
        confidence_threshold: float = 0.7,
    ):
        """
        Инициализация Smart Aligner.
        
        Args:
            max_gap_threshold: Максимальный порог между речью и действием (секунды)
            min_speech_gap: Минимальная пауза между речью для анализа
            pause_word_threshold: Порог для определения слов-пауз
            confidence_threshold: Минимальный confidence для сопоставления
        """
        self.max_gap_threshold = max_gap_threshold
        self.min_speech_gap = min_speech_gap
        self.pause_word_threshold = pause_word_threshold
        self.confidence_threshold = confidence_threshold
    
    def align(
        self,
        voice_segments: List[VoiceSegment],
        screen_actions: List[ScreenAction],
        language: str = "ru"
    ) -> AlignmentResult:
        """
        Основной метод синхронизации голоса и действий.
        
        Args:
            voice_segments: Сегменты голоса из ASR
            screen_actions: Действия на экране
            language: Язык для корректного анализа
            
        Returns:
            AlignmentResult с синхронизированными шагами
        """
        logger.info(f"Starting alignment: {len(voice_segments)} voice segments, "
                   f"{len(screen_actions)} actions")
        
        if not voice_segments or not screen_actions:
            return self._empty_result()
        
        # Шаг 1: Очистка речи от пауз и раздумий
        cleaned_segments = self._clean_pauses(voice_segments, language)
        
        # Шаг 2: Сопоставление действий с речью
        matched_pairs = self._match_actions_to_speech(cleaned_segments, screen_actions)
        
        # Шаг 3: Создание выровненных шагов
        aligned_steps = self._create_aligned_steps(matched_pairs, cleaned_segments)
        
        # Шаг 4: Вычисление метрик
        total_original = sum(s.original_duration for s in aligned_steps)
        total_aligned = sum(s.duration for s in aligned_steps)
        total_silence = total_original - total_aligned
        
        compression = total_original / total_aligned if total_aligned > 0 else 1.0
        quality = self._calculate_quality(aligned_steps, voice_segments)
        
        result = AlignmentResult(
            steps=aligned_steps,
            total_original_duration=total_original,
            total_aligned_duration=total_aligned,
            total_silence_removed=max(0, total_silence),
            compression_ratio=compression,
            alignment_quality=quality,
        )
        
        logger.info(f"Alignment complete: {len(aligned_steps)} steps, "
                   f"compression {compression:.2f}x, quality {quality:.2f}")
        
        return result
    
    def _clean_pauses(
        self,
        segments: List[VoiceSegment],
        language: str
    ) -> List[VoiceSegment]:
        """
        Очистка сегментов от пауз и раздумий.
        
        Удаляет или сокращает:
        - Слова-паузы (эээ, ммм, ну и т.д.)
        - Длинные паузы между предложениями
        - Неуверенную речь
        """
        cleaned = []
        
        for segment in segments:
            # Анализируем текст на наличие пауз
            text = segment.text.lower()
            
            pause_count = 0
            pause_words = []
            
            for pattern in self.PAUSE_PATTERNS:
                import re
                matches = re.findall(pattern, text)
                pause_count += len(matches)
                pause_words.extend(matches)
            
            # Если много пауз - это раздумье
            pause_ratio = len(pause_words) / len(text.split()) if text.split() else 0
            
            if pause_ratio > self.pause_word_threshold:
                # Сокращаем сегмент на 20%
                new_duration = segment.end - segment.start
                new_end = segment.start + new_duration * 0.8
                
                cleaned.append(VoiceSegment(
                    start=segment.start,
                    end=new_end,
                    text=segment.text,
                    confidence=segment.confidence * 0.8,  # Снижаем confidence
                    words=segment.words,
                ))
            else:
                cleaned.append(segment)
        
        return cleaned
    
    def _match_actions_to_speech(
        self,
        voice_segments: List[VoiceSegment],
        screen_actions: List[ScreenAction]
    ) -> List[Tuple[VoiceSegment, ScreenAction]]:
        """
        Сопоставление действий с речью.
        
        Алгоритм:
        1. Для каждого действия ищем ближайший сегмент речи
        2. Проверяем контекст (слова-маркеры)
        3. Вычисляем confidence匹配
        4. Учитываем временной gap
        """
        matched = []
        used_voices = set()
        used_actions = set()
        
        for action in screen_actions:
            if action.timestamp in used_actions:
                continue
            
            best_match = None
            best_score = 0
            best_gap = float('inf')
            
            for i, voice in enumerate(voice_segments):
                if i in used_voices:
                    continue
                
                # Вычисляем gap между речью и действием
                voice_end = voice.end
                action_time = action.timestamp
                
                # Действие может быть до, во время или после речи
                if action_time >= voice_end:
                    gap = action_time - voice_end
                else:
                    gap = abs(voice.start - action_time)
                
                # Пропускаем если gap слишком большой
                if gap > self.max_gap_threshold:
                    continue
                
                # Анализируем контекст речи
                context_score = self._analyze_action_context(voice.text, action.action_type)
                
                # Комбинированный score
                # Учитываем: gap越小越好, context_score越高越好
                gap_penalty = max(0, (gap / self.max_gap_threshold))
                combined_score = context_score * (1 - gap_penalty * 0.3)
                
                if combined_score > best_score:
                    best_match = voice
                    best_score = combined_score
                    best_gap = gap
            
            if best_match is not None:
                match_idx = voice_segments.index(best_match)
                used_voices.add(match_idx)
                used_actions.add(action.timestamp)
                
                # Вычисляем сколько времени можно вырезать
                silence_removed = self._calculate_silence_removal(
                    best_match, action, best_gap
                )
                
                # Обновляем сегмент с информацией о вырезанном времени
                aligned_voice = VoiceSegment(
                    start=best_match.start,
                    end=best_match.end,
                    text=best_match.text,
                    confidence=best_score,
                    words=best_match.words,
                )
                
                matched.append((aligned_voice, action, silence_removed))
        
        return matched
    
    def _analyze_action_context(
        self,
        text: str,
        action_type: ActionType
    ) -> float:
        """
        Анализ контекста речи для определения типа действия.
        
        Returns:
            Score от 0 до 1, где 1 - идеальное совпадение
        """
        text_lower = text.lower()
        
        if action_type not in self.ACTION_PATTERNS:
            return 0.5
        
        patterns = self.ACTION_PATTERNS[action_type]
        
        import re
        
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return 1.0
        
        # Если нет явного маркера, используем similarity с типичными фразами
        typical_phrases = {
            ActionType.CLICK: [
                "нажми на кнопку",
                "нажми здесь",
                "кликни по ссылке",
            ],
            ActionType.SCROLL: [
                "прокрути вниз",
                "пролистай страницу",
            ],
            ActionType.TYPE: [
                "введи текст",
                "напиши сообщение",
            ],
        }
        
        if action_type in typical_phrases:
            max_sim = 0
            for phrase in typical_phrases[action_type]:
                sim = SequenceMatcher(None, text_lower, phrase).ratio()
                max_sim = max(max_sim, sim)
            
            return max_sim
        
        return 0.3
    
    def _calculate_silence_removal(
        self,
        voice: VoiceSegment,
        action: ScreenAction,
        gap: float
    ) -> float:
        """
        Вычисление количества "мёртвого времени" для удаления.
        
        Логика:
        - Если действие после речи: удаляем gap
        - Если действие во время речи: ничего не удаляем
        - Если действие до речи: удаляем время до начала речи
        """
        voice_end = voice.end
        action_time = action.timestamp
        
        if action_time >= voice_end:
            # Действие после речи - классический случай
            # Удаляем время между концом речи и действием
            # Но оставляем небольшой буфер (0.2с) для естественности
            return max(0, gap - 0.2)
        else:
            # Действие во время речи - проверяем контекст
            # Возможно, была пауза-раздумье
            return 0
    
    def _create_aligned_steps(
        self,
        matched_pairs: List[Tuple[VoiceSegment, ScreenAction, float]],
        all_voices: List[VoiceSegment]
    ) -> List[AlignedStep]:
        """Создание синхронизированных шагов."""
        steps = []
        
        for i, (voice, action, silence_removed) in enumerate(matched_pairs):
            # Вычисляем новые тайминги
            # Начало - как в оригинале
            new_start = voice.start
            
            # Конец - с учетом удаленного silence
            new_end = voice.end - silence_removed
            
            # Если новый конец раньше начала - корректируем
            if new_end <= new_start:
                new_end = new_start + 0.5  # Минимальная длительность
            
            # Confidence на основе gap
            confidence = voice.confidence
            
            step = AlignedStep(
                step_number=i + 1,
                original_start=voice.start,
                original_end=voice.end,
                aligned_start=new_start,
                aligned_end=new_end,
                text=voice.text,
                action=action,
                silence_removed=silence_removed,
                confidence=confidence,
            )
            
            steps.append(step)
        
        # Обрабатываем несопоставленные действия
        unmatched_actions = []
        for action in all_voices:
            pass  # Здесь можно обработать действия без речи
        
        return steps
    
    def _calculate_quality(
        self,
        aligned_steps: List[AlignedStep],
        original_voices: List[VoiceSegment]
    ) -> float:
        """Вычисление метрики качества синхронизации."""
        if not aligned_steps or not original_voices:
            return 0.0
        
        # Факторы качества:
        # 1. Процент сопоставленных действий
        matched_count = len(aligned_steps)
        total_count = len(original_voices)
        coverage_score = min(1.0, matched_count / max(1, total_count))
        
        # 2. Средний confidence
        avg_confidence = sum(s.confidence for s in aligned_steps) / max(1, len(aligned_steps))
        
        # 3. Количество "мёртвого времени" удалено разумно
        # (не слишком много, не слишком мало)
        total_removed = sum(s.silence_removed for s in aligned_steps)
        total_duration = sum(s.original_duration for s in aligned_steps)
        removal_ratio = total_removed / max(0.1, total_duration)
        
        # Идеальное соотношение удаления - 10-30%
        if removal_ratio < 0.1:
            removal_score = removal_ratio / 0.1
        elif removal_ratio > 0.3:
            removal_score = max(0, 1 - (removal_ratio - 0.3) / 0.7)
        else:
            removal_score = 1.0
        
        # Комбинированный score
        quality = (
            coverage_score * 0.3 +
            avg_confidence * 0.4 +
            removal_score * 0.3
        )
        
        return min(1.0, quality)
    
    def _empty_result(self) -> AlignmentResult:
        """Пустой результат для случаев без данных."""
        return AlignmentResult(
            steps=[],
            total_original_duration=0,
            total_aligned_duration=0,
            total_silence_removed=0,
            compression_ratio=1.0,
            alignment_quality=0.0,
        )
    
    def apply_alignment(
        self,
        video_path: str,
        audio_path: str,
        alignment_result: AlignmentResult,
        output_path: str
    ) -> bool:
        """
        Применение синхронизации к видео и аудио.
        
        Args:
            video_path: Путь к видео
            audio_path: Путь к аудио
            alignment_result: Результат синхронизации
            output_path: Путь для сохранения
            
        Returns:
            True если успешно
        """
        from app.services.video_processor import video_processor
        
        # Создаем сегменты для видео-процессора
        segments = []
        
        for step in alignment_result.steps:
            from app.services.video_processor import StepSegment
            
            seg = StepSegment(
                start_time=step.aligned_start,
                end_time=step.aligned_end,
                original_start=step.original_start,
                original_end=step.original_end,
                text=step.text,
                audio_duration=step.duration,
            )
            segments.append(seg)
        
        # Применяем time-stretching и зум
        success = video_processor.generate_video_with_zoom(
            input_video=video_path,
            output_video=output_path,
            steps=segments,
        )
        
        return success
    
    def estimate_time_savings(
        self,
        voice_segments: List[VoiceSegment],
        screen_actions: List[ScreenAction]
    ) -> Dict[str, Any]:
        """
        Предварительная оценка экономии времени.
        
        Args:
            voice_segments: Сегменты голоса
            screen_actions: Действия на экране
            
        Returns:
            Словарь с оценками
        """
        result = self.align(voice_segments, screen_actions)
        
        return {
            "original_duration_seconds": result.total_original_duration,
            "aligned_duration_seconds": result.total_aligned_duration,
            "time_saved_seconds": result.total_silence_removed,
            "compression_ratio": result.compression_ratio,
            "estimated_steps": len(result.steps),
            "quality_score": result.alignment_quality,
        }


# Экземпляр сервиса для использования в приложении
smart_aligner = SmartAligner()
