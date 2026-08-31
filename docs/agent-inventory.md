# Inventário de Agents

`agents/catalog.yaml` é a fonte única de verdade. `AgentRegistry` valida o YAML, recusa IDs duplicados, resolve ID/nome/alias sem diferenciar maiúsculas e minúsculas e verifica imports/atributos em `doctor`. Não mantenha uma lista paralela no orquestrador ou na CLI.

O catálogo atual contém 24 componentes.

| Grupo | IDs e propósito |
|---|---|
| Contexto e coordenação | `context` seleciona contexto; `requirements` define escopo; `architecture_guard` identifica pedido estrutural. |
| Escrita de tarefa | `implementation` altera a tarefa aprovada; `documentation_writer` atualiza documentação necessária; `project_documentation` documenta o projeto; `code_documentation` documenta código alterado; `test_author` cria/atualiza testes relacionados. |
| Teste e diagnóstico | `test` executa a suíte; `bug_reproduction` propõe reprodução verificável para relatos de falha; `review` examina o diff; `debug` diagnostica usando testes, diff e contexto. |
| Análises especializadas | `security`, `database`, `api_contract`, `quality`, `dependency`, `performance`, `frontend`, `observability`, `release` e `refactor` analisam o contexto selecionado em modo leitura. |
| Documentação e Git | `documentation` avalia impactos de documentação; `git` sugere commits sem criá-los. |

## Registro e invocação

Cada item do catálogo declara módulo, classe, modo, tipo, ferramentas, dependências, modelos e comando de invocação. `Orchestrator.available_agents()`, os endpoints `/agents*` e `dev-agent agents` consultam esse catálogo via `AgentRegistry`.

`LegacyAgentAdapter` existe para compatibilizar agentes que retornem `str`, convertendo-os em `SubAgentResult`. Os componentes do catálogo atual usam o contrato estruturado e não precisam do adaptador.

## Dependências declaradas

As dependências no catálogo descrevem ordem/intenção, mas não representam por si só um agendador genérico. No pipeline de tarefa atual, a ordem é codificada por `Orchestrator.task()`:

```text
context -> requirements -> implementation
        -> code_documentation/test_author/documentation_writer
        -> test/bug_reproduction -> review/documentation/especialistas
```

O `project_documentation` é acionado condicionalmente quando o objetivo começa por `documentar o projeto`. `git` é independente e chamado por `dev-agent commit`.

Para os valores exatos de módulo, classe, modo, ferramentas e dependências, consulte `agents/catalog.yaml` ou execute `dev-agent agents list`, `dev-agent agents show <id>`, `dev-agent agents graph` e `dev-agent agents doctor`.
