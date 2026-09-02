# Arquitetura e extensibilidade para agentes

## Fronteiras obrigatórias

- `cli/` é somente cliente da API local; não conhece agentes diretamente.
- `api/` traduz HTTP em chamadas do `Orchestrator`.
- `core/` contém contratos (`ContextPacket`, `SubAgentResult`) e coordenação; o orquestrador serializa escrita.
- `agents/` especializam uma etapa e trocam apenas pacotes e resumos, nunca histórico bruto.
- `tools/` encapsula filesystem, busca, terminal, testes e Git. Operações de arquivo validam a raiz ativa por `FileSystem`.
- `providers/` define o protocolo de LLM. Detalhes de Codex permanecem em `providers/codex/`.

## Extensibilidade

Para adicionar um agent, implemente `SubAgent`, aceite `ContextPacket`, retorne `SubAgentResult`, registre a etapa no orquestrador e declare-a em `agents/catalog.yaml`, a fonte única lida por `AgentRegistry`. Um agent legado que retorna `str` pode usar `LegacyAgentAdapter`.

Para uma tool, modele entrada e saída estruturadas, valide caminhos e argumentos, registre eventos seguros e disponibilize fake testável. Para um provider, implemente `LLMProvider` em pacote próprio e mantenha autenticação e argumentos específicos encapsulados.

Não acrescente frameworks ou camadas sem necessidade demonstrável. Para detalhes observáveis do projeto, consulte a documentação humana em `docs/` somente quando ela for selecionada ou necessária à tarefa.
