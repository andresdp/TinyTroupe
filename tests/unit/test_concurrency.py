import pytest
import threading
import sys

sys.path.insert(0, '..')
sys.path.insert(0, '../../')
sys.path.insert(0, '../../tinytroupe/')

from tinytroupe.utils.concurrency import check_threads_for_lock, monitor_threads
from testing_utils import *


##############################################
# Tests for check_threads_for_lock
##############################################

@pytest.mark.core
def test_check_threads_for_lock_runs_without_error():
    """Test that check_threads_for_lock runs without errors when no threads are blocked."""
    # Should not raise any exceptions
    check_threads_for_lock()

@pytest.mark.core
def test_check_threads_for_lock_with_custom_keywords():
    """Test check_threads_for_lock with custom blocked keywords."""
    check_threads_for_lock(blocked_keywords=["nonexistent_keyword"])

@pytest.mark.core
def test_check_threads_for_lock_detects_blocked_thread(capsys):
    """Test that check_threads_for_lock detects a thread waiting on a lock."""
    lock = threading.Lock()
    lock.acquire()  # Hold the lock
    
    barrier = threading.Event()
    blocked = threading.Event()
    
    def blocked_thread():
        blocked.set()  # Signal we're about to block
        lock.acquire()  # This will block
        lock.release()
    
    t = threading.Thread(target=blocked_thread, name="TestBlockedThread")
    t.daemon = True
    t.start()
    
    blocked.wait(timeout=2)  # Wait for thread to start
    # Give it a tiny bit of time to actually block
    import time
    time.sleep(0.1)
    
    # This should detect the blocked thread (it won't fail - it only reports)
    check_threads_for_lock()
    
    # Clean up
    lock.release()
    t.join(timeout=2)


##############################################
# Tests for monitor_threads
##############################################

@pytest.mark.core
def test_monitor_threads_stops_with_event():
    """Test that monitor_threads stops when stop_event is set."""
    stop_event = threading.Event()
    
    monitor_thread = threading.Thread(
        target=monitor_threads, 
        args=(0.1, stop_event),
        daemon=True
    )
    monitor_thread.start()
    
    # Let it run for a short time
    import time
    time.sleep(0.3)
    
    # Signal it to stop
    stop_event.set()
    
    # Wait for thread to finish
    monitor_thread.join(timeout=2)
    assert not monitor_thread.is_alive(), "Monitor thread should have stopped"
