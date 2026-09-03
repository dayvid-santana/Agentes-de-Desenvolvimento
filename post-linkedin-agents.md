Nos últimos meses venho construindo o DevAgent: uma ferramenta local que coordena tarefas de desenvolvimento assistidas por IA direto no meu terminal, sem depender de um serviço externo guardando meu código.

O núcleo da ideia é simples: em vez de um único prompt genérico tentando fazer tudo, o trabalho passa por um time de agentes especializados, cada um com uma responsabilidade clara.

Hoje são 26 agentes trabalhando em conjunto, organizados em grupos:

→ Contexto e coordenação — entendem o pedido e selecionam só o que é relevante do projeto antes de qualquer ação.

→ Escrita de tarefa — implementam a mudança aprovada e já deixam documentação e testes atualizados junto.

→ Teste e diagnóstico — rodam a suíte, revisam o diff e ajudam a investigar falhas.

→ Análises especializadas — olhares dedicados para segurança, banco de dados, performance, arquitetura, contratos de API e mais, sempre em modo leitura.

→ Git — sugere agrupamentos de commit seguindo Conventional Commits, sem nunca commitar sozinho.

Cada etapa que escreve código roda isolada em uma branch e worktree próprios, com revisão antes de qualquer merge. A ideia não é remover o humano da equação, e sim dar contexto e disciplina para que a IA ajude de forma mais confiável em um fluxo de trabalho real.

Ainda é um projeto pessoal em evolução, mas já é a ferramenta que uso no dia a dia. Bom aprendizado sobre orquestração de agentes, design de contexto e como manter um sistema desses previsível.
