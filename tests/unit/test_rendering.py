import pytest
import json
from datetime import datetime

import sys
sys.path.insert(0, '..')
sys.path.insert(0, '../../')
sys.path.insert(0, '../../tinytroupe/')

from tinytroupe.utils.rendering import (
    inject_html_css_style_prefix,
    break_text_at_length,
    pretty_datetime,
    dedent,
    wrap_text,
    RichTextStyle,
)
from testing_utils import *


##############################################
# Tests for inject_html_css_style_prefix
##############################################

@pytest.mark.core
def test_inject_html_css_style_prefix_basic():
    """Test injecting a style prefix into a simple HTML string."""
    html = '<div style="color: red;">Hello</div>'
    result = inject_html_css_style_prefix(html, 'font-size: 20px')
    assert 'font-size: 20px' in result
    assert 'color: red' in result

@pytest.mark.core
def test_inject_html_css_style_prefix_multiple():
    """Test injecting a prefix into HTML with multiple style attributes."""
    html = '<div style="color: red;"><span style="font-weight: bold;">Text</span></div>'
    result = inject_html_css_style_prefix(html, 'margin: 0')
    assert result.count('margin: 0') == 2

@pytest.mark.core
def test_inject_html_css_style_prefix_no_style():
    """Test that HTML without style attributes is unchanged."""
    html = '<div class="test">Hello</div>'
    result = inject_html_css_style_prefix(html, 'font-size: 20px')
    assert result == html


##############################################
# Tests for break_text_at_length
##############################################

@pytest.mark.core
def test_break_text_at_length_within_limit():
    """Test that short text is returned unchanged."""
    text = "Hello World"
    assert break_text_at_length(text, max_length=50) == text

@pytest.mark.core
def test_break_text_at_length_exceeds_limit():
    """Test that long text is truncated with ellipsis marker."""
    text = "Hello World, this is a long text"
    result = break_text_at_length(text, max_length=11)
    assert result == "Hello World (...)"

@pytest.mark.core
def test_break_text_at_length_none():
    """Test that None max_length returns text unchanged."""
    text = "Hello World"
    assert break_text_at_length(text, max_length=None) == text

@pytest.mark.core
def test_break_text_at_length_dict_input():
    """Test that dict input is converted to JSON string."""
    data = {"key": "value"}
    result = break_text_at_length(data, max_length=5)
    assert result.startswith("{")
    assert result.endswith("(...)")

@pytest.mark.core
def test_break_text_at_length_dict_no_limit():
    """Test that dict input without limit returns full JSON."""
    data = {"key": "value"}
    result = break_text_at_length(data, max_length=None)
    parsed = json.loads(result)
    assert parsed == data


##############################################
# Tests for pretty_datetime
##############################################

@pytest.mark.core
def test_pretty_datetime():
    """Test datetime formatting."""
    dt = datetime(2025, 3, 15, 14, 30)
    assert pretty_datetime(dt) == "2025-03-15 14:30"

@pytest.mark.core
def test_pretty_datetime_midnight():
    """Test midnight datetime formatting."""
    dt = datetime(2024, 1, 1, 0, 0)
    assert pretty_datetime(dt) == "2024-01-01 00:00"


##############################################
# Tests for dedent
##############################################

@pytest.mark.core
def test_dedent_removes_indentation():
    """Test that indentation is properly removed."""
    text = """
        Hello
        World
    """
    result = dedent(text)
    assert result == "Hello\nWorld"

@pytest.mark.core
def test_dedent_no_indentation():
    """Test that text without indentation is unchanged (after strip)."""
    text = "Hello\nWorld"
    result = dedent(text)
    assert result == "Hello\nWorld"


##############################################
# Tests for wrap_text
##############################################

@pytest.mark.core
def test_wrap_text_basic():
    """Test text wrapping at default width."""
    text = "A " * 60  # 120 characters
    result = wrap_text(text)
    lines = result.split('\n')
    assert all(len(line) <= 100 for line in lines)

@pytest.mark.core
def test_wrap_text_custom_width():
    """Test text wrapping with custom width."""
    text = "Hello World " * 10
    result = wrap_text(text, width=20)
    lines = result.split('\n')
    assert all(len(line) <= 20 for line in lines)

@pytest.mark.core
def test_wrap_text_short():
    """Test that short text is not wrapped."""
    text = "Short text"
    result = wrap_text(text, width=100)
    assert result == text


##############################################
# Tests for RichTextStyle
##############################################

@pytest.mark.core
def test_rich_text_style_stimulus_conversation():
    """Test style for CONVERSATION stimulus."""
    style = RichTextStyle.get_style_for("stimulus", "CONVERSATION")
    assert style == RichTextStyle.STIMULUS_CONVERSATION_STYLE

@pytest.mark.core
def test_rich_text_style_stimulus_thought():
    """Test style for THOUGHT stimulus."""
    style = RichTextStyle.get_style_for("stimulus", "THOUGHT")
    assert style == RichTextStyle.STIMULUS_THOUGHT_STYLE

@pytest.mark.core
def test_rich_text_style_stimulus_default():
    """Test default style for unknown stimulus type."""
    style = RichTextStyle.get_style_for("stimulus", "UNKNOWN")
    assert style == RichTextStyle.STIMULUS_DEFAULT_STYLE

@pytest.mark.core
def test_rich_text_style_stimuli_alias():
    """Test that 'stimuli' works as alias for 'stimulus'."""
    style = RichTextStyle.get_style_for("stimuli", "CONVERSATION")
    assert style == RichTextStyle.STIMULUS_CONVERSATION_STYLE

@pytest.mark.core
def test_rich_text_style_action_done():
    """Test style for DONE action."""
    style = RichTextStyle.get_style_for("action", "DONE")
    assert style == RichTextStyle.ACTION_DONE_STYLE

@pytest.mark.core
def test_rich_text_style_action_talk():
    """Test style for TALK action."""
    style = RichTextStyle.get_style_for("action", "TALK")
    assert style == RichTextStyle.ACTION_TALK_STYLE

@pytest.mark.core
def test_rich_text_style_action_think():
    """Test style for THINK action."""
    style = RichTextStyle.get_style_for("action", "THINK")
    assert style == RichTextStyle.ACTION_THINK_STYLE

@pytest.mark.core
def test_rich_text_style_action_default():
    """Test default style for unknown action type."""
    style = RichTextStyle.get_style_for("action", "UNKNOWN")
    assert style == RichTextStyle.ACTION_DEFAULT_STYLE

@pytest.mark.core
def test_rich_text_style_intervention():
    """Test style for intervention."""
    style = RichTextStyle.get_style_for("intervention")
    assert style == RichTextStyle.INTERVENTION_DEFAULT_STYLE

@pytest.mark.core
def test_rich_text_style_unknown_kind():
    """Test that unknown kind returns None."""
    style = RichTextStyle.get_style_for("unknown_kind")
    assert style is None
