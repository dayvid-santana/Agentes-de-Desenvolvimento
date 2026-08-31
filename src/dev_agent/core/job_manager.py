"""Planeja e executa tarefas dos agents em worktrees isolados."""
from __future__ import annotations

# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Retomar jobs interrompidos a partir do último checkpoint da tarefa.
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Controlar aprovação, execução assíncrona e cancelamento de tarefas.

import threading
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dev_agent.core.models import AgentJob, Checkpoint, TaskPlan, TaskStatus
from dev_agent.errors import ArchitectureDecisionRequired, DevAgentError, UnsafeCommandError
from dev_agent.memory.job_store import JobState, JobStore
from dev_agent.security.architecture_guard import ArchitectureGuard
from dev_agent.security.redaction import SensitiveDataRedactor
from dev_agent.tools.git import GitTool


class TaskJobManager:
    """Mantém jobs locais e delega toda escrita ao ``Orchestrator`` do worktree."""

    def __init__(self, orchestrator_factory: Callable[[Path, threading.Event], object], store: JobStore | None = None) -> None:
        self.orchestrator_factory = orchestrator_factory
        self.store = store or JobStore()
        self.state = self.store.load()
        self._lock = threading.RLock()
        self._cancellations: dict[str, threading.Event] = {}
        self._recover_interrupted_jobs()

    def create_plan(self, project_root: Path, project_name: str, objective: str, relevant_files: list[str]) -> TaskPlan:
        """Registra o plano sem criar arquivos ou executar o Codex."""
        root = project_root.resolve()
        git = GitTool(root)
        assessment = ArchitectureGuard().assess(objective)
        warnings: list[str] = []
        if not git.is_repository():
            warnings.append("A execução isolada exige que o projeto esteja em um repositório Git.")
        elif not git.is_clean():
            warnings.append("Há alterações locais; faça commit ou stash antes de aprovar a execução isolada.")
        if assessment.reason:
            warnings.append(assessment.reason)
        plan = TaskPlan(
            id=uuid4().hex,
            project_root=root,
            project_name=project_name,
            objective=objective,
            base_branch=git.branch().strip() or None,
            relevant_files=relevant_files,
            warnings=warnings,
            architecture_decision_required=assessment.required,
            created_at=self._now(),
        )
        with self._lock:
            self.state.plans[plan.id] = plan
            self._save()
        return plan

    def start(self, plan_id: str, *, confirmed_write: bool) -> AgentJob:
        """Inicia uma tarefa aprovada e retorna imediatamente seu estado enfileirado."""
        if not confirmed_write:
            raise UnsafeCommandError("A tarefa pode alterar arquivos no worktree. Envie confirmed_write=true após confirmação explícita.")
        with self._lock:
            plan = self._plan(plan_id)
            if plan.architecture_decision_required and not plan.architecture_approved:
                raise ArchitectureDecisionRequired("O plano exige uma decisão arquitetural antes da execução.")
            if plan.id in self.state.jobs:
                return self.state.jobs[plan.id]
            job = AgentJob(
                id=plan.id,
                plan_id=plan.id,
                project_root=plan.project_root,
                objective=plan.objective,
                status="queued",
                created_at=self._now(),
            )
            self.state.jobs[job.id] = job
            cancel_event = threading.Event()
            self._cancellations[job.id] = cancel_event
            self._save()
        threading.Thread(target=self._run, args=(job.id, cancel_event), name=f"dev-agent-{job.id[:8]}", daemon=True).start()
        return job

    def get_job(self, job_id: str) -> AgentJob:
        with self._lock:
            try:
                return self.state.jobs[job_id]
            except KeyError as exc:
                raise DevAgentError(f"Job não encontrado: {job_id}.") from exc

    def get_plan(self, plan_id: str) -> TaskPlan:
        with self._lock:
            return self._plan(plan_id)

    def approve_architecture(self, plan_id: str, decision: str) -> TaskPlan:
        """Registra a decisão explícita necessária para um plano estrutural."""
        if len(decision.strip()) < 10:
            raise DevAgentError("Descreva a decisão arquitetural para aprovar o plano.")
        with self._lock:
            plan = self._plan(plan_id)
            updated = plan.model_copy(update={"architecture_approved": True, "architecture_decision": decision.strip()[:1_000]})
            self.state.plans[plan_id] = updated
            self._save()
            return updated

    def cancel(self, job_id: str) -> AgentJob:
        """Cancela job pendente/bloqueado ou solicita interrupção cooperativa de job em execução."""
        with self._lock:
            job = self.get_job(job_id)
            if job.status in {"completed", "failed", "cancelled"}:
                return job
            cancellation = self._cancellations.setdefault(job_id, threading.Event())
            cancellation.set()
            if job.status in {"queued", "blocked"}:
                job = job.model_copy(update={"status": "cancelled", "cancellation_requested": True, "resumable": False, "finished_at": self._now()})
            else:
                job = job.model_copy(update={"cancellation_requested": True})
            self.state.jobs[job.id] = job
            self._save()
            return job

    def resume(self, job_id: str) -> AgentJob:
        """Retoma um job interrompido a partir do seu último checkpoint, no mesmo worktree."""
        with self._lock:
            job = self.get_job(job_id)
            if job.status == "running":
                return job
            if not job.resumable or job.worktree_path is None or job.worktree_removed:
                raise DevAgentError("Este job não pode ser retomado; não há checkpoint utilizável ou o worktree foi removido.")
            if job.resume_attempts >= 3:
                raise DevAgentError("Este job atingiu o limite de 3 retomadas; revise o erro e crie um novo plano.")
            job = job.model_copy(update={"status": "queued", "error": None, "cancellation_requested": False, "finished_at": None, "resume_attempts": job.resume_attempts + 1})
            self.state.jobs[job.id] = job
            cancel_event = threading.Event()
            self._cancellations[job.id] = cancel_event
            self._save()
        threading.Thread(target=self._run, args=(job.id, cancel_event), name=f"dev-agent-{job.id[:8]}-resume", daemon=True).start()
        return job

    def cleanup_worktree(self, job_id: str, *, confirmed_cleanup: bool) -> AgentJob:
        """Remove um worktree de job finalizado após confirmação explícita."""
        if not confirmed_cleanup:
            raise UnsafeCommandError("A remoção do worktree descarta alterações não commitadas. Envie confirmed_cleanup=true após confirmação explícita.")
        with self._lock:
            job = self.get_job(job_id)
            if job.status not in {"completed", "failed", "cancelled", "blocked"}:
                raise DevAgentError("Aguarde o job terminar antes de remover seu worktree.")
            if job.worktree_removed or not job.worktree_path:
                return job
            GitTool(job.project_root).remove_worktree(job.worktree_path)
            updated = job.model_copy(update={"worktree_removed": True, "worktree_path": None, "resumable": False})
            self.state.jobs[job_id] = updated
            self._save()
            return updated

    def _run(self, job_id: str, cancellation: threading.Event) -> None:
        try:
            if cancellation.is_set():
                self._finish(job_id, "cancelled")
                return
            self._update(job_id, status="running", started_at=self._now())
            job = self.get_job(job_id)
            if job.worktree_path is None:
                worktree, branch = GitTool(job.project_root).create_worktree(job.id)
                self._update(job_id, worktree_path=worktree, branch=branch)
            else:
                worktree, branch = job.worktree_path, job.branch
            if cancellation.is_set():
                self._finish(job_id, "cancelled")
                return
            service = self.orchestrator_factory(worktree, cancellation)
            plan = self.get_plan(job.plan_id)
            results = service.task(
                job.objective,
                architecture_approved=plan.architecture_approved,
                job_id=job.id,
                on_checkpoint=lambda point: self._on_checkpoint(job_id, point),
                resume_from=job.last_checkpoint,
            )
            diff = SensitiveDataRedactor.redact(GitTool(worktree).full_diff()) or ""
            partial = any(item.agent == "test" and item.warnings for item in results)
            final_status = "partially_completed" if partial else "completed"
            final_phase = TaskStatus.PARTIALLY_COMPLETED if partial else TaskStatus.COMPLETED
            self._update(job_id, results=results, diff=diff, resumable=False)
            self._finish(job_id, "cancelled" if cancellation.is_set() else final_status, phase=final_phase)
        except Exception as exc:  # Mantém a falha no job sem derrubar a API local.
            job = self.get_job(job_id)
            if cancellation.is_set():
                self._finish(job_id, "cancelled")
            elif job.last_checkpoint is not None:
                self._finish(job_id, "blocked", error=self._safe_error(exc), resumable=True)
            else:
                self._finish(job_id, "failed", error=self._safe_error(exc))

    def _on_checkpoint(self, job_id: str, point: Checkpoint) -> None:
        self._update(job_id, phase=point.phase, last_checkpoint=point, results=point.results, resumable=True)

    def _finish(self, job_id: str, status: str, *, error: str | None = None, phase: TaskStatus | None = None, resumable: bool | None = None) -> None:
        changes: dict[str, object] = {"status": status, "error": error, "finished_at": self._now()}
        if phase is not None:
            changes["phase"] = phase
        if resumable is not None:
            changes["resumable"] = resumable
        if status == "cancelled":
            changes["resumable"] = False
        self._update(job_id, **changes)

    def _update(self, job_id: str, **changes) -> AgentJob:
        with self._lock:
            job = self.get_job(job_id)
            updated = job.model_copy(update=changes)
            self.state.jobs[job_id] = updated
            self._save()
            return updated

    def _plan(self, plan_id: str) -> TaskPlan:
        try:
            return self.state.plans[plan_id]
        except KeyError as exc:
            raise DevAgentError(f"Plano não encontrado: {plan_id}.") from exc

    def _recover_interrupted_jobs(self) -> None:
        interrupted = False
        for job_id, job in list(self.state.jobs.items()):
            if job.status in {"queued", "running"}:
                if job.resumable and job.worktree_path is not None and not job.worktree_removed:
                    changes = {
                        "status": "blocked",
                        "error": "A API local foi reiniciada antes de o job terminar; use resume para continuar do último checkpoint.",
                        "finished_at": self._now(),
                    }
                else:
                    changes = {
                        "status": "failed",
                        "error": "A API local foi reiniciada antes de o job terminar.",
                        "finished_at": self._now(),
                    }
                self.state.jobs[job_id] = job.model_copy(update=changes)
                interrupted = True
        if interrupted:
            self._save()

    def _save(self) -> None:
        self.store.save(JobState(plans=self.state.plans, jobs=self.state.jobs))

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _safe_error(error: Exception) -> str:
        message = str(error)
        if any(term in message.lower() for term in ("api key", "token", "password", "secret")):
            return "A tarefa falhou; os detalhes foram ocultados por segurança."
        return (SensitiveDataRedactor.redact(message) or "")[:500] or "A tarefa falhou sem detalhes disponíveis."
