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


# ======================================================================
# Content filter tests
# ======================================================================

@pytest.mark.core
def test_faculty_content_filter_prompt_stored(setup):
    """content_filter_prompt is stored and accessible."""
    filter_prompt = "Keep only the sidebar and the main content area."
    faculty = TinyWebBrowserFaculty(content_filter_prompt=filter_prompt)
    assert faculty._content_filter_prompt == filter_prompt


@pytest.mark.core
def test_faculty_content_filter_default_none(setup):
    """content_filter_prompt defaults to None (no filtering)."""
    faculty = TinyWebBrowserFaculty()
    assert faculty._content_filter_prompt is None


@pytest.mark.core
def test_constraints_mention_content_filtering(setup):
    """The constraints prompt mentions content filtering."""
    faculty = TinyWebBrowserFaculty()
    prompt = faculty.actions_constraints_prompt()
    assert "CONTENT FILTERED" in prompt or "content filter" in prompt.lower()


@pytest.mark.slow
def test_content_filter_reduces_content(setup):
    """When content_filter_prompt is set, _apply_content_filter reduces page content."""
    faculty = TinyWebBrowserFaculty(
        content_filter_prompt="Keep only headings and links. Remove all body text.",
    )

    # Simulate a large page with mixed content
    page_content = (
        "# Main Heading\n"
        "link: https://example.com\n"
        "paragraph: " + "Lorem ipsum dolor sit amet. " * 200 + "\n"
        "## Sub Heading\n"
        "link: https://example.com/about\n"
        "paragraph: " + "Consectetur adipiscing elit. " * 200 + "\n"
    )

    filtered = faculty._apply_content_filter(page_content)

    # The filter should have reduced the content
    assert len(filtered) < len(page_content)
    # The suppression marker should appear
    assert "CONTENT FILTERED" in filtered


# ======================================================================
# Page guide tests
# ======================================================================

@pytest.mark.core
def test_faculty_page_guide_prompt_stored(setup):
    """page_guide_prompt is stored and accessible."""
    guide_prompt = "Describe the sidebar and the main form area."
    faculty = TinyWebBrowserFaculty(page_guide_prompt=guide_prompt)
    assert faculty._page_guide_prompt == guide_prompt


@pytest.mark.core
def test_faculty_page_guide_default_none(setup):
    """page_guide_prompt defaults to None (no guide generation)."""
    faculty = TinyWebBrowserFaculty()
    assert faculty._page_guide_prompt is None


@pytest.mark.core
def test_constraints_mention_page_guide(setup):
    """The constraints prompt mentions the page guide feature."""
    faculty = TinyWebBrowserFaculty()
    prompt = faculty.actions_constraints_prompt()
    assert "page guide" in prompt.lower() or "Page guide" in prompt


@pytest.mark.core
def test_actions_mention_full_page_content_on_demand(setup):
    """The actions prompt mentions get_content for full page detail."""
    faculty = TinyWebBrowserFaculty()
    prompt = faculty.actions_definitions_prompt()
    assert "full page content" in prompt.lower() or "full page structure" in prompt.lower()


@pytest.mark.core
def test_faculty_page_guide_serialization_roundtrip(setup):
    """page_guide_prompt survives JSON serialization / deserialization."""
    guide_prompt = "Describe the form layout and input fields."
    faculty = TinyWebBrowserFaculty(
        page_guide_prompt=guide_prompt,
        content_filter_prompt="Keep only headings.",
        browser_channel="chromium",
    )

    json_dict = faculty.to_json()
    assert json_dict["page_guide_prompt"] == guide_prompt
    assert json_dict["content_filter_prompt"] == "Keep only headings."

    restored = TinyWebBrowserFaculty.from_json(json_dict)
    assert restored._page_guide_prompt == guide_prompt
    assert restored._content_filter_prompt == "Keep only headings."


@pytest.mark.core
def test_faculty_page_guide_and_filter_coexist(setup):
    """page_guide_prompt and content_filter_prompt can both be set simultaneously."""
    faculty = TinyWebBrowserFaculty(
        page_guide_prompt="Describe the sidebar and buttons.",
        content_filter_prompt="Keep only form elements.",
    )
    assert faculty._page_guide_prompt is not None
    assert faculty._content_filter_prompt is not None


@pytest.mark.core
def test_page_guide_generates_concise_output(setup):
    """_apply_page_guide generates a concise NL guide from page content."""
    faculty = TinyWebBrowserFaculty(
        page_guide_prompt=(
            "Describe: 1) The search form with input and submit button. "
            "2) The navigation links at the top."
        ),
    )

    # Simulate a page with known interactive elements
    page_content = (
        "[Page: Example Search]\n"
        "  [0] heading \"Search Portal\"\n"
        "  [1] navigation \"Main Nav\"\n"
        "    [2] link \"Home\"\n"
        "    [3] link \"About\"\n"
        "    [4] link \"Contact\"\n"
        "  [5] heading \"Search\"\n"
        "  [6] textbox \"Enter your search query...\" [placeholder]\n"
        "  [7] button \"Search\"\n"
        "  [8] heading \"Results\"\n"
        "  [9] paragraph \"No results yet.\"\n"
    )

    guide = faculty._apply_page_guide(page_content)

    # Guide should be non-empty and concise (not the full tree)
    assert len(guide) > 50
    assert len(guide) < len(page_content) * 3  # should not balloon

    # Guide should mention key elements from the instructions
    guide_lower = guide.lower()
    assert "search" in guide_lower or "textbox" in guide_lower or "input" in guide_lower
    assert "button" in guide_lower or "submit" in guide_lower


@pytest.mark.core
def test_page_guide_observation_flow(setup):
    """With page_guide_prompt set, process_action produces BROWSER_PAGE_GUIDE
    and a metadata-only BROWSER_OBSERVATION (no full tree)."""
    oscar = create_oscar_the_architect()
    faculty = TinyWebBrowserFaculty(
        browser_channel="chromium",
        headless=True,
        user_interaction=AutoUserInteraction(),
        page_guide_prompt=(
            "Describe: 1) The main heading. 2) Any links on the page."
        ),
    )
    oscar.add_mental_faculty(faculty)

    try:
        result = faculty.process_action(
            oscar,
            {"type": "BROWSE_ACTION", "content": "goto https://example.com", "target": ""},
        )
        assert result is True

        # Inspect the stimuli stored in episodic memory
        memories = oscar.episodic_memory.retrieve_all()
        all_stimuli = []
        for mem in memories:
            content = mem.get("content", {})
            if isinstance(content, dict):
                for s in content.get("stimuli", []):
                    all_stimuli.append(s)

        stim_types = [s.get("type") for s in all_stimuli]

        # Should have a BROWSER_PAGE_GUIDE stimulus
        assert "BROWSER_PAGE_GUIDE" in stim_types, (
            f"Expected BROWSER_PAGE_GUIDE in stimuli, got: {stim_types}"
        )

        # Should have a BROWSER_OBSERVATION stimulus
        assert "BROWSER_OBSERVATION" in stim_types

        # The BROWSER_OBSERVATION should NOT contain the full page tree
        # (since the guide is active, tree is opt-in)
        browser_obs = [s for s in all_stimuli if s["type"] == "BROWSER_OBSERVATION"]
        for obs in browser_obs:
            obs_text = obs.get("content", "")
            assert "Page content omitted" in obs_text or "get_content" in obs_text

    finally:
        faculty.close_browser()


@pytest.mark.core
def test_get_content_returns_full_tree_when_guide_active(setup):
    """BROWSE_ACTION get_content always returns the full accessibility tree,
    even when page_guide_prompt is set."""
    oscar = create_oscar_the_architect()
    faculty = TinyWebBrowserFaculty(
        browser_channel="chromium",
        headless=True,
        user_interaction=AutoUserInteraction(),
        page_guide_prompt="Describe the main heading and links.",
    )
    oscar.add_mental_faculty(faculty)

    try:
        # Navigate first
        faculty.process_action(
            oscar,
            {"type": "BROWSE_ACTION", "content": "goto https://example.com", "target": ""},
        )

        # Request full content
        faculty.process_action(
            oscar,
            {"type": "BROWSE_ACTION", "content": "get_content", "target": ""},
        )

        # Find the BROWSER_OBSERVATION from the get_content action
        memories = oscar.episodic_memory.retrieve_all()
        all_stimuli = []
        for mem in memories:
            content = mem.get("content", {})
            if isinstance(content, dict):
                for s in content.get("stimuli", []):
                    all_stimuli.append(s)

        # Find observations from the get_content action
        get_content_obs = [
            s for s in all_stimuli
            if s["type"] == "BROWSER_OBSERVATION"
            and "get_content" in s.get("content", "")
        ]
        assert len(get_content_obs) > 0, "Should have a BROWSER_OBSERVATION for get_content"

        # The observation should contain actual page content (full tree forced)
        obs_content = get_content_obs[-1]["content"]
        assert "```" in obs_content, (
            "get_content observation should include the full tree in a code block"
        )
        # Should NOT say content was omitted
        assert "Page content omitted" not in obs_content

    finally:
        faculty.close_browser()


@pytest.mark.core
def test_no_guide_preserves_full_tree_in_observation(setup):
    """Without page_guide_prompt, BROWSER_OBSERVATION includes the full tree (backward compat)."""
    oscar = create_oscar_the_architect()
    faculty = TinyWebBrowserFaculty(
        browser_channel="chromium",
        headless=True,
        user_interaction=AutoUserInteraction(),
        # No page_guide_prompt — backward-compatible mode
    )
    oscar.add_mental_faculty(faculty)

    try:
        result = faculty.process_action(
            oscar,
            {"type": "BROWSE_ACTION", "content": "goto https://example.com", "target": ""},
        )
        assert result is True

        # Find BROWSER_OBSERVATION stimuli
        memories = oscar.episodic_memory.retrieve_all()
        all_stimuli = []
        for mem in memories:
            content = mem.get("content", {})
            if isinstance(content, dict):
                for s in content.get("stimuli", []):
                    all_stimuli.append(s)

        browser_obs = [s for s in all_stimuli if s["type"] == "BROWSER_OBSERVATION"]
        assert len(browser_obs) > 0

        # Should contain actual page content (the tree)
        obs_content = browser_obs[-1]["content"]
        assert "Page content" in obs_content
        assert "```" in obs_content
        # Should NOT have the opt-in message
        assert "Page content omitted" not in obs_content

        # Should NOT have BROWSER_PAGE_GUIDE
        stim_types = [s.get("type") for s in all_stimuli]
        assert "BROWSER_PAGE_GUIDE" not in stim_types

    finally:
        faculty.close_browser()


# ======================================================================
# Underspecified selector guard tests
# ======================================================================

@pytest.mark.core
def test_reject_bare_element_type_selectors(setup):
    """Bare HTML element types like 'radio', 'button', 'input' are rejected."""
    for bare in ("radio", "button", "input", "textbox", "checkbox",
                 "select", "textarea", "link", "label"):
        result = TinyWebBrowserFaculty._reject_underspecified_selector(bare, "click")
        assert result is not None, f"'{bare}' should be rejected"
        assert result["success"] is False
        assert "too generic" in result["error"]


@pytest.mark.core
def test_reject_bare_role_selectors(setup):
    """Bare role= selectors like 'role=radio', 'role=button' are rejected."""
    for role_type in ("radio", "button", "checkbox", "textbox", "input"):
        selector = f"role={role_type}"
        result = TinyWebBrowserFaculty._reject_underspecified_selector(selector, "click")
        assert result is not None, f"'{selector}' should be rejected"
        assert result["success"] is False
        assert "too generic" in result["error"]


@pytest.mark.core
def test_accept_qualified_role_selectors(setup):
    """Role selectors with [name=...] qualifier are accepted."""
    qualified = [
        'role=radio[name="Left is better"]',
        'role=button[name="Submit"]',
        'role=textbox[name="Enter your query"]',
        'role=checkbox[name="Donate query"]',
    ]
    for selector in qualified:
        result = TinyWebBrowserFaculty._reject_underspecified_selector(selector, "click")
        assert result is None, f"'{selector}' should be accepted"


@pytest.mark.core
def test_accept_text_and_css_selectors(setup):
    """Text=, CSS class, ID, and :has-text() selectors are accepted."""
    valid = [
        "text=Submit",
        "text=Send",
        "#my-button",
        ".submit-btn",
        "button:has-text('Send')",
        "listitem:has-text('<unset query>')",
        "input[name=email]",
        "[data-testid='submit']",
        "div.results >> button",
    ]
    for selector in valid:
        result = TinyWebBrowserFaculty._reject_underspecified_selector(selector, "click")
        assert result is None, f"'{selector}' should be accepted"


@pytest.mark.core
def test_reject_empty_selector(setup):
    """Empty string selector is rejected with a helpful message."""
    result = TinyWebBrowserFaculty._reject_underspecified_selector("", "click")
    assert result is not None
    assert result["success"] is False
    assert "requires a selector" in result["error"]


@pytest.mark.core
def test_reject_case_insensitive(setup):
    """Rejection is case-insensitive ('Radio', 'BUTTON', 'Role=Radio')."""
    for selector in ("Radio", "BUTTON", "INPUT", "Role=Radio", "ROLE=BUTTON"):
        result = TinyWebBrowserFaculty._reject_underspecified_selector(selector, "click")
        assert result is not None, f"'{selector}' should be rejected (case insensitive)"


@pytest.mark.core
def test_error_message_suggests_alternatives(setup):
    """Error messages include actionable examples of qualified selectors."""
    result = TinyWebBrowserFaculty._reject_underspecified_selector("radio", "click")
    assert "role=radio[name=" in result["error"]
    assert "text=" in result["error"]
    assert "BROWSE" in result["error"]

    # role= variant also gives good suggestions
    result = TinyWebBrowserFaculty._reject_underspecified_selector("role=button", "click")
    assert "role=button[name=" in result["error"]


@pytest.mark.core
def test_constraints_mention_bare_selectors(setup):
    """The constraints prompt warns against bare element-type selectors."""
    faculty = TinyWebBrowserFaculty()
    prompt = faculty.actions_constraints_prompt()
    assert "bare element" in prompt.lower() or "click radio" in prompt.lower() or "too generic" in prompt.lower() or "Never use bare" in prompt
