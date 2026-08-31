<!--
dev-agent
Autor: Dayvid Santana
Data: 31/08/2026
Objetivo: Documentar o projeto atual de forma abrangente.
-->
<!--
DevAgent-Task: 4826528013919681285
-->


# Visão geral do DevAgent

Este documento descreve o estado observado no repositório. O DevAgent é um pacote Python local que coordena tarefas de desenvolvimento assistidas por IA em projetos que contêm `dev-agent.yaml`. A execução de modelo em produção depende da CLI Codex instalada no computador; não há integração HTTP direta com um modelo neste código.

## Componentes e fronteiras

| Área | Responsabilidade atual |
|---|---|
| `src/dev_agent/cli/` | Comandos Typer que iniciam, param e consomem a API local por HTTP. Não instancia agentes diretamente. |
| `src/dev_agent/api/` | Aplicação FastAPI e rotas para operações locais, planos, jobs e integrações de assistentes. |
| `src/dev_agent/core/` | Contratos Pydantic, orquestração, máquina de estados, gateway de assistente e gerenciamento assíncrono de jobs. |
| `src/dev_agent/agents/` | Agentes especializados de contexto, escrita, teste, revisão, diagnóstico e análise. O registro vem de `agents/catalog.yaml`. |
| `src/dev_agent/tools/` | Operações encapsuladas de arquivos, busca, Git, terminal e testes. |
| `src/dev_agent/providers/` | Protocolo independente de provider e adaptador da CLI Codex em `providers/codex/`. |
| `src/dev_agent/security/` | Heurística arquitetural, política de comandos destrutivos e redação de padrões sensíveis. |
| `src/dev_agent/memory/` | Armazenamento local de sessão, planos e jobs. |
| `src/dev_agent/headers/` | Serviço central que acrescenta cabeçalhos aos formatos suportados quando um arquivo alterado ainda não tem cabeçalho. |
| `tests/` | Testes unitários e de integração local, com fakes para o provider e Git quando necessário. |

`AGENTS.md` na raiz complementa essas fronteiras com regras de implementação. O `ContextAgent` inclui esse arquivo e eventuais `AGENTS.md` aninhados como instruções para os agentes.

## Dependências e empacotamento

O projeto usa Hatchling, requer Python 3.11 ou superior e publica o comando `dev-agent`. As dependências de runtime declaradas são FastAPI, Uvicorn, Pydantic, PyYAML, Typer, Rich e HTTPX. As dependências opcionais `dev` adicionam `pytest` e `pytest-asyncio`.

O `Dockerfile` cria uma imagem baseada em `python:3.11-slim`, instala Git e o pacote com o extra `dev`. O `compose.yaml` oferece os serviços `api` e `tests`. Ele é adequado para desenvolvimento local; a autenticação necessária para o Codex continua fora do contêiner no fluxo documentado.

## Dados locais produzidos em execução

Com a configuração padrão do Windows, sessão, planos e jobs ficam em `%LOCALAPPDATA%\DevAgent`. Os nomes de arquivos usados são `current-session.json`, `agent-jobs.json` e, enquanto uma gravação de jobs está em curso, um arquivo de lock de mesmo sufixo `.lock`. Em erro de permissão durante gravação, sessão e jobs usam `%TEMP%\DevAgent` como fallback.

O processo da API iniciado pela CLI usa `%LOCALAPPDATA%\DevAgent\server.pid` para registrar o PID. Esse arquivo não substitui a verificação de saúde: a CLI considera o servidor ativo somente se `GET /health` responder com sucesso.

## Limites observáveis

- O repositório não contém licença, pipeline de CI, definição de release/publicação, política de suporte ou política de privacidade.
- Não há banco de dados, fila, servidor remoto, autenticação de API ou mecanismo de multiusuário implementados.
- O catálogo declara dependências entre agentes, mas o único fluxo de tarefa implementado é a sequência fixa do `Orchestrator`; não existe agendador genérico baseado no grafo.
- A integração com Codex e a prontidão autenticada são exercitadas com fakes/monkeypatch nos testes. Não há teste automatizado contra uma conta Codex real.

Para comandos de operação, consulte o [README](../README.md). Os comportamentos de execução, segurança e verificação estão detalhados, respectivamente, em [orchestration.md](orchestration.md), [security.md](security.md) e [testing.md](testing.md).
