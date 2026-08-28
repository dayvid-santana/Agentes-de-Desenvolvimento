# DevAgent
# Autor: Dayvid Santana
# Data: 26/08/2026
# Objetivo: Expor a listagem de comandos da CLI.
"""Comandos globais que falam exclusivamente com a API local."""
from __future__ import annotations
import shutil
import sys
import importlib.util
from pathlib import Path

import httpx
import typer
from rich import print
from rich.pretty import Pretty

from dev_agent.cli import server
from dev_agent.config.loader import CONFIG_NAME, discover_project, load_config, render_default_config
from dev_agent.errors import DevAgentError
from dev_agent.memory.session_store import SessionStore

app = typer.Typer(help="DevAgent — assistente global de desenvolvimento.", no_args_is_help=True)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

def _cwd() -> Path: return Path.cwd()
def _api(method: str, endpoint: str, payload: dict | None = None):
    if not server.running() and not server.start(): raise typer.BadParameter("Não foi possível iniciar a API local do DevAgent.")
    response = httpx.request(method, f"{server.URL}{endpoint}", json=payload, timeout=900)
    if response.is_error: raise typer.BadParameter(response.json().get("detail", response.text))
    return response.json()
def _project_payload(**extra): return {"cwd": str(_cwd()), **extra}

@app.command("commands")
def commands() -> None:
    """Lista os comandos principais e exemplos rápidos de uso."""
    print(
        "[bold]Comandos disponíveis[/bold]\n\n"
        "[cyan]init[/cyan]     Cria o arquivo dev-agent.yaml no projeto atual.\n"
        "[cyan]doctor[/cyan]   Verifica Python, Git, Codex, API e configuração.\n"
        "[cyan]start[/cyan]    Inicia a API local.\n"
        "[cyan]stop[/cyan]     Para a API local.\n"
        "[cyan]status[/cyan]   Exibe o estado da API local.\n"
        "[cyan]context[/cyan]  Monta o contexto do projeto.\n"
        "[cyan]ask[/cyan]      Responde uma pergunta sobre o projeto.\n"
        "[cyan]task[/cyan]     Executa uma tarefa de desenvolvimento.\n"
        "[cyan]review[/cyan]   Revisa alterações; use --staged para o índice Git.\n"
        "[cyan]test[/cyan]     Executa os testes configurados.\n"
        "[cyan]debug[/cyan]    Investiga um problema no projeto.\n"
        "[cyan]commit[/cyan]   Sugere um plano de commit.\n"
        "[cyan]session[/cyan]  Consulta a sessão; use session clear para removê-la.\n\n"
        "[bold]Exemplos[/bold]\n"
        "dev-agent ask \"Explique o fluxo de cadastro\"\n"
        "dev-agent task \"Adicione validação de CPF\"\n"
        "dev-agent review --staged\n\n"
        "Use [cyan]dev-agent <comando> --help[/cyan] para os detalhes de cada comando."
    )

@app.command()
def init() -> None:
    """Cria dev-agent.yaml sem sobrescrever arquivo existente."""
    target = _cwd() / CONFIG_NAME
    if target.exists(): raise typer.BadParameter(f"{target} já existe; não será sobrescrito.")
    target.write_text(render_default_config(_cwd().name), encoding="utf-8", newline="\n")
    print(f"[green]Criado[/green] {target}")

@app.command()
def doctor() -> None:
    """Verifica runtime, Git, Codex, API e configuração do diretório atual."""
    rows = {"Python": shutil.which("python") or "ausente", "Git": shutil.which("git") or "ausente", "Codex": shutil.which("codex") or "ausente", "FastAPI": "disponível" if importlib.util.find_spec("fastapi") else "ausente", "API local": "ativa" if server.running() else "inativa"}
    try:
        root = discover_project(_cwd())
        load_config(root)
        rows["Projeto"] = str(root)
    except DevAgentError as exc: rows["Projeto"] = str(exc)
    print(Pretty(rows))

@app.command()
def start() -> None: print("[green]Servidor iniciado.[/green]" if server.start() else "Servidor já está ativo.")
@app.command()
def stop() -> None: print("[green]Servidor parado.[/green]" if server.stop() else "Servidor não estava ativo.")
@app.command()
def status() -> None: print("[green]ativo[/green]" if server.running() else "inativo")
@app.command()
def context(objective: str = "Compreender o projeto") -> None: print(Pretty(_api("POST", "/agent/context", _project_payload(objective=objective))))
@app.command()
def ask(question: str) -> None: print(Pretty(_api("POST", "/agent/ask", _project_payload(objective=question))))
@app.command()
def task(objective: str) -> None: print(Pretty(_api("POST", "/agent/task", _project_payload(objective=objective))))
@app.command()
def review(staged: bool = typer.Option(False, "--staged")) -> None: print(Pretty(_api("POST", "/agent/review", _project_payload(staged=staged))))
@app.command()
def test() -> None: print(Pretty(_api("POST", "/agent/test", _project_payload())))
@app.command()
def debug(message: str = "Investigar o estado atual do projeto") -> None: print(Pretty(_api("POST", "/agent/debug", _project_payload(objective=message))))
@app.command()
def commit() -> None: print(Pretty(_api("POST", "/git/commit-plan", _project_payload())))

session_app = typer.Typer(help="Consulta ou limpa a memória do projeto ativo.")
@session_app.callback(invoke_without_command=True)
def session(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        value = SessionStore().load(); print(Pretty(value.model_dump(mode="json") if value else "Não há sessão ativa."))
@session_app.command("clear")
def session_clear() -> None: SessionStore().clear(); print("Sessão ativa removida.")
app.add_typer(session_app, name="session")

def main() -> None: app()
if __name__ == "__main__": main()
