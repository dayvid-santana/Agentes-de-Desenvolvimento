# DevAgent
# Autor: Dayvid Santana
# Data: 01/09/2026
# Objetivo: Cobrir a captura de diff staged e a classificação livre de tipo do GitAgent.
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Cobrir o encadeamento de agentes especialistas.
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Cobrir os novos agentes de documentação, teste e reprodução.
import subprocess
from pathlib import Path
from dev_agent.agents.git_agent import GitAgent
from dev_agent.config.loader import render_default_config
from dev_agent.core.orchestrator import Orchestrator
from dev_agent.memory.session_store import SessionStore
from dev_agent.tools.git import GitTool


def _real_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "servico.py").write_text("def calcular():\n    return 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "servico.py"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)
    return repo

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


def test_commit_plan_uses_provider_to_describe_the_real_diff(tmp_path: Path, monkeypatch):
    class RecordingProvider(FakeCodexProvider):
        def __init__(self):
            self.prompts: list[str] = []

        def run(self, prompt, project_root, *, write_access=False, timeout_seconds=600):
            self.prompts.append(prompt)
            return "MENSAGEM: feat(auth): valida CPF antes de salvar o cadastro\nJUSTIFICATIVA: Único arquivo alterado, mudança coesa."

    provider = RecordingProvider()
    agent = GitAgent(tmp_path, provider)
    monkeypatch.setattr(agent.git, "status", lambda: " M src/cadastro.py")
    monkeypatch.setattr(agent.git, "diff_paths", lambda paths: "diff --git a/src/cadastro.py b/src/cadastro.py\n+validar_cpf(cpf)")

    plan = agent.commit_plan()

    assert len(plan) == 1
    assert plan[0].message == "feat(auth): valida CPF antes de salvar o cadastro"
    assert plan[0].rationale == "Único arquivo alterado, mudança coesa."
    assert "validar_cpf(cpf)" in provider.prompts[0]


def test_commit_plan_includes_new_file_content_for_untracked_files(tmp_path: Path, monkeypatch):
    class RecordingProvider(FakeCodexProvider):
        def __init__(self):
            self.prompts: list[str] = []

        def run(self, prompt, project_root, *, write_access=False, timeout_seconds=600):
            self.prompts.append(prompt)
            return "MENSAGEM: feat(relatorios): adiciona exportação em CSV\nJUSTIFICATIVA: Novo módulo autocontido."

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "exportar_csv.py").write_text("def exportar(): return 'csv'", encoding="utf-8")

    provider = RecordingProvider()
    agent = GitAgent(tmp_path, provider)
    monkeypatch.setattr(agent.git, "status", lambda: "?? src/exportar_csv.py")

    plan = agent.commit_plan()

    assert plan[0].message == "feat(relatorios): adiciona exportação em CSV"
    assert "def exportar" in provider.prompts[0]


def test_commit_plan_falls_back_when_provider_is_unavailable(tmp_path: Path, monkeypatch):
    agent = GitAgent(tmp_path, provider=None)
    monkeypatch.setattr(agent.git, "status", lambda: " M src/main.py")
    plan = agent.commit_plan()
    assert plan[0].message == "feat(scope): descreve a alteração principal"


def test_diff_paths_captures_staged_changes(tmp_path: Path):
    repo = _real_repo(tmp_path)
    (repo / "servico.py").write_text("def calcular():\n    return 2\n", encoding="utf-8")
    subprocess.run(["git", "add", "servico.py"], cwd=repo, check=True)

    diff = GitTool(repo).diff_paths(["servico.py"])

    assert "return 2" in diff, "alterações staged devem aparecer no diff usado para gerar a sugestão de commit"


def test_commit_plan_does_not_fall_back_when_changes_are_staged(tmp_path: Path):
    """Reproduz o defeito relatado: `git diff` (sem HEAD) fica vazio para arquivos staged,
    fazendo o commit_plan cair no texto genérico mesmo com um diff real disponível."""
    repo = _real_repo(tmp_path)
    (repo / "servico.py").write_text("def calcular():\n    return 2\n", encoding="utf-8")
    subprocess.run(["git", "add", "servico.py"], cwd=repo, check=True)

    class RecordingProvider(FakeCodexProvider):
        def __init__(self):
            self.prompts: list[str] = []

        def run(self, prompt, project_root, *, write_access=False, timeout_seconds=600):
            self.prompts.append(prompt)
            return "MENSAGEM: fix(servico): corrige valor retornado por calcular\nJUSTIFICATIVA: Corrige o retorno incorreto da função."

    provider = RecordingProvider()
    plan = GitAgent(repo, provider).commit_plan()

    assert plan[0].message == "fix(servico): corrige valor retornado por calcular"
    assert "return 2" in provider.prompts[0], "o diff staged real deve chegar ao provider, não ficar vazio"


def test_commit_plan_lets_the_llm_pick_a_type_other_than_the_heuristic_default(tmp_path: Path, monkeypatch):
    class RecordingProvider(FakeCodexProvider):
        def run(self, prompt, project_root, *, write_access=False, timeout_seconds=600):
            assert "feat, fix, refactor, test, docs, chore, build, ci, perf, style" in prompt
            assert "pista fraca" in prompt
            return "MENSAGEM: fix(cadastro): corrige validação de CPF duplicada\nJUSTIFICATIVA: Bug real corrigido, não recurso novo."

    agent = GitAgent(tmp_path, RecordingProvider())
    monkeypatch.setattr(agent.git, "status", lambda: " M src/cadastro.py")
    monkeypatch.setattr(agent.git, "diff_paths", lambda paths: "diff --git a/src/cadastro.py b/src/cadastro.py\n-if cpf:\n+if cpf and not duplicado(cpf):")

    plan = agent.commit_plan()

    # O bucket é agrupado como "feat" por heurística de caminho, mas o LLM pode
    # classificar como "fix" quando o diff mostra uma correção — a sugestão final
    # deve respeitar a classificação do LLM, não a heurística.
    assert plan[0].message.startswith("fix(")


def test_task_runs_specialists(tmp_path: Path, monkeypatch):
    from dev_agent.core.models import SubAgentResult

    (tmp_path / "dev-agent.yaml").write_text(render_default_config("Demo"), encoding="utf-8")
    service = Orchestrator(tmp_path, FakeCodexProvider(), SessionStore(tmp_path / "session.json"))
    monkeypatch.setattr(service.git, "diff", lambda staged=False: "")
    monkeypatch.setattr("dev_agent.core.orchestrator.TestAgent.run", lambda self, packet: SubAgentResult(agent="test", summary="ok"))
    results = service.task("Adicionar validação simples")
    expected = {"requirements", "code_documentation", "test_author", "bug_reproduction", "documentation_writer", "security", "database", "api_contract", "quality", "dependency", "performance", "frontend", "observability", "release", "refactor"}
    assert {item.agent for item in results} >= expected


def test_changed_files_include_deleted_paths(tmp_path: Path, monkeypatch):
    (tmp_path / "dev-agent.yaml").write_text(render_default_config("Demo"), encoding="utf-8")
    path = tmp_path / "src" / "obsolete.py"; path.parent.mkdir(); path.write_text("value = 1", encoding="utf-8")
    service = Orchestrator(tmp_path, FakeCodexProvider(), SessionStore(tmp_path / "session.json"))
    before = service._file_snapshot()
    path.unlink()
    assert "src\\obsolete.py" in service._changed_files(before)
