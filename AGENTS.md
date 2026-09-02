# AGENTS.md — DevAgent

## Regras globais obrigatórias

- Preserve a arquitetura existente, mudanças preexistentes do usuário e os limites de `AGENTS.md` do escopo selecionado.
- Python 3.11+, type hints, UTF-8 e `pathlib.Path`. Código novo usa nomes em português e camelCase; não renomeie código legado apenas por estilo.
- Não exponha credenciais, conteúdo de `.env`, chaves ou segredos em logs, contexto, respostas ou testes.
- Não faça push, não altere Git global e não execute operações destrutivas sem confirmação.
- Execute `pytest` antes de entregar uma alteração.
- Decisões arquiteturais relevantes devem usar o formato `DECISÃO ARQUITETURAL NECESSÁRIA`.

## Documentação para pessoas e contexto para IA

`README.md` e `docs/` são documentação humana. `agent-context/` contém instruções técnicas para agentes de IA e não deve ser alterado durante tarefas comuns de documentação. Este arquivo é o índice obrigatório e curto; carregue os contextos especializados abaixo apenas quando forem relevantes.

## Contextos especializados

- [Arquitetura e extensibilidade](agent-context/architecture.md): `cli`, `api`, `core`, `agents`, `tools`, `providers`, configuração, catálogo ou novos componentes.
- [Seleção de contexto](agent-context/context.md): `ContextAgent`, `ContextPacket`, busca, limites de tokens, `AGENTS.md` ou `agent-context/`.
- [Testes e qualidade](agent-context/testing.md): testes, `pytest`, fake, cobertura, regressão, integração ou CI.
- [Segurança e autonomia](agent-context/security.md): segredos, autenticação, permissões, filesystem, terminal, Git ou comandos destrutivos.
- [Documentação humana](agent-context/documentation.md): README, `docs/`, API, guias, operação ou documentação.

Os links acima são a fonte de roteamento: mantenha os títulos e descrições com palavras-chave específicas do domínio. Um contexto especializado deve ser conciso, factual, autocontido e não repetir regras globais.
