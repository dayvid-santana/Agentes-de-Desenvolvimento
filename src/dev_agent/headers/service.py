"""Aplicação central de cabeçalhos sem quebrar formatos especiais."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from dev_agent.config.models import DevAgentConfig

class HeaderService:
    _line = {".py": "#", ".yaml": "#", ".yml": "#", ".ps1": "#", ".sh": "#", ".js": "//", ".ts": "//", ".tsx": "//", ".jsx": "//", ".java": "//", ".cs": "//", ".c": "//", ".cpp": "//", ".h": "//", ".sql": "--"}
    _block = {".css": ("/*", " * ", " */"), ".html": ("<!--", "", "-->"), ".xml": ("<!--", "", "-->"), ".md": ("<!--", "", "-->")}
    _excluded_names = {"package-lock.json", "poetry.lock", "uv.lock"}

    def __init__(self, config: DevAgentConfig) -> None:
        self.config = config

    def supports(self, path: Path) -> bool:
        return path.name not in self._excluded_names and path.suffix.lower() in {*self._line, *self._block}

    def apply(self, path: Path, content: str, objective: str, task_key: str, existing: str | None = None) -> str:
        if not self.config.headers.enabled or not self.supports(path):
            return content
        old = existing if existing is not None else ""
        initial = not old or self.config.project.name not in old[:2000]
        entry = self._entry(path, objective, initial)
        if task_key and f"DevAgent-Task: {task_key}" in old:
            return content
        marker = self._marker(path, task_key)
        entry = f"{entry}{marker}\n"
        if initial:
            return self._insert_safely(path, content, entry, initial=True)
        if not self.config.headers.history:
            return content
        return self._insert_safely(path, content, entry, initial=False)

    def _entry(self, path: Path, objective: str, initial: bool) -> str:
        fields = ([self.config.project.name] if initial else []) + [f"Autor: {self.config.headers.author}", f"Data: {date.today().strftime(self.config.headers.date_format)}", f"Objetivo: {objective}"]
        if path.suffix.lower() in self._line:
            prefix = self._line[path.suffix.lower()]
            return "\n".join(f"{prefix} {field}" for field in fields) + "\n"
        opening, prefix, closing = self._block[path.suffix.lower()]
        return opening + "\n" + "\n".join(f"{prefix}{field}" for field in fields) + "\n" + closing + "\n"

    def _marker(self, path: Path, task_key: str) -> str:
        if not task_key:
            return ""
        if path.suffix.lower() in self._line:
            return f"{self._line[path.suffix.lower()]} DevAgent-Task: {task_key}\n"
        opening, prefix, closing = self._block[path.suffix.lower()]
        return f"{opening}\n{prefix}DevAgent-Task: {task_key}\n{closing}\n"

    def _insert_safely(self, path: Path, content: str, entry: str, initial: bool) -> str:
        if path.suffix.lower() == ".py" and content.startswith("#!"):
            line, _, rest = content.partition("\n")
            return f"{line}\n{entry}\n{rest}"
        if path.suffix.lower() == ".xml" and content.startswith("<?xml"):
            line, _, rest = content.partition("\n")
            return f"{line}\n{entry}\n{rest}"
        return f"{entry}\n{content}" if initial else f"{entry}\n{content}"
