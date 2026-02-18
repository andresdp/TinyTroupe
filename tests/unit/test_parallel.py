import pytest
import time
from concurrent.futures import ThreadPoolExecutor

import sys
sys.path.insert(0, '..')
sys.path.insert(0, '../../')
sys.path.insert(0, '../../tinytroupe/')

from tinytroupe.utils.parallel import parallel_map, parallel_map_dict, parallel_map_cross
from testing_utils import *


##############################################
# Tests for parallel_map
##############################################

@pytest.mark.core
def test_parallel_map_basic():
    """Test basic parallel_map with simple operations."""
    result = parallel_map([1, 2, 3, 4], lambda x: x * 2)
    assert result == [2, 4, 6, 8]

@pytest.mark.core
def test_parallel_map_preserves_order():
    """Test that parallel_map returns results in the same order as inputs."""
    result = parallel_map([5, 3, 1, 4, 2], lambda x: x * 10)
    assert result == [50, 30, 10, 40, 20]

@pytest.mark.core
def test_parallel_map_empty_list():
    """Test parallel_map with an empty list."""
    result = parallel_map([], lambda x: x * 2)
    assert result == []

@pytest.mark.core
def test_parallel_map_single_element():
    """Test parallel_map with a single element."""
    result = parallel_map([42], lambda x: x + 1)
    assert result == [43]

@pytest.mark.core
def test_parallel_map_with_max_workers():
    """Test parallel_map with explicit max_workers."""
    result = parallel_map([1, 2, 3], lambda x: x ** 2, max_workers=2)
    assert result == [1, 4, 9]

@pytest.mark.core
def test_parallel_map_string_operations():
    """Test parallel_map with string operations."""
    result = parallel_map(["hello", "world"], lambda s: s.upper())
    assert result == ["HELLO", "WORLD"]

@pytest.mark.core
def test_parallel_map_actually_parallel():
    """Test that parallel_map actually executes in parallel (time-based)."""
    def slow_op(x):
        time.sleep(0.1)
        return x * 2
    
    start = time.time()
    result = parallel_map([1, 2, 3, 4], slow_op, max_workers=4)
    elapsed = time.time() - start
    
    assert result == [2, 4, 6, 8]
    # If sequential, would take ~0.4s; parallel should be much faster
    assert elapsed < 0.35, f"Expected parallel execution, but took {elapsed:.2f}s"


##############################################
# Tests for parallel_map_dict
##############################################

@pytest.mark.core
def test_parallel_map_dict_basic():
    """Test basic parallel_map_dict with simple operations."""
    d = {"a": 1, "b": 2, "c": 3}
    result = parallel_map_dict(d, lambda item: item[1] * 2)
    assert result == {"a": 2, "b": 4, "c": 6}

@pytest.mark.core
def test_parallel_map_dict_empty():
    """Test parallel_map_dict with empty dict."""
    result = parallel_map_dict({}, lambda item: item[1])
    assert result == {}

@pytest.mark.core
def test_parallel_map_dict_key_preservation():
    """Test that keys are preserved in the result."""
    d = {"x": 10, "y": 20}
    result = parallel_map_dict(d, lambda item: item[0] + str(item[1]))
    assert result == {"x": "x10", "y": "y20"}

@pytest.mark.core
def test_parallel_map_dict_with_max_workers():
    """Test parallel_map_dict with explicit max_workers."""
    d = {"a": 1, "b": 2}
    result = parallel_map_dict(d, lambda item: item[1] + 10, max_workers=1)
    assert result == {"a": 11, "b": 12}


##############################################
# Tests for parallel_map_cross
##############################################

@pytest.mark.core
def test_parallel_map_cross_basic():
    """Test basic cross-product parallel map."""
    result = parallel_map_cross(
        [[1, 2], [10, 20]],
        lambda a, b: a + b
    )
    # Cross product: (1,10), (1,20), (2,10), (2,20)
    assert sorted(result) == [11, 12, 21, 22]

@pytest.mark.core
def test_parallel_map_cross_single_iterable():
    """Test cross map with a single iterable."""
    result = parallel_map_cross(
        [[1, 2, 3]],
        lambda x: x * 2
    )
    assert sorted(result) == [2, 4, 6]

@pytest.mark.core
def test_parallel_map_cross_three_iterables():
    """Test cross map with three iterables."""
    result = parallel_map_cross(
        [[1, 2], ["a", "b"], [True]],
        lambda x, y, z: f"{x}{y}{z}"
    )
    assert len(result) == 4  # 2 * 2 * 1 = 4
    assert "1aTrue" in result
    assert "2bTrue" in result

@pytest.mark.core
def test_parallel_map_cross_empty_iterable():
    """Test cross map with an empty iterable (should return empty)."""
    result = parallel_map_cross(
        [[1, 2], []],
        lambda a, b: a + b
    )
    assert result == []

@pytest.mark.core
def test_parallel_map_cross_with_max_workers():
    """Test cross map with explicit max_workers."""
    result = parallel_map_cross(
        [[1, 2], [3, 4]],
        lambda a, b: a * b,
        max_workers=2
    )
    assert sorted(result) == [3, 4, 6, 8]
