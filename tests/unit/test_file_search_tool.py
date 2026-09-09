"""Regressão: um diretório inacessível em qualquer lugar da árvore (link/junction
quebrado, permissão negada) não pode derrubar a varredura inteira."""
import subprocess
import sys
from pathlib import Path

import pytest

from dev_agent.tools.search import FileSearchTool


def _make_dangling_junction(root: Path) -> Path:
    """Reproduz o bug real: um junction do Windows que apontava para um diretório
    válido, cujo alvo foi depois removido (ex.: projeto renomeado/movido) — como
    o `.uv-python` do `uv` quando o diretório do projeto muda de lugar."""
    target = root / "target"
    target.mkdir()
    link = root / "broken"
    subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True)
    target.rmdir()
    return link


@pytest.mark.skipif(sys.platform != "win32", reason="junctions são um conceito do Windows")
def test_walk_files_tolerates_a_dangling_junction(tmp_path: Path) -> None:
    _make_dangling_junction(tmp_path)
    (tmp_path / "real.py").write_text("x = 1\n", encoding="utf-8")

    tool = FileSearchTool(tmp_path, excludes=[])
    found = {path.name for path in tool.walk_files()}

    assert "real.py" in found


@pytest.mark.skipif(sys.platform != "win32", reason="junctions são um conceito do Windows")
def test_find_names_still_works_alongside_a_dangling_junction(tmp_path: Path) -> None:
    _make_dangling_junction(tmp_path)
    src = tmp_path / "src"
    src.mkdir()
    (src / "service.py").write_text("x = 1\n", encoding="utf-8")

    tool = FileSearchTool(tmp_path, excludes=[])

    assert tool.find_names(["service"]) == ["src/service.py"]


def test_walk_files_prunes_excluded_directories_before_descending(tmp_path: Path) -> None:
    excluded_dir = tmp_path / "node_modules"
    excluded_dir.mkdir()
    (excluded_dir / "lib.js").write_text("x", encoding="utf-8")
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")

    tool = FileSearchTool(tmp_path, excludes=["node_modules/**"])
    found = {path.name for path in tool.walk_files()}

    assert "app.py" in found
    assert "lib.js" not in found
