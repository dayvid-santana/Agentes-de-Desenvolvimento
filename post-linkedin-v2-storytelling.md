VERSÃO 2 — Storytelling / jornada pessoal

Toda vez que eu pedia pra uma IA "implementar tal coisa no meu projeto", eu sentia o mesmo problema: ou ela mudava coisa demais, ou esquecia de atualizar teste, ou commitava algo que eu nem tinha revisado direito.

Foi assim que comecei a construir o DevAgent, uma ferramenta que roda local, no meu terminal, e resolve isso dividindo o trabalho entre agentes especializados em vez de um único prompt tentando dar conta de tudo.

Hoje são 26 agentes, cada um com uma função clara:
— um entende o pedido e escolhe só o contexto relevante do projeto;
— outro implementa a mudança aprovada;
— outros cuidam de testes, documentação e revisão do diff;
— um time de especialistas analisa segurança, performance, banco de dados e arquitetura, sempre em modo leitura;
— e um agente de Git sugere os commits certos, no padrão Conventional Commits, sem nunca commitar sozinho.

Cada tarefa de escrita roda isolada em uma branch e worktree próprios. Nada entra na branch principal sem eu confirmar explicitamente. É IA ajudando dentro de um fluxo de engenharia de verdade, não substituindo a revisão.

É um projeto pessoal, ainda em construção, mas já é minha ferramenta de trabalho no dia a dia — e um baita laboratório para entender orquestração de múltiplos agentes na prática.

#IA #DevTools #EngenhariaDeSoftware #Automação
