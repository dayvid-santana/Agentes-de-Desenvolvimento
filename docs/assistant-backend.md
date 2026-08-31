<!--
DevAgent
Autor: Dayvid Santana
Data: 28/08/2026
Objetivo: Documentar o backend local para integração de assistentes externas.
-->
<!--
DevAgent
Autor: Dayvid Santana
Data: 28/08/2026
Objetivo: Documentar planejamento, prontidão e jobs isolados dos agents.
-->

# Backend para assistente externa

O DevAgent expõe uma integração REST local para o repositório da assistente virtual. A assistente envia uma solicitação identificando o agent desejado, e o backend a encaminha ao `Orchestrator`.

O serviço permanece restrito a `127.0.0.1:8765`. Não o exponha na internet: esta versão não implementa autenticação nem isolamento multiusuário.

## Contrato

Liste os agents invocáveis diretamente:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/assistant/agents
```

Envie uma análise de segurança ao agent especializado:

```powershell
$body = @{
  cwd = "C:\Projetos\Faturas"
  agent = "security"
  objective = "Avalie autenticação, validação de entrada e exposição de segredos"
} | ConvertTo-Json

Invoke-RestMethod http://127.0.0.1:8765/assistant/invocations -Method Post -ContentType "application/json" -Body $body
```

Os agents de análise aceitos incluem `requirements`, `security`, `database`, `api_contract`, `quality`, `dependency`, `performance`, `frontend`, `observability`, `release`, `refactor`, `documentation`, `bug_reproduction`, `context`, `ask`, `review`, `test`, `debug` e `git`.

## Tarefas que alteram código

Não envie `agent: "task"` para `/assistant/invocations`: esse atalho foi bloqueado. Primeiro, crie um plano sem alterar arquivos:

```json
POST /assistant/task-plans

{
  "cwd": "C:\\Projetos\\Faturas",
  "objective": "Adicionar validação de CPF"
}
```

O plano informa arquivos relevantes, a branch-base, riscos e se é necessária uma decisão arquitetural. Se for necessária, registre a decisão humana antes da execução:

```json
POST /assistant/task-plans/{id}/architecture-approval

{
  "decision": "Usar validação no serviço de domínio e manter o contrato atual da API."
}
```

Depois da confirmação explícita do usuário, inicie o plano:

```json
POST /assistant/task-plans/{id}/start

{
  "confirmed_write": true
}
```

O resultado inicial é um job com estado `queued`. Consulte `GET /assistant/jobs/{id}` para obter `running`, `completed`, `partially_completed`, `failed`, `cancelled` ou `blocked`, a fase atual ou terminal do pipeline, o diff redigido, os resumos redigidos dos agents e o caminho do worktree. Para solicitar interrupção, use `POST /assistant/jobs/{id}/cancel`.

Se a API local for reiniciada com o job em andamento, ou se ele falhar depois de concluir ao menos uma fase, o job vira `blocked` (em vez de `failed`) e mantém o worktree. Use `POST /assistant/jobs/{id}/resume` para retomar a partir da última fase concluída, no mesmo worktree/branch, sem repetir chamadas ao provider já feitas com sucesso. Um job cancelado explicitamente nunca fica retomável. Veja [docs/orchestration.md](orchestration.md) para os detalhes da máquina de estados.

Cada job cria uma branch `dev-agent/{id}` em um worktree separado. O checkout principal não é alterado. O projeto precisa estar limpo antes da execução; assim, mudanças locais preexistentes não são perdidas nem misturadas à tarefa. Após revisar ou integrar as mudanças, remova o worktree apenas com confirmação explícita via `POST /assistant/jobs/{id}/cleanup` e `{ "confirmed_cleanup": true }`; essa operação descarta alterações não commitadas naquele worktree.

## Prontidão do Codex

Use `GET /health/codex` para verificar a CLI, a autenticação e uma chamada mínima em modo somente leitura. O resultado é armazenado por até 60 segundos e não expõe credenciais nem a saída bruta do Codex. No terminal, `dev-agent doctor` apresenta o mesmo diagnóstico.
