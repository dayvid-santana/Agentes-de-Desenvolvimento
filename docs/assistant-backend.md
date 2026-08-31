<!--
dev-agent
Autor: Dayvid Santana
Data: 31/08/2026
Objetivo: Documentar o projeto atual de forma abrangente.
-->
<!--
DevAgent-Task: 4826528013919681285
-->


# API local e backend para assistentes externas

## Escopo e segurança

A aplicação FastAPI se chama `DevAgent` e tem versão `0.1.0`. Ao executar o módulo `dev_agent.api.app`, ela escuta em `127.0.0.1:8765`. Erros de domínio retornam HTTP 400 no formato `{ "detail": "..." }`; validações de corpo/caminho feitas pelo FastAPI retornam HTTP 422.

Não há autenticação, autorização, TLS ou isolamento multiusuário. A API é um backend local e não deve ser publicada em rede. Caminhos enviados em `cwd` devem levar, diretamente ou por um diretório pai, a um `dev-agent.yaml` válido.

## Endpoints gerais

| Método e rota | Corpo | Resultado |
|---|---|---|
| `GET /health` | — | Estado da API e host configurado. |
| `GET /health/codex?force=false` | — | `CodexReadiness` sanitizado. A consulta fica em cache por até 60 segundos, salvo `force=true`. |
| `GET /agents` | — | Descritores do catálogo para a API/CLI. |
| `GET /agents/catalog` | — | Manifests do catálogo declarativo. |
| `GET /agents/catalog/{agent_id}` | — | Manifest por ID, nome ou alias. |
| `GET /agents/graph` | — | Mapa de dependências declaradas. |
| `GET /agents/doctor` | — | Diagnóstico de dependências e entrypoints. |
| `GET /session` | — | Sessão local atual, ou `null`. |
| `POST /project/activate` | `{ "cwd": "..." }` | Raiz, nome e resultado do contexto inicial. |
| `POST /agent/context` | `{ "cwd": "...", "objective": "..." }` | `ContextPacket` e resultado do agente de contexto. |
| `POST /agent/ask` | igual ao anterior | Resposta de leitura. |
| `POST /agent/review` | `{ "cwd": "...", "staged": false }` | Revisão do diff atual ou staged. |
| `POST /agent/test` | `{ "cwd": "..." }` | Resultado da suíte configurada. |
| `POST /agent/debug` | `{ "cwd": "...", "objective": "..." }` | Diagnóstico baseado em contexto e testes. |
| `POST /git/commit-plan` | `{ "cwd": "..." }` | Sugestões de commits; não grava commits. |

`POST /agent/task` está marcado como obsoleto e sempre recusa a execução direta. Use o fluxo de planos abaixo.

## Invocações de leitura para assistentes externas

`GET /assistant/agents` informa os agentes invocáveis diretamente.

`POST /assistant/invocations` aceita:

```json
{
  "cwd": "C:\\Projetos\\Faturas",
  "agent": "security",
  "objective": "Avaliar autenticação e exposição de segredos",
  "staged": false,
  "confirmed_write": false
}
```

Os campos `agent` e `objective` têm, respectivamente, limite de 80 e 4.000 caracteres. Os nomes aceitos são `ask`, `context`, `review`, `test`, `debug`, `git`, `documentation`, `bug_reproduction` e os especialistas `requirements`, `security`, `database`, `api_contract`, `quality`, `dependency`, `performance`, `frontend`, `observability`, `release` e `refactor`.

`agent: "task"` aparece na listagem para indicar o fluxo disponível, porém a invocação direta é deliberadamente recusada. `implementation`, agentes de escrita e políticas não são invocáveis por essa rota.

## Planos e jobs de escrita

1. Crie um plano sem escrever:

   ```http
   POST /assistant/task-plans
   Content-Type: application/json

   {"cwd":"C:\\Projetos\\Faturas","objective":"Adicionar validação de CPF"}
   ```

2. Se `architecture_decision_required` for verdadeiro, registre uma decisão humana de 10 a 1.000 caracteres:

   ```http
   POST /assistant/task-plans/{id}/architecture-approval

   {"decision":"Manter o contrato atual e validar no serviço de domínio."}
   ```

3. Inicie a tarefa de fundo explicitamente:

   ```http
   POST /assistant/task-plans/{id}/start

   {"confirmed_write":true}
   ```

   Antes de enfileirar o job, essa rota executa a verificação de prontidão do Codex na raiz do projeto. Se ela falhar, a rota devolve erro de domínio e nenhum job é criado.

4. Consulte ou controle o job:

   | Método e rota | Efeito |
   |---|---|
   | `GET /assistant/jobs/{id}` | Devolve o job, fase, resultados, diff redigido, branch e worktree. |
   | `POST /assistant/jobs/{id}/cancel` | Solicita cancelamento cooperativo. |
| `POST /assistant/jobs/{id}/resume` | Retoma um job bloqueado com checkpoint e worktree registrado que ainda não foi marcado como removido. |
   | `POST /assistant/jobs/{id}/cleanup` com `{ "confirmed_cleanup": true }` | Remove worktree de job finalizado, bloqueado ou cancelado. |

Os status persistidos são `queued`, `running`, `completed`, `partially_completed`, `failed`, `cancelled` e `blocked`. Consulte [orchestration.md](orchestration.md) para as regras de worktree, checkpoint e retomada.

## Formatos relevantes de resposta

`SubAgentResult` contém `agent`, `summary`, `files_read`, `files_changed`, `tests_executed`, `warnings`, `architecture_decision_required` e `next_actions`.

`TaskPlan` contém ID, raiz/nome do projeto, objetivo, branch-base, arquivos relevantes, avisos, necessidade/aprovação/decisão arquitetural, confirmação requerida e data de criação. `AgentJob` acrescenta status, fase, branch, worktree, resultados, diff, erro sanitizado, dados de cancelamento/retomada e checkpoint.

Não há documentação OpenAPI versionada, exemplos para todas as respostas, paginação, nem endpoints para listar ou recuperar um plano isoladamente. Como a aplicação usa a configuração padrão do FastAPI, o esquema e a interface interativa usuais ficam expostos em `/openapi.json` e `/docs` quando o servidor está em execução; esse contrato não é versionado nem verificado diretamente pela suíte do projeto.
