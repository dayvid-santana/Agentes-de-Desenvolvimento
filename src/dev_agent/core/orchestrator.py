# dev-agent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Conectar depuração a evidências do projeto.
# DevAgent-Task: debug-evidence-20260828
"""Coordena subagents com pacotes isolados e serialização de escrita."""
from __future__ import annotations

# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Integrar agentes especialistas ao fluxo de tarefas.
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Centralizar a listagem de agentes disponíveis.
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Associar cada agente ao comando que o aciona.
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Integrar documentação, autoria de testes e reprodução de bugs.
import threading
from pathlib import Path

from dev_agent.agents.context_agent import ContextAgent
from dev_agent.agents.code_documentation_agent import CodeDocumentationAgent
from dev_agent.agents.bug_reproduction_agent import BugReproductionAgent
from dev_agent.agents.debug_agent import DebugAgent
from dev_agent.agents.documentation_agent import DocumentationAgent
from dev_agent.agents.git_agent import GitAgent
from dev_agent.agents.implementation_agent import ImplementationAgent
from dev_agent.agents.review_agent import ReviewAgent
from dev_agent.agents.specialist_agents import (
    ApiContractAgent,
    DatabaseAgent,
    DependencyAgent,
    DocumentationWriterAgent,
    FrontendAgent,
    ObservabilityAgent,
    PerformanceAgent,
    QualityAgent,
    RefactorAgent,
    ReleaseAgent,
    RequirementsAgent,
    SecurityAgent,
)
from dev_agent.agents.test_agent import TestAgent
from dev_agent.agents.test_author_agent import TestAuthorAgent
from dev_agent.config.loader import load_config
from dev_agent.core.models import AgentDescriptor, ContextPacket, SubAgentResult
from dev_agent.headers.service import HeaderService
from dev_agent.memory.session_store import ProjectSession, SessionStore
from dev_agent.providers.base import LLMProvider
from dev_agent.security.architecture_guard import ArchitectureGuard
from dev_agent.tools.git import GitTool
from dev_agent.tools.terminal import TerminalTool
from dev_agent.tools.tests import TestTool
from dev_agent.logging import event

class Orchestrator:
    _write_lock = threading.Lock()
    def __init__(self, root: Path, provider: LLMProvider, session_store: SessionStore | None = None) -> None:
        self.root, self.config, self.provider = root.resolve(), load_config(root.resolve()), provider
        self.store = session_store or SessionStore()
        self.context_agent = ContextAgent(self.root, self.config)
        self.git = GitTool(self.root)

    @staticmethod
    def available_agents() -> list[AgentDescriptor]:
        return [
            AgentDescriptor(name="context", description="Seleciona instruções, código, testes e diff relevantes.", mode="read", command="dev-agent context"),
            AgentDescriptor(name="requirements", description="Define critérios de aceite, escopo e ambiguidades.", mode="read", command='dev-agent task "<objetivo>"'),
            AgentDescriptor(name="implementation", description="Implementa a tarefa aprovada.", mode="write", command='dev-agent task "<objetivo>"'),
            AgentDescriptor(name="documentation_writer", description="Atualiza documentação quando a alteração exigir.", mode="write", command='dev-agent task "<objetivo>"'),
            AgentDescriptor(name="code_documentation", description="Documenta código alterado sem editar cabeçalhos existentes.", mode="write", command='dev-agent task "<objetivo>"'),
            AgentDescriptor(name="test_author", description="Cria testes de regressão para alterações de código.", mode="write", command='dev-agent task "<objetivo>"'),
            AgentDescriptor(name="bug_reproduction", description="Produz passos verificáveis para reproduzir falhas.", mode="read", command='dev-agent task "<relato de falha>"'),
            AgentDescriptor(name="test", description="Executa a suíte de testes configurada.", mode="execute", command="dev-agent test"),
            AgentDescriptor(name="review", description="Revisa o diff em busca de regressões e riscos.", mode="read", command="dev-agent review [--staged]"),
            AgentDescriptor(name="documentation", description="Avalia impactos de documentação.", mode="read", command='dev-agent task "<objetivo>"'),
            AgentDescriptor(name="debug", description="Diagnostica falhas com testes, diff e contexto.", mode="read", command='dev-agent debug "<problema>"'),
            AgentDescriptor(name="security", description="Analisa segurança, validação e exposição de dados.", mode="read", command='dev-agent task "<objetivo>"'),
            AgentDescriptor(name="database", description="Analisa persistência, migrations e integridade de dados.", mode="read", command='dev-agent task "<objetivo>"'),
            AgentDescriptor(name="api_contract", description="Protege compatibilidade de contratos de API.", mode="read", command='dev-agent task "<objetivo>"'),
            AgentDescriptor(name="quality", description="Identifica lacunas de testes e casos de borda.", mode="read", command='dev-agent task "<objetivo>"'),
            AgentDescriptor(name="dependency", description="Avalia dependências visíveis no contexto.", mode="read", command='dev-agent task "<objetivo>"'),
            AgentDescriptor(name="performance", description="Aponta possíveis gargalos e formas de medi-los.", mode="read", command='dev-agent task "<objetivo>"'),
            AgentDescriptor(name="frontend", description="Analisa interface, acessibilidade e responsividade.", mode="read", command='dev-agent task "<objetivo>"'),
            AgentDescriptor(name="observability", description="Sugere logs, métricas e rastreamento seguros.", mode="read", command='dev-agent task "<objetivo>"'),
            AgentDescriptor(name="release", description="Verifica itens necessários para publicação.", mode="read", command='dev-agent task "<objetivo>"'),
            AgentDescriptor(name="refactor", description="Separa refatorações necessárias das opcionais.", mode="read", command='dev-agent task "<objetivo>"'),
            AgentDescriptor(name="git", description="Sugere um plano de commit sem criar commits.", mode="read", command="dev-agent commit"),
            AgentDescriptor(name="architecture_guard", description="Solicita decisão para mudanças estruturais.", mode="guard", command='dev-agent task "<objetivo estrutural>"'),
        ]

    def context(self, objective: str = "Compreender o projeto") -> tuple[ContextPacket, SubAgentResult]:
        session = self.store.load()
        previous = session.summaries[-1] if session and session.project_root == self.root and session.summaries else None
        packet = self.context_agent.build(objective, previous_summary=previous, git_diff=self.git.diff())
        result = self.context_agent.run(packet)
        self._remember(objective, packet, result)
        return packet, result

    def ask(self, objective: str) -> SubAgentResult:
        packet, _ = self.context(objective)
        context = "\n\n".join(f"### {name}\n{text}" for name, text in packet.file_contents.items())
        answer = self.provider.run(f"Responda em português à pergunta: {objective}\nUse somente este contexto do projeto:\n{context}", self.root, write_access=False)
        result = SubAgentResult(agent="ask", summary=answer, files_read=packet.relevant_files)
        self._remember(objective, packet, result)
        return result

    def task(self, objective: str) -> list[SubAgentResult]:
        event("orchestrator.task.started", project=str(self.root))
        assessment = ArchitectureGuard().assess(objective)
        if assessment.required and self.config.security.require_architecture_approval:
            return [SubAgentResult(agent="architecture_guard", summary=f"DECISÃO ARQUITETURAL NECESSÁRIA\n\nContexto: {assessment.reason}\n\nProblema: a tarefa indica uma mudança estrutural.\n\nOpção A: aprovar a abordagem proposta.\nVantagens: avanço direto.\nDesvantagens: impacto estrutural ainda precisa de desenho.\n\nOpção B: delimitar a mudança antes de implementar.\nVantagens: reduz risco.\nDesvantagens: exige decisão do usuário.\n\nMinha recomendação: delimitar a mudança.\n\nImpacto estimado: alto.", architecture_decision_required=True)]
        with self._write_lock:
            packet, context_result = self.context(objective)
            requirements_result = RequirementsAgent(self.provider).run(packet)
            before = self._file_snapshot()
            implementation = ImplementationAgent(self.provider).run(packet)
            changed = self._changed_files(before)
            self._apply_headers(changed, objective)
            refreshed = self.context_agent.build(objective, git_diff=self.git.diff(), changed_files=changed)
            before_code_documentation = self._file_snapshot()
            code_documentation = CodeDocumentationAgent(self.provider).run(refreshed)
            code_documentation_changed = self._changed_files(before_code_documentation)
            self._apply_headers(code_documentation_changed, objective)
            code_documentation.files_changed = code_documentation_changed
            changed = list(dict.fromkeys([*changed, *code_documentation_changed]))
            refreshed = self.context_agent.build(objective, git_diff=self.git.diff(), changed_files=changed)
            before_tests = self._file_snapshot()
            test_author = TestAuthorAgent(self.provider).run(refreshed)
            test_author_changed = self._changed_files(before_tests)
            self._apply_headers(test_author_changed, objective)
            test_author.files_changed = test_author_changed
            changed = list(dict.fromkeys([*changed, *test_author_changed]))
            refreshed = self.context_agent.build(objective, git_diff=self.git.diff(), changed_files=changed)
            before_documentation = self._file_snapshot()
            documentation_writer = DocumentationWriterAgent(self.provider).run(refreshed)
            documentation_changed = self._changed_files(before_documentation)
            self._apply_headers(documentation_changed, objective)
            documentation_writer.files_changed = documentation_changed
            changed = list(dict.fromkeys([*changed, *documentation_changed]))
            refreshed = self.context_agent.build(objective, git_diff=self.git.diff(), changed_files=changed)
            test_result = TestAgent(TestTool(TerminalTool(self.root), self.config.testing.command)).run(refreshed)
            bug_reproduction = BugReproductionAgent(self.provider).run(refreshed)
            review_result = ReviewAgent(self.provider).run(refreshed)
            docs_result = DocumentationAgent().run(refreshed)
            specialist_results = [
                SecurityAgent(self.provider).run(refreshed),
                DatabaseAgent(self.provider).run(refreshed),
                ApiContractAgent(self.provider).run(refreshed),
                QualityAgent(self.provider).run(refreshed),
                DependencyAgent(self.provider).run(refreshed),
                PerformanceAgent(self.provider).run(refreshed),
                FrontendAgent(self.provider).run(refreshed),
                ObservabilityAgent(self.provider).run(refreshed),
                ReleaseAgent(self.provider).run(refreshed),
                RefactorAgent(self.provider).run(refreshed),
            ]
            results = [context_result, requirements_result, implementation, code_documentation, test_author, documentation_writer, test_result, bug_reproduction, review_result, docs_result, *specialist_results]
            for result in results: self._remember(objective, refreshed, result)
            event("orchestrator.task.finished", project=str(self.root), agents=[item.agent for item in results], changed_files=changed)
            return results

    def review(self, staged: bool = False) -> SubAgentResult:
        packet, _ = self.context("Revisar alterações staged" if staged else "Revisar alterações atuais")
        packet.git_diff = self.git.diff(staged)
        return ReviewAgent(self.provider).run(packet)

    def test(self) -> SubAgentResult:
        packet, _ = self.context("Executar testes do projeto")
        return TestAgent(TestTool(TerminalTool(self.root), self.config.testing.command)).run(packet)

    def debug(self, objective: str) -> SubAgentResult:
        packet, _ = self.context(objective)
        tests = TestTool(TerminalTool(self.root), self.config.testing.command)
        result = DebugAgent(self.provider, tests).run(packet)
        self._remember(objective, packet, result)
        return result

    def commit_plan(self): return GitAgent(self.root).commit_plan()

    def _file_snapshot(self) -> dict[str, tuple[int, int]]:
        snapshot: dict[str, tuple[int, int]] = {}
        for path in self.root.rglob("*"):
            if not path.is_file() or any(part in {".git", ".venv", "venv", "node_modules", "__pycache__"} for part in path.parts):
                continue
            try:
                state = path.stat(); snapshot[str(path.relative_to(self.root))] = (state.st_mtime_ns, state.st_size)
            except OSError: pass
        return snapshot

    def _changed_files(self, before: dict[str, tuple[int, int]]) -> list[str]:
        after = self._file_snapshot()
        return [name for name, state in after.items() if before.get(name) != state]

    def _apply_headers(self, files: list[str], objective: str) -> None:
        service = HeaderService(self.config)
        task_key = str(abs(hash(objective)))
        for name in files:
            path = self.root / name
            if not path.is_file() or not service.supports(path): continue
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            updated = service.apply(path, content, objective[:100], task_key, existing=content)
            if updated != content: path.write_text(updated, encoding="utf-8", newline="\n")

    def _remember(self, objective: str, packet: ContextPacket, result: SubAgentResult) -> None:
        session = self.store.load()
        if not session or session.project_root != self.root:
            session = ProjectSession(project_root=self.root, project_name=self.config.project.name)
        session.objective = objective
        session.recent_tasks = (session.recent_tasks + [objective])[-10:]
        session.related_files = packet.relevant_files[-30:]
        session.summaries = (session.summaries + [f"{result.agent}: {result.summary[:500]}"])[-20:]
        session.open_risks = result.warnings[-10:]
        self.store.activate(session)
