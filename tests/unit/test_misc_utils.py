import pytest

import sys
sys.path.insert(0, '..')
sys.path.insert(0, '../../')
sys.path.insert(0, '../../tinytroupe/')

from tinytroupe.utils.misc import custom_hash, fresh_id, reset_fresh_id, first_non_none, name_or_empty
from testing_utils import *


##############################################
# Tests for custom_hash
##############################################

@pytest.mark.core
def test_custom_hash_deterministic():
    """Test that custom_hash produces the same result for the same input."""
    assert custom_hash("hello") == custom_hash("hello")

@pytest.mark.core
def test_custom_hash_different_inputs():
    """Test that different inputs produce different hashes."""
    assert custom_hash("hello") != custom_hash("world")

@pytest.mark.core
def test_custom_hash_various_types():
    """Test that custom_hash works with various types."""
    assert isinstance(custom_hash(42), str)
    assert isinstance(custom_hash([1, 2, 3]), str)
    assert isinstance(custom_hash({"key": "value"}), str)
    assert isinstance(custom_hash(None), str)

@pytest.mark.core
def test_custom_hash_is_sha256():
    """Test that custom_hash returns a valid SHA-256 hex digest."""
    h = custom_hash("test")
    assert len(h) == 64  # SHA-256 hex digest length
    assert all(c in '0123456789abcdef' for c in h)


##############################################
# Tests for fresh_id
##############################################

@pytest.mark.core
def test_fresh_id_increments():
    """Test that fresh_id returns incrementing IDs in the same scope."""
    scope = "test_increments"
    reset_fresh_id(scope)
    id1 = fresh_id(scope)
    id2 = fresh_id(scope)
    id3 = fresh_id(scope)
    assert id1 < id2 < id3

@pytest.mark.core
def test_fresh_id_independent_scopes():
    """Test that different scopes have independent ID sequences."""
    scope_a = "test_scope_a"
    scope_b = "test_scope_b"
    reset_fresh_id(scope_a)
    reset_fresh_id(scope_b)
    id_a = fresh_id(scope_a)
    id_b = fresh_id(scope_b)
    assert id_a == id_b == 1

@pytest.mark.core
def test_fresh_id_default_scope():
    """Test that fresh_id works with the default scope."""
    reset_fresh_id("default")
    id1 = fresh_id()
    id2 = fresh_id()
    assert id2 == id1 + 1


##############################################
# Tests for reset_fresh_id
##############################################

@pytest.mark.core
def test_reset_fresh_id_specific_scope():
    """Test resetting a specific scope."""
    scope = "test_reset_scope"
    reset_fresh_id(scope)
    fresh_id(scope)
    fresh_id(scope)
    reset_fresh_id(scope)
    assert fresh_id(scope) == 1

@pytest.mark.core
def test_reset_fresh_id_all_scopes():
    """Test resetting all scopes."""
    scope1 = "test_reset_all_1"
    scope2 = "test_reset_all_2"
    fresh_id(scope1)
    fresh_id(scope2)
    reset_fresh_id()  # reset all
    assert fresh_id(scope1) == 1
    assert fresh_id(scope2) == 1

@pytest.mark.core
def test_reset_fresh_id_nonexistent_scope():
    """Test that resetting a non-existent scope does nothing."""
    reset_fresh_id("nonexistent_scope")  # Should not raise


##############################################
# Tests for first_non_none
##############################################

@pytest.mark.core
def test_first_non_none_basic():
    """Test basic first_non_none behavior."""
    assert first_non_none(None, None, 3) == 3

@pytest.mark.core
def test_first_non_none_first_is_value():
    """Test when first arg is not None."""
    assert first_non_none(1, 2, 3) == 1

@pytest.mark.core
def test_first_non_none_all_none():
    """Test when all args are None."""
    assert first_non_none(None, None, None) is None

@pytest.mark.core
def test_first_non_none_empty():
    """Test with no arguments."""
    assert first_non_none() is None

@pytest.mark.core
def test_first_non_none_zero_is_valid():
    """Test that zero is returned (not confused with None)."""
    assert first_non_none(None, 0, 1) == 0

@pytest.mark.core
def test_first_non_none_false_is_valid():
    """Test that False is returned (not confused with None)."""
    assert first_non_none(None, False, True) is False


##############################################
# Tests for name_or_empty
##############################################

@pytest.mark.core
def test_name_or_empty_with_named():
    """Test with a named entity."""
    class MockEntity:
        def __init__(self, name):
            self.name = name
    assert name_or_empty(MockEntity("Test")) == "Test"

@pytest.mark.core
def test_name_or_empty_with_none():
    """Test with None entity."""
    assert name_or_empty(None) == ""
