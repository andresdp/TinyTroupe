import pytest
import os
import json
import tempfile

import sys
sys.path.insert(0, '..')
sys.path.insert(0, '../../')
sys.path.insert(0, '../../tinytroupe/')

from tinytroupe.tools.tiny_word_processor import TinyWordProcessor
from tinytroupe.extraction import ArtifactExporter
from testing_utils import *


##############################################
# Tests for TinyWordProcessor initialization
##############################################

@pytest.mark.core
def test_word_processor_initialization():
    """Test TinyWordProcessor initializes correctly."""
    wp = TinyWordProcessor()
    assert wp.name == "wordprocessor"
    assert wp.owner is None
    assert wp.exporter is None
    assert wp.enricher is None
    assert wp.real_world_side_effects is False

@pytest.mark.core
def test_word_processor_with_exporter():
    """Test TinyWordProcessor with exporter."""
    with tempfile.TemporaryDirectory() as tmpdir:
        exporter = ArtifactExporter(base_output_folder=tmpdir)
        wp = TinyWordProcessor(exporter=exporter)
        assert wp.exporter is exporter


##############################################
# Tests for write_document
##############################################

@pytest.mark.core
def test_write_document_with_exporter():
    """Test write_document exports documents to various formats."""
    with tempfile.TemporaryDirectory() as tmpdir:
        exporter = ArtifactExporter(base_output_folder=tmpdir)
        wp = TinyWordProcessor(exporter=exporter)
        
        wp.write_document(title="Test Doc", content="This is test content.", author="Tester")
        
        # Check that md, docx and json files were created
        assert os.path.exists(os.path.join(tmpdir, "Document", "Test Doc.Tester.md"))
        assert os.path.exists(os.path.join(tmpdir, "Document", "Test Doc.Tester.docx"))
        assert os.path.exists(os.path.join(tmpdir, "Document", "Test Doc.Tester.json"))
        
        # Verify JSON content
        with open(os.path.join(tmpdir, "Document", "Test Doc.Tester.json"), "r") as f:
            data = json.load(f)
            assert data["title"] == "Test Doc"
            assert "test content" in data["content"]
            assert data["author"] == "Tester"

@pytest.mark.core
def test_write_document_without_author():
    """Test write_document without author uses title as artifact name."""
    with tempfile.TemporaryDirectory() as tmpdir:
        exporter = ArtifactExporter(base_output_folder=tmpdir)
        wp = TinyWordProcessor(exporter=exporter)
        
        wp.write_document(title="No Author Doc", content="Content here.")
        
        assert os.path.exists(os.path.join(tmpdir, "Document", "No Author Doc.md"))
        assert os.path.exists(os.path.join(tmpdir, "Document", "No Author Doc.json"))

@pytest.mark.core
def test_write_document_no_exporter():
    """Test write_document without exporter does not raise."""
    wp = TinyWordProcessor()
    # Should not raise an exception
    wp.write_document(title="Test", content="Content")


##############################################
# Tests for _process_action
##############################################

@pytest.mark.core
def test_process_action_write_document():
    """Test _process_action processes WRITE_DOCUMENT action."""
    with tempfile.TemporaryDirectory() as tmpdir:
        exporter = ArtifactExporter(base_output_folder=tmpdir)
        wp = TinyWordProcessor(exporter=exporter)
        
        action = {
            "type": "WRITE_DOCUMENT",
            "content": json.dumps({"title": "Action Doc", "content": "Action content."})
        }
        
        result = wp._process_action(None, action)
        assert result is True

@pytest.mark.core
def test_process_action_write_document_dict_content():
    """Test _process_action with dict content (not string)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        exporter = ArtifactExporter(base_output_folder=tmpdir)
        wp = TinyWordProcessor(exporter=exporter)
        
        action = {
            "type": "WRITE_DOCUMENT",
            "content": {"title": "Dict Doc", "content": "Dict content."}
        }
        
        result = wp._process_action(None, action)
        assert result is True

@pytest.mark.core
def test_process_action_unknown_type():
    """Test _process_action returns False for unknown action types."""
    wp = TinyWordProcessor()
    action = {"type": "UNKNOWN_ACTION", "content": "something"}
    result = wp._process_action(None, action)
    assert result is False

@pytest.mark.core
def test_process_action_none_content():
    """Test _process_action returns False when content is None."""
    wp = TinyWordProcessor()
    action = {"type": "WRITE_DOCUMENT", "content": None}
    result = wp._process_action(None, action)
    assert result is False

@pytest.mark.core
def test_process_action_invalid_json():
    """Test _process_action handles invalid JSON gracefully."""
    wp = TinyWordProcessor()
    action = {"type": "WRITE_DOCUMENT", "content": "not valid json {{{"}
    result = wp._process_action(None, action)
    # Should return False (error handling catches the exception)
    assert result is False


##############################################
# Tests for prompt methods
##############################################

@pytest.mark.core
def test_actions_definitions_prompt():
    """Test that actions_definitions_prompt returns expected content."""
    wp = TinyWordProcessor()
    prompt = wp.actions_definitions_prompt()
    assert "WRITE_DOCUMENT" in prompt
    assert "title" in prompt
    assert "content" in prompt

@pytest.mark.core
def test_actions_constraints_prompt():
    """Test that actions_constraints_prompt returns expected content."""
    wp = TinyWordProcessor()
    prompt = wp.actions_constraints_prompt()
    assert "WRITE_DOCUMENT" in prompt
    assert isinstance(prompt, str)
    assert len(prompt) > 0
