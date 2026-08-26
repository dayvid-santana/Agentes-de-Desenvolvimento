from pathlib import Path
from dev_agent.agents.git_agent import GitAgent
from dev_agent.config.loader import render_default_config
from dev_agent.core.orchestrator import Orchestrator
from dev_agent.memory.session_store import SessionStore

class FakeCodexProvider:
    def available(self): return True
    def run(self, prompt, project_root, *, write_access=False, timeout_seconds=600): return "Resposta fake"

def test_orchestrator_context_uses_fake_provider_and_session(tmp_path: Path):
    (tmp_path / "dev-agent.yaml").write_text(render_default_config("Demo"), encoding="utf-8")
    service = Orchestrator(tmp_path, FakeCodexProvider(), SessionStore(tmp_path / "session.json"))
    packet, result = service.context("Entender projeto")
    assert packet.project_name == "Demo" and result.agent == "context"

def test_commit_plan_groups_tests_and_code(tmp_path: Path, monkeypatch):
    agent = GitAgent(tmp_path)
    monkeypatch.setattr(agent.git, "status", lambda: " M src/main.py\n M tests/test_main.py")
    plan = agent.commit_plan()
    assert len(plan) == 2
    assert plan[0].message.startswith("feat:") or plan[0].message.startswith("feat(")
