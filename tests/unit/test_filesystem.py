from pathlib import Path
import pytest
from dev_agent.errors import PathOutsideProjectError
from dev_agent.tools.filesystem import FileSystem

def test_filesystem_rejects_path_traversal(tmp_path: Path):
    fs = FileSystem(tmp_path / "root"); fs.project_root.mkdir()
    with pytest.raises(PathOutsideProjectError): fs.resolve("../outside.txt")

def test_filesystem_reads_and_writes_inside_project(tmp_path: Path):
    fs = FileSystem(tmp_path); fs.write_text("src/example.py", "x = 1")
    assert fs.read_text("src/example.py").content == "x = 1"
