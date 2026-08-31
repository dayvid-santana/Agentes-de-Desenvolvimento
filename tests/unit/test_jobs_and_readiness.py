# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Cobrir prontidão, isolamento e ciclo de vida de jobs dos agents.
from __future__ import annotations

import sys
# dev-agent
# Autor: Dayvid Santana
# Data: 31/08/2026
# Objetivo: Cobrir status parcial para falhas de teste em jobs.
# DevAgent-Task: resolve-audit-gaps-20260831

import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dev_agent.core.job_manager import TaskJobManager
from dev_agent.core.models import Checkpoint, SubAgentResult, TaskStatus
from dev_agent.errors import DevAgentError, ToolExecutionError, UnsafeCommandError
from dev_agent.memory.job_store import JobStore
from dev_agent.providers.codex.provider import CodexProvider
from dev_agent.tools.terminal import CommandResult, TerminalTool


def test_codex_readiness_uses_a_minimal_read_only_probe(tmp_path: Path, monkeypatch):
    calls: list[list[str]] = []
    CodexProvider._readiness_cache.clear()
    monkeypatch.setattr("dev_agent.providers.codex.provider.shutil.which", lambda _: "C:/tools/codex.exe")

    def run(self, command, timeout_seconds=None, cancel_event=None, input_text=None):
        calls.append(command)
        return CommandResult(command=command, exit_code=0, stdout="codex 1.0\n" if command[-1] == "--version" else "READY", stderr="", duration_ms=1)

    monkeypatch.setattr(TerminalTool, "run", run)
    readiness = CodexProvider().readiness(tmp_path, force=True)

    assert readiness.ready and readiness.category == "ready"
    assert any("read-only" in command for command in calls)


def test_codex_retries_only_read_only_transient_failures(tmp_path: Path, monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr("dev_agent.providers.codex.provider.shutil.which", lambda _: "C:/tools/codex.exe")
    monkeypatch.setattr("dev_agent.providers.codex.provider.time.sleep", lambda _: None)

    def run(self, command, timeout_seconds=None, cancel_event=None, input_text=None):
        calls.append(command)
        if len(calls) == 1:
            return CommandResult(command=command, exit_code=1, stdout="", stderr="network timeout", duration_ms=1)
        return CommandResult(command=command, exit_code=0, stdout="ok", stderr="", duration_ms=1)

    monkeypatch.setattr(TerminalTool, "run", run)
    assert CodexProvider().run("analise", tmp_path) == "ok"
    assert len(calls) == 2

    calls.clear()
    with pytest.raises(ToolExecutionError):
        CodexProvider().run("altere", tmp_path, write_access=True)
    assert len(calls) == 1


def test_terminal_can_cancel_a_running_process(tmp_path: Path):
    cancelled = threading.Event()
    threading.Timer(0.1, cancelled.set).start()

    with pytest.raises(ToolExecutionError, match="cancelada"):
        TerminalTool(tmp_path).run([sys.executable, "-c", "import time; time.sleep(5)"], timeout_seconds=5, cancel_event=cancelled)


class FakeGit:
    removed: list[Path] = []

    def __init__(self, root: Path) -> None:
        self.root = root

    def is_repository(self) -> bool:
        return True

    def is_clean(self) -> bool:
        return True

    def branch(self) -> str:
        return "main"

    def create_worktree(self, job_id: str) -> tuple[Path, str]:
        worktree = self.root / ".worktrees" / job_id
        worktree.mkdir(parents=True, exist_ok=True)
        return worktree, f"dev-agent/{job_id}"

    def diff(self) -> str:
        return "+ alteração isolada"

    def full_diff(self) -> str:
        return "+ alteração isolada"

    def remove_worktree(self, target: Path) -> None:
        self.removed.append(target)


class FakeOrchestrator:
    def __init__(self) -> None:
        self.architecture_approved = False
        self.calls = 0

    def task(self, objective: str, *, architecture_approved: bool = False, job_id=None, on_checkpoint=None, resume_from=None):
        self.architecture_approved = architecture_approved
        self.calls += 1
        return [SubAgentResult(agent="implementation", summary=f"Executado: {objective}")]


def test_job_runs_in_isolated_worktree_and_persists_result(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("dev_agent.core.job_manager.GitTool", FakeGit)
    services: list[FakeOrchestrator] = []

    def factory(root: Path, cancellation: threading.Event):
        service = FakeOrchestrator()
        services.append(service)
        return service

    manager = TaskJobManager(factory, JobStore(tmp_path / "jobs.json"))
    plan = manager.create_plan(tmp_path, "Demo", "Adicionar validação", ["src/service.py"])
    job = manager.start(plan.id, confirmed_write=True)
    for _ in range(50):
        job = manager.get_job(job.id)
        if job.status in {"completed", "partially_completed", "failed", "cancelled", "blocked"}:
            break
        time.sleep(0.01)

    assert job.status == "completed"
    assert job.worktree_path and job.worktree_path != tmp_path
    assert job.results[0].agent == "implementation"
    assert JobStore(tmp_path / "jobs.json").load().jobs[job.id].status == "completed"


def test_job_marks_failed_tests_as_partially_completed(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("dev_agent.core.job_manager.GitTool", FakeGit)

    class TestFailingOrchestrator:
        def task(self, objective, **_):
            return [SubAgentResult(agent="test", summary="falhou", warnings=["1 failed"])]

    manager = TaskJobManager(lambda root, cancellation: TestFailingOrchestrator(), JobStore(tmp_path / "jobs.json"))
    plan = manager.create_plan(tmp_path, "Demo", "Adicionar validação", [])
    job = manager.start(plan.id, confirmed_write=True)
    for _ in range(50):
        job = manager.get_job(job.id)
        if job.status in {"partially_completed", "failed", "cancelled", "blocked"}:
            break
        time.sleep(0.01)

    assert job.status == "partially_completed"
    assert job.phase == TaskStatus.PARTIALLY_COMPLETED


def test_architecture_plan_requires_recorded_approval(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("dev_agent.core.job_manager.GitTool", FakeGit)
    manager = TaskJobManager(lambda root, cancellation: FakeOrchestrator(), JobStore(tmp_path / "jobs.json"))
    plan = manager.create_plan(tmp_path, "Demo", "Adicionar autenticação", [])

    with pytest.raises(Exception, match="decisão arquitetural"):
        manager.start(plan.id, confirmed_write=True)

    approved = manager.approve_architecture(plan.id, "Usar autenticação local com sessão por usuário.")
    assert approved.architecture_approved


def test_worktree_cleanup_requires_confirmation(tmp_path: Path, monkeypatch):
    FakeGit.removed = []
    monkeypatch.setattr("dev_agent.core.job_manager.GitTool", FakeGit)
    manager = TaskJobManager(lambda root, cancellation: FakeOrchestrator(), JobStore(tmp_path / "jobs.json"))
    plan = manager.create_plan(tmp_path, "Demo", "Adicionar validação", [])
    job = manager.start(plan.id, confirmed_write=True)
    for _ in range(50):
        job = manager.get_job(job.id)
        if job.status == "completed":
            break
        time.sleep(0.01)

    with pytest.raises(UnsafeCommandError):
        manager.cleanup_worktree(job.id, confirmed_cleanup=False)

    cleaned = manager.cleanup_worktree(job.id, confirmed_cleanup=True)
    assert cleaned.worktree_removed and cleaned.worktree_path is None
    assert FakeGit.removed


class FlakyOrchestrator:
    """Falha após um checkpoint na primeira tentativa; conclui ao ser retomado."""

    def __init__(self) -> None:
        self.calls = 0

    def task(self, objective: str, *, architecture_approved: bool = False, job_id=None, on_checkpoint=None, resume_from=None):
        self.calls += 1
        if resume_from is None:
            checkpoint = Checkpoint(
                job_id=job_id or "job",
                phase=TaskStatus.EXECUTING,
                step_index=2,
                completed_agents=["context", "requirements", "implementation"],
                results=[SubAgentResult(agent="implementation", summary="parcial")],
                changed_files=["src/service.py"],
                created_at=datetime.now(timezone.utc),
            )
            if on_checkpoint:
                on_checkpoint(checkpoint)
            raise RuntimeError("falha transitória simulada")
        return [*resume_from.results, SubAgentResult(agent="review", summary="ok")]


def test_job_can_be_resumed_from_its_last_checkpoint_after_a_failure(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("dev_agent.core.job_manager.GitTool", FakeGit)
    create_calls: list[str] = []
    real_create_worktree = FakeGit.create_worktree

    def counting_create_worktree(self, job_id):
        create_calls.append(job_id)
        return real_create_worktree(self, job_id)

    monkeypatch.setattr(FakeGit, "create_worktree", counting_create_worktree)
    orchestrators: list[FlakyOrchestrator] = []

    def factory(root: Path, cancellation: threading.Event):
        service = FlakyOrchestrator()
        orchestrators.append(service)
        return service

    manager = TaskJobManager(factory, JobStore(tmp_path / "jobs.json"))
    plan = manager.create_plan(tmp_path, "Demo", "Adicionar validação", ["src/service.py"])
    job = manager.start(plan.id, confirmed_write=True)
    for _ in range(50):
        job = manager.get_job(job.id)
        if job.status in {"completed", "partially_completed", "failed", "cancelled", "blocked"}:
            break
        time.sleep(0.01)

    assert job.status == "blocked"
    assert job.resumable
    assert job.last_checkpoint is not None
    assert job.last_checkpoint.phase == TaskStatus.EXECUTING
    worktree_after_first_attempt = job.worktree_path

    resumed = manager.resume(job.id)
    for _ in range(50):
        resumed = manager.get_job(resumed.id)
        if resumed.status in {"completed", "failed", "cancelled"}:
            break
        time.sleep(0.01)

    assert resumed.status == "completed"
    assert [item.agent for item in resumed.results] == ["implementation", "review"]
    assert resumed.worktree_path == worktree_after_first_attempt
    assert create_calls == [job.id], "o worktree não deve ser recriado ao retomar"
    assert len(orchestrators) == 2 and orchestrators[1].calls == 1


def test_resume_rejects_a_job_without_a_usable_checkpoint(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("dev_agent.core.job_manager.GitTool", FakeGit)
    manager = TaskJobManager(lambda root, cancellation: FakeOrchestrator(), JobStore(tmp_path / "jobs.json"))
    plan = manager.create_plan(tmp_path, "Demo", "Adicionar validação", [])
    job = manager.start(plan.id, confirmed_write=True)
    for _ in range(50):
        job = manager.get_job(job.id)
        if job.status == "completed":
            break
        time.sleep(0.01)

    with pytest.raises(DevAgentError, match="não pode ser retomado"):
        manager.resume(job.id)


def test_blocked_job_can_be_cancelled_without_a_running_thread(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("dev_agent.core.job_manager.GitTool", FakeGit)
    manager = TaskJobManager(lambda root, cancellation: FakeOrchestrator(), JobStore(tmp_path / "jobs.json"))
    plan = manager.create_plan(tmp_path, "Demo", "Adicionar validação", [])
    job = manager.start(plan.id, confirmed_write=True)
    for _ in range(50):
        job = manager.get_job(job.id)
        if job.status == "completed":
            break
        time.sleep(0.01)
    manager.state.jobs[job.id] = job.model_copy(update={"status": "blocked", "resumable": True})

    cancelled = manager.cancel(job.id)

    assert cancelled.status == "cancelled"
    assert cancelled.resumable is False


def test_restart_marks_a_resumable_interrupted_job_as_blocked_not_failed(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("dev_agent.core.job_manager.GitTool", FakeGit)
    store = JobStore(tmp_path / "jobs.json")
    manager = TaskJobManager(lambda root, cancellation: FakeOrchestrator(), store)
    plan = manager.create_plan(tmp_path, "Demo", "Adicionar validação", [])
    job = manager.start(plan.id, confirmed_write=True)
    for _ in range(50):
        job = manager.get_job(job.id)
        if job.status == "completed":
            break
        time.sleep(0.01)
    manager.state.jobs[job.id] = job.model_copy(update={"status": "running", "resumable": True})
    manager._save()

    restarted = TaskJobManager(lambda root, cancellation: FakeOrchestrator(), store)

    recovered = restarted.get_job(job.id)
    assert recovered.status == "blocked"
    assert "resume" in recovered.error.lower()
