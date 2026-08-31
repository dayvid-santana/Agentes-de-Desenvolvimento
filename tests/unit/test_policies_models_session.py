from pathlib import Path
# dev-agent
# Autor: Dayvid Santana
# Data: 31/08/2026
# Objetivo: Cobrir redação de segredos em contexto persistido.
# DevAgent-Task: resolve-audit-gaps-20260831

import pytest
from dev_agent.core.models import ContextPacket, SubAgentResult
from dev_agent.errors import UnsafeCommandError
from dev_agent.memory.session_store import ProjectSession, SessionStore
from dev_agent.security.architecture_guard import ArchitectureGuard
from dev_agent.security.command_policy import CommandPolicy
from dev_agent.security.redaction import SensitiveDataRedactor

def test_context_packet_and_result_defaults(tmp_path: Path):
    packet = ContextPacket(project_name="x", project_root=tmp_path, objective="teste")
    result = SubAgentResult(agent="context", summary="ok")
    assert packet.relevant_files == [] and result.files_changed == []

def test_session_switch_discards_previous_project(tmp_path: Path):
    store = SessionStore(tmp_path / "session.json")
    store.activate(ProjectSession(project_root=tmp_path / "a", project_name="A", recent_tasks=["old"]))
    store.activate(ProjectSession(project_root=tmp_path / "b", project_name="B"))
    assert store.load().project_name == "B" and store.load().recent_tasks == []

def test_architecture_guard_and_destructive_command_policy():
    assert ArchitectureGuard().assess("Trocar framework de backend").required
    with pytest.raises(UnsafeCommandError): CommandPolicy().ensure_safe("git reset --hard")
    CommandPolicy().ensure_safe("git reset --hard", confirmed=True)


def test_redactor_removes_secret_values_but_preserves_context():
    text = 'API_KEY="super-secret-value"\nAuthorization: Bearer abcdefghijklmnop\nname = "demo"'
    redacted = SensitiveDataRedactor.redact(text)
    assert "super-secret-value" not in redacted
    assert "abcdefghijklmnop" not in redacted
    assert 'name = "demo"' in redacted
