# Testes e qualidade para agentes

Execute `pytest` antes da entrega. Integrações externas devem ser injetáveis e usar fakes nos testes, sem chamadas reais ao provider.

Adicione testes proporcionais à mudança, especialmente para descoberta de projeto, configuração, segurança, cabeçalhos, memória, orquestração, API e seleção de contexto. Prefira afirmar comportamento observável e regressões concretas; não altere testes para ocultar falhas de implementação.

O comando de teste vem de `testing.command` em `dev-agent.yaml`. O contexto de testes deve incluir o arquivo afetado, seus testes de nome correspondente e dependências locais apenas até a profundidade configurada.
