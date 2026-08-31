<!--
dev-agent
Autor: Dayvid Santana
Data: 31/08/2026
Objetivo: Documentar o projeto atual de forma abrangente.
-->
<!--
DevAgent-Task: 4826528013919681285
-->


# Segurança e limites operacionais

## Limites de arquivo e execução

`FileSystem.resolve()` resolve caminhos e confirma que permanecem dentro da raiz ativa; tentativas de sair dela levantam `PathOutsideProjectError`. As ferramentas de contexto e escrita usam essa abstração.

`TerminalTool` executa listas de argumentos com `shell=False` e usa `CommandPolicy` antes de iniciar o processo. Sem confirmação explícita, a política bloqueia:

- `git reset --hard`;
- `git clean` com força e diretórios;
- `git push --force`/`-f`;
- `git branch -D`;
- remoções recursivas/forçadas como `rm -rf`, `Remove-Item -Recurse -Force`, `del /s` e equivalentes reconhecidos.

O bloqueio é baseado em padrões de texto, não em uma análise completa de shell ou em sandbox de sistema. O projeto não declara um mecanismo de autorização do usuário além dos campos/flags de confirmação do próprio DevAgent. A configuração `security.require_destructive_command_approval` não é consultada por `TerminalTool`; na implementação atual, comandos reconhecidos continuam exigindo confirmação mesmo se o campo for alterado.

## Contexto, logs e persistência

`SensitiveDataRedactor` remove valores associados a chaves comuns (`api_key`, `token`, `secret`, `password`), Bearer tokens longos, chaves privadas PEM, credenciais em URLs e formatos usuais de tokens. Ele é aplicado a conteúdo de contexto, diff, respostas/resultados, erros de job e dados que entram na sessão.

O logger estruturado exclui campos cujo nome inclui `secret`, `token`, `password`, `content` ou `prompt`. Essa filtragem avalia somente o nome do campo e não redige valores. Em particular, `TerminalTool` registra o campo `command`; `CodexProvider` passa o prompt como argumento de `codex exec`, portanto o prompt pode ser escrito no log local dentro desse campo. Este é um limite conhecido da implementação atual: não inclua segredos nos objetivos/prompts e proteja os logs locais.

Sessão e jobs são persistidos localmente, por padrão em `%LOCALAPPDATA%\DevAgent` (com fallback no diretório temporário para alguns erros de permissão). Resumos, avisos, diffs e erros de job passam pela redação antes de serem persistidos. Contudo, `TaskPlan.objective`, `AgentJob.objective`, `ProjectSession.objective` e `ProjectSession.recent_tasks` recebem o texto informado pelo usuário sem uma etapa equivalente de redação. Assim, a afirmação do `JobStore` de que não grava prompts ou credenciais não é uma garantia técnica para esses campos: não use segredos em objetivos, decisões ou argumentos de CLI. Não há criptografia ou mecanismo de retenção configurável documentado.

## Codex e API

`CodexProvider` chama `codex exec` com `--ask-for-approval never` e usa sandbox `read-only` para análises e `workspace-write` para agentes que escrevem. Chamadas somente leitura podem repetir até três vezes diante de erros transitórios; chamadas de escrita têm uma tentativa. A prontidão executa uma sonda `READY` em modo leitura e devolve um diagnóstico sanitizado, com cache de 60 segundos.

O servidor padrão é ligado a loopback, mas não possui autenticação, autorização, rate limiting, TLS nem isolamento multiusuário. A exposição fora da máquina local é um risco não mitigado pelo código atual. A execução Docker também publica apenas em `127.0.0.1` no Compose fornecido.

## Aprovação e isolamento de tarefas

O guard arquitetural é uma heurística por palavras-chave; pedidos que mencionam, por exemplo, autenticação, banco de dados, contrato público, fila ou deploy exigem decisão registrada. `Orchestrator.task()` respeita `security.require_architecture_approval`, mas a criação/início normal de planos usa `TaskJobManager`, que exige aprovação sempre que a heurística marcar o objetivo. Isso não substitui revisão técnica humana.

Uma tarefa que escreve exige confirmação, repositório Git limpo e worktree separado. A remoção do worktree exige confirmação adicional e pode descartar alterações não commitadas nele. Não há commit, push ou rollback automáticos.
