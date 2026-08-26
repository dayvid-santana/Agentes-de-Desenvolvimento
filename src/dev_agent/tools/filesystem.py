"""Operações de arquivo limitadas à raiz ativa."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from dev_agent.errors import PathOutsideProjectError


class FileContent(BaseModel):
    path: str
    content: str
    truncated: bool = False


class FileSystem:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()

    def resolve(self, path: str | Path) -> Path:
        candidate = Path(path)
        resolved = (self.project_root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
        try:
            resolved.relative_to(self.project_root)
        except ValueError as exc:
            raise PathOutsideProjectError(f"Caminho fora do projeto ativo: {path}") from exc
        return resolved

    def read_text(self, path: str | Path, max_chars: int | None = None) -> FileContent:
        target = self.resolve(path)
        content = target.read_text(encoding="utf-8")
        if max_chars is not None and len(content) > max_chars:
            return FileContent(path=str(target.relative_to(self.project_root)), content=content[:max_chars], truncated=True)
        return FileContent(path=str(target.relative_to(self.project_root)), content=content)

    def write_text(self, path: str | Path, content: str) -> Path:
        target = self.resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
        return target

    def list_files(self, pattern: str = "**/*") -> list[str]:
        return [str(item.relative_to(self.project_root)) for item in self.project_root.glob(pattern) if item.is_file()]

