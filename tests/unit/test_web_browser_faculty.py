"""
Unit tests for the web browser mental faculty and its supporting classes.

Tests cover:
  - The UserInteraction protocol and its implementations
    (AutoUserInteraction, ConsoleUserInteraction).
  - The BrowserController Playwright wrapper
    (requires a real browser — marked ``@pytest.mark.slow``).
  - The TinyWebBrowserFaculty mental faculty itself, including prompt
    generation, action dispatch, user-facing methods, and serialization.
"""

import json
import logging
import os
import sys

import pytest

sys.path.insert(0, '../../tinytroupe/')
sys.path.insert(0, '../../')
sys.path.insert(0, '..')

from tinytroupe.agent.web_browser_faculty import TinyWebBrowserFaculty
from tinytroupe.ui.user_interaction import (
    AutoUserInteraction,
    ConsoleUserInteraction,
    UserInteraction,
)
from tinytroupe.examples import create_oscar_the_architect, create_lisa_the_data_scientist

from testing_utils import *

logger = logging.getLogger("tinytroupe")


# ======================================================================
# UserInteraction tests
# ======================================================================

@pytest.mark.core
def test_auto_user_interaction_confirm(setup):
    """AutoUserInteraction.confirm() returns the configured default."""
    # Default (auto_confirm=True)
    ui = AutoUserInteraction(auto_confirm=True)
    assert ui.confirm("Proceed?") is True
    assert len(ui.history) == 1
    assert ui.history[0]["kind"] == "confirm"
    assert ui.history[0]["response"] is True

    # auto_confirm=False
    ui2 = AutoUserInteraction(auto_confirm=False)
    assert ui2.confirm("Proceed?") is False


@pytest.mark.core
def test_auto_user_interaction_prompt(setup):
    """AutoUserInteraction.prompt() returns the configured value."""
    ui = AutoUserInteraction(auto_prompt_value="test_answer")
    result = ui.prompt("Enter code:")
    assert result == "test_answer"
    assert len(ui.history) == 1
    assert ui.history[0]["kind"] == "prompt"


@pytest.mark.core
def test_auto_user_interaction_notify(setup):
    """AutoUserInteraction.notify() records and returns None."""
    ui = AutoUserInteraction()
    ui.notify("Browser navigated.")
    assert len(ui.history) == 1
    assert ui.history[0]["kind"] == "notify"
    assert ui.history[0]["response"] is None


@pytest.mark.core
def test_auto_user_interaction_pause_for_action(setup):
    """AutoUserInteraction.pause_for_action() records and returns immediately."""
    ui = AutoUserInteraction()
    ui.pause_for_action("Please log in manually.")
    assert len(ui.history) == 1
    assert ui.history[0]["kind"] == "pause_for_action"


@pytest.mark.core
def test_auto_user_interaction_history_accumulation(setup):
    """Multiple interactions accumulate in history."""
    ui = AutoUserInteraction()
    ui.confirm("Q1?")
    ui.prompt("Q2?")
    ui.notify("Info")
    ui.pause_for_action("Do something")
    assert len(ui.history) == 4


@pytest.mark.core
def test_console_user_interaction_exists(setup):
    """ConsoleUserInteraction can be instantiated (methods not called to avoid blocking)."""
    ui = ConsoleUserInteraction()
    assert ui is not None


@pytest.mark.core
def test_user_interaction_protocol_enforced(setup):
    """UserInteraction ABC cannot be instantiated directly."""
    with pytest.raises(TypeError):
        UserInteraction()


# ======================================================================
# BrowserController tests (require real browser)
# ======================================================================

@pytest.fixture
def controller():
    """Create a BrowserController with auto-interaction and tear it down after the test."""
    from tinytroupe.tools.browser_controller import BrowserController

    ctrl = BrowserController(
        channel="chromium",
        headless=True,
        user_interaction=AutoUserInteraction(),
        confirm_destructive=False,
    )
    yield ctrl
    ctrl.close()


@pytest.mark.slow
def test_launch_and_close(setup, controller):
    """Browser can be launched and closed."""
    assert not controller.is_alive()
    controller.launch()
    assert controller.is_alive()
    controller.close()
    assert not controller.is_alive()


@pytest.mark.slow
def test_context_manager(setup):
    """BrowserController works as a context manager."""
    from tinytroupe.tools.browser_controller import BrowserController

    with BrowserController(
        channel="chromium", headless=True,
        user_interaction=AutoUserInteraction(),
    ) as ctrl:
        assert ctrl.is_alive()
    assert not ctrl.is_alive()


@pytest.mark.slow
def test_goto_and_metadata(setup, controller):
    """goto() navigates and returns URL/title."""
    controller.launch()
    result = controller.goto("https://example.com")
    assert result["success"] is True
    assert "example.com" in result["url"]

    meta = controller.get_page_metadata()
    assert "example" in meta["title"].lower() or "example.com" in meta["url"]


@pytest.mark.slow
def test_screenshot(setup, controller):
    """screenshot() saves a PNG and returns a valid path."""
    controller.launch()
    controller.goto("https://example.com")
    path = controller.screenshot()
    assert path is not None
    assert os.path.isfile(path)
    assert path.endswith(".png")


@pytest.mark.slow
def test_visible_text_extraction(setup, controller):
    """get_visible_text() returns page text content."""
    controller.launch()
    controller.goto("https://example.com")
    text = controller.get_visible_text()
    assert "Example Domain" in text


@pytest.mark.slow
def test_cleaned_html_extraction(setup, controller):
    """get_cleaned_html() strips scripts and returns HTML."""
    controller.launch()
    controller.goto("https://example.com")
    html = controller.get_cleaned_html()
    assert "<script" not in html.lower()
    assert "example" in html.lower()


@pytest.mark.slow
def test_accessibility_tree_extraction(setup, controller):
    """get_accessibility_tree() returns a structured representation."""
    controller.launch()
    controller.goto("https://example.com")
    tree = controller.get_accessibility_tree()
    assert len(tree) > 10


@pytest.mark.slow
def test_content_strategy_dispatch(setup, controller):
    """get_page_content() dispatches to the correct strategy."""
    controller.launch()
    controller.goto("https://example.com")

    content_default = controller.get_page_content()
    assert len(content_default) > 0

    content_text = controller.get_page_content("visible_text")
    assert "Example Domain" in content_text


@pytest.mark.slow
def test_tab_management(setup, controller):
    """Tab open / switch / close operations work correctly."""
    controller.launch()
    controller.goto("https://example.com")

    result = controller.new_tab("https://example.com")
    assert result["success"] is True
    assert result["tab_index"] == 1

    tabs = controller.list_tabs()
    assert len(tabs) == 2

    result = controller.switch_tab(0)
    assert result["success"] is True

    result = controller.close_tab(1)
    assert result["success"] is True
    assert len(controller.list_tabs()) == 1


@pytest.mark.slow
def test_action_log(setup, controller):
    """Action log records all operations."""
    controller.launch()
    controller.goto("https://example.com")
    controller.screenshot()

    log = controller.get_action_log()
    action_names = [entry["action"] for entry in log]
    assert "launch" in action_names
    assert "goto" in action_names
    assert "screenshot" in action_names


@pytest.mark.slow
def test_click_nonexistent_element(setup, controller):
    """Clicking a nonexistent element returns an error dict (not an exception)."""
    controller.launch()
    controller.goto("https://example.com")
    result = controller.click("#nonexistent-element-xyz")
    assert result["success"] is False
    assert "error" in result


@pytest.mark.slow
def test_ensure_launched_idempotent(setup, controller):
    """ensure_launched() is idempotent — calling it twice doesn't break anything."""
    controller.ensure_launched()
    assert controller.is_alive()
    controller.ensure_launched()  # should be a no-op
    assert controller.is_alive()


@pytest.mark.slow
def test_max_content_length_truncation(setup):
    """Content is truncated when max_content_length is set."""
    from tinytroupe.tools.browser_controller import BrowserController

    ctrl = BrowserController(
        channel="chromium", headless=True,
        user_interaction=AutoUserInteraction(),
        max_content_length=50,
    )
    try:
        ctrl.launch()
        ctrl.goto("https://example.com")
        text = ctrl.get_visible_text()
        assert len(text) <= 50 + len("\n\n... [content truncated]")
        assert "[content truncated]" in text
    finally:
        ctrl.close()


# ======================================================================
# TinyWebBrowserFaculty tests
# ======================================================================

@pytest.mark.core
def test_faculty_instantiation(setup):
    """Faculty can be instantiated with default parameters."""
    faculty = TinyWebBrowserFaculty()
    assert faculty.name == "WebBrowser"
    assert not faculty.is_browser_open()


@pytest.mark.core
def test_faculty_actions_definitions_prompt(setup):
    """actions_definitions_prompt() returns the template content."""
    faculty = TinyWebBrowserFaculty()
    prompt = faculty.actions_definitions_prompt()
    assert "BROWSE" in prompt
    assert "BROWSE_ACTION" in prompt
    assert "BROWSE_REQUEST_USER_HELP" in prompt


@pytest.mark.core
def test_faculty_actions_constraints_prompt(setup):
    """actions_constraints_prompt() returns constraint text."""
    faculty = TinyWebBrowserFaculty()
    prompt = faculty.actions_constraints_prompt()
    assert "Safety" in prompt or "safety" in prompt or "cautious" in prompt
    assert "Observe" in prompt or "observe" in prompt


@pytest.mark.core
def test_faculty_registration_with_agent(setup):
    """Faculty can be added to a TinyPerson agent."""
    oscar = create_oscar_the_architect()
    faculty = TinyWebBrowserFaculty()
    oscar.add_mental_faculty(faculty)

    assert faculty in oscar._mental_faculties


@pytest.mark.core
def test_faculty_process_action_returns_false_for_unknown(setup):
    """process_action() returns False for unrecognized action types."""
    oscar = create_oscar_the_architect()
    faculty = TinyWebBrowserFaculty()
    result = faculty.process_action(oscar, {"type": "TALK", "content": "hello", "target": ""})
    assert result is False


@pytest.mark.core
def test_faculty_serialization_roundtrip(setup):
    """Faculty config survives JSON serialization / deserialization."""
    faculty = TinyWebBrowserFaculty(
        browser_channel="chromium",
        headless=True,
        content_strategy="cleaned_html",
        viewport_width=1920,
        viewport_height=1080,
    )

    json_dict = faculty.to_json()
    assert json_dict["browser_channel"] == "chromium"
    assert json_dict["headless"] is True
    assert json_dict["content_strategy"] == "cleaned_html"
    assert json_dict["viewport_width"] == 1920

    restored = TinyWebBrowserFaculty.from_json(json_dict)
    assert restored._browser_channel == "chromium"
    assert restored._headless is True
    assert restored._content_strategy == "cleaned_html"
    assert restored._viewport_width == 1920
    # Browser should NOT be open after deserialization
    assert not restored.is_browser_open()


@pytest.mark.core
def test_faculty_user_facing_methods_exist(setup):
    """All user-facing methods exist and are callable."""
    faculty = TinyWebBrowserFaculty()
    assert callable(faculty.user_browse)
    assert callable(faculty.user_action)
    assert callable(faculty.user_goto)
    assert callable(faculty.user_screenshot)
    assert callable(faculty.user_get_page_content)
    assert callable(faculty.user_pause_for_login)
    assert callable(faculty.user_inject_credentials)
    assert callable(faculty.user_save_session)
    assert callable(faculty.user_load_session)


@pytest.mark.core
def test_faculty_custom_user_interaction(setup):
    """Faculty accepts a custom UserInteraction instance."""
    custom_ui = AutoUserInteraction(auto_confirm=False, auto_prompt_value="custom")
    faculty = TinyWebBrowserFaculty(user_interaction=custom_ui)
    assert faculty._user_interaction is custom_ui


@pytest.mark.slow
def test_faculty_user_goto_and_screenshot(setup):
    """user_goto() navigates and user_screenshot() returns a path."""
    faculty = TinyWebBrowserFaculty(
        browser_channel="chromium",
        headless=True,
        user_interaction=AutoUserInteraction(),
    )
    try:
        result = faculty.user_goto("https://example.com")
        assert result["success"] is True

        path = faculty.user_screenshot()
        assert path is not None
        assert os.path.isfile(path)
    finally:
        faculty.close_browser()


@pytest.mark.slow
def test_faculty_user_get_page_content(setup):
    """user_get_page_content() returns page content."""
    faculty = TinyWebBrowserFaculty(
        browser_channel="chromium",
        headless=True,
        user_interaction=AutoUserInteraction(),
    )
    try:
        faculty.user_goto("https://example.com")
        content = faculty.user_get_page_content()
        assert len(content) > 0
    finally:
        faculty.close_browser()


@pytest.mark.slow
def test_faculty_user_action_dispatch(setup):
    """user_action() dispatches low-level commands correctly."""
    faculty = TinyWebBrowserFaculty(
        browser_channel="chromium",
        headless=True,
        user_interaction=AutoUserInteraction(),
    )
    try:
        result = faculty.user_action("goto https://example.com")
        assert result["success"] is True

        result = faculty.user_action("screenshot")
        assert result["success"] is True
        assert "screenshot" in result
    finally:
        faculty.close_browser()


@pytest.mark.slow
def test_faculty_process_browse_action(setup):
    """process_action() handles BROWSE_ACTION and feeds observation to agent."""
    oscar = create_oscar_the_architect()
    faculty = TinyWebBrowserFaculty(
        browser_channel="chromium",
        headless=True,
        user_interaction=AutoUserInteraction(),
    )
    oscar.add_mental_faculty(faculty)

    try:
        result = faculty.process_action(
            oscar,
            {"type": "BROWSE_ACTION", "content": "goto https://example.com", "target": ""},
        )
        assert result is True
        # Agent should have received observations
        assert oscar.episodic_memory.count() > 0
    finally:
        faculty.close_browser()


@pytest.mark.slow
def test_faculty_process_request_user_help(setup):
    """process_action() handles BROWSE_REQUEST_USER_HELP."""
    auto_ui = AutoUserInteraction()
    lisa = create_lisa_the_data_scientist()
    faculty = TinyWebBrowserFaculty(
        browser_channel="chromium",
        headless=True,
        user_interaction=auto_ui,
    )
    lisa.add_mental_faculty(faculty)

    try:
        # First navigate somewhere
        faculty.user_goto("https://example.com")

        result = faculty.process_action(
            lisa,
            {"type": "BROWSE_REQUEST_USER_HELP", "content": "I need help with a CAPTCHA", "target": ""},
        )
        assert result is True
        # AutoUserInteraction should have recorded the pause
        assert any(h["kind"] == "pause_for_action" for h in auto_ui.history)
    finally:
        faculty.close_browser()
