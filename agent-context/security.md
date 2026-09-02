# Segurança e autonomia para agentes

Não registre, exponha ou use como contexto conteúdo de `.env`, chaves, credenciais ou segredos. Preserve a redação de dados sensíveis e mantenha operações de arquivo dentro da raiz ativa por `FileSystem`.

Implementações normais são autônomas. Mudanças arquiteturais relevantes exigem `DECISÃO ARQUITETURAL NECESSÁRIA`; comandos destrutivos exigem confirmação explícita. Não reverta alterações preexistentes, não faça push automaticamente e não altere configurações globais do Git.

Evite comandos de shell quando uma tool estruturada for suficiente. Trate diffs, objetivos e logs locais como conteúdo potencialmente sensível.
