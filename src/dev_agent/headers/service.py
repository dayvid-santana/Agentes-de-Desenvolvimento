"""Aplicação central de cabeçalhos sem quebrar formatos especiais."""
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Preservar cabeçalhos existentes durante a documentação de código.
# DevAgent
# Autor: Dayvid Santana
# Data: 01/09/2026
# Objetivo: Substituir o propósito genérico de cabeçalhos inseridos em lote.
from __future__ import annotations

from datetime import date
from pathlib import Path

from dev_agent.config.models import DevAgentConfig

class HeaderService:
    _line = {".py": "#", ".yaml": "#", ".yml": "#", ".ps1": "#", ".sh": "#", ".js": "//", ".ts": "//", ".tsx": "//", ".jsx": "//", ".java": "//", ".cs": "//", ".c": "//", ".cpp": "//", ".h": "//", ".sql": "--"}
    _block = {".css": ("/*", " * ", " */"), ".html": ("<!--", "", "-->"), ".xml": ("<!--", "", "-->"), ".md": ("<!--", "", "-->")}
    _excluded_names = {"package-lock.json", "poetry.lock", "uv.lock"}
    _generic_batch_purpose = "Adicionar cabeçalho padrão."

    def __init__(self, config: DevAgentConfig) -> None:
        self.config = config

    def supports(self, path: Path) -> bool:
        return path.name not in self._excluded_names and path.suffix.lower() in {*self._line, *self._block}

    def has_header(self, path: Path, content: str) -> bool:
        """Indica se o arquivo já inicia com um cabeçalho preservável."""
        if not self.supports(path):
            return False
        text = content.lstrip("\ufeff")
        if path.suffix.lower() == ".py" and text.startswith("#!"):
            text = text.partition("\n")[2]
        if path.suffix.lower() == ".xml" and text.startswith("<?xml"):
            text = text.partition("\n")[2]
        first = next((line.lstrip() for line in text.splitlines() if line.strip()), "")
        if path.suffix.lower() in self._line:
            return first.startswith(self._line[path.suffix.lower()])
        return first.startswith(self._block[path.suffix.lower()][0])

    def needs_header(self, path: Path, content: str) -> bool:
        return self.config.headers.enabled and self.supports(path) and (
            not self.has_header(path, content) or self._has_generic_batch_purpose(path, content)
        )

    def apply(self, path: Path, content: str, objective: str, task_key: str, existing: str | None = None) -> str:
        old = existing if existing is not None else content
        if not self.needs_header(path, old):
            return content
        if self._has_generic_batch_purpose(path, old):
            return self._replace_generic_batch_purpose(path, content, objective)
        entry = self._entry(path, objective, initial=True)
        marker = self._marker(path, task_key)
        entry = f"{entry}{marker}\n"
        return self._insert_safely(path, content, entry, initial=True)

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

    def _has_generic_batch_purpose(self, path: Path, content: str) -> bool:
        return (
            self.has_header(path, content)
            and "DevAgent-Task: headers" in content
            and f"Objetivo: {self._generic_batch_purpose}" in content
        )

    def _replace_generic_batch_purpose(self, path: Path, content: str, objective: str) -> str:
        if path.suffix.lower() in self._line:
            current = f"{self._line[path.suffix.lower()]} Objetivo: {self._generic_batch_purpose}"
            replacement = f"{self._line[path.suffix.lower()]} Objetivo: {objective}"
        else:
            prefix = self._block[path.suffix.lower()][1]
            current = f"{prefix}Objetivo: {self._generic_batch_purpose}"
            replacement = f"{prefix}Objetivo: {objective}"
        return content.replace(current, replacement, 1)

    def _insert_safely(self, path: Path, content: str, entry: str, initial: bool) -> str:
        if path.suffix.lower() == ".py" and content.startswith("#!"):
            line, _, rest = content.partition("\n")
            return f"{line}\n{entry}\n{rest}"
        if path.suffix.lower() == ".xml" and content.startswith("<?xml"):
            line, _, rest = content.partition("\n")
            return f"{line}\n{entry}\n{rest}"
        return f"{entry}\n{content}" if initial else f"{entry}\n{content}"
