import pytest

import sys
sys.path.insert(0, '..')
sys.path.insert(0, '../../')
sys.path.insert(0, '../../tinytroupe/')

from tinytroupe.utils.behavior import _compute_single_action_jaccard_similarity, next_action_jaccard_similarity
from testing_utils import *


##############################################
# Tests for _compute_single_action_jaccard_similarity
##############################################

@pytest.mark.core
def test_jaccard_identical_actions():
    """Test that identical actions have similarity 1.0."""
    action = {"type": "TALK", "target": "user", "content": "hello world"}
    result = _compute_single_action_jaccard_similarity(action, action)
    assert result == 1.0

@pytest.mark.core
def test_jaccard_different_types():
    """Test that actions with different types have similarity 0.0."""
    a1 = {"type": "TALK", "target": "user", "content": "hello"}
    a2 = {"type": "THINK", "target": "user", "content": "hello"}
    result = _compute_single_action_jaccard_similarity(a1, a2)
    assert result == 0.0

@pytest.mark.core
def test_jaccard_different_targets():
    """Test that actions with different targets have similarity 0.0."""
    a1 = {"type": "TALK", "target": "alice", "content": "hello"}
    a2 = {"type": "TALK", "target": "bob", "content": "hello"}
    result = _compute_single_action_jaccard_similarity(a1, a2)
    assert result == 0.0

@pytest.mark.core
def test_jaccard_same_type_target_different_content():
    """Test actions with same type/target but different content."""
    a1 = {"type": "TALK", "target": "user", "content": "hello world"}
    a2 = {"type": "TALK", "target": "user", "content": "goodbye world"}
    result = _compute_single_action_jaccard_similarity(a1, a2)
    assert 0.0 < result < 1.0

@pytest.mark.core
def test_jaccard_empty_content():
    """Test actions with empty content."""
    a1 = {"type": "TALK", "target": "user", "content": ""}
    a2 = {"type": "TALK", "target": "user", "content": ""}
    result = _compute_single_action_jaccard_similarity(a1, a2)
    assert result == 1.0

@pytest.mark.core
def test_jaccard_no_type_or_target():
    """Test actions without type or target fields (similarity based on content only)."""
    a1 = {"content": "hello world"}
    a2 = {"content": "hello world"}
    result = _compute_single_action_jaccard_similarity(a1, a2)
    assert result == 1.0

@pytest.mark.core
def test_jaccard_missing_content_key():
    """Test actions without content key (defaults to empty string)."""
    a1 = {"type": "TALK", "target": "user"}
    a2 = {"type": "TALK", "target": "user"}
    result = _compute_single_action_jaccard_similarity(a1, a2)
    assert result == 1.0  # both default to empty string


##############################################
# Tests for next_action_jaccard_similarity
##############################################

class MockAgent:
    """Minimal mock agent for testing next_action_jaccard_similarity."""
    def __init__(self, last_action=None):
        self._last_action = last_action
    
    def last_remembered_action(self):
        return self._last_action

@pytest.mark.core
def test_next_action_similarity_no_current_action():
    """Test that similarity is 0.0 when agent has no current action."""
    agent = MockAgent(last_action=None)
    proposed = {"type": "TALK", "target": "user", "content": "hello"}
    result = next_action_jaccard_similarity(agent, proposed)
    assert result == 0.0

@pytest.mark.core
def test_next_action_similarity_single_action():
    """Test similarity with a single proposed action."""
    current = {"type": "TALK", "target": "user", "content": "hello world"}
    agent = MockAgent(last_action=current)
    proposed = {"type": "TALK", "target": "user", "content": "hello world"}
    result = next_action_jaccard_similarity(agent, proposed)
    assert result == 1.0

@pytest.mark.core
def test_next_action_similarity_list_of_actions():
    """Test that max similarity is returned for a list of proposed actions."""
    current = {"type": "TALK", "target": "user", "content": "hello world"}
    agent = MockAgent(last_action=current)
    proposed_list = [
        {"type": "THINK", "target": "self", "content": "something else"},  # Different type => 0.0
        {"type": "TALK", "target": "user", "content": "hello world"},  # Identical => 1.0
    ]
    result = next_action_jaccard_similarity(agent, proposed_list)
    assert result == 1.0

@pytest.mark.core
def test_next_action_similarity_empty_list():
    """Test that empty proposed list returns 0.0."""
    current = {"type": "TALK", "target": "user", "content": "hello"}
    agent = MockAgent(last_action=current)
    result = next_action_jaccard_similarity(agent, [])
    assert result == 0.0

@pytest.mark.core
def test_next_action_similarity_list_with_non_dicts():
    """Test that non-dict items in a list are skipped."""
    current = {"type": "TALK", "target": "user", "content": "hello"}
    agent = MockAgent(last_action=current)
    proposed_list = ["not_a_dict", 42, None]
    result = next_action_jaccard_similarity(agent, proposed_list)
    assert result == 0.0
