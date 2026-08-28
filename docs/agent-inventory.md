<!--
DevAgent
Autor: Dayvid Santana
Criado em: 28/08/2026
Editado em: 28/08/2026
Objetivo: Inventariar os Agents do DevAgent e documentar a fonte única do catálogo.
-->

# Inventário de Agents — DevAgent

Este documento é gerado a partir da leitura de `agents/catalog.yaml` (a fonte
única de verdade) e do código em `src/dev_agent/agents/`. Não edite listas de
Agents aqui manualmente sem antes atualizar o catálogo — use
`dev-agent agents list` / `dev-agent agents doctor` para conferir que este
documento continua refletindo o catálogo real.

## Como o catálogo é usado

- `AgentRegistry` (`src/dev_agent/agents/registry.py`) carrega
  `agents/catalog.yaml`, valida IDs duplicados e verifica se cada entrypoint
  (`module` + `class_name`) existe.
- `Orchestrator.available_agents()` delega para `AgentRegistry` — não há mais
  uma lista duplicada de Agents no orquestrador.
- `GET /agents`, `GET /agents/catalog`, `GET /agents/catalog/{id}`,
  `GET /agents/graph` e `GET /agents/doctor` expõem o catálogo pela API local.
- `dev-agent agents [list|show|graph|doctor]` expõe o mesmo catálogo pela CLI,
  que continua sem importar `agents/` diretamente (fala apenas com a API),
  conforme a regra de `AGENTS.md`.
- `LegacyAgentAdapter` (`src/dev_agent/agents/legacy_adapter.py`) normaliza
  Agents que ainda retornam `str` (em vez de `SubAgentResult`) sem exigir
  reescrita. Nenhum Agent do catálogo atual precisa dele hoje — ele existe
  para futuras integrações externas ou Agents plugáveis.

## Inventário

Todos os 23 componentes abaixo já estavam implementados e em uso pelo
`Orchestrator` antes desta auditoria; o trabalho desta etapa foi declará-los
em `agents/catalog.yaml` como fonte única, não reescrevê-los. Recomendação
para todos: **manter**.

| id | módulo.classe | modo | finalidade | dependências | acionado por |
|---|---|---|---|---|---|
| context | `context_agent.agent.ContextAgent` | read | Seleciona instruções, código, testes e diff relevantes | — | `dev-agent context`, início de toda tarefa |
| requirements | `requirements_agent.agent.RequirementsAgent` | read | Critérios de aceite, escopo e ambiguidades | context | `dev-agent task` |
| implementation | `implementation_agent.agent.ImplementationAgent` | write | Implementa a tarefa aprovada via provider | context, requirements | `dev-agent task` |
| documentation_writer | `documentation_writer_agent.agent.DocumentationWriterAgent` | write | Atualiza README/docs quando necessário | implementation | `dev-agent task` |
| code_documentation | `code_documentation_agent.agent.CodeDocumentationAgent` | write | Documenta código alterado sem tocar cabeçalhos | implementation | `dev-agent task` |
| test_author | `test_author_agent.agent.TestAuthorAgent` | write | Cria testes de regressão para a alteração | implementation | `dev-agent task` |
| bug_reproduction | `bug_reproduction_agent.agent.BugReproductionAgent` | read | Passos verificáveis de reprodução de falha | — | `dev-agent task` |
| test | `test_agent.agent.TestAgent` | execute | Executa a suíte configurada (`testing.command`) | — | `dev-agent test`, `dev-agent task` |
| review | `review_agent.agent.ReviewAgent` | read | Revisa diff em busca de regressões/riscos | — | `dev-agent review` |
| documentation | `documentation_agent.agent.DocumentationAgent` | read | Avalia impacto de documentação (sem provider) | — | `dev-agent task` |
| debug | `debug_agent.agent.DebugAgent` | read | Diagnóstico baseado em testes, diff e contexto | context | `dev-agent debug` |
| security | `security_agent.agent.SecurityAgent` | read | Segurança, validação, exposição de dados | — | `dev-agent task` |
| database | `database_agent.agent.DatabaseAgent` | read | Persistência, migrations, integridade | — | `dev-agent task` |
| api_contract | `api_contract_agent.agent.ApiContractAgent` | read | Compatibilidade de contratos de API | — | `dev-agent task` |
| quality | `quality_agent.agent.QualityAgent` | read | Lacunas de teste e casos de borda | — | `dev-agent task` |
| dependency | `dependency_agent.agent.DependencyAgent` | read | Dependências visíveis no contexto | — | `dev-agent task` |
| performance | `performance_agent.agent.PerformanceAgent` | read | Gargalos e como medi-los | — | `dev-agent task` |
| frontend | `frontend_agent.agent.FrontendAgent` | read | Interface, acessibilidade, responsividade | — | `dev-agent task` |
| observability | `observability_agent.agent.ObservabilityAgent` | read | Logs, métricas e rastreamento seguros | — | `dev-agent task` |
| release | `release_agent.agent.ReleaseAgent` | read | Itens necessários para publicação | — | `dev-agent task` |
| refactor | `refactor_agent.agent.RefactorAgent` | read | Separa refatoração necessária da opcional | — | `dev-agent task` |
| git | `git_agent.agent.GitAgent` | read (service) | Plano de commit (Conventional Commits), sem commitar | — | `dev-agent commit` |
| architecture_guard | `security.architecture_guard.ArchitectureGuard` | guard (policy) | Interrompe tarefas estruturais para aprovação | — | avaliado no início de `dev-agent task` |

Onze dos agentes acima (`security` … `refactor`) compartilham a base
`specialist_base.ReadOnlySpecialistAgent`: mesma execução somente leitura,
mesma Skill `evidence-review`, e diferem apenas por `specialty`/`instructions`.
Isso já é a forma correta de reduzir Agents redundantes a uma única classe
parametrizada — não há necessidade de consolidação adicional.

## Skills usadas pelos Agents

`src/dev_agent/skills/registry.py` contém um catálogo pequeno e fixo
(`code-header`, `code-documentation`, `test-design`, `bug-reproduction`,
`evidence-review`) injetado nos prompts. Não há carregamento progressivo por
enquanto — o catálogo é pequeno o bastante para não justificar essa
complexidade ainda; reavaliar se o número de Skills crescer.

## Lacunas conhecidas (não resolvidas nesta etapa)

- `LegacyAgentAdapter` e `AgentManifest.legacy` existem mas nenhum Agent do
  catálogo é `legacy: true` hoje — todos já implementam `SubAgent` ou são
  serviços simples. Útil quando um Agent plugável externo for integrado.
- `dev-agent agents graph` reflete apenas as dependências declaradas
  manualmente em `agents/catalog.yaml`; elas não são verificadas contra a
  ordem real de chamadas em `Orchestrator.task()`.
- Não há ainda um comando `dev-agent explain <agent-id>` nem `route --dry-run`.
- `Orchestrator.task()` agora roda sobre uma máquina de estados explícita com
  checkpoints e retomada (`dev-agent resume <id>`) — ver
  [docs/orchestration.md](orchestration.md) para as fases, o que já está
  implementado e o que ainda é apenas contrato reservado para uso futuro.
