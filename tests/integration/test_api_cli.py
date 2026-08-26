from pathlib import Path
from fastapi.testclient import TestClient
from dev_agent.api.app import app
from dev_agent.config.loader import render_default_config

def test_health_endpoint():
    client = TestClient(app)
    assert client.get("/health").json()["status"] == "ok"

def test_project_activate_via_api(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    (tmp_path / "dev-agent.yaml").write_text(render_default_config("Demo"), encoding="utf-8")
    client = TestClient(app)
    response = client.post("/project/activate", json={"cwd": str(tmp_path)})
    assert response.status_code == 200
    assert response.json()["project_name"] == "Demo"
