<!--
DevAgent
Autor: Dayvid Santana
Criado em: 28/08/2026
Editado em: 28/08/2026
Objetivo: Documentar a máquina de estados, os checkpoints e a retomada de jobs.
-->

# Orquestração: fases, checkpoints e retomada

`Orchestrator.task()` executa um pipeline fixo de agents (não um loop aberto
de ferramentas). Esse pipeline agora é acompanhado por uma máquina de
estados explícita (`core/state_machine.py`, `TaskStateMachine`) que valida
transições, limita passos, detecta repetição de fase e produz um
`Checkpoint` (`core/models.py`) ao final de cada fase.

## Fases usadas hoje pelo pipeline

`TaskStatus` (`core/models.py`) define o conjunto completo de fases pedido
para o Harness — incluindo `documenting`, `preparing_git` e `rolled_back`,
reservadas para uso futuro (ver "Fases não usadas" abaixo). O pipeline de
`task()` percorre, na ordem:

```
RECEIVED
   -> DISCOVERING     (context)
   -> PLANNING        (requirements)                     [checkpoint 1]
   -> EXECUTING        (implementation, code_documentation,
                        test_author, documentation_writer) [checkpoint 2]
   -> TESTING          (test, bug_reproduction)            [checkpoint 3]
   -> REVIEWING        (review, documentation, 10 specialistas) [checkpoint 4]
   -> COMPLETED | PARTIALLY_COMPLETED
```

`PARTIALLY_COMPLETED` é usado quando o `TestAgent` reporta falha (em vez de
`COMPLETED`); o job continua com todos os resultados coletados — a tarefa não
é abortada por um teste falho, mas o status final sinaliza isso claramente.

Nota de design: a documentação (`documentation_writer`) já acontece dentro do
cluster EXECUTING, não depois de REVIEWING. Isso reflete o pipeline real
(documentar faz parte de implementar a mudança, não uma etapa final
separada) — não foi reordenado para caber no rótulo `DOCUMENTING` só por
completude cosmética.

## Checkpoints

Cada checkpoint grava: `phase` (fase recém-concluída), `step_index`,
`completed_agents`, os `SubAgentResult` acumulados até ali e os arquivos
alterados até ali. `TaskJobManager` persiste o último checkpoint em
`AgentJob.last_checkpoint` (via `JobStore`, sem gravar prompts, diffs ou
segredos) e expõe a fase atual em `AgentJob.phase` — visível em
`dev-agent job <id>`.

## Retomada (`dev-agent resume <id>`)

Quando a API local é reiniciada com um job `queued`/`running`, ou quando o
pipeline falha após pelo menos um checkpoint, o job passa a `blocked` (em
vez de `failed` incondicionalmente) contanto que o worktree ainda exista.
`dev-agent resume <id>` (`POST /assistant/jobs/{id}/resume`) relança o
pipeline no mesmo worktree/branch a partir da fase seguinte ao checkpoint —
sem recriar o worktree e sem repetir chamadas ao provider já concluídas com
sucesso. Um job cancelado explicitamente (`dev-agent cancel`) nunca fica
resumível — cancelamento é uma decisão do usuário, não uma interrupção.

## Proteção contra loops

O pipeline de `task()` é determinístico (mesma ordem sempre), então
"detecção de loop" aqui não é a mesma coisa que em um agent de ferramentas
livre. `TaskStateMachine` aplica dois limites, ambos configuráveis por
instância: `max_steps` (total de transições permitidas numa execução) e
`max_phase_repeats` (quantas vezes a mesma fase pode ser reexecutada). Isso
protege principalmente o ciclo `TESTING -> EXECUTING -> TESTING`, hoje
modelado na tabela de transições mas não acionado automaticamente pelo
orquestrador (não há retry automático de implementação após teste falho).

## Fases não usadas hoje

`AWAITING_APPROVAL` já existe como decisão arquitetural, mas é resolvida
antes de `task()` criar a máquina de estados (`ArchitectureGuard`, no nível
do `TaskPlan`), não como uma transição dentro do pipeline. `DOCUMENTING`,
`PREPARING_GIT` e `ROLLED_BACK` estão definidos no contrato (`TaskStatus`) e
na tabela de transições para consistência com o desenho completo pedido para
o Harness, mas nenhum caminho de código os produz ainda — não há um passo de
"preparar Git" dentro de `task()` (isso é `GitAgent.commit_plan()`,
separado) nem um mecanismo de rollback automático. Adicionar esses fluxos é
trabalho futuro, não uma lacuna silenciosa: documentado aqui para não serem
reintroduzidos por engano como "já implementados".

## Limitação conhecida

`TaskStateMachine` é recriada a cada chamada de `task()` (inclusive em uma
retomada); ela não mantém contagem de fases entre chamadas diferentes. Ou
seja, `max_phase_repeats` protege uma única execução, mas não impede que um
job seja retomado repetidamente pelo usuário após falhas sucessivas. Isso é
aceitável porque retomar exige uma ação explícita do usuário (`dev-agent
resume`) — não é um loop automático — mas fica registrado como limitação.
