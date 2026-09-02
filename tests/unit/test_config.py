# DevAgent
# Autor: Dayvid Santana
# Data: 02/09/2026
# Objetivo: Cobrir a configuração de caminhos de contexto para agentes.
from pathlib import Path
import pytest
from dev_agent.config.loader import discover_project, load_config, render_default_config
from dev_agent.errors import InvalidProjectConfigError, ProjectNotFoundError


def test_default_config_declares_agent_context_paths(tmp_path: Path):
    (tmp_path / "dev-agent.yaml").write_text(render_default_config("project"), encoding="utf-8")

    config = load_config(tmp_path)

    assert config.context.contextosAgentes == ["agent-context/**"]

def test_discovers_config_from_nested_directory(tmp_path: Path):
    root = tmp_path / "project"; nested = root / "src" / "domain"; nested.mkdir(parents=True)
    (root / "dev-agent.yaml").write_text(render_default_config("project"), encoding="utf-8")
    assert discover_project(nested) == root

def test_discovery_requires_configuration(tmp_path: Path):
    with pytest.raises(ProjectNotFoundError): discover_project(tmp_path)

def test_invalid_yaml_has_clear_domain_error(tmp_path: Path):
    (tmp_path / "dev-agent.yaml").write_text("project: [", encoding="utf-8")
    with pytest.raises(InvalidProjectConfigError): load_config(tmp_path)

def test_config_validates_required_project_name(tmp_path: Path):
    (tmp_path / "dev-agent.yaml").write_text("project: {}", encoding="utf-8")
    with pytest.raises(InvalidProjectConfigError): load_config(tmp_path)
