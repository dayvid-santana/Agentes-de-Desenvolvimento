VERSÃO 1 — Direta / objetiva

Nos últimos meses venho construindo o DevAgent: uma ferramenta local que coordena tarefas de desenvolvimento assistidas por IA direto no meu terminal, sem depender de um serviço externo guardando meu código.

A ideia central: em vez de um prompt genérico tentando fazer tudo, o trabalho passa por um time de 26 agentes especializados, cada um com uma responsabilidade só sua. São organizados em grupos:

→ Contexto e coordenação — entendem o pedido e selecionam só o que é relevante do projeto antes de qualquer ação.
→ Escrita de tarefa — implementam a mudança aprovada e já deixam documentação e testes atualizados junto.
→ Teste e diagnóstico — rodam a suíte, revisam o diff e ajudam a investigar falhas.
→ Análises especializadas — segurança, banco de dados, performance, arquitetura, contratos de API, entre outras, sempre em modo leitura.
→ Git — sugere agrupamentos de commit seguindo Conventional Commits, sem nunca commitar sozinho.

Na prática: cada mudança de código roda isolada em uma branch e worktree Git próprios, passa por revisão automática e só é integrada com confirmação explícita minha. Uma API local em FastAPI orquestra tudo e conversa com a Codex CLI como motor de IA — sem chamadas externas escondidas.

Ainda é um projeto pessoal em evolução, mas já é a ferramenta que uso no dia a dia. Bom aprendizado sobre orquestração de agentes, design de contexto e como manter um sistema desses previsível.

#IA #DevTools #Automação #Engenharia de Software
