# Seleção de contexto para agentes

O objetivo é entregar o menor `ContextPacket` que ainda permita uma decisão segura e verificável. Nunca envie o repositório inteiro como contexto padrão.

1. Inclua sempre o `AGENTS.md` da raiz.
2. Inclua `AGENTS.md` aninhado somente se um caminho explícito, alterado ou encontrado pertencer ao seu diretório.
3. Resolva links Markdown do `AGENTS.md` para `agent-context/` e selecione-os pelas palavras do objetivo e dos caminhos envolvidos.
4. Priorize caminhos explícitos, mudanças no diff, dependências locais, testes correspondentes e documentação humana diretamente relacionada.
5. Respeite `context.max_files`, `context.max_file_chars` e `context.max_total_chars`; redija conteúdo sensível antes de montar o pacote.

Ao criar um novo contexto especializado, adicione um link no `AGENTS.md` raiz, mantenha-o focado em um domínio e use palavras-chave que permitam a seleção. Não use `agent-context/` como área de documentação para usuários.
