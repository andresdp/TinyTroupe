import pytest
import os
import json
import tempfile

import sys
sys.path.insert(0, '..')
sys.path.insert(0, '../../')
sys.path.insert(0, '../../tinytroupe/')

from tinytroupe.utils.json import JsonSerializableRegistry, merge_dicts, remove_duplicate_items, post_init
from testing_utils import *


##############################################
# Tests for merge_dicts
##############################################

@pytest.mark.core
def test_merge_dicts_new_key():
    """Test adding a key that only exists in the additions dict."""
    current = {"a": 1}
    additions = {"b": 2}
    result = merge_dicts(current, additions)
    assert result == {"a": 1, "b": 2}

@pytest.mark.core
def test_merge_dicts_none_value_replaced():
    """Test that a None value in current is replaced by the additions value."""
    current = {"a": None}
    additions = {"a": 42}
    result = merge_dicts(current, additions)
    assert result == {"a": 42}

@pytest.mark.core
def test_merge_dicts_recursive():
    """Test recursive merging of nested dicts."""
    current = {"a": {"x": 1}}
    additions = {"a": {"y": 2}}
    result = merge_dicts(current, additions)
    assert result == {"a": {"x": 1, "y": 2}}

@pytest.mark.core
def test_merge_dicts_list_concatenation():
    """Test that lists are concatenated and duplicates removed."""
    current = {"a": [1, 2, 3]}
    additions = {"a": [3, 4, 5]}
    result = merge_dicts(current, additions)
    assert result == {"a": [1, 2, 3, 4, 5]}

@pytest.mark.core
def test_merge_dicts_list_no_dedup():
    """Test that duplicate removal can be disabled."""
    current = {"a": [1, 2, 3]}
    additions = {"a": [3, 4]}
    result = merge_dicts(current, additions, remove_duplicates=False)
    assert result == {"a": [1, 2, 3, 3, 4]}

@pytest.mark.core
def test_merge_dicts_type_conflict():
    """Test that merging different types raises TypeError."""
    current = {"a": [1, 2]}
    additions = {"a": "string"}
    with pytest.raises(TypeError):
        merge_dicts(current, additions)

@pytest.mark.core
def test_merge_dicts_same_type_no_overwrite_conflict():
    """Test that same-type different values raise ValueError when overwrite=False."""
    current = {"a": 1}
    additions = {"a": 2}
    with pytest.raises(ValueError):
        merge_dicts(current, additions, overwrite=False, error_on_conflict=True)

@pytest.mark.core
def test_merge_dicts_same_type_overwrite():
    """Test that same-type values can be overwritten."""
    current = {"a": 1}
    additions = {"a": 2}
    result = merge_dicts(current, additions, overwrite=True)
    assert result == {"a": 2}

@pytest.mark.core
def test_merge_dicts_same_type_no_overwrite_no_error():
    """Test that conflicts are silently ignored when error_on_conflict=False."""
    current = {"a": 1}
    additions = {"a": 2}
    result = merge_dicts(current, additions, overwrite=False, error_on_conflict=False)
    assert result == {"a": 1}

@pytest.mark.core
def test_merge_dicts_does_not_mutate_original():
    """Test that merge_dicts does not mutate the original dict."""
    current = {"a": 1}
    additions = {"b": 2}
    result = merge_dicts(current, additions)
    assert "b" not in current


##############################################
# Tests for remove_duplicate_items
##############################################

@pytest.mark.core
def test_remove_duplicate_items_basic():
    """Test basic duplicate removal."""
    assert remove_duplicate_items([1, 2, 3, 2, 1]) == [1, 2, 3]

@pytest.mark.core
def test_remove_duplicate_items_empty():
    """Test with empty list."""
    assert remove_duplicate_items([]) == []

@pytest.mark.core
def test_remove_duplicate_items_dicts():
    """Test duplicate removal with unhashable dict elements."""
    lst = [{"a": 1}, {"b": 2}, {"a": 1}]
    result = remove_duplicate_items(lst)
    assert len(result) == 2
    assert result[0] == {"a": 1}
    assert result[1] == {"b": 2}

@pytest.mark.core
def test_remove_duplicate_items_preserves_order():
    """Test that order is preserved."""
    assert remove_duplicate_items([3, 1, 2, 1, 3]) == [3, 1, 2]

@pytest.mark.core
def test_remove_duplicate_items_mixed_types():
    """Test with mixed types."""
    lst = [1, "a", 1, "a", 2]
    result = remove_duplicate_items(lst)
    assert result == [1, "a", 2]


##############################################
# Tests for JsonSerializableRegistry
##############################################

class SimpleSerializable(JsonSerializableRegistry):
    serializable_attributes = ["name", "value"]

    def __init__(self, name="test", value=42):
        self.name = name
        self.value = value

class NestedSerializable(JsonSerializableRegistry):
    serializable_attributes = ["label", "child"]

    def __init__(self, label="parent", child=None):
        self.label = label
        self.child = child

class SuppressedSerializable(JsonSerializableRegistry):
    serializable_attributes = ["name", "secret", "visible"]
    suppress_attributes_from_serialization = ["secret"]

    def __init__(self, name="test", secret="hidden", visible="shown"):
        self.name = name
        self.secret = secret
        self.visible = visible

class RenamedSerializable(JsonSerializableRegistry):
    serializable_attributes = ["internal_name"]
    serializable_attributes_renaming = {"internal_name": "externalName"}

    def __init__(self, internal_name="value"):
        self.internal_name = internal_name


@pytest.mark.core
def test_json_serializable_to_json():
    """Test basic serialization."""
    obj = SimpleSerializable(name="hello", value=99)
    result = obj.to_json()
    assert result["name"] == "hello"
    assert result["value"] == 99
    assert result["json_serializable_class_name"] == "SimpleSerializable"

@pytest.mark.core
def test_json_serializable_from_json():
    """Test basic deserialization."""
    data = {"json_serializable_class_name": "SimpleSerializable", "name": "world", "value": 7}
    obj = SimpleSerializable.from_json(data)
    assert obj.name == "world"
    assert obj.value == 7

@pytest.mark.core
def test_json_serializable_roundtrip():
    """Test serialization followed by deserialization."""
    original = SimpleSerializable(name="roundtrip", value=123)
    data = original.to_json()
    restored = SimpleSerializable.from_json(data)
    assert restored.name == original.name
    assert restored.value == original.value

@pytest.mark.core
def test_json_serializable_nested():
    """Test serialization with nested JsonSerializableRegistry objects."""
    child = SimpleSerializable(name="child_obj", value=10)
    parent = NestedSerializable(label="parent_obj", child=child)
    data = parent.to_json()
    assert data["child"]["name"] == "child_obj"
    assert data["child"]["json_serializable_class_name"] == "SimpleSerializable"

@pytest.mark.core
def test_json_serializable_suppressed_attributes():
    """Test that suppressed attributes are excluded from serialization."""
    obj = SuppressedSerializable(name="test", secret="top_secret", visible="yes")
    data = obj.to_json()
    assert "secret" not in data
    assert data["name"] == "test"
    assert data["visible"] == "yes"

@pytest.mark.core
def test_json_serializable_include_override():
    """Test the include parameter to override serializable attributes."""
    obj = SimpleSerializable(name="test", value=42)
    data = obj.to_json(include=["name"])
    assert "name" in data
    assert "value" not in data

@pytest.mark.core
def test_json_serializable_suppress_override():
    """Test the suppress parameter to suppress additional attributes."""
    obj = SimpleSerializable(name="test", value=42)
    data = obj.to_json(suppress=["value"])
    assert "name" in data
    assert "value" not in data

@pytest.mark.core
def test_json_serializable_file_io():
    """Test serialization to and from a file."""
    obj = SimpleSerializable(name="file_test", value=55)
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "test.json")
        obj.to_json(file_path=file_path)
        assert os.path.exists(file_path)

        restored = SimpleSerializable.from_json(file_path)
        assert restored.name == "file_test"
        assert restored.value == 55

@pytest.mark.core
def test_json_serializable_subclass_registration():
    """Test that subclasses are automatically registered."""
    assert "SimpleSerializable" in JsonSerializableRegistry.class_mapping
    assert "NestedSerializable" in JsonSerializableRegistry.class_mapping

@pytest.mark.core
def test_json_serializable_with_list_attribute():
    """Test serialization of list attributes."""
    class ListSerializable(JsonSerializableRegistry):
        serializable_attributes = ["items"]
        def __init__(self, items=None):
            self.items = items or []

    obj = ListSerializable(items=[1, 2, 3])
    data = obj.to_json()
    assert data["items"] == [1, 2, 3]

    restored = ListSerializable.from_json(data)
    assert restored.items == [1, 2, 3]

@pytest.mark.core
def test_json_serializable_attribute_renaming():
    """Test that attribute renaming works during serialization."""
    obj = RenamedSerializable(internal_name="renamed_value")
    data = obj.to_json()
    assert "externalName" in data
    assert data["externalName"] == "renamed_value"


##############################################
# Tests for post_init decorator
##############################################

@pytest.mark.core
def test_post_init_decorator():
    """Test the post_init decorator calls _post_init after __init__."""
    @post_init
    class MyClass:
        def __init__(self):
            self.init_called = True
            self.post_init_called = False

        def _post_init(self):
            self.post_init_called = True

    obj = MyClass()
    assert obj.init_called is True
    assert obj.post_init_called is True
