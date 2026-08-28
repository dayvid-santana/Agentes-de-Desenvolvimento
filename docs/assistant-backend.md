<!--
DevAgent
Autor: Dayvid Santana
Data: 28/08/2026
Objetivo: Documentar o backend local para integração de assistentes externas.
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

Para alterações, use `agent: "task"` somente depois de o usuário confirmar expressamente a operação. O campo `confirmed_write` é obrigatório nesse caso:

```json
{
  "cwd": "C:\\Projetos\\Faturas",
  "agent": "task",
  "objective": "Adicionar validação de CPF",
  "confirmed_write": true
}
```

Os subagents internos de escrita não são invocados isoladamente; `task` preserva a serialização, os cabeçalhos e os testes controlados pelo `Orchestrator`.
