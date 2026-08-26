"""Carregamento seguro e descoberta da configuração de projeto."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from dev_agent.config.models import DevAgentConfig
from dev_agent.errors import InvalidProjectConfigError, ProjectNotFoundError

CONFIG_NAME = "dev-agent.yaml"


def discover_project(start: Path) -> Path:
    """Encontra a raiz configurada, subindo a partir de ``start``."""
    current = start.expanduser().resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / CONFIG_NAME).is_file():
            return candidate
    raise ProjectNotFoundError(f"Não encontrei {CONFIG_NAME} a partir de {start}.")


def load_config(project_root: Path) -> DevAgentConfig:
    """Lê e valida a configuração YAML de uma raiz já descoberta."""
    config_path = project_root / CONFIG_NAME
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise InvalidProjectConfigError(f"Não foi possível ler {config_path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise InvalidProjectConfigError(f"YAML inválido em {config_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise InvalidProjectConfigError(f"{config_path} deve conter um objeto YAML.")
    try:
        return DevAgentConfig.model_validate(raw)
    except ValidationError as exc:
        raise InvalidProjectConfigError(f"Configuração inválida em {config_path}: {exc}") from exc


def render_default_config(project_name: str, author: str = "Dayvid Santana") -> str:
    """Gera um arquivo inicial explícito e fácil de editar."""
    return f'''project:
  name: {project_name}
  author: {author}

documentation:
  priority: [AGENTS.md, docs/**, README.md]

context:
  include: [src/**, tests/**, docs/**, AGENTS.md, README.md]
  exclude: [.git/**, .venv/**, venv/**, node_modules/**, dist/**, build/**, coverage/**, __pycache__/**, "*.pyc", "*.log"]
  max_files: 12
  max_file_chars: 16000
  max_total_chars: 80000
  dependency_depth: 1

testing:
  command: pytest

git:
  conventional_commits: true
  review_staged: true
  suggest_commit_split: true

headers:
  enabled: true
  author: {author}
  date_format: "%d/%m/%Y"
  history: true

security:
  require_architecture_approval: true
  require_destructive_command_approval: true
'''
