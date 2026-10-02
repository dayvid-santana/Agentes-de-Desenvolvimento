# Exploração de aplicações web

O agente `explorador_aplicacao` percorre uma aplicação web com Playwright. Ele descobre links e controles visíveis, tenta interações seguras, verifica validações HTML nativas e registra erros de navegação, console, rede, acessibilidade e layout responsivo. Jornadas configuradas acrescentam expectativas específicas do produto.

## Instalação

Playwright é opcional. Instale o extra e o navegador Chromium no ambiente que executa a API local:

```powershell
python -m pip install -e ".[browser]"
python -m playwright install chromium
```

Firefox e WebKit podem ser selecionados em `testeAplicacao.motor` depois que seus navegadores forem instalados com Playwright.

## Execução

Configure `urlBase` em `dev-agent.yaml` e execute:

```powershell
dev-agent testar-aplicacao
dev-agent testar-aplicacao "Percorrer cadastro e recuperação de senha"
```

O agente pode iniciar a aplicação usando `comandoInicial`. O comando é uma lista de argumentos, executada sem shell, no diretório do projeto. Se não houver comando, a aplicação precisa estar em execução. Sem `urlBase`, o agente procura um único servidor HTML nas portas locais comuns; se encontrar nenhum ou mais de um, encerra com relatório bloqueado para evitar testar a aplicação errada.

Exemplo para um servidor Vite:

```yaml
testeAplicacao:
  urlBase: http://127.0.0.1:5173
  comandoInicial: [npm, run, dev, --, --host, 127.0.0.1]
  origensPermitidas: []
  paginasMaximas: 24
  acoesMaximas: 120
  tempoLimiteSegundos: 180
  motor: chromium
```

O agente encerra o processo que iniciou ao terminar. Requisições para outras origens são bloqueadas e aparecem como limitações do relatório. Para aplicações que chamam uma API em outra origem, inclua a origem exata da API em `origensPermitidas`. Aplicações remotas exigem origem explícita e `ambienteDeTesteConfirmado: true`.

## Jornadas e expectativas

O rastreamento de links e os sinais de interface não definem regras de negócio. Configure jornadas para afirmar resultados esperados:

```yaml
testeAplicacao:
  urlBase: http://127.0.0.1:5173
  jornadas:
    - nome: login
      objetivo: Usuário de teste entra e abre o painel
      passos:
        - acao: ir
          valor: /login
        - acao: preencher
          alvo: E-mail
          valor: qa@example.invalid
        - acao: clicar
          alvo: Entrar
          alteraEstado: true
        - acao: ver_url
          valor: /painel
        - acao: ver_texto
          alvo: Meu painel
```

As ações disponíveis são `ir`, `clicar`, `preencher`, `selecionar`, `marcar`, `ver_texto`, `ver_url`, `ver_visivel` e `ver_oculto`. Os alvos de interação usam nomes acessíveis ou labels, sem seletores CSS arbitrários.

## Mutação, autenticação e evidências

Por padrão, o agente não envia formulários nem executa controles com sinais de ação destrutiva. Para jornadas que alteram dados, configure um ambiente isolado, confirme-o e forneça um comando de reset executável sem shell:

```yaml
testeAplicacao:
  urlBase: http://127.0.0.1:5173
  ambienteDeTesteConfirmado: true
  permitirMutacoes: true
  comandoReset: [npm, run, test:data:reset]
  capturarTelas: true
```

O reset roda antes de cada interação mutável e jornada mutável. Os formulários exploratórios recebem dados sintéticos, inclusive e-mails em `example.invalid`; campos de arquivo ficam sem preenchimento. Não use dados de produção.

`arquivoEstadoSessao` aceita um caminho relativo dentro do projeto para um estado Playwright previamente criado. Esse arquivo contém cookies e tokens: mantenha-o fora do Git e não o inclua em objetivos ou logs. Screenshots ficam desativados por padrão porque podem conter dados da página; `capturarTelas: true` exige confirmação do ambiente de teste e mascara campos de entrada comuns.

O relatório JSON e screenshots, quando habilitados, ficam em `.dev-agent/usabilidade/<execução>/`, dentro da raiz do projeto. A pasta é ignorada pelo Git. O relatório inclui itens descobertos, tentados, ignorados, expectativas, observações, passos, achados, limitações, percentuais e caminhos de evidência.

## Interpretação da cobertura

`percentualExecucao` mede controles exercitados entre os controles visíveis descobertos. `percentualAssertivo` mede assertivas explícitas de jornadas e regras HTML nativas que passaram. A exploração sem expectativa de negócio fica marcada como inconclusiva, mesmo quando a interface mudou. O relatório não afirma cobertura de rotas ocultas, permissões não configuradas ou combinações não descobertas.

As verificações de teclado cobrem o foco inicial por Tab; responsividade mede excesso horizontal global; nomes acessíveis são uma verificação heurística. Esses sinais ajudam a reproduzir problemas, mas não representam uma auditoria WCAG nem substituem testes com pessoas. Playwright automatiza aplicações executadas em navegador; aplicativos nativos precisam de outra ferramenta.
