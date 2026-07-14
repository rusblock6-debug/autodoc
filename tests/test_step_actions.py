"""
Тесты типизации действий шага (click / select / drag / input).

Расширение пишет поле action в лог событий; make_step_placeholder строит
заглушку текста шага по типу действия (до Vision-обработки).

Запуск внутри контейнера:
    docker compose exec celery-worker python -m pytest tests/test_step_actions.py -v
"""

import pytest

from app.api.sessions import make_step_placeholder


class TestClickPlaceholder:
    def test_click_with_text(self):
        action, placeholder, hint = make_step_placeholder(
            {"action": "click", "element_text": "Сохранить"}
        )
        assert action == "click"
        assert placeholder == "Нажмите «Сохранить»"
        assert hint == "Сохранить"

    def test_click_without_text_uses_tag(self):
        action, placeholder, _ = make_step_placeholder(
            {"action": "click", "element": "DIV"}
        )
        assert placeholder == "Нажмите на элемент DIV"

    def test_legacy_log_without_action_is_click(self):
        """Старые записи без поля action трактуются как клик."""
        action, placeholder, _ = make_step_placeholder({"element_text": "ОК"})
        assert action == "click"
        assert placeholder.startswith("Нажмите")

    def test_unknown_action_falls_back_to_click(self):
        action, _, _ = make_step_placeholder(
            {"action": "hover", "element_text": "x"}
        )
        assert action == "click"


class TestSelectPlaceholder:
    def test_select_uses_selected_text(self):
        action, placeholder, hint = make_step_placeholder(
            {"action": "select", "selected_text": "Американские школы", "element_text": "DIV-текст"}
        )
        assert action == "select"
        assert placeholder == "Выделите текст «Американские школы»"
        assert hint == "Американские школы"

    def test_select_truncates_long_text(self):
        long_text = "х" * 200
        _, placeholder, _ = make_step_placeholder(
            {"action": "select", "selected_text": long_text}
        )
        assert len(placeholder) < 80
        assert placeholder.startswith("Выделите текст «")

    def test_select_without_text(self):
        _, placeholder, _ = make_step_placeholder({"action": "select"})
        assert placeholder == "Выделите текст"


class TestDragPlaceholder:
    def test_drag_with_element_text(self):
        action, placeholder, _ = make_step_placeholder(
            {"action": "drag", "element_text": "Карточка задачи"}
        )
        assert action == "drag"
        assert placeholder == "Перетащите «Карточка задачи»"

    def test_drag_without_text(self):
        _, placeholder, _ = make_step_placeholder({"action": "drag"})
        assert placeholder == "Перетащите элемент"


class TestInputPlaceholder:
    def test_input_with_label_and_value(self):
        action, placeholder, hint = make_step_placeholder(
            {"action": "input", "field_label": "Email", "input_value": "a@b.ru"}
        )
        assert action == "input"
        assert placeholder == "Введите «a@b.ru» в поле «Email»"
        assert "Email" in hint and "a@b.ru" in hint

    def test_input_label_only(self):
        _, placeholder, _ = make_step_placeholder(
            {"action": "input", "field_label": "Поиск"}
        )
        assert placeholder == "Введите значение в поле «Поиск»"

    def test_input_no_label_no_value(self):
        _, placeholder, _ = make_step_placeholder({"action": "input"})
        assert placeholder == "Введите значение в поле"

    def test_input_falls_back_to_element_text_as_label(self):
        _, placeholder, _ = make_step_placeholder(
            {"action": "input", "element_text": "Имя пользователя"}
        )
        assert "Имя пользователя" in placeholder


class TestGuideStepModel:
    def test_action_column_exists_with_click_default(self):
        from app.models import GuideStep

        col = GuideStep.__table__.columns["action"]
        assert col.default.arg == "click"
        assert col.nullable is False

    def test_analyze_screenshot_accepts_action_param(self):
        import inspect
        from app.services.ai_service import AIService

        params = inspect.signature(AIService.analyze_screenshot).parameters
        assert "action" in params
        assert params["action"].default == "click"
