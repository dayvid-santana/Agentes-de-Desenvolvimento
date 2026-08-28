"""API local, escutada somente em 127.0.0.1."""
from __future__ import annotations
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Expor os agentes disponíveis pela API local.
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from dev_agent.config.loader import discover_project
from dev_agent.errors import DevAgentError
from dev_agent.memory.session_store import SessionStore
from dev_agent.core.orchestrator import Orchestrator
from dev_agent.providers.codex.provider import CodexProvider

app = FastAPI(title="DevAgent", version="0.1.0")

class ProjectRequest(BaseModel): cwd: Path
class ObjectiveRequest(ProjectRequest): objective: str
class ReviewRequest(ProjectRequest): staged: bool = False

def orchestrator(cwd: Path) -> Orchestrator:
    return Orchestrator(discover_project(cwd), CodexProvider())

@app.exception_handler(DevAgentError)
async def known_error(_, exc: DevAgentError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})

@app.get("/health")
def health(): return {"status": "ok", "host": "127.0.0.1"}

@app.get("/agents")
def agents(): return [agent.model_dump() for agent in Orchestrator.available_agents()]

@app.get("/session")
def session():
    current = SessionStore().load()
    return current.model_dump(mode="json") if current else None

@app.post("/project/activate")
def activate(request: ProjectRequest):
    service = orchestrator(request.cwd)
    packet, result = service.context()
    return {"project_root": str(packet.project_root), "project_name": packet.project_name, "result": result.model_dump(mode="json")}

@app.post("/agent/context")
def context(request: ObjectiveRequest):
    packet, result = orchestrator(request.cwd).context(request.objective)
    return {"packet": packet.model_dump(mode="json"), "result": result.model_dump(mode="json")}

@app.post("/agent/ask")
def ask(request: ObjectiveRequest): return orchestrator(request.cwd).ask(request.objective).model_dump(mode="json")
@app.post("/agent/task")
def task(request: ObjectiveRequest): return [item.model_dump(mode="json") for item in orchestrator(request.cwd).task(request.objective)]
@app.post("/agent/review")
def review(request: ReviewRequest): return orchestrator(request.cwd).review(request.staged).model_dump(mode="json")
@app.post("/agent/test")
def test(request: ProjectRequest): return orchestrator(request.cwd).test().model_dump(mode="json")
@app.post("/agent/debug")
def debug(request: ObjectiveRequest): return orchestrator(request.cwd).debug(request.objective).model_dump(mode="json")
@app.post("/git/commit-plan")
def commit_plan(request: ProjectRequest): return [item.model_dump() for item in orchestrator(request.cwd).commit_plan()]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("dev_agent.api.app:app", host="127.0.0.1", port=8765, reload=False)
