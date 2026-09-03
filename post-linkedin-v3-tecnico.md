VERSÃO 3 — Para público mais técnico

Venho construindo o DevAgent: uma CLI + API local (FastAPI) que orquestra agentes de IA especializados para tarefas de desenvolvimento, usando a Codex CLI como provider e Git worktrees para isolar escrita.

Por que agentes especializados em vez de um único prompt? Porque cada etapa de uma tarefa de dev exige um tipo de raciocínio diferente — e misturar tudo em um prompt só tende a gerar contexto poluído e resultados inconsistentes.

A arquitetura atual tem 26 agentes registrados em um catálogo declarativo (YAML), agrupados por responsabilidade:

• Contexto e coordenação: seleção de contexto, escopo de requisitos, detecção de mudança estrutural.
• Escrita: implementação da tarefa aprovada, documentação (de projeto e de código) e autoria de testes.
• Teste e diagnóstico: execução da suíte, reprodução de bugs, revisão de diff, debug guiado por evidência.
• Especialistas somente-leitura: segurança, banco de dados, contratos de API, performance, padrões de projeto, observabilidade, frontend, entre outros.
• Git: sugestão de commits em Conventional Commits — sem autonomia para commitar.

O pipeline de escrita roda assim:
task → plano sem escrita → decisão arquitetural (quando aplicável) → run --confirm → branch + worktree isolados → testes/revisão → job assíncrono.

Nenhuma escrita acontece sem confirmação explícita, e mudanças estruturais (auth, migração de banco, contrato público) exigem uma decisão registrada antes da execução.

Ainda é um projeto pessoal em evolução — mas tem sido um laboratório valioso sobre orquestração de agentes, design de contexto e como manter esse tipo de sistema previsível e auditável.

#IA #Orquestração de Agentes #DevTools #EngenhariaDeSoftware
