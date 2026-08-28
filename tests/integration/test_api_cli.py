# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Cobrir a listagem de agentes pela API e CLI.
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Cobrir o argumento posicional do comando de depuração.
from pathlib import Path
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from dev_agent.api.app import app
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
    assert "review --staged" in result.output


def test_agents_command_uses_local_api(monkeypatch):
    monkeypatch.setattr("dev_agent.cli.app._api", lambda method, endpoint: [{"name": "context", "mode": "read", "command": "dev-agent context"}])
    result = runner.invoke(cli_app, ["agents"])
    assert result.exit_code == 0
    assert "context" in result.output
    assert "dev-agent context" in result.output


def test_debug_accepts_a_positional_message(monkeypatch):
    recorded: dict[str, object] = {}

    def api(method, endpoint, payload=None):
        recorded.update(method=method, endpoint=endpoint, payload=payload)
        return {"agent": "debug", "summary": "ok"}

    monkeypatch.setattr("dev_agent.cli.app._api", api)
    result = runner.invoke(cli_app, ["debug", "Erro ao salvar fatura"])
    assert result.exit_code == 0
    assert recorded["payload"] == {"cwd": str(Path.cwd()), "objective": "Erro ao salvar fatura"}
