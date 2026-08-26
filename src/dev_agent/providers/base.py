"""Contrato independente da implementação local do Codex."""
from __future__ import annotations
from typing import Protocol
from pathlib import Path

class LLMProvider(Protocol):
    def available(self) -> bool: ...
    def run(self, prompt: str, project_root: Path, *, write_access: bool = False, timeout_seconds: int = 600) -> str: ...
