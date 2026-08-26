from pathlib import Path
from dev_agent.agents.context_agent import ContextAgent
from dev_agent.agents.review_agent import ReviewAgent
from dev_agent.config.loader import load_config, render_default_config
from dev_agent.core.models import ContextPacket

class FakeCodexProvider:
    def available(self): return True
    def run(self, prompt, project_root, *, write_access=False, timeout_seconds=600): return "Resumo fake"

def test_context_agent_prioritizes_agents_and_docs(tmp_path: Path):
    (tmp_path / "dev-agent.yaml").write_text(render_default_config("Demo"), encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("Regra importante", encoding="utf-8")
    (tmp_path / "src").mkdir(); (tmp_path / "src" / "AGENTS.md").write_text("Regra específica", encoding="utf-8")
    (tmp_path / "docs").mkdir(); (tmp_path / "docs" / "guide.md").write_text("Guia", encoding="utf-8")
    agent = ContextAgent(tmp_path, load_config(tmp_path)); packet = agent.build("explicar guia")
    assert "AGENTS.md" in packet.documentation and packet.instructions == ["Regra importante", "Regra específica"]

def test_review_detects_literal_secret(tmp_path: Path):
    packet = ContextPacket(project_name="Demo", project_root=tmp_path, objective="review", git_diff='+ API_KEY = "secretvalue"')
    result = ReviewAgent().run(packet)
    assert "Possível segredo" in result.summary
