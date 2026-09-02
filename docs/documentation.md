<!--
dev-agent
Autor: Dayvid Santana
Data: 02/09/2026
Objetivo: Definir o padrão de documentação humana e sua separação do contexto de IA.
-->

# Padrão de documentação humana

Este repositório separa a documentação para pessoas das instruções de trabalho dos agentes de IA.

| Público | Local | Finalidade |
|---|---|---|
| Pessoas | `README.md` e `docs/` | Instalar, operar, desenvolver e compreender o produto. |
| Agentes de IA | `AGENTS.md` e `agent-context/` | Aplicar regras de implementação e receber contexto técnico mínimo e direcionado. |

`AGENTS.md` é apenas o índice obrigatório e curto. Seus links para `agent-context/*.md` descrevem quando um contexto especializado deve ser carregado. Esses arquivos não substituem documentação humana e não devem ser modificados por `document-project` ou por atualizações de documentação de uma tarefa comum.

## Estrutura recomendada

```text
README.md
docs/
  overview.md
  architecture.md
  development.md
  configuration.md
  operation.md
  api.md                  # quando existir API pública
  decisions/
    README.md
    0001-titulo-curto.md
```

Nem todo projeto precisa de todos os arquivos. Crie um documento quando houver conteúdo verificável para mantê-lo; mantenha uma seção no README que aponte para os documentos existentes.

## Template de README

```md
# Nome do projeto

Objetivo e público-alvo em poucas linhas.

## Início rápido

## Pré-requisitos

## Instalação

## Execução

## Testes

## Documentação

Links para os documentos em `docs/`.
```

## Conteúdo dos documentos

- `architecture.md`: componentes, fronteiras, fluxos, dependências e limitações.
- `development.md`: ambiente local, comandos, testes, convenções e contribuição.
- `configuration.md`: configurações, valores padrão e como fornecer variáveis; nunca valores secretos.
- `operation.md`: deploy, observabilidade, troubleshooting e recuperação, quando aplicável.
- `api.md`: autenticação, contratos, exemplos, erros e compatibilidade.
- `decisions/`: decisões curtas (ADR) com contexto, decisão, consequências e status.

Toda afirmação deve ter evidência no repositório. Se ela ainda não existir, registre a lacuna explicitamente em vez de supor.
