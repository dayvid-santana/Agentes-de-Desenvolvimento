# dev-agent
# Autor: Dayvid Santana
# Criado em: 28/08/2026
# Editado em: 28/08/2026
# Objetivo: Validar transições de fase, limitar passos e produzir checkpoints de uma tarefa.
"""Máquina de estados explícita usada por ``Orchestrator.task``.

O pipeline de ``task()`` é uma sequência fixa e determinística de fases (não
um loop aberto de ferramentas), então "detecção de loop" aqui significa:
nenhuma fase pode ser reexecutada além de ``max_phase_repeats`` vezes e a
tarefa inteira não pode exceder ``max_steps`` transições. Isso protege
principalmente o ciclo TESTING -> EXECUTING -> TESTING (retrabalho após falha
de teste), hoje modelado mas não acionado automaticamente pelo orquestrador.
"""
from __future__ import annotations

from datetime import datetime, timezone

from dev_agent.core.models import Checkpoint, SubAgentResult, TaskStatus
from dev_agent.errors import InvalidStateTransitionError, TaskLoopDetectedError

_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.RECEIVED: {TaskStatus.DISCOVERING, TaskStatus.CANCELLED},
    TaskStatus.DISCOVERING: {TaskStatus.PLANNING, TaskStatus.BLOCKED, TaskStatus.FAILED, TaskStatus.CANCELLED},
    TaskStatus.PLANNING: {
        TaskStatus.AWAITING_APPROVAL,
        TaskStatus.EXECUTING,
        TaskStatus.BLOCKED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.AWAITING_APPROVAL: {TaskStatus.EXECUTING, TaskStatus.CANCELLED},
    TaskStatus.EXECUTING: {TaskStatus.TESTING, TaskStatus.BLOCKED, TaskStatus.FAILED, TaskStatus.CANCELLED},
    TaskStatus.TESTING: {
        TaskStatus.REVIEWING,
        TaskStatus.EXECUTING,
        TaskStatus.BLOCKED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.REVIEWING: {
        TaskStatus.DOCUMENTING,
        TaskStatus.COMPLETED,
        TaskStatus.PARTIALLY_COMPLETED,
        TaskStatus.BLOCKED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.DOCUMENTING: {
        TaskStatus.PREPARING_GIT,
        TaskStatus.COMPLETED,
        TaskStatus.BLOCKED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.PREPARING_GIT: {TaskStatus.COMPLETED, TaskStatus.BLOCKED, TaskStatus.FAILED, TaskStatus.CANCELLED},
    TaskStatus.BLOCKED: {
        TaskStatus.DISCOVERING,
        TaskStatus.PLANNING,
        TaskStatus.EXECUTING,
        TaskStatus.TESTING,
        TaskStatus.REVIEWING,
        TaskStatus.COMPLETED,
        TaskStatus.PARTIALLY_COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.FAILED: {TaskStatus.ROLLED_BACK},
    TaskStatus.PARTIALLY_COMPLETED: {TaskStatus.ROLLED_BACK},
    TaskStatus.COMPLETED: set(),
    TaskStatus.CANCELLED: set(),
    TaskStatus.ROLLED_BACK: set(),
}

TERMINAL_STATES = {
    TaskStatus.COMPLETED,
    TaskStatus.PARTIALLY_COMPLETED,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
    TaskStatus.ROLLED_BACK,
}

# Fase concluída -> próxima fase a executar ao retomar a partir de um checkpoint.
RESUME_NEXT_PHASE: dict[TaskStatus, TaskStatus] = {
    TaskStatus.PLANNING: TaskStatus.EXECUTING,
    TaskStatus.EXECUTING: TaskStatus.TESTING,
    TaskStatus.TESTING: TaskStatus.REVIEWING,
    TaskStatus.REVIEWING: TaskStatus.COMPLETED,
}


class TaskStateMachine:
    """Valida transições de fase e registra checkpoints para um job."""

    def __init__(self, job_id: str, *, max_steps: int = 40, max_phase_repeats: int = 3) -> None:
        self.job_id = job_id
        self.max_steps = max_steps
        self.max_phase_repeats = max_phase_repeats
        self.status: TaskStatus = TaskStatus.RECEIVED
        self.steps_taken = 0
        self._phase_counts: dict[TaskStatus, int] = {}
        self.checkpoints: list[Checkpoint] = []

    def transition(self, target: TaskStatus) -> TaskStatus:
        allowed = _TRANSITIONS.get(self.status, set())
        if target not in allowed:
            raise InvalidStateTransitionError(f"Transição inválida de {self.status.value} para {target.value}.")
        self.steps_taken += 1
        if self.steps_taken > self.max_steps:
            raise TaskLoopDetectedError(f"Job {self.job_id} excedeu o máximo de {self.max_steps} passos.")
        seen = self._phase_counts.get(target, 0) + 1
        self._phase_counts[target] = seen
        if seen > self.max_phase_repeats:
            raise TaskLoopDetectedError(f"Fase {target.value} foi repetida {seen} vezes no job {self.job_id}; possível loop.")
        self.status = target
        return self.status

    def checkpoint(
        self,
        *,
        step_index: int,
        completed_agents: list[str],
        results: list[SubAgentResult],
        changed_files: list[str],
    ) -> Checkpoint:
        point = Checkpoint(
            job_id=self.job_id,
            phase=self.status,
            step_index=step_index,
            completed_agents=list(completed_agents),
            results=list(results),
            changed_files=list(changed_files),
            created_at=datetime.now(timezone.utc),
        )
        self.checkpoints.append(point)
        return point

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATES

    @property
    def latest_checkpoint(self) -> Checkpoint | None:
        return self.checkpoints[-1] if self.checkpoints else None
