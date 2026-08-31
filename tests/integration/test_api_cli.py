# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Cobrir a retomada de jobs bloqueados a partir do último checkpoint.
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Cobrir o catálogo declarativo de Agents pela API e os subcomandos da CLI.
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Cobrir a listagem de agentes pela API e CLI.
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Cobrir o argumento posicional do comando de depuração.
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Cobrir o backend de integração para assistentes externas.
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Cobrir o planejamento seguro e assíncrono de tarefas externas.
import time
from datetime import datetime, timezone
from pathlib import Path
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from dev_agent.api.app import app
from dev_agent.core.job_manager import TaskJobManager
from dev_agent.memory.job_store import JobStore
from dev_agent.cli.app import app as cli_app
from dev_agent.config.loader import render_default_config


runner = CliRunner()

def test_health_endpoint():
    client = TestClient(app)
    assert client.get("/health").json()["status"] == "ok"


def test_agents_endpoint_lists_registered_agents():
    client = TestClient(app)
    response = client.get("/agents")
    assert response.status_code == 200
    agents = response.json()
    assert {"context", "implementation", "architecture_guard"} <= {item["name"] for item in agents}
    assert next(item for item in agents if item["name"] == "context")["command"] == "dev-agent context"


def test_agents_catalog_endpoints_are_backed_by_the_registry():
    client = TestClient(app)

    catalog = client.get("/agents/catalog")
    assert catalog.status_code == 200
    assert {item["id"] for item in catalog.json()} >= {"context", "implementation", "architecture_guard"}

    show = client.get("/agents/catalog/context")
    assert show.status_code == 200
    assert show.json()["class_name"] == "ContextAgent"

    assert client.get("/agents/catalog/does-not-exist").status_code == 400

    graph = client.get("/agents/graph")
    assert graph.json()["implementation"] == ["context", "requirements"]

    doctor = client.get("/agents/doctor")
    assert doctor.status_code == 200
    assert all(item["status"] == "ok" for item in doctor.json())


def test_assistant_backend_lists_direct_agents():
    client = TestClient(app)

    response = client.get("/assistant/agents")

    assert response.status_code == 200
    assert {"ask", "security", "task"} <= {item["name"] for item in response.json()}


def test_assistant_backend_requires_confirmation_for_tasks(tmp_path: Path):
    (tmp_path / "dev-agent.yaml").write_text(render_default_config("Demo"), encoding="utf-8")
    client = TestClient(app)

    response = client.post(
        "/assistant/invocations",
        json={"cwd": str(tmp_path), "agent": "task", "objective": "Alterar um arquivo"},
    )

    assert response.status_code == 400
    assert "/assistant/task-plans" in response.json()["detail"]


def test_assistant_backend_creates_task_plan_without_writing(tmp_path: Path, monkeypatch):
    (tmp_path / "dev-agent.yaml").write_text(render_default_config("Demo"), encoding="utf-8")
    from dev_agent.api import assistant_backend

    monkeypatch.setattr(
        assistant_backend,
        "jobs",
        TaskJobManager(lambda root, cancellation: None, JobStore(tmp_path / "jobs.json")),
    )
    client = TestClient(app)

    response = client.post(
        "/assistant/task-plans",
        json={"cwd": str(tmp_path), "objective": "Adicionar validação simples"},
    )

    assert response.status_code == 200
    assert response.json()["requires_confirmation"]
    assert response.json()["project_name"] == "Demo"

def test_assistant_backend_resumes_a_blocked_job(tmp_path: Path, monkeypatch):
    from dev_agent.api import assistant_backend
    from dev_agent.core.models import Checkpoint, SubAgentResult, TaskStatus

    (tmp_path / "dev-agent.yaml").write_text(render_default_config("Demo"), encoding="utf-8")

    class ResumableOrchestrator:
        def task(self, objective, *, architecture_approved=False, job_id=None, on_checkpoint=None, resume_from=None):
            return [*resume_from.results, SubAgentResult(agent="review", summary="ok")]

    manager = TaskJobManager(lambda root, cancellation: ResumableOrchestrator(), JobStore(tmp_path / "jobs.json"))
    plan = manager.create_plan(tmp_path, "Demo", "Adicionar validação", [])
    job = manager.start(plan.id, confirmed_write=True)
    for _ in range(50):
        job = manager.get_job(job.id)
        if job.status in {"completed", "partially_completed", "failed", "cancelled", "blocked"}:
            break
        time.sleep(0.01)
    checkpoint = Checkpoint(
        job_id=job.id,
        phase=TaskStatus.EXECUTING,
        step_index=2,
        completed_agents=["implementation"],
        results=[SubAgentResult(agent="implementation", summary="parcial")],
        changed_files=[],
        created_at=datetime.now(timezone.utc),
    )
    manager.state.jobs[job.id] = job.model_copy(update={"status": "blocked", "resumable": True, "last_checkpoint": checkpoint, "worktree_path": tmp_path})
    manager._save()
    monkeypatch.setattr(assistant_backend, "jobs", manager)
    client = TestClient(app)

    response = client.post(f"/assistant/jobs/{job.id}/resume")
    assert response.status_code == 200

    for _ in range(50):
        job = manager.get_job(job.id)
        if job.status in {"completed", "partially_completed", "failed", "cancelled", "blocked"}:
            break
        time.sleep(0.01)
    assert job.status == "completed"
    assert [item.agent for item in job.results] == ["implementation", "review"]


def test_project_activate_via_api(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    (tmp_path / "dev-agent.yaml").write_text(render_default_config("Demo"), encoding="utf-8")
    client = TestClient(app)
    response = client.post("/project/activate", json={"cwd": str(tmp_path)})
    assert response.status_code == 200
    assert response.json()["project_name"] == "Demo"


def test_commands_lists_the_main_cli_commands():
    result = runner.invoke(cli_app, ["commands"])

    assert result.exit_code == 0
    assert "Comandos disponíveis" in result.output
    assert "init" in result.output
    assert "task" in result.output
    assert "document" in result.output
    assert "review --staged" in result.output


def test_document_command_creates_a_safe_documentation_plan(monkeypatch):
    recorded: dict[str, object] = {}

    def api(method, endpoint, payload=None):
        recorded.update(method=method, endpoint=endpoint, payload=payload)
        return {"id": "plan-123"}

    monkeypatch.setattr("dev_agent.cli.app._api", api)
    result = runner.invoke(cli_app, ["document", "src/modulo.py"])
    assert result.exit_code == 0
    assert recorded["method"] == "POST"
    assert recorded["endpoint"] == "/assistant/task-plans"
    assert "src/modulo.py" in recorded["payload"]["objective"]


def test_document_is_listed_in_cli_help():
    result = runner.invoke(cli_app, ["--help"])
    assert result.exit_code == 0
    assert "document" in result.output


def test_document_project_creates_a_project_documentation_plan(monkeypatch):
    recorded: dict[str, object] = {}

    def api(method, endpoint, payload=None):
        recorded.update(method=method, endpoint=endpoint, payload=payload)
        return {"id": "plan-project-docs"}

    monkeypatch.setattr("dev_agent.cli.app._api", api)
    result = runner.invoke(cli_app, ["document-project"])
    assert result.exit_code == 0
    assert recorded["endpoint"] == "/assistant/task-plans"
    assert recorded["payload"]["objective"].startswith("Documentar o projeto")


def test_agents_command_uses_local_api(monkeypatch):
    monkeypatch.setattr("dev_agent.cli.app._api", lambda method, endpoint: [{"name": "context", "mode": "read", "command": "dev-agent context"}])
    result = runner.invoke(cli_app, ["agents"])
    assert result.exit_code == 0
    assert "context" in result.output
    assert "dev-agent context" in result.output


def test_agents_subcommands_call_the_expected_endpoints(monkeypatch):
    calls: list[tuple[str, str]] = []

    def api(method, endpoint, payload=None):
        calls.append((method, endpoint))
        return {}

    monkeypatch.setattr("dev_agent.cli.app._api", api)
    for args, endpoint in [
        (["agents", "list"], "/agents/catalog"),
        (["agents", "show", "context"], "/agents/catalog/context"),
        (["agents", "graph"], "/agents/graph"),
        (["agents", "doctor"], "/agents/doctor"),
    ]:
        result = runner.invoke(cli_app, args)
        assert result.exit_code == 0, result.output
        assert calls[-1] == ("GET", endpoint)


def test_resume_command_calls_the_job_resume_endpoint(monkeypatch):
    calls: list[tuple[str, str]] = []

    def api(method, endpoint, payload=None):
        calls.append((method, endpoint))
        return {"status": "queued"}

    monkeypatch.setattr("dev_agent.cli.app._api", api)
    result = runner.invoke(cli_app, ["resume", "job-123"])
    assert result.exit_code == 0
    assert calls[-1] == ("POST", "/assistant/jobs/job-123/resume")


def test_debug_accepts_a_positional_message(monkeypatch):
    recorded: dict[str, object] = {}

    def api(method, endpoint, payload=None):
        recorded.update(method=method, endpoint=endpoint, payload=payload)
        return {"agent": "debug", "summary": "ok"}

    monkeypatch.setattr("dev_agent.cli.app._api", api)
    result = runner.invoke(cli_app, ["debug", "Erro ao salvar fatura"])
    assert result.exit_code == 0
    assert recorded["payload"] == {"cwd": str(Path.cwd()), "objective": "Erro ao salvar fatura"}
