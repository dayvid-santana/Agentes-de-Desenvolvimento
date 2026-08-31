# dev-agent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Unificar a listagem de Agents na fonte única AgentRegistry.
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
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Importar cada agente especialista de seu módulo próprio.
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Executar mudanças estruturais somente após aprovação registrada.
import threading
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from dev_agent.agents.context_agent import ContextAgent
from dev_agent.agents.git_agent import GitAgent
from dev_agent.agents.registry import AgentRegistry
from dev_agent.agents.test_agent import TestAgent
from dev_agent.config.loader import load_config
from dev_agent.core.models import AgentDescriptor, Checkpoint, ContextPacket, SubAgentResult, TaskStatus
from dev_agent.core.state_machine import TaskStateMachine
from dev_agent.headers.service import HeaderService
from dev_agent.memory.session_store import ProjectSession, SessionStore
from dev_agent.providers.base import LLMProvider
from dev_agent.security.architecture_guard import ArchitectureGuard
from dev_agent.security.redaction import SensitiveDataRedactor
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
        """Fonte única: lê ``agents/catalog.yaml`` via ``AgentRegistry``."""
        return [manifest.descriptor() for manifest in AgentRegistry().list()]

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
        result = SubAgentResult(agent="ask", summary=SensitiveDataRedactor.redact(answer) or "", files_read=packet.relevant_files)
        self._remember(objective, packet, result)
        return result

    def task(
        self,
        objective: str,
        *,
        architecture_approved: bool = False,
        job_id: str | None = None,
        on_checkpoint: Callable[[Checkpoint], None] | None = None,
        resume_from: Checkpoint | None = None,
    ) -> list[SubAgentResult]:
        """Executa o pipeline de fases da tarefa, com checkpoints e retomada opcional.

        Sem ``resume_from``, o pipeline roda do início (DISCOVERING…REVIEWING).
        Com ``resume_from`` (um :class:`Checkpoint` de uma execução interrompida),
        pula as fases já concluídas, reconstrói apenas o contexto necessário e
        continua a partir da fase seguinte — sem repetir chamadas ao provider já
        feitas com sucesso.
        """
        event("orchestrator.task.started", project=str(self.root))
        assessment = ArchitectureGuard().assess(objective)
        if assessment.required and self.config.security.require_architecture_approval and not architecture_approved:
            return [SubAgentResult(agent="architecture_guard", summary=f"DECISÃO ARQUITETURAL NECESSÁRIA\n\nContexto: {assessment.reason}\n\nProblema: a tarefa indica uma mudança estrutural.\n\nOpção A: aprovar a abordagem proposta.\nVantagens: avanço direto.\nDesvantagens: impacto estrutural ainda precisa de desenho.\n\nOpção B: delimitar a mudança antes de implementar.\nVantagens: reduz risco.\nDesvantagens: exige decisão do usuário.\n\nMinha recomendação: delimitar a mudança.\n\nImpacto estimado: alto.", architecture_decision_required=True)]

        machine = TaskStateMachine(job_id or uuid4().hex)
        results: list[SubAgentResult] = list(resume_from.results) if resume_from else []
        changed: list[str] = list(resume_from.changed_files) if resume_from else []
        resume_phase = resume_from.phase if resume_from else None

        def checkpoint(step_index: int) -> None:
            self._sanitize_results(results)
            point = machine.checkpoint(step_index=step_index, completed_agents=[item.agent for item in results], results=results, changed_files=changed)
            if on_checkpoint:
                on_checkpoint(point)

        with self._write_lock:
            if resume_from is None:
                machine.transition(TaskStatus.DISCOVERING)
                packet, context_result = self.context(objective)
                results.append(context_result)
                machine.transition(TaskStatus.PLANNING)
                results.append(self._provider_agent("requirements").run(packet))
                checkpoint(1)
            else:
                machine.status = TaskStatus.BLOCKED
                packet, _ = self.context(objective)

            if resume_phase in (None, TaskStatus.PLANNING):
                machine.transition(TaskStatus.EXECUTING)
                before = self._file_snapshot()
                implementation = self._provider_agent("implementation").run(packet)
                implementation_changed = self._changed_files(before)
                self._apply_headers(implementation_changed, objective)
                changed = list(dict.fromkeys([*changed, *implementation_changed]))
                refreshed = self.context_agent.build(objective, git_diff=self.git.diff(), changed_files=changed)

                before_code_documentation = self._file_snapshot()
                code_documentation = self._provider_agent("code_documentation").run(refreshed)
                code_documentation_changed = self._changed_files(before_code_documentation)
                self._apply_headers(code_documentation_changed, objective)
                code_documentation.files_changed = code_documentation_changed
                changed = list(dict.fromkeys([*changed, *code_documentation_changed]))
                refreshed = self.context_agent.build(objective, git_diff=self.git.diff(), changed_files=changed)

                before_tests = self._file_snapshot()
                test_author = self._provider_agent("test_author").run(refreshed)
                test_author_changed = self._changed_files(before_tests)
                self._apply_headers(test_author_changed, objective)
                test_author.files_changed = test_author_changed
                changed = list(dict.fromkeys([*changed, *test_author_changed]))
                refreshed = self.context_agent.build(objective, git_diff=self.git.diff(), changed_files=changed)

                before_documentation = self._file_snapshot()
                documentation_writer = self._provider_agent("documentation_writer").run(refreshed)
                documentation_changed = self._changed_files(before_documentation)
                self._apply_headers(documentation_changed, objective)
                documentation_writer.files_changed = documentation_changed
                changed = list(dict.fromkeys([*changed, *documentation_changed]))

                results += [implementation, code_documentation, test_author, documentation_writer]
                if objective.lower().startswith("documentar o projeto"):
                    before_project_docs = self._file_snapshot()
                    project_documentation = self._provider_agent("project_documentation").run(refreshed)
                    project_documentation.files_changed = self._changed_files(before_project_docs)
                    self._apply_headers(project_documentation.files_changed, objective)
                    changed = list(dict.fromkeys([*changed, *project_documentation.files_changed]))
                    results.append(project_documentation)
                checkpoint(2)
            else:
                refreshed = self.context_agent.build(objective, git_diff=self.git.diff(), changed_files=changed)

            if resume_phase in (None, TaskStatus.PLANNING, TaskStatus.EXECUTING):
                machine.transition(TaskStatus.TESTING)
                test_result = TestAgent(TestTool(self._terminal(), self.config.testing.command)).run(refreshed)
                bug_reproduction = self._provider_agent("bug_reproduction").run(refreshed)
                results += [test_result, bug_reproduction]
                checkpoint(3)

            if resume_phase != TaskStatus.REVIEWING:
                machine.transition(TaskStatus.REVIEWING)
                review_result = self._provider_agent("review").run(refreshed)
                docs_result = AgentRegistry().create("documentation").run(refreshed)
                specialist_results = [
                    self._provider_agent(agent_id).run(refreshed)
                    for agent_id in ("security", "database", "api_contract", "quality", "dependency", "performance", "frontend", "observability", "release", "refactor")
                ]
                results += [review_result, docs_result, *specialist_results]
                checkpoint(4)

            failed_tests = any(item.agent == "test" and item.warnings for item in results)
            machine.transition(TaskStatus.PARTIALLY_COMPLETED if failed_tests else TaskStatus.COMPLETED)
            self._sanitize_results(results)
            for result in results: self._remember(objective, refreshed, result)
            event("orchestrator.task.finished", project=str(self.root), agents=[item.agent for item in results], changed_files=changed, phase=machine.status.value)
            return results

    def review(self, staged: bool = False) -> SubAgentResult:
        packet, _ = self.context("Revisar alterações staged" if staged else "Revisar alterações atuais")
        packet.git_diff = SensitiveDataRedactor.redact(self.git.diff(staged))
        return self._provider_agent("review").run(packet)

    def test(self) -> SubAgentResult:
        packet, _ = self.context("Executar testes do projeto")
        return TestAgent(TestTool(self._terminal(), self.config.testing.command)).run(packet)

    def debug(self, objective: str) -> SubAgentResult:
        packet, _ = self.context(objective)
        tests = TestTool(self._terminal(), self.config.testing.command)
        result = AgentRegistry().create("debug", self.provider, tests).run(packet)
        self._remember(objective, packet, result)
        return result

    def commit_plan(self): return GitAgent(self.root).commit_plan()

    def _terminal(self) -> TerminalTool:
        return TerminalTool(self.root, cancel_event=getattr(self.provider, "cancel_event", None))

    def _provider_agent(self, agent_id: str):
        return AgentRegistry().create(agent_id, self.provider)

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
        modified = [name for name, state in after.items() if before.get(name) != state]
        deleted = [name for name in before if name not in after]
        return [*modified, *deleted]

    def _apply_headers(self, files: list[str], objective: str) -> None:
        service = HeaderService(self.config)
        task_key = str(abs(hash(objective)))
        for name in files:
            path = self.root / name
            if not path.is_file() or not service.supports(path): continue
            try:
                content = self.context_agent.files.read_text(name).content
            except (OSError, UnicodeDecodeError):
                continue
            updated = service.apply(path, content, objective[:100], task_key, existing=content)
            if updated != content: self.context_agent.files.write_text(name, updated)

    def _remember(self, objective: str, packet: ContextPacket, result: SubAgentResult) -> None:
        session = self.store.load()
        if not session or session.project_root != self.root:
            session = ProjectSession(project_root=self.root, project_name=self.config.project.name)
        session.objective = objective
        session.recent_tasks = (session.recent_tasks + [objective])[-10:]
        session.related_files = packet.relevant_files[-30:]
        summary = SensitiveDataRedactor.redact(result.summary) or ""
        session.summaries = (session.summaries + [f"{result.agent}: {summary[:500]}"])[-20:]
        session.open_risks = [(SensitiveDataRedactor.redact(item) or "") for item in result.warnings[-10:]]
        self.store.activate(session)

    @staticmethod
    def _sanitize_results(results: list[SubAgentResult]) -> None:
        for result in results:
            result.summary = SensitiveDataRedactor.redact(result.summary) or ""
            result.warnings = [(SensitiveDataRedactor.redact(item) or "") for item in result.warnings]
