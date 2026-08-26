# AGENTS.md — DevAgent

## Arquitetura e limites

- `cli/` é somente cliente da API local; não conhece agents diretamente.
- `api/` transforma HTTP em chamadas do `Orchestrator`.
- `core/` contém contratos (`ContextPacket`, `SubAgentResult`) e coordenação; o orquestrador serializa escrita.
- `agents/` especializam uma única etapa e trocam apenas pacotes e resumos, nunca histórico bruto.
- `tools/` encapsula filesystem, busca, terminal, testes e Git. Toda operação de arquivo deve validar a raiz ativa via `FileSystem`.
- `providers/` define o protocolo de LLM. Particularidades de Codex não podem sair de `providers/codex/`.

## Convenções

- Python 3.11+, type hints, UTF-8, `pathlib.Path` para caminhos.
- Funções pequenas e erros explícitos em `errors.py`.
- Não adicionar frameworks ou camadas sem necessidade demonstrável.
- Logs não devem conter credenciais, conteúdo de `.env`, chaves ou segredos.

## SubAgents e contexto

O `ContextAgent` deve priorizar `AGENTS.md` do escopo, `AGENTS.md` da raiz, `docs/`, README, código e testes. Ele seleciona arquivos progressivamente, respeitando `context.max_*`; um agent recebe somente o `ContextPacket` necessário. Agents de leitura podem ser paralelizados em evolução futura; escrita permanece serializada até existir lock por arquivo confiável.

## Testes

Execute `pytest` antes de entregar. Integrações externas são injetáveis e usam fakes nos testes. Cubra alterações em descoberta, configuração, segurança, cabeçalhos, memória, orquestração e API.

## Cabeçalhos

`HeaderService` é a única fonte da regra de cabeçalhos. Código criado ou significativamente modificado recebe projeto, autor, data dinâmica e objetivo curto. Uma tarefa lógica gera uma única entrada por arquivo. Preserve shebang, declaração XML, licença e formatos que não admitem comentário; nunca altere JSON estrito, lockfiles, gerados, dependências, binários ou artefatos de build apenas para inserir cabeçalho.

## Segurança e autonomia

Implementações normais são autônomas. Decisões arquiteturais relevantes exigem o formato `DECISÃO ARQUITETURAL NECESSÁRIA`; comandos destrutivos exigem confirmação. Não reverta alterações preexistentes do usuário, não faça push automaticamente e não altere Git global.

## Extensibilidade

Para adicionar agent: implemente `SubAgent`, aceite `ContextPacket`, retorne `SubAgentResult` e registre a etapa no orquestrador. Para adicionar tool: crie input/saída estruturados, validação, logs e uma fake testável. Para provider: implemente `LLMProvider` em novo pacote, mantendo autenticação e argumentos específicos encapsulados.
