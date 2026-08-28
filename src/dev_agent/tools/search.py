"""Busca textual e de arquivos, preservando limites de contexto."""
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Aplicar o escopo de arquivos configurado às buscas de contexto.
from __future__ import annotations

import fnmatch
from pathlib import Path


class FileSearchTool:
    def __init__(self, root: Path, excludes: list[str], includes: list[str] | None = None) -> None:
        self.root = root
        self.excludes = excludes
        self.includes = includes or ["**/*"]

    def is_excluded(self, path: Path) -> bool:
        text = path.relative_to(self.root).as_posix()
        return any(
            fnmatch.fnmatch(text, pattern)
            or any(fnmatch.fnmatch(part, pattern.rstrip("/**")) for part in path.parts)
            for pattern in self.excludes
        )

    def allows(self, path: Path) -> bool:
        if self.is_excluded(path):
            return False
        text = path.relative_to(self.root).as_posix()
        return any(fnmatch.fnmatch(text, pattern) for pattern in self.includes)

    def find_names(self, terms: list[str], limit: int = 12) -> list[str]:
        lowered = [term.lower() for term in terms if len(term) > 2]
        found: list[str] = []
        for path in self.root.rglob("*"):
            if not path.is_file() or not self.allows(path):
                continue
            relative = path.relative_to(self.root).as_posix()
            if any(term in relative.lower() for term in lowered):
                found.append(relative)
            if len(found) >= limit:
                break
        return found

    def search_text(self, terms: list[str], limit: int = 12) -> list[str]:
        lowered = [term.lower() for term in terms if len(term) > 2]
        found: list[str] = []
        for path in self.root.rglob("*"):
            if not path.is_file() or not self.allows(path) or path.stat().st_size > 1_000_000:
                continue
            try:
                content = path.read_text(encoding="utf-8").lower()
            except (OSError, UnicodeDecodeError):
                continue
            if any(term in content for term in lowered):
                found.append(path.relative_to(self.root).as_posix())
            if len(found) >= limit:
                break
        return found
