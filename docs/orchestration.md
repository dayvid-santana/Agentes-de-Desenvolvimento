<!--
dev-agent
Autor: Dayvid Santana
Data: 31/08/2026
Objetivo: Documentar o projeto atual de forma abrangente.
-->
<!--
DevAgent-Task: 4826528013919681285
-->


# Orquestração, jobs e retomada

## Pipeline atual

`Orchestrator.task()` usa uma sequência fixa, não um loop aberto de ferramentas. A guarda arquitetural é avaliada antes da máquina de estados. Sem aprovação necessária, ou quando ela já foi registrada, as fases reais são:

```text
RECEIVED
  -> DISCOVERING  : ContextAgent
  -> PLANNING     : RequirementsAgent                 (checkpoint 1)
  -> EXECUTING    : Implementation, CodeDocumentation,
                    TestAuthor, DocumentationWriter   (checkpoint 2)
  -> TESTING      : TestAgent, BugReproduction        (checkpoint 3)
  -> REVIEWING    : Review, Documentation e dez especialistas
                                                     (checkpoint 4)
  -> COMPLETED | PARTIALLY_COMPLETED
```

Quando o objetivo começa por `documentar o projeto` (sem diferenciar maiúsculas/minúsculas), `ProjectDocumentationAgent` é incluído na fase `EXECUTING`, depois de `DocumentationWriterAgent`.

O resultado final é `PARTIALLY_COMPLETED` quando o resultado do agente `test` contém avisos. A revisão e os especialistas ainda são executados nesse caso; a falha de testes não interrompe automaticamente a coleta de resultados.

## Contexto e escrita

`ContextAgent` prioriza `AGENTS.md` da raiz e dos subdiretórios, caminhos explícitos no objetivo, arquivos alterados, código/testes relacionados e documentação. Para Python, segue imports locais e testes de nome correspondente até `context.dependency_depth`. A seleção respeita `include`, `exclude`, `max_files`, `max_file_chars` e `max_total_chars`; o conteúdo é redigido antes de formar o pacote.

Na fase de execução, o orquestrador tira snapshots de arquivos antes e depois de cada agente que pode escrever. Ele atualiza a lista de arquivos modificados e, para formatos suportados, aplica `HeaderService` aos arquivos alterados que ainda não tenham cabeçalho. As escritas são serializadas por `Orchestrator._write_lock` dentro do processo.

## Planos e worktrees

`POST /assistant/task-plans` cria um `TaskPlan` persistido, sem chamar o Codex para escrever nem criar worktree. O plano registra arquivos relevantes, branch-base, avisos e a necessidade de decisão arquitetural.

`start` exige `confirmed_write=true`. Antes de executar, o gerenciador exige a aprovação registrada quando aplicável, e `GitTool.create_worktree()` exige um repositório Git limpo. Ele cria:

- branch `dev-agent/<id>`;
- worktree em `.<nome-do-projeto>-dev-agent-worktrees/<id>` ao lado da raiz do projeto.

O checkout principal não é alterado pela tarefa. O diff final é lido no worktree e passa pelo redator antes de ser persistido no job.

## Checkpoints, cancelamento e retomada

Cada checkpoint contém a fase concluída, índice da etapa, agentes concluídos, resultados acumulados e arquivos alterados. `TaskJobManager` o persiste em `AgentJob.last_checkpoint` junto ao estado do job.

Se o processo falhar depois de um checkpoint, o job fica `blocked` e pode ser retomado no mesmo worktree. Uma reinicialização da API também converte job `queued`/`running` em `blocked` quando ele está marcado como retomável, tem `worktree_path` e esse worktree ainda não foi marcado como removido; o recuperador não verifica a existência do caminho no sistema de arquivos. Nos demais casos ele falha. `resume` reutiliza os resultados do checkpoint e pula fases já concluídas. Há no máximo três retomadas por job. Um cancelamento explícito desabilita a retomada.

`cancel` é cooperativo: o evento de cancelamento faz o `TerminalTool` terminar o processo em execução. `cleanup` requer confirmação e usa `git worktree remove --force`; portanto, descarta alterações não commitadas daquele worktree.

## Estados declarados que não fazem parte do fluxo automático

`TaskStatus` e a tabela de transições também contêm `AWAITING_APPROVAL`, `DOCUMENTING`, `PREPARING_GIT` e `ROLLED_BACK`.

- A aprovação arquitetural ocorre no `TaskPlan`, antes de `task()`, e não como transição de pipeline.
- A documentação atual ocorre em `EXECUTING`, não em `DOCUMENTING`.
- `GitAgent.commit_plan()` é separado; não há preparação de Git automática.
- Não existe rollback automático implementado.

A máquina limita uma execução a 40 transições e cada fase a três repetições. Como ela é recriada em cada chamada de `task()`, esse limite não acumula entre chamadas de retomada; o limite independente de três retomadas do job é a proteção persistida.
