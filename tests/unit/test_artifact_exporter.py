import pytest
import os
import json
import tempfile

import sys
sys.path.insert(0, '..')
sys.path.insert(0, '../../')
sys.path.insert(0, '../../tinytroupe/')

from tinytroupe.extraction import ArtifactExporter
from testing_utils import *


##############################################
# Tests for ArtifactExporter edge cases
##############################################

@pytest.fixture
def tmp_exporter():
    """Create an exporter with a temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield ArtifactExporter(base_output_folder=tmpdir), tmpdir

@pytest.mark.core
def test_artifact_exporter_invalid_chars_in_name(tmp_exporter):
    """Test that invalid characters in artifact name are sanitized."""
    exporter, tmpdir = tmp_exporter
    artifact_data = {"content": "Test content", "name": "test"}
    
    # Name with invalid characters
    exporter.export("test/artifact:name", artifact_data, content_type="record", target_format="json")
    
    # File should be created with sanitized name (/ and : replaced with -)
    expected_path = os.path.join(tmpdir, "record", "test-artifact-name.json")
    assert os.path.exists(expected_path), f"Expected file at {expected_path}"

@pytest.mark.core
def test_artifact_exporter_compose_filepath_with_content_type(tmp_exporter):
    """Test _compose_filepath uses content_type as subfolder."""
    exporter, tmpdir = tmp_exporter
    path = exporter._compose_filepath("test data", "artifact", "MyType", "txt")
    assert "MyType" in path
    assert path.endswith("artifact.txt")

@pytest.mark.core
def test_artifact_exporter_compose_filepath_no_content_type(tmp_exporter):
    """Test _compose_filepath with no content_type."""
    exporter, tmpdir = tmp_exporter
    path = exporter._compose_filepath("test data", "artifact", None, "txt")
    assert path.endswith("artifact.txt")

@pytest.mark.core
def test_artifact_exporter_compose_filepath_no_format(tmp_exporter):
    """Test _compose_filepath with no target_format defaults to txt for strings."""
    exporter, tmpdir = tmp_exporter
    path = exporter._compose_filepath("string data", "artifact", "record", None)
    assert path.endswith("artifact.txt")

@pytest.mark.core
def test_artifact_exporter_unsupported_format(tmp_exporter):
    """Test that unsupported format raises ValueError."""
    exporter, tmpdir = tmp_exporter
    with pytest.raises(ValueError, match="Unsupported target format"):
        exporter.export("test", "Test content", content_type="text", target_format="xlsx")

@pytest.mark.core
def test_artifact_exporter_json_with_string_data(tmp_exporter):
    """Test that exporting a string as JSON raises ValueError."""
    exporter, tmpdir = tmp_exporter
    with pytest.raises(ValueError, match="must be a dictionary"):
        exporter.export("test", "string data", content_type="text", target_format="json")

@pytest.mark.core
def test_artifact_exporter_invalid_data_type(tmp_exporter):
    """Test that invalid data types raise ValueError."""
    exporter, tmpdir = tmp_exporter
    with pytest.raises(ValueError, match="must be either a string or a dictionary"):
        exporter.export("test", 12345, content_type="text", target_format="txt")

@pytest.mark.core
def test_artifact_exporter_docx_invalid_format(tmp_exporter):
    """Test that invalid original format for DOCX export raises ValueError."""
    exporter, tmpdir = tmp_exporter
    with pytest.raises(ValueError, match="original format cannot be"):
        exporter.export("test", "Content", content_type="text", content_format="csv", target_format="docx")

@pytest.mark.core
def test_artifact_exporter_text_with_dict(tmp_exporter):
    """Test exporting a dict as text extracts the 'content' field."""
    exporter, tmpdir = tmp_exporter
    artifact_data = {"content": "Extracted content", "title": "Test"}
    exporter.export("test_dict_text", artifact_data, content_type="text", target_format="txt")
    
    filepath = os.path.join(tmpdir, "text", "test_dict_text.txt")
    assert os.path.exists(filepath)
    with open(filepath, "r") as f:
        assert "Extracted content" in f.read()

@pytest.mark.core
def test_artifact_exporter_markdown_format(tmp_exporter):
    """Test exporting with 'markdown' target format."""
    exporter, tmpdir = tmp_exporter
    exporter.export("test_md", "# Heading\nContent", content_type="doc", target_format="markdown")
    
    filepath = os.path.join(tmpdir, "doc", "test_md.markdown")
    assert os.path.exists(filepath)

@pytest.mark.core
def test_artifact_exporter_creates_directories(tmp_exporter):
    """Test that nested directories are created automatically."""
    exporter, tmpdir = tmp_exporter
    exporter.export("deep_test", "Content", content_type="deep/nested/type", target_format="txt")
    
    filepath = os.path.join(tmpdir, "deep/nested/type", "deep_test.txt")
    assert os.path.exists(filepath)

@pytest.mark.core
def test_artifact_exporter_multiple_invalid_chars(tmp_exporter):
    """Test sanitization with multiple different invalid characters."""
    exporter, tmpdir = tmp_exporter
    artifact_data = {"content": "Test", "key": "value"}
    
    # Name with multiple invalid chars: / \ : * ? " < > | \n \t
    name = 'a/b\\c:d*e?f"g<h>i|j'
    exporter.export(name, artifact_data, content_type="record", target_format="json")
    
    expected_name = "a-b-c-d-e-f-g-h-i-j"
    expected_path = os.path.join(tmpdir, "record", f"{expected_name}.json")
    assert os.path.exists(expected_path), f"Expected sanitized file at {expected_path}"
