"""Persistência pequena da sessão ativa em LOCALAPPDATA."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from pydantic import BaseModel, Field


class ProjectSession(BaseModel):
    project_root: Path
    project_name: str
    objective: str | None = None
    recent_tasks: list[str] = Field(default_factory=list)
    related_files: list[str] = Field(default_factory=list)
    approved_architecture_decisions: list[str] = Field(default_factory=list)
    summaries: list[str] = Field(default_factory=list)
    open_risks: list[str] = Field(default_factory=list)


class SessionStore:
    def __init__(self, path: Path | None = None) -> None:
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "DevAgent"
        self.path = path or base / "current-session.json"

    def load(self) -> ProjectSession | None:
        if not self.path.exists():
            return None
        return ProjectSession.model_validate_json(self.path.read_text(encoding="utf-8"))

    def activate(self, session: ProjectSession) -> None:
        current = self.load()
        if current and current.project_root != session.project_root:
            self.clear()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(session.model_dump_json(indent=2), encoding="utf-8")
        except PermissionError:
            self.path = Path(tempfile.gettempdir()) / "DevAgent" / "current-session.json"
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(session.model_dump_json(indent=2), encoding="utf-8")

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()
