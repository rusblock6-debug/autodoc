"""
Workers package for AI processing.
Изолированные subprocess для тяжелых AI/Video задач.
"""

from .ai_runner import execute_task, main

__all__ = ["execute_task", "main"]
