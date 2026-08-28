# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Cobrir checkpoints e retomada do pipeline de Orchestrator.task().
from __future__ import annotations

from pathlib import Path

from dev_agent.config.loader import render_default_config
from dev_agent.core.models import SubAgentResult, TaskStatus
from dev_agent.core.orchestrator import Orchestrator
from dev_agent.memory.session_store import SessionStore


class RecordingProvider:
    def __init__(self) -> None:
        self.calls = 0

    def available(self) -> bool:
        return True

    def run(self, prompt: str, project_root: Path, *, write_access: bool = False, timeout_seconds: int = 600) -> str:
        self.calls += 1
        return "Resposta fake"


def _service(tmp_path: Path, provider: RecordingProvider, monkeypatch) -> Orchestrator:
    (tmp_path / "dev-agent.yaml").write_text(render_default_config("Demo"), encoding="utf-8")
    service = Orchestrator(tmp_path, provider, SessionStore(tmp_path / "session.json"))
    monkeypatch.setattr(service.git, "diff", lambda staged=False: "")
    monkeypatch.setattr(
        "dev_agent.core.orchestrator.TestAgent.run",
        lambda self, packet: SubAgentResult(agent="test", summary="ok"),
    )
    return service


def test_task_emits_one_checkpoint_per_phase_in_order(tmp_path: Path, monkeypatch):
    provider = RecordingProvider()
    service = _service(tmp_path, provider, monkeypatch)
    checkpoints = []

    service.task("Adicionar validação simples", job_id="job-1", on_checkpoint=checkpoints.append)

    assert [point.phase for point in checkpoints] == [
        TaskStatus.PLANNING,
        TaskStatus.EXECUTING,
        TaskStatus.TESTING,
        TaskStatus.REVIEWING,
    ]
    assert [point.step_index for point in checkpoints] == [1, 2, 3, 4]
    assert checkpoints[-1].results[-1].agent == "refactor"


def test_resuming_from_a_checkpoint_skips_already_completed_phases(tmp_path: Path, monkeypatch):
    provider = RecordingProvider()
    service = _service(tmp_path, provider, monkeypatch)
    checkpoints = []
    fresh_results = service.task("Adicionar validação simples", job_id="job-1", on_checkpoint=checkpoints.append)
    fresh_calls = provider.calls

    executing_checkpoint = next(point for point in checkpoints if point.phase == TaskStatus.EXECUTING)
    assert {item.agent for item in executing_checkpoint.results} == {"context", "requirements", "implementation", "code_documentation", "test_author", "documentation_writer"}

    provider.calls = 0
    resumed_results = service.task("Adicionar validação simples", job_id="job-1", resume_from=executing_checkpoint)

    # A retomada não deve recontatar o provider para as fases já concluídas
    # (requirements + implementation + documentation_writer chamam o provider
    # neste fixture; code_documentation e test_author já não chamam por não
    # haver arquivo de código selecionado no contexto).
    assert provider.calls == fresh_calls - 3
    assert {item.agent for item in resumed_results} == {item.agent for item in fresh_results}
    # Os resultados já concluídos são preservados exatamente, não recriados.
    assert resumed_results[:6] == executing_checkpoint.results


def test_resuming_from_the_last_phase_does_no_further_work(tmp_path: Path, monkeypatch):
    provider = RecordingProvider()
    service = _service(tmp_path, provider, monkeypatch)
    checkpoints = []
    service.task("Adicionar validação simples", job_id="job-1", on_checkpoint=checkpoints.append)
    reviewing_checkpoint = checkpoints[-1]

    provider.calls = 0
    resumed_results = service.task("Adicionar validação simples", job_id="job-1", resume_from=reviewing_checkpoint)

    assert provider.calls == 0
    assert resumed_results == reviewing_checkpoint.results
