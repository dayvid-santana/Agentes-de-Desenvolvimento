"""API local, escutada somente em 127.0.0.1."""
from __future__ import annotations
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Expor o catálogo declarativo de Agents (AgentRegistry) pela API local.
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Expor os agentes disponíveis pela API local.
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Integrar uma assistente externa ao backend local dos agents.
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Expor a prontidão autenticada do Codex pela API local.
# DevAgent
# Autor: Dayvid Santana
# Data: 01/09/2026
# Objetivo: Expor a verificação e aplicação confirmada de cabeçalhos ausentes.
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from dev_agent.agents.registry import AgentRegistry
from dev_agent.api.assistant_backend import router as assistant_backend_router
from dev_agent.config.loader import discover_project
from dev_agent.errors import DevAgentError, UnsafeCommandError
from dev_agent.memory.session_store import SessionStore
from dev_agent.core.models import HeaderBatchResult
from dev_agent.core.orchestrator import Orchestrator
from dev_agent.providers.codex.provider import CodexProvider

app = FastAPI(title="DevAgent", version="0.1.0")
app.include_router(assistant_backend_router)

class ProjectRequest(BaseModel): cwd: Path
class ObjectiveRequest(ProjectRequest): objective: str
class ReviewRequest(ProjectRequest): staged: bool = False
class HeadersRequest(ProjectRequest):
    confirmed_apply: bool = False
    objective: str = "Adicionar cabeçalho padrão."

def orchestrator(cwd: Path) -> Orchestrator:
    return Orchestrator(discover_project(cwd), CodexProvider())

@app.exception_handler(DevAgentError)
async def known_error(_, exc: DevAgentError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})

@app.get("/health")
def health(): return {"status": "ok", "host": "127.0.0.1"}

@app.get("/health/codex")
def codex_health(force: bool = False):
    return CodexProvider().readiness(Path.cwd(), force=force).model_dump(mode="json")

@app.get("/agents")
def agents(): return [agent.model_dump() for agent in Orchestrator.available_agents()]

@app.get("/agents/catalog")
def agents_catalog(): return [manifest.model_dump(mode="json") for manifest in AgentRegistry().list()]

@app.get("/agents/catalog/{agent_id}")
def agents_catalog_show(agent_id: str):
    try:
        return AgentRegistry().get(agent_id).model_dump(mode="json")
    except KeyError as exc:
        raise DevAgentError(str(exc)) from exc

@app.get("/agents/graph")
def agents_graph(): return AgentRegistry().graph()

@app.get("/agents/doctor")
def agents_doctor(): return AgentRegistry().doctor()

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
@app.post("/agent/task", deprecated=True)
def task(request: ObjectiveRequest):
    raise UnsafeCommandError(
        "A execução direta foi desativada. Crie um plano em /assistant/task-plans e inicie-o com confirmação explícita."
    )
@app.post("/agent/review")
def review(request: ReviewRequest): return orchestrator(request.cwd).review(request.staged).model_dump(mode="json")
@app.post("/agent/test")
def test(request: ProjectRequest): return orchestrator(request.cwd).test().model_dump(mode="json")
@app.post("/agent/debug")
def debug(request: ObjectiveRequest): return orchestrator(request.cwd).debug(request.objective).model_dump(mode="json")
@app.post("/git/commit-plan")
def commit_plan(request: ProjectRequest): return [item.model_dump() for item in orchestrator(request.cwd).commit_plan()]

@app.post("/headers", response_model=HeaderBatchResult)
def headers(request: HeadersRequest) -> HeaderBatchResult:
    service = orchestrator(request.cwd)
    if request.confirmed_apply:
        return service.aplicarCabecalhosAusentes(request.objective)
    return service.listarCabecalhosAusentes()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("dev_agent.api.app:app", host="127.0.0.1", port=8765, reload=False)
