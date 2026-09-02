# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Cobrir os agentes especialistas adicionados ao DevAgent.
# DevAgent-Task: debug-evidence-20260828
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Cobrir a seleção de código e dependências de contexto.
# DevAgent-Task: context-code-selection-20260828
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Cobrir documentação de código, testes e reprodução de bugs.
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Importar e cobrir cada agente em módulo próprio.
# DevAgent
# Autor: Dayvid Santana
# Data: 01/09/2026
# Objetivo: Cobrir a análise somente leitura de padrões de projeto.
# DevAgent
# Autor: Dayvid Santana
# Data: 01/09/2026
# Objetivo: Cobrir a orientação de modelagem de código para reutilização externa.
# DevAgent
# Autor: Dayvid Santana
# Data: 01/09/2026
# Objetivo: Cobrir a exigência de documentação de todas as declarações selecionadas.
# DevAgent
# Autor: Dayvid Santana
# Data: 02/09/2026
# Objetivo: Cobrir a seleção progressiva de instruções para agentes de IA.
from pathlib import Path
from dev_agent.agents.api_contract_agent import ApiContractAgent
from dev_agent.agents.bug_reproduction_agent import BugReproductionAgent
from dev_agent.agents.code_documentation_agent import CodeDocumentationAgent
from dev_agent.agents.code_modeling_agent import CodeModelingAgent
from dev_agent.agents.context_agent import ContextAgent
from dev_agent.agents.database_agent import DatabaseAgent
from dev_agent.agents.debug_agent import DebugAgent
from dev_agent.agents.dependency_agent import DependencyAgent
from dev_agent.agents.design_patterns_agent import DesignPatternsAgent
from dev_agent.agents.documentation_writer_agent import DocumentationWriterAgent
from dev_agent.agents.frontend_agent import FrontendAgent
from dev_agent.agents.observability_agent import ObservabilityAgent
from dev_agent.agents.performance_agent import PerformanceAgent
from dev_agent.agents.project_documentation_agent import ProjectDocumentationAgent
from dev_agent.agents.quality_agent import QualityAgent
from dev_agent.agents.refactor_agent import RefactorAgent
from dev_agent.agents.release_agent import ReleaseAgent
from dev_agent.agents.requirements_agent import RequirementsAgent
from dev_agent.agents.review_agent import ReviewAgent
from dev_agent.agents.security_agent import SecurityAgent
from dev_agent.agents.test_author_agent import TestAuthorAgent
from dev_agent.config.loader import load_config, render_default_config
from dev_agent.core.models import ContextPacket
from dev_agent.tools import tests as test_tools

class FakeCodexProvider:
    def available(self): return True
    def run(self, prompt, project_root, *, write_access=False, timeout_seconds=600): return "Resumo fake"

def test_context_agent_loads_only_root_and_scope_agent_instructions(tmp_path: Path):
    (tmp_path / "dev-agent.yaml").write_text(render_default_config("Demo"), encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("Regra importante", encoding="utf-8")
    (tmp_path / "src").mkdir(); (tmp_path / "src" / "AGENTS.md").write_text("Regra específica", encoding="utf-8")
    (tmp_path / "docs").mkdir(); (tmp_path / "docs" / "guide.md").write_text("Guia", encoding="utf-8")
    agent = ContextAgent(tmp_path, load_config(tmp_path)); packet = agent.build("explicar guia")
    assert "AGENTS.md" in packet.documentation and packet.instructions == ["Regra importante"]


def test_context_agent_loads_scoped_agent_instructions_for_selected_source(tmp_path: Path):
    (tmp_path / "dev-agent.yaml").write_text(render_default_config("Demo"), encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("Regra global", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "AGENTS.md").write_text("Regra do codigo", encoding="utf-8")
    (tmp_path / "src" / "service.py").write_text("def run(): pass", encoding="utf-8")

    packet = ContextAgent(tmp_path, load_config(tmp_path)).build("Corrigir src/service.py")

    assert packet.instructions == ["Regra global", "Regra do codigo"]


def test_context_agent_loads_only_relevant_agent_context_referenced_by_agents_md(tmp_path: Path):
    (tmp_path / "dev-agent.yaml").write_text(render_default_config("Demo"), encoding="utf-8")
    (tmp_path / "agent-context").mkdir()
    (tmp_path / "agent-context" / "api.md").write_text("Contrato de API", encoding="utf-8")
    (tmp_path / "agent-context" / "database.md").write_text("Modelo de dados", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text(
        "Regra global\n- [API](agent-context/api.md): endpoints, contratos e HTTP.\n"
        "- [Banco de dados](agent-context/database.md): persistencia e migrations.",
        encoding="utf-8",
    )

    packet = ContextAgent(tmp_path, load_config(tmp_path)).build("Alterar endpoint da API")

    assert "agent-context/api.md" in packet.relevant_files
    assert "agent-context/database.md" not in packet.relevant_files
    assert packet.instructions[-1] == "Contrato de API"


def test_context_agent_matches_documentar_with_documentacao_context(tmp_path: Path):
    (tmp_path / "dev-agent.yaml").write_text(render_default_config("Demo"), encoding="utf-8")
    (tmp_path / "agent-context").mkdir()
    (tmp_path / "agent-context" / "documentation.md").write_text("Padrao humano", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text(
        "- [Documentação humana](agent-context/documentation.md): README e documentação.",
        encoding="utf-8",
    )

    packet = ContextAgent(tmp_path, load_config(tmp_path)).build("Documentar o projeto")

    assert "agent-context/documentation.md" in packet.relevant_files


def test_context_agent_rejects_link_outside_configured_agent_context(tmp_path: Path):
    (tmp_path / "dev-agent.yaml").write_text(render_default_config("Demo"), encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "security.md").write_text("Documento humano", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text(
        "- [Segurança](docs/security.md): autenticação e permissões.",
        encoding="utf-8",
    )

    packet = ContextAgent(tmp_path, load_config(tmp_path)).build("Revisar segurança")

    assert packet.instructions == ["- [Segurança](docs/security.md): autenticação e permissões."]


def test_context_agent_does_not_load_fallback_docs_for_changed_source(tmp_path: Path):
    (tmp_path / "dev-agent.yaml").write_text(render_default_config("Demo"), encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("Regra importante", encoding="utf-8")
    (tmp_path / "docs").mkdir(); (tmp_path / "docs" / "guide.md").write_text("Guia", encoding="utf-8")
    (tmp_path / "src").mkdir(); (tmp_path / "src" / "service.py").write_text("def run(): pass", encoding="utf-8")
    packet = ContextAgent(tmp_path, load_config(tmp_path)).build("investigar falha", git_diff="+++ b/src/service.py\n")
    assert "src/service.py" in packet.relevant_files
    assert "docs/guide.md" not in packet.relevant_files


def test_context_agent_respects_include_and_follows_local_dependencies(tmp_path: Path):
    config = render_default_config("Demo").replace(
        "include: [src/**, tests/**, docs/**, AGENTS.md, README.md]",
        "include: [src/**, tests/**]",
    )
    (tmp_path / "dev-agent.yaml").write_text(config, encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "private").mkdir()
    (tmp_path / "src" / "workflow.py").write_text("from .validator import validate", encoding="utf-8")
    (tmp_path / "src" / "validator.py").write_text("def validate(): pass", encoding="utf-8")
    (tmp_path / "tests" / "test_workflow.py").write_text("def test_workflow(): pass", encoding="utf-8")
    (tmp_path / "private" / "workflow_notes.py").write_text("workflow", encoding="utf-8")

    packet = ContextAgent(tmp_path, load_config(tmp_path)).build("Corrigir src/workflow.py")

    assert {"src/workflow.py", "src/validator.py", "tests/test_workflow.py"} <= set(packet.relevant_files)
    assert "private/workflow_notes.py" not in packet.relevant_files


def test_context_agent_includes_explicit_untracked_changes(tmp_path: Path):
    (tmp_path / "dev-agent.yaml").write_text(render_default_config("Demo"), encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "new_service.py").write_text("def run(): pass", encoding="utf-8")
    packet = ContextAgent(tmp_path, load_config(tmp_path)).build("Documentar serviço", changed_files=["src/new_service.py"])
    assert "src/new_service.py" in packet.relevant_files


def test_debug_agent_uses_test_evidence_and_read_only_provider(tmp_path: Path):
    class RecordingProvider(FakeCodexProvider):
        def __init__(self): self.prompt = ""; self.write_access = True
        def run(self, prompt, project_root, *, write_access=False, timeout_seconds=600):
            self.prompt, self.write_access = prompt, write_access
            return "Diagnóstico: mais provável."

    class FailingTests:
        def run(self):
            return test_tools.TestResult(command="pytest", exit_code=1, stdout="1 failed", stderr="AssertionError: esperado", failed=1)

    provider = RecordingProvider()
    packet = ContextPacket(project_name="Demo", project_root=tmp_path, objective="falha no cadastro", git_diff="+++ b/src/service.py\n", file_contents={"src/service.py": "def run(): pass"})
    result = DebugAgent(provider, FailingTests()).run(packet)
    assert result.tests_executed == ["pytest"] and result.warnings
    assert "AssertionError: esperado" in provider.prompt and not provider.write_access

def test_review_detects_literal_secret(tmp_path: Path):
    packet = ContextPacket(project_name="Demo", project_root=tmp_path, objective="review", git_diff='+ API_KEY = "secretvalue"')
    result = ReviewAgent().run(packet)
    assert "Possível segredo" in result.summary


def test_specialist_agents_use_read_only_provider(tmp_path: Path):
    packet = ContextPacket(project_name="Demo", project_root=tmp_path, objective="Adicionar tela", git_diff="+ def view(): pass")
    agents = [RequirementsAgent, CodeModelingAgent, SecurityAgent, DatabaseAgent, ApiContractAgent, QualityAgent, DependencyAgent, DesignPatternsAgent, PerformanceAgent, FrontendAgent, ObservabilityAgent, ReleaseAgent, RefactorAgent]
    for agent_type in agents:
        result = agent_type(FakeCodexProvider()).run(packet)
        assert result.agent and result.summary == "Resumo fake"


def test_code_modeling_agent_requests_a_copyable_structured_response(tmp_path: Path):
    class RecordingProvider(FakeCodexProvider):
        def __init__(self):
            self.prompt = ""
            self.write_access = True

        def run(self, prompt, project_root, *, write_access=False, timeout_seconds=600):
            self.prompt = prompt
            self.write_access = write_access
            return "Modelo proposto"

    provider = RecordingProvider()
    result = CodeModelingAgent(provider).run(ContextPacket(project_name="Demo", project_root=tmp_path, objective="Modelar faturas"))

    assert result.agent == "code_modeling"
    assert "Pontos de extensão para novas features" in provider.prompt
    assert not provider.write_access


def test_documentation_writer_receives_write_access(tmp_path: Path):
    class RecordingProvider(FakeCodexProvider):
        def __init__(self):
            self.write_access = False

        def run(self, prompt, project_root, *, write_access=False, timeout_seconds=600):
            self.write_access = write_access
            return "Documentação avaliada"

    provider = RecordingProvider()
    packet = ContextPacket(project_name="Demo", project_root=tmp_path, objective="Adicionar tela")
    result = DocumentationWriterAgent(provider).run(packet)
    assert result.agent == "documentation_writer" and provider.write_access


def test_project_documentation_agent_receives_write_access(tmp_path: Path):
    class RecordingProvider(FakeCodexProvider):
        def __init__(self): self.write_access = False
        def run(self, prompt, project_root, *, write_access=False, timeout_seconds=600):
            self.write_access = write_access
            return "Documentação do projeto atualizada"

    provider = RecordingProvider()
    result = ProjectDocumentationAgent(provider).run(ContextPacket(project_name="Demo", project_root=tmp_path, objective="Documentar o projeto atual"))
    assert result.agent == "project_documentation" and provider.write_access


def test_code_documentation_and_test_author_receive_write_access(tmp_path: Path):
    class RecordingProvider(FakeCodexProvider):
        def __init__(self):
            self.accesses: list[bool] = []

        def run(self, prompt, project_root, *, write_access=False, timeout_seconds=600):
            self.accesses.append(write_access)
            return "Alteração avaliada"

    provider = RecordingProvider()
    packet = ContextPacket(project_name="Demo", project_root=tmp_path, objective="Criar serviço", file_contents={"src/service.py": "def run(): pass"}, relevant_files=["src/service.py"])
    assert CodeDocumentationAgent(provider).run(packet).agent == "code_documentation"
    assert TestAuthorAgent(provider).run(packet).agent == "test_author"
    assert provider.accesses == [True, True]


def test_code_documentation_agent_requires_all_selected_declarations_to_be_documented(tmp_path: Path):
    class RecordingProvider(FakeCodexProvider):
        def __init__(self):
            self.prompt = ""

        def run(self, prompt, project_root, *, write_access=False, timeout_seconds=600):
            self.prompt = prompt
            return "Documentação atualizada"

    provider = RecordingProvider()
    CodeDocumentationAgent(provider).run(
        ContextPacket(
            project_name="Demo",
            project_root=tmp_path,
            objective="Documentar módulo",
            relevant_files=["src/service.py"],
            file_contents={"src/service.py": "class Service:\n    def run(self): pass\n"},
        )
    )

    assert "todas as classes, funções, métodos e declarações de tipos" in provider.prompt
    assert "incluindo elementos privados" in provider.prompt


def test_bug_reproduction_is_read_only_and_skips_non_bug_requests(tmp_path: Path):
    class RecordingProvider(FakeCodexProvider):
        def __init__(self):
            self.write_access = True

        def run(self, prompt, project_root, *, write_access=False, timeout_seconds=600):
            self.write_access = write_access
            return "Passos de reprodução"

    provider = RecordingProvider()
    bug = BugReproductionAgent(provider).run(ContextPacket(project_name="Demo", project_root=tmp_path, objective="Erro ao salvar fatura"))
    skipped = BugReproductionAgent(provider).run(ContextPacket(project_name="Demo", project_root=tmp_path, objective="Adicionar filtro"))
    assert bug.summary == "Passos de reprodução" and not provider.write_access
    assert "Não aplicável" in skipped.summary
