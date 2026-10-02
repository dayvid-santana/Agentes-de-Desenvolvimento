"""Exploração controlada de aplicações web com Playwright."""
from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import shlex
import signal
import subprocess
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from uuid import uuid4

from dev_agent.config.models import ConfiguracaoTesteAplicacao, JornadaAplicacao, PassoJornadaAplicacao
from dev_agent.core.models import AchadoAplicacao, ItemCoberturaAplicacao, RelatorioExploracaoAplicacao
from dev_agent.errors import PathOutsideProjectError, ToolExecutionError
from dev_agent.logging import event
from dev_agent.security.command_policy import CommandPolicy
from dev_agent.security.redaction import SensitiveDataRedactor
from dev_agent.tools.filesystem import FileSystem


_PORTASComuns = (4173, 5173, 3000, 8080, 8000, 4200, 5000)
_ACOESDeRisco = re.compile(
    r"\b(apagar|excluir|remover|deletar|delete|remove|destroy|comprar|pagar|payment|checkout|"
    r"transferir|transfer|enviar|submit|salvar|save|criar|create|publicar|publish|confirmar|confirm|logout|sign out|sair|desconectar)\b",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_NUMEROPrivado = re.compile(r"(?<!\w)(?:\+?\d[\d .()/-]{7,}\d)(?!\w)")


def origemHttp(url: str) -> str | None:
    """Retorna a origem normalizada de uma URL HTTP(S), sem credenciais."""
    try:
        partes = urlsplit(url)
        if partes.scheme.lower() not in {"http", "https"} or not partes.hostname or partes.username or partes.password:
            return None
        porta = partes.port or (443 if partes.scheme.lower() == "https" else 80)
        host = partes.hostname.lower()
        if ":" in host:
            host = f"[{host}]"
        return f"{partes.scheme.lower()}://{host}:{porta}"
    except ValueError:
        return None


def urlPermitida(url: str, origens: set[str]) -> bool:
    origem = origemHttp(url)
    return origem is not None and origem in origens


def _sanitizarTexto(valor: str | None, limite: int = 300) -> str:
    texto = SensitiveDataRedactor.redact(valor or "") or ""
    texto = _EMAIL.sub("[e-mail]", texto)
    texto = _NUMEROPrivado.sub("[dado numérico]", texto)
    return " ".join(texto.split())[:limite]


def _urlRelatorio(url: str) -> str:
    partes = urlsplit(url)
    segmentos = []
    caminho = SensitiveDataRedactor.redact(partes.path) or partes.path
    for segmento in caminho.split("/"):
        if (re.fullmatch(r"\d{5,}|[0-9a-fA-F-]{32,}", segmento)
                or _EMAIL.search(segmento)
                or _NUMEROPrivado.search(segmento)
                or "[REDACTED]" in segmento):
            segmentos.append(":id")
        else:
            segmentos.append(segmento)
    return urlunsplit((partes.scheme, partes.netloc, "/".join(segmentos), "", ""))


class FerramentaExploracaoAplicacao:
    """Executa jornadas declaradas e explora controles visíveis sem sair da origem permitida."""

    def __init__(
        self,
        raizProjeto: Path,
        configuracao: ConfiguracaoTesteAplicacao,
        cancelamento=None,
        criadorProcesso=None,
        executorComando=None,
        criadorConexaoHttp=None,
        playwrightFactory=None,
        erroPlaywright=None,
        timeoutPlaywright=None,
    ) -> None:
        self.raizProjeto = raizProjeto.resolve()
        self.configuracao = configuracao
        self.cancelamento = cancelamento
        self.arquivos = FileSystem(self.raizProjeto)
        self._relatorio: RelatorioExploracaoAplicacao | None = None
        self._diretorioExecucao: Path | None = None
        self._origens: set[str] = set()
        self._fimLimite = 0.0
        self._acoesExecutadas = 0
        self._achadosConhecidos: set[tuple[str, str, str]] = set()
        self._processo: subprocess.Popen | None = None
        self.criadorProcesso = criadorProcesso or subprocess.Popen
        self.executorComando = executorComando or subprocess.run
        self.criadorConexaoHttp = criadorConexaoHttp or http.client.HTTPConnection
        self.playwrightFactory = playwrightFactory
        self.erroPlaywright = erroPlaywright
        self.timeoutPlaywright = timeoutPlaywright

    def executar(self, objetivo: str) -> RelatorioExploracaoAplicacao:
        inicio = datetime.now(timezone.utc)
        idExecucao = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:8]
        self._relatorio = RelatorioExploracaoAplicacao(
            identificadorExecucao=idExecucao,
            objetivo=_sanitizarTexto(objetivo, 500),
            status="parcial",
            inicio=inicio,
        )
        self._fimLimite = time.monotonic() + self.configuracao.tempoLimiteSegundos
        try:
            self._diretorioExecucao = self.arquivos.resolve(Path(self.configuracao.pastaArtefatos) / idExecucao)
            self._diretorioExecucao.mkdir(parents=True, exist_ok=True)
        except (OSError, PathOutsideProjectError) as exc:
            self._limitar("Não foi possível criar a pasta de artefatos dentro do projeto.")
            return self._finalizar("bloqueado")

        try:
            urlBase = self._resolverUrlBase()
            if not urlBase:
                self._limitar("Aplicação web não identificada. Configure testeAplicacao.urlBase; comandoInicial também pode iniciar o servidor local.")
                return self._finalizar("bloqueado")
            self._relatorio.urlBase = _urlRelatorio(urlBase)
            self._origens = self._resolverOrigens(urlBase)
            if not urlPermitida(urlBase, self._origens):
                self._limitar("A origem configurada não está na lista permitida.")
                return self._finalizar("bloqueado")

            estadoSessao = self._resolverEstadoSessao()
            if estadoSessao is False:
                return self._finalizar("bloqueado")
            if self.configuracao.comandoInicial:
                try:
                    self._iniciarAplicacao()
                except ToolExecutionError:
                    return self._finalizar("bloqueado")

            try:
                if self.playwrightFactory is None:
                    from playwright.sync_api import Error as ErroPlaywright
                    from playwright.sync_api import TimeoutError as TimeoutPlaywright
                    from playwright.sync_api import sync_playwright
                    playwrightFactory = sync_playwright
                else:
                    playwrightFactory = self.playwrightFactory
                    ErroPlaywright = self.erroPlaywright or Exception
                    TimeoutPlaywright = self.timeoutPlaywright or TimeoutError
            except ImportError:
                self._limitar('Playwright não está instalado. Instale com `pip install -e ".[browser]"` e `python -m playwright install chromium`.')
                return self._finalizar("bloqueado")

            try:
                with playwrightFactory() as playwright:
                    navegador = getattr(playwright, self.configuracao.motor).launch(headless=True)
                    try:
                        self._explorar(navegador, urlBase, estadoSessao, ErroPlaywright, TimeoutPlaywright, objetivo)
                    finally:
                        navegador.close()
            except (ErroPlaywright, OSError) as exc:
                mensagem = str(exc).lower()
                if "executable doesn't exist" in mensagem or "browser has not been installed" in mensagem:
                    self._limitar(f"O navegador {self.configuracao.motor} não está instalado. Execute `python -m playwright install {self.configuracao.motor}`.")
                else:
                    self._limitar(f"Falha ao iniciar Playwright: {_sanitizarTexto(str(exc))}")
                return self._finalizar("bloqueado")
            except Exception as exc:
                # O relatório conserva o erro sanitizado; o conteúdo da página não é enviado ao provider.
                self._limitar(f"A exploração foi interrompida: {_sanitizarTexto(str(exc))}")
                return self._finalizar("parcial")

            status = self._determinarStatus()
            return self._finalizar(status)
        finally:
            self._encerrarAplicacao()

    def _resolverUrlBase(self) -> str | None:
        if self.configuracao.urlBase:
            return self.configuracao.urlBase
        candidatas = []
        for porta in _PORTASComuns:
            conexao = self.criadorConexaoHttp("127.0.0.1", porta, timeout=0.35)
            try:
                conexao.request("GET", "/")
                resposta = conexao.getresponse()
                tipo = resposta.getheader("Content-Type", "").lower()
                resposta.read(256)
                if resposta.status < 500 and ("text/html" in tipo or resposta.status in {401, 403}):
                    candidatas.append(f"http://127.0.0.1:{porta}/")
            except (OSError, http.client.HTTPException):
                pass
            finally:
                conexao.close()
        return candidatas[0] if len(candidatas) == 1 else None

    def _resolverOrigens(self, urlBase: str) -> set[str]:
        origemBase = origemHttp(urlBase)
        origens = {origemHttp(item) for item in self.configuracao.origensPermitidas}
        origens.discard(None)
        if origemBase:
            origens.add(origemBase)
        return {item for item in origens if item is not None}

    def _resolverEstadoSessao(self) -> str | None | bool:
        caminho = self.configuracao.arquivoEstadoSessao
        if not caminho:
            return None
        try:
            arquivo = self.arquivos.resolve(caminho)
        except PathOutsideProjectError:
            self._limitar("arquivoEstadoSessao precisa permanecer dentro da raiz do projeto.")
            return False
        if not arquivo.is_file():
            self._limitar("O arquivo de estado de sessão configurado não existe.")
            return False
        return str(arquivo)

    def _iniciarAplicacao(self) -> None:
        comando = self.configuracao.comandoInicial
        try:
            CommandPolicy().ensure_safe(shlex.join(comando))
            opcoes = {
                "cwd": self.raizProjeto,
                "stdin": subprocess.DEVNULL,
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
                "shell": False,
            }
            if os.name == "nt":
                opcoes["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            else:
                opcoes["start_new_session"] = True
            self._processo = self.criadorProcesso(comando, **opcoes)
            event("tool.browser_app.started", executable=Path(comando[0]).name)
        except Exception as exc:
            self._limitar(f"Não foi possível iniciar a aplicação pelo comando configurado ({type(exc).__name__}).")
            raise ToolExecutionError("Falha ao iniciar aplicação de teste.") from exc

    def _encerrarAplicacao(self) -> None:
        processo = self._processo
        self._processo = None
        if processo is None or processo.poll() is not None:
            return
        try:
            if os.name == "nt":
                self.executorComando(
                    ["taskkill", "/PID", str(processo.pid), "/T", "/F"],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=8,
                    check=False,
                    shell=False,
                )
            else:
                os.killpg(processo.pid, signal.SIGTERM)
                try:
                    processo.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(processo.pid, signal.SIGKILL)
            processo.wait(timeout=5)
            event("tool.browser_app.stopped", exit_code=processo.returncode)
        except (OSError, subprocess.TimeoutExpired):
            try:
                processo.terminate()
                processo.wait(timeout=3)
            except (OSError, subprocess.TimeoutExpired):
                processo.kill()

    def _explorar(self, navegador, urlBase: str, estadoSessao, erroPlaywright, timeoutPlaywright, objetivo: str) -> None:
        assert self._relatorio is not None
        fila: deque[str] = deque([urlBase])
        visitadas: set[str] = set()
        controlsVistos: set[str] = set()
        limitesAtingidos = False
        for indiceViewport, viewport in enumerate(self.configuracao.viewports):
            if self._cancelado() or self._esgotado():
                limitesAtingidos = True
                break
            contextoArgs = {"viewport": {"width": viewport.largura, "height": viewport.altura}}
            if estadoSessao:
                contextoArgs["storage_state"] = estadoSessao
            contexto = navegador.new_context(**contextoArgs)
            self._configurarRede(contexto)
            paginas = contexto.pages
            pagina = paginas[0] if paginas else contexto.new_page()
            try:
                if indiceViewport == 0:
                    try:
                        self._navegar(pagina, urlBase, timeoutPlaywright)
                    except erroPlaywright as exc:
                        if self._processo is not None:
                            self._aguardarServidor(pagina, urlBase, erroPlaywright)
                        else:
                            self._limitar(f"A aplicação não respondeu em urlBase ({type(exc).__name__}).")
                            continue
                    while fila and len(visitadas) < self.configuracao.paginasMaximas and not self._esgotado():
                        if self._cancelado():
                            limitesAtingidos = True
                            break
                        urlAtual = fila.popleft()
                        chavePagina = self._chaveUrl(urlAtual)
                        if chavePagina in visitadas or not urlPermitida(urlAtual, self._origens):
                            continue
                        visitadas.add(chavePagina)
                        self._observarEventos(pagina)
                        try:
                            resposta = self._navegar(pagina, urlAtual, timeoutPlaywright)
                            statusHttp = resposta.status if resposta else None
                            assinatura = self._assinaturaPagina(pagina)
                            conteudo = pagina.locator("body").inner_text(timeout=self.configuracao.limiteAcaoMs).strip()
                            statusItem = "aprovado" if conteudo else "inconclusivo"
                            observacao = "A rota carregou conteúdo visível." if conteudo else "A rota carregou sem texto visível para verificar."
                            if statusHttp is not None and statusHttp >= 400:
                                statusItem = "falhou"
                                observacao = f"A rota respondeu HTTP {statusHttp}."
                                self._adicionarAchado("alta" if statusHttp >= 500 else "media", "navegacao", "Rota respondeu com erro HTTP", urlAtual, "Resposta HTTP de sucesso", f"HTTP {statusHttp}", [f"Abrir {_urlRelatorio(urlAtual)}"], "alta", pagina)
                            itemPagina = ItemCoberturaAplicacao(
                                identificador=f"pagina-{len(visitadas)}-{hashlib.sha1(chavePagina.encode()).hexdigest()[:8]}",
                                tipo="pagina",
                                nome=_urlRelatorio(urlAtual),
                                url=_urlRelatorio(urlAtual),
                                status=statusItem,
                                expectativa="A rota responde e apresenta conteúdo navegável.",
                                fonteExpectativa="resposta HTTP e conteúdo visível",
                                observacao=observacao,
                                passos=[f"Abrir {_urlRelatorio(urlAtual)}"],
                            )
                            self._relatorio.itens.append(itemPagina)
                            if statusItem == "inconclusivo":
                                self._limitar(f"Não foi possível inferir conteúdo textual em {_urlRelatorio(urlAtual)}.")
                            self._verificarAcessibilidade(pagina, urlAtual)
                            if indiceViewport == 0:
                                controles = self._coletarControles(pagina)
                                if len(visitadas) == 1:
                                    self._verificarTeclado(pagina, urlAtual, len(controles))
                                for controle in controles:
                                    if self._esgotado() or self._cancelado():
                                        limitesAtingidos = True
                                        break
                                    chaveControle = self._chaveControle(urlAtual, controle)
                                    if chaveControle in controlsVistos:
                                        continue
                                    controlsVistos.add(chaveControle)
                                    self._relatorio.controlesDescobertos += 1
                                    self._explorarControle(navegador, urlAtual, controle, erroPlaywright, timeoutPlaywright)
                                    if controle.get("href") and not controle.get("arriscado"):
                                        destino = urljoin(urlAtual, controle["href"])
                                        if not self.configuracao.permitirMutacoes and _ACOESDeRisco.search(destino):
                                            continue
                                        if urlPermitida(destino, self._origens) and self._chaveUrl(destino) not in visitadas:
                                            destinoLimpo = urlunsplit((*urlsplit(destino)[:3], "", ""))
                                            fila.append(destinoLimpo)
                                for destino in self._linksPagina(pagina, urlAtual):
                                    if self._chaveUrl(destino) not in visitadas and destino not in fila:
                                        fila.append(destino)
                            else:
                                self._verificarViewport(pagina, viewport.nome, urlAtual)
                        except timeoutPlaywright:
                            self._relatorio.itens.append(ItemCoberturaAplicacao(
                                identificador=f"pagina-timeout-{len(visitadas)}",
                                tipo="pagina",
                                nome=_urlRelatorio(urlAtual),
                                url=_urlRelatorio(urlAtual),
                                status="falhou",
                                expectativa="A rota carrega dentro do limite configurado.",
                                fonteExpectativa="limite operacional",
                                observacao="Tempo limite ao carregar ou inspecionar a rota.",
                                passos=[f"Abrir {_urlRelatorio(urlAtual)}"],
                            ))
                            self._adicionarAchado("media", "navegacao", "Rota excedeu o tempo limite", urlAtual, "Carregamento dentro do limite configurado", "Tempo limite excedido", [f"Abrir {_urlRelatorio(urlAtual)}"], "media", pagina)
                        except erroPlaywright as exc:
                            self._adicionarAchado("media", "interacao", "Falha durante exploração da rota", urlAtual, None, type(exc).__name__, [f"Abrir {_urlRelatorio(urlAtual)}"], "media", pagina)
                        if len(visitadas) >= self.configuracao.paginasMaximas or self._acoesExecutadas >= self.configuracao.acoesMaximas:
                            limitesAtingidos = bool(fila)
                            break
                else:
                    for urlAtual in list(visitadas):
                        if self._esgotado() or self._cancelado():
                            limitesAtingidos = True
                            break
                        self._navegar(pagina, urlAtual, timeoutPlaywright)
                        self._verificarViewport(pagina, viewport.nome, urlAtual)
            finally:
                contexto.close()

        chavesPendentes = {self._chaveUrl(url) for url in fila} - visitadas
        self._relatorio.paginasDescobertas = max(self._relatorio.paginasDescobertas, len(visitadas) + len(chavesPendentes))
        self._relatorio.paginasVisitadas = len(visitadas)
        if fila or limitesAtingidos:
            self._limitar("O inventário pode estar incompleto: o limite de páginas, ações ou tempo foi atingido.")
        if self._cancelado():
            self._limitar("Execução cancelada.")
            self._relatorio.status = "cancelado"
        for jornada in self.configuracao.jornadas:
            if self._esgotado() or self._cancelado():
                self._limitar("Jornadas restantes não executadas por limite de execução.")
                break
            self._executarJornada(navegador, urlBase, jornada, erroPlaywright, timeoutPlaywright)

    def _navegar(self, pagina, url: str, timeoutPlaywright):
        if not urlPermitida(url, self._origens):
            raise ToolExecutionError("Origem bloqueada pela configuração de teste.")
        return pagina.goto(url, wait_until="domcontentloaded", timeout=self.configuracao.limiteAcaoMs)

    def _aguardarServidor(self, pagina, urlBase: str, erroPlaywright) -> None:
        limite = time.monotonic() + self.configuracao.inicializacaoLimiteSegundos
        ultimoErro = None
        while time.monotonic() < limite and not self._cancelado():
            if self._processo is not None and self._processo.poll() is not None:
                break
            try:
                self._navegar(pagina, urlBase, timeoutPlaywright)
                return
            except erroPlaywright as exc:
                ultimoErro = exc
                time.sleep(0.35)
        raise ToolExecutionError(f"Aplicação não ficou pronta ({type(ultimoErro).__name__ if ultimoErro else 'processo encerrado'}).")

    def _coletarControles(self, pagina) -> list[dict]:
        controles = pagina.evaluate(
            """() => {
              const visiveis = el => {
                const estilo = getComputedStyle(el);
                return estilo.display !== 'none' && estilo.visibility !== 'hidden' && el.getClientRects().length > 0;
              };
              const nome = el => {
                const porRotulo = [...(el.labels || [])].map(item => item.innerText.trim()).filter(Boolean).join(' ');
                const rotuloRef = (el.getAttribute('aria-labelledby') || '').split(/\\s+/)
                  .map(id => document.getElementById(id)?.innerText.trim() || '').filter(Boolean).join(' ');
                return el.getAttribute('aria-label') || rotuloRef || porRotulo ||
                  (el.innerText || el.value || el.getAttribute('title') || '').trim() ||
                  el.getAttribute('placeholder') || '';
              };
              const elementos = [...document.querySelectorAll(
                'a[href],button,input:not([type=hidden]),select,textarea,[role=button],[role=link],[role=tab],[role=menuitem]'
              )].filter(visiveis);
              return elementos.map((el, indice) => {
                const tag = el.tagName.toLowerCase();
                const tipo = (el.getAttribute('type') || '').toLowerCase();
                let papel = el.getAttribute('role');
                if (!papel && tag === 'a') papel = 'link';
                if (!papel && tag === 'button') papel = 'button';
                if (!papel && tag === 'textarea') papel = 'textbox';
                if (!papel && tag === 'select') papel = 'combobox';
                if (!papel && tag === 'input') {
                  papel = ({checkbox:'checkbox',radio:'radio',range:'slider',number:'spinbutton',submit:'button',reset:'button',button:'button'})[tipo] || 'textbox';
                }
                const textoAcessivel = !!(el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') ||
                  (el.labels && [...el.labels].some(item => item.innerText.trim())) ||
                  ((tag === 'button' || tag === 'a' || ['submit','button','reset'].includes(tipo)) && nome(el)));
                return {
                  indice, tag, tipo, papel: papel || 'generic', nome: nome(el), textoAcessivel,
                  href: el.getAttribute('href') || '', desabilitado: !!el.disabled,
                  emFormulario: !!el.closest('form'), submit: tipo === 'submit' || (tag === 'button' && (!el.type || el.type === 'submit')),
                  obrigatorio: !!el.required, placeholder: el.getAttribute('placeholder') || '',
                  identificador: el.id || '',
                  somenteInterface: papel === 'tab' || el.hasAttribute('aria-expanded') || el.hasAttribute('aria-pressed') ||
                    /\\b(menu|abrir|fechar|expandir|recolher|mostrar|ocultar|pr[oó]ximo|anterior|voltar)\\b/i.test(nome(el)),
                  arriscado: /\\b(delete|remove|destroy|purchase|checkout|payment|transfer|submit|save|create|publish|confirm|excluir|remover|apagar|deletar|comprar|pagar|transferir|enviar|salvar|criar|publicar|confirmar)\\b/i.test(nome(el))
                };
              });
            }"""
        )
        duplicados: dict[tuple[str, str], int] = {}
        for controle in controles:
            chave = (controle.get("papel", "generic"), controle.get("nome", ""))
            controle["duplicado"] = duplicados.get(chave, 0)
            duplicados[chave] = controle["duplicado"] + 1
        return controles

    def _linksPagina(self, pagina, urlAtual: str) -> list[str]:
        links = pagina.locator("a[href]").evaluate_all(
            "els => els.filter(el => el.getClientRects().length).map(el => ({href:el.href,nome:el.innerText||el.getAttribute('aria-label')||''}))"
        )
        destinos = []
        for link in links:
            destino = urljoin(urlAtual, link["href"])
            if link.get("nome") and _ACOESDeRisco.search(link["nome"]):
                continue
            if _ACOESDeRisco.search(destino):
                continue
            if urlPermitida(destino, self._origens) and self._chaveUrl(destino) != self._chaveUrl(urlAtual):
                destinos.append(urlunsplit((*urlsplit(destino)[:3], "", "")))
        return list(dict.fromkeys(destinos))

    def _configurarRede(self, contexto) -> None:
        def decidirRota(rota):
            url = rota.request.url
            if urlPermitida(url, self._origens):
                rota.continue_()
                return
            origem = origemHttp(url)
            host = urlsplit(origem).hostname if origem else "origem não HTTP"
            self._limitar(f"Requisição para origem não permitida foi bloqueada ({host}).")
            rota.abort()

        contexto.route("**/*", decidirRota)

    def _verificarTeclado(self, pagina, url: str, controlesVisiveis: int) -> None:
        assert self._relatorio is not None
        if controlesVisiveis == 0:
            return
        focos = 0
        tentativas = min(8, controlesVisiveis, self.configuracao.acoesMaximas - self._acoesExecutadas)
        for _ in range(max(0, tentativas)):
            try:
                pagina.keyboard.press("Tab")
                self._acoesExecutadas += 1
                estado = pagina.evaluate(
                    """() => {
                      const el = document.activeElement;
                      const papel = el?.getAttribute('role') || '';
                      const interativo = (!!el && /^(A|BUTTON|INPUT|SELECT|TEXTAREA)$/.test(el.tagName)) ||
                        ['button','link','tab','menuitem','checkbox','radio','textbox','combobox'].includes(papel);
                      return {interativo:!!interativo,visivel:!!el && el.getClientRects().length > 0};
                    }"""
                )
                if estado["interativo"] and estado["visivel"]:
                    focos += 1
            except Exception:
                break
        status = "aprovado" if focos else "falhou"
        observacao = f"{focos} foco(s) interativo(s) visível(is) em {tentativas} pressionamento(s) de Tab."
        self._relatorio.itens.append(ItemCoberturaAplicacao(
            identificador=f"teclado-{hashlib.sha1(self._chaveUrl(url).encode()).hexdigest()[:8]}",
            tipo="teclado", nome="Ordem inicial de foco", url=_urlRelatorio(url), status=status,
            expectativa="Tab alcança controles interativos visíveis.",
            fonteExpectativa="comportamento de foco do navegador", observacao=observacao,
            passos=[f"Abrir {_urlRelatorio(url)}", "Pressionar Tab"],
        ))
        if not focos:
            self._adicionarAchado("media", "acessibilidade", "Tab não alcançou controles interativos visíveis",
                                  url, "Controles interativos recebem foco por teclado", observacao,
                                  [f"Abrir {_urlRelatorio(url)}", "Pressionar Tab"], "baixa", pagina)

    def _verificarAcessibilidade(self, pagina, url: str) -> None:
        controlesSemNome = pagina.evaluate(
            """() => [...document.querySelectorAll('button,a[href],input:not([type=hidden]),select,textarea,[role=button],[role=link]')]
              .filter(el => getComputedStyle(el).display !== 'none' && el.getClientRects().length)
              .filter(el => {
                const ref = (el.getAttribute('aria-labelledby') || '').split(/\\s+/).map(id => document.getElementById(id)?.innerText.trim() || '').join('');
                const label = [...(el.labels || [])].some(item => item.innerText.trim());
                const text = (el.innerText || el.value || '').trim();
                return !(el.getAttribute('aria-label') || ref || label || text);
              }).length"""
        )
        if controlesSemNome:
            self._adicionarAchado(
                "media", "acessibilidade", f"{controlesSemNome} controle(s) visível(is) sem nome acessível",
                url, "Controles interativos com nome acessível", f"{controlesSemNome} sem nome detectável",
                [f"Abrir {_urlRelatorio(url)}"], "media", pagina,
            )

    def _verificarViewport(self, pagina, nomeViewport: str, url: str) -> None:
        dimensoes = pagina.evaluate("() => ({larguraJanela: document.documentElement.clientWidth, larguraPagina: document.documentElement.scrollWidth})")
        excesso = dimensoes["larguraPagina"] - dimensoes["larguraJanela"]
        status = "falhou" if excesso > 2 else "aprovado"
        self._relatorio.itens.append(ItemCoberturaAplicacao(
            identificador=f"viewport-{nomeViewport}-{hashlib.sha1(self._chaveUrl(url).encode()).hexdigest()[:8]}",
            tipo="viewport", nome=nomeViewport, url=_urlRelatorio(url), status=status,
            expectativa="Conteúdo cabe na largura da viewport sem rolagem horizontal global.",
            fonteExpectativa="heurística de responsividade",
            observacao=f"Excesso horizontal de {excesso}px." if excesso > 2 else "Sem excesso horizontal global detectado.",
            passos=[f"Abrir {_urlRelatorio(url)} em {nomeViewport}"],
        ))
        if excesso > 2:
            self._adicionarAchado("media", "interacao", "Conteúdo excede a largura da viewport", url,
                                  "Rolagem horizontal global ausente", f"Excesso de {excesso}px em {nomeViewport}",
                                  [f"Abrir {_urlRelatorio(url)} em {nomeViewport}"], "media", pagina)

    def _explorarControle(self, navegador, urlAtual: str, controle: dict, erroPlaywright, timeoutPlaywright) -> None:
        nome = str(controle.get("nome") or "")
        papel = controle.get("papel", "generic")
        alvo = _sanitizarTexto(nome) or f"{papel} sem nome"
        identificador = f"controle-{hashlib.sha1(self._chaveControle(urlAtual, controle).encode()).hexdigest()[:12]}"
        passos = [f"Abrir {_urlRelatorio(urlAtual)}", f"Interagir com {papel}: {alvo}"]
        tipo = controle.get("tipo", "")

        if not controle.get("textoAcessivel") and papel not in {"generic"}:
            self._adicionarAchado("media", "acessibilidade", "Controle sem nome acessível", urlAtual,
                                  "Nome acessível por texto, label ou ARIA", papel, passos, "alta")
        if controle.get("desabilitado"):
            self._relatorio.itens.append(ItemCoberturaAplicacao(
                identificador=identificador, tipo="controle", nome=alvo, url=_urlRelatorio(urlAtual),
                status="ignorado", observacao="Controle desabilitado.", passos=passos,
            ))
            self._relatorio.controlesIgnorados += 1
            return
        if controle.get("href") and not urlPermitida(urljoin(urlAtual, controle["href"]), self._origens):
            self._limitar("Link para uma origem fora da allowlist foi bloqueado.")
            self._ignorarControle(identificador, alvo, urlAtual, passos, "Destino fora das origens permitidas.", "bloqueado")
            return
        if tipo == "password" or tipo == "file":
            self._ignorarControle(identificador, alvo, urlAtual, passos, "Campo de senha ou arquivo exige dados explícitos de teste.")
            return
        if papel in {"textbox", "combobox", "checkbox", "radio", "spinbutton", "slider"}:
            self._testarValidacaoCampo(navegador, urlAtual, controle, identificador, alvo, passos, erroPlaywright)
            return
        ehFormularioMutavel = controle.get("emFormulario") and (controle.get("submit") or papel == "button")
        ehAcaoArriscada = controle.get("arriscado")
        ehBotao = papel in {"button", "menuitem"}
        mutavel = bool(ehFormularioMutavel or ehAcaoArriscada or (ehBotao and not controle.get("somenteInterface")))
        if mutavel and not self.configuracao.permitirMutacoes:
            self._ignorarControle(identificador, alvo, urlAtual, passos, "Ação potencialmente mutável bloqueada; configure um ambiente de teste e reset explícito.")
            return
        if not nome and papel in {"link", "button", "tab", "menuitem"}:
            self._ignorarControle(identificador, alvo, urlAtual, passos, "Controle sem nome acessível não pode ser acionado de forma confiável.")
            return
        if self._esgotado() or self._cancelado():
            self._ignorarControle(identificador, alvo, urlAtual, passos, "Limite de ações ou tempo atingido.", "bloqueado")
            return
        if mutavel and not self._executarReset():
            self._ignorarControle(identificador, alvo, urlAtual, passos, "Reset do ambiente de teste falhou.", "bloqueado")
            return

        contextoArgs = {}
        if self.configuracao.arquivoEstadoSessao:
            contextoArgs["storage_state"] = str(self.arquivos.resolve(self.configuracao.arquivoEstadoSessao))
        contexto = navegador.new_context(**contextoArgs)
        self._configurarRede(contexto)
        pagina = contexto.new_page()
        self._observarEventos(pagina)
        status = "inconclusivo"
        observacao = "A interação foi tentada, sem uma expectativa de negócio configurada."
        esperado = None
        fonte = None
        try:
            self._navegar(pagina, urlAtual, erroPlaywright)
            antesUrl = self._chaveUrl(pagina.url)
            antesAssinatura = self._assinaturaPagina(pagina)
            localizador = self._localizador(pagina, papel, nome, int(controle.get("duplicado", 0)))
            if mutavel and controle.get("submit"):
                self._preencherFormularioTeste(localizador)
            localizador.click(timeout=self.configuracao.limiteAcaoMs)
            pagina.wait_for_timeout(100)
            paginaAtual = contexto.pages[-1]
            depoisUrl = self._chaveUrl(paginaAtual.url)
            depoisAssinatura = self._assinaturaPagina(paginaAtual)
            href = controle.get("href")
            if href:
                destino = self._chaveUrl(urljoin(urlAtual, href))
                esperado = f"Navegação para {_urlRelatorio(destino)}"
                fonte = "href declarado no link"
                if depoisUrl == destino:
                    status = "aprovado"
                    observacao = "O link abriu o destino declarado."
                elif depoisUrl != antesUrl:
                    status = "falhou"
                    observacao = f"O link abriu {_urlRelatorio(paginaAtual.url)}, diferente do destino declarado."
                else:
                    status = "falhou"
                    observacao = "O link não navegou para o destino declarado."
                    self._adicionarAchado("alta", "navegacao", "Link não abriu o destino declarado", urlAtual,
                                          esperado, observacao, passos, "alta", paginaAtual)
            elif depoisUrl != antesUrl:
                observacao = f"A interação navegou para {_urlRelatorio(paginaAtual.url)}; comportamento de negócio não especificado."
            elif depoisAssinatura != antesAssinatura:
                observacao = "A interface mudou após a interação; o resultado de negócio precisa de uma expectativa explícita."
            else:
                observacao = "Nenhuma mudança observável de URL ou conteúdo após a interação."
                self._adicionarAchado("baixa", "interacao", "Controle sem resposta observável", urlAtual,
                                      None, observacao, passos, "baixa", paginaAtual)
        except erroPlaywright as exc:
            status = "falhou"
            observacao = f"A interação não pôde ser concluída ({type(exc).__name__})."
            self._adicionarAchado("media", "interacao", "Falha ao acionar controle", urlAtual, esperado,
                                  observacao, passos, "media", pagina)
            self._capturarTela(pagina, identificador)
        finally:
            contexto.close()
        self._relatorio.itens.append(ItemCoberturaAplicacao(
            identificador=identificador, tipo="controle", nome=alvo, url=_urlRelatorio(urlAtual),
            status=status, expectativa=esperado, fonteExpectativa=fonte, observacao=observacao, passos=passos,
        ))
        self._relatorio.controlesExercitados += 1
        self._acoesExecutadas += 1

    def _preencherFormularioTeste(self, botaoEnvio) -> None:
        formulario = botaoEnvio.locator("xpath=ancestor::form[1]")
        campos = formulario.locator("input:not([type=hidden]):not([type=submit]):not([type=button]):not([type=reset]):not([type=image]),select,textarea")
        gruposRadio: set[str] = set()
        for indice in range(campos.count()):
            campo = campos.nth(indice)
            tipo = (campo.get_attribute("type") or "text").lower()
            if campo.is_disabled() or tipo == "file":
                continue
            if tipo in {"checkbox", "radio"}:
                if tipo == "radio":
                    grupo = campo.get_attribute("name") or f"sem-nome-{indice}"
                    if grupo in gruposRadio:
                        continue
                    gruposRadio.add(grupo)
                if campo.is_visible() and (not campo.get_attribute("checked") or campo.get_attribute("required")):
                    campo.check(timeout=self.configuracao.limiteAcaoMs)
                continue
            if campo.evaluate("el => el.tagName.toLowerCase() === 'select'"):
                opcoes = campo.locator("option").evaluate_all(
                    "els => els.filter(el => !el.disabled && el.value).map(el => el.value)"
                )
                if opcoes:
                    campo.select_option(value=opcoes[0], timeout=self.configuracao.limiteAcaoMs)
                continue
            if tipo == "email":
                valor = f"dev-agent-{uuid4().hex[:10]}@example.invalid"
            elif tipo == "url":
                valor = "https://example.invalid"
            elif tipo == "number":
                valor = campo.get_attribute("min") or "1"
            elif tipo == "date":
                valor = "2000-01-01"
            elif tipo == "datetime-local":
                valor = "2000-01-01T12:00"
            elif tipo == "time":
                valor = "12:00"
            elif tipo == "password":
                valor = uuid4().hex + "Aa1!"
            elif tipo in {"range", "color"}:
                continue
            elif campo.evaluate("el => el.tagName.toLowerCase() === 'textarea'"):
                valor = "Texto de teste DevAgent"
            elif tipo in {"tel"}:
                valor = "11999999999"
            else:
                valor = "Teste DevAgent"
            campo.fill(valor, timeout=self.configuracao.limiteAcaoMs)

    def _testarValidacaoCampo(self, navegador, urlAtual: str, controle: dict, identificador: str,
                              alvo: str, passos: list[str], erroPlaywright) -> None:
        assert self._relatorio is not None
        papel = controle.get("papel", "textbox")
        nome = str(controle.get("nome") or "")
        tipo = str(controle.get("tipo") or "")
        esperado = None
        fonte = None
        status = "inconclusivo"
        observacao = "Campo identificado; nenhuma regra nativa de validação declarada."
        if controle.get("obrigatorio"):
            esperado = "Campo obrigatório rejeita valor vazio."
            fonte = "atributo required da interface"
        elif tipo == "email":
            esperado = "Campo de e-mail rejeita formato inválido."
            fonte = "tipo email do HTML"
        else:
            self._relatorio.itens.append(ItemCoberturaAplicacao(
                identificador=identificador, tipo="controle", nome=alvo, url=_urlRelatorio(urlAtual),
                status=status, expectativa=esperado, fonteExpectativa=fonte, observacao=observacao, passos=passos,
            ))
            self._relatorio.controlesExercitados += 1
            return
        self._relatorio.assertivasConfiguradas += 1
        contextoArgs = {}
        if self.configuracao.arquivoEstadoSessao:
            contextoArgs["storage_state"] = str(self.arquivos.resolve(self.configuracao.arquivoEstadoSessao))
        contexto = navegador.new_context(**contextoArgs)
        self._configurarRede(contexto)
        pagina = contexto.new_page()
        try:
            self._navegar(pagina, urlAtual, erroPlaywright)
            localizador = self._localizador(pagina, papel, nome, int(controle.get("duplicado", 0)))
            if self.configuracao.permitirMutacoes:
                if not self._executarReset():
                    status = "bloqueado"
                    observacao = "Reset do ambiente de teste falhou; o campo não foi alterado."
                    self._relatorio.controlesIgnorados += 1
                else:
                    if papel in {"checkbox", "radio", "combobox", "slider"}:
                        valido = localizador.evaluate("elemento => elemento.checkValidity()")
                    elif tipo == "email":
                        localizador.fill("endereco-invalido", timeout=self.configuracao.limiteAcaoMs)
                        valido = localizador.evaluate("elemento => elemento.checkValidity()")
                    else:
                        localizador.fill("", timeout=self.configuracao.limiteAcaoMs)
                        valido = localizador.evaluate("elemento => elemento.checkValidity()")
                    self._registrarResultadoValidacao(urlAtual, esperado, passos, pagina, valido)
            else:
                estadoCampo = localizador.evaluate(
                    """el => ({valido:el.checkValidity(),vazio:el.matches(':checkbox,:radio') ? !el.checked :
                      el.tagName.toLowerCase() === 'select' ? !el.value : !el.value})"""
                )
                if controle.get("obrigatorio") and estadoCampo["vazio"]:
                    self._registrarResultadoValidacao(urlAtual, esperado, passos, pagina, estadoCampo["valido"])
                elif tipo == "email" and not estadoCampo["vazio"]:
                    self._registrarResultadoValidacao(urlAtual, esperado, passos, pagina, estadoCampo["valido"])
                else:
                    observacao = "Valor não foi alterado; regra nativa identificada, mas exige campo vazio ou inválido para confirmar."
            self._acoesExecutadas += 1
        except erroPlaywright as exc:
            status = "inconclusivo"
            observacao = f"Não foi possível verificar a validação ({type(exc).__name__})."
        finally:
            contexto.close()
        self._relatorio.itens.append(ItemCoberturaAplicacao(
            identificador=identificador, tipo="controle", nome=alvo, url=_urlRelatorio(urlAtual),
            status=status, expectativa=esperado, fonteExpectativa=fonte, observacao=observacao, passos=passos,
        ))
        self._relatorio.controlesExercitados += 1

    def _registrarResultadoValidacao(self, urlAtual: str, esperado: str, passos: list[str], pagina, valido: bool) -> None:
        assert self._relatorio is not None
        if valido:
            self._relatorio.itens.append(ItemCoberturaAplicacao(
                identificador=f"assertiva-validacao-{len(self._relatorio.itens) + 1}",
                tipo="controle", nome="Validação do campo", url=_urlRelatorio(urlAtual), status="falhou",
                expectativa=esperado, fonteExpectativa="validação nativa HTML",
                observacao="O navegador aceitou o valor inválido para a regra declarada.", passos=passos,
            ))
            self._adicionarAchado("media", "assertiva", "Campo não aplicou validação nativa declarada", urlAtual,
                                  esperado, "O navegador aceitou o valor inválido.", passos, "alta", pagina)
        else:
            self._relatorio.assertivasAprovadas += 1
            self._relatorio.itens.append(ItemCoberturaAplicacao(
                identificador=f"assertiva-validacao-{len(self._relatorio.itens) + 1}",
                tipo="controle", nome="Validação do campo", url=_urlRelatorio(urlAtual), status="aprovado",
                expectativa=esperado, fonteExpectativa="validação nativa HTML",
                observacao="O navegador rejeitou o valor inválido conforme a regra declarada.", passos=passos,
            ))

    def _executarJornada(self, navegador, urlBase: str, jornada: JornadaAplicacao, erroPlaywright, timeoutPlaywright) -> None:
        assert self._relatorio is not None
        assertivasJornada = sum(passo.acao.startswith("ver_") for passo in jornada.passos)
        self._relatorio.assertivasConfiguradas += assertivasJornada
        mutavel = self.configuracao.permitirMutacoes and any(
            passo.alteraEstado or passo.acao in {"clicar", "preencher", "selecionar", "marcar"}
            for passo in jornada.passos
        )
        passosFeitos: list[str] = []
        falhas: list[str] = []
        contextoArgs = {}
        if self.configuracao.arquivoEstadoSessao:
            contextoArgs["storage_state"] = str(self.arquivos.resolve(self.configuracao.arquivoEstadoSessao))
        contexto = navegador.new_context(**contextoArgs)
        self._configurarRede(contexto)
        pagina = contexto.new_page()
        self._observarEventos(pagina)
        try:
            if mutavel and not self._executarReset():
                falhas.append("O comandoReset falhou antes da jornada.")
            else:
                for passo in jornada.passos:
                    if self._cancelado() or self._esgotado():
                        falhas.append("Jornada interrompida pelo limite ou cancelamento.")
                        break
                    self._aplicarPasso(pagina, urlBase, passo, timeoutPlaywright)
                    passosFeitos.append(f"{passo.acao}: {_sanitizarTexto(passo.alvo or passo.valor)}")
                    self._acoesExecutadas += 1
                    if passo.acao.startswith("ver_"):
                        self._relatorio.assertivasAprovadas += 1
        except erroPlaywright as exc:
            falhas.append(f"{type(exc).__name__}: {_sanitizarTexto(str(exc))}")
        except (AssertionError, ValueError, ToolExecutionError) as exc:
            falhas.append(_sanitizarTexto(str(exc)))
        status = "falhou" if falhas else "aprovado" if assertivasJornada else "inconclusivo"
        observacao = "; ".join(falhas) if falhas else "Todas as assertivas configuradas passaram." if assertivasJornada else "Jornada executada sem assertivas explícitas."
        self._relatorio.itens.append(ItemCoberturaAplicacao(
            identificador=f"jornada-{hashlib.sha1(jornada.nome.encode()).hexdigest()[:10]}",
            tipo="jornada", nome=_sanitizarTexto(jornada.nome), url=_urlRelatorio(pagina.url) if pagina.url else _urlRelatorio(urlBase),
            status=status, expectativa=jornada.objetivo, fonteExpectativa="jornada configurada",
            observacao=observacao, passos=passosFeitos,
        ))
        if falhas:
            self._adicionarAchado("alta", "assertiva", f"Jornada falhou: {_sanitizarTexto(jornada.nome)}", pagina.url or urlBase,
                                  jornada.objetivo, observacao, passosFeitos, "alta", pagina)
            self._capturarTela(pagina, f"jornada-{hashlib.sha1(jornada.nome.encode()).hexdigest()[:10]}")
        contexto.close()

    def _aplicarPasso(self, pagina, urlBase: str, passo: PassoJornadaAplicacao, timeoutPlaywright) -> None:
        if passo.acao == "ir":
            destino = urljoin(urlBase, passo.valor or "")
            if not urlPermitida(destino, self._origens):
                raise ValueError("A jornada tentou navegar para uma origem não permitida.")
            if _ACOESDeRisco.search(destino) and not self.configuracao.permitirMutacoes:
                raise ValueError("A rota parece mutável e foi bloqueada pela configuração.")
            resposta = self._navegar(pagina, destino, timeoutPlaywright)
            if resposta and resposta.status >= 400:
                raise AssertionError(f"Navegação respondeu HTTP {resposta.status}.")
        elif passo.acao == "clicar":
            if not self.configuracao.permitirMutacoes and (passo.alteraEstado or _ACOESDeRisco.search(passo.alvo)):
                raise ValueError("Ação potencialmente mutável bloqueada pela configuração.")
            self._localizadorJornada(pagina, passo.alvo, "botao_ou_link").click(timeout=self.configuracao.limiteAcaoMs)
        elif passo.acao == "preencher":
            self._localizadorJornada(pagina, passo.alvo, "campo").fill(passo.valor or "", timeout=self.configuracao.limiteAcaoMs)
        elif passo.acao == "selecionar":
            self._localizadorJornada(pagina, passo.alvo, "campo").select_option(label=passo.valor, timeout=self.configuracao.limiteAcaoMs)
        elif passo.acao == "marcar":
            self._localizadorJornada(pagina, passo.alvo, "campo").check(timeout=self.configuracao.limiteAcaoMs)
        elif passo.acao == "ver_texto":
            pagina.get_by_text(passo.alvo, exact=False).first.wait_for(state="visible", timeout=self.configuracao.limiteAcaoMs)
        elif passo.acao == "ver_url":
            if (passo.valor or "") not in _urlRelatorio(pagina.url):
                raise AssertionError(f"URL observada {_urlRelatorio(pagina.url)} não contém a expectativa configurada.")
        elif passo.acao == "ver_visivel":
            self._localizadorJornada(pagina, passo.alvo, "texto").wait_for(state="visible", timeout=self.configuracao.limiteAcaoMs)
        elif passo.acao == "ver_oculto":
            self._localizadorJornada(pagina, passo.alvo, "texto").wait_for(state="hidden", timeout=self.configuracao.limiteAcaoMs)

    @staticmethod
    def _localizadorJornada(pagina, alvo: str, tipo: str):
        if tipo == "campo":
            return pagina.get_by_label(alvo, exact=True).first
        if tipo == "botao_ou_link":
            botao = pagina.get_by_role("button", name=alvo, exact=True)
            return botao.first if botao.count() else pagina.get_by_role("link", name=alvo, exact=True).first
        return pagina.get_by_text(alvo, exact=False).first

    @staticmethod
    def _localizador(pagina, papel: str, nome: str, duplicado: int):
        localizador = pagina.get_by_role(papel, name=nome, exact=True)
        total = localizador.count()
        return localizador.nth(min(duplicado, total - 1)) if total else localizador.first

    def _executarReset(self) -> bool:
        comando = self.configuracao.comandoReset
        if not (self.configuracao.ambienteDeTesteConfirmado and comando):
            return False
        try:
            CommandPolicy().ensure_safe(shlex.join(comando), confirmed=True)
            resultado = self.executorComando(
                comando,
                cwd=self.raizProjeto,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=min(60, self.configuracao.tempoLimiteSegundos),
                shell=False,
                check=False,
            )
            return resultado.returncode == 0
        except (OSError, subprocess.SubprocessError, ValueError):
            return False

    def _observarEventos(self, pagina) -> None:
        pagina.on("console", lambda mensagem: self._registrarEvento("console", pagina.url, mensagem.text) if mensagem.type == "error" else None)
        pagina.on("pageerror", lambda erro: self._registrarEvento("console", pagina.url, type(erro).__name__))
        pagina.on("requestfailed", lambda requisicao: self._registrarEvento("rede", requisicao.url, "Requisição falhou") if urlPermitida(requisicao.url, self._origens) else None)
        pagina.on("response", lambda resposta: self._registrarEvento("rede", resposta.url, f"HTTP {resposta.status}")
                   if resposta.status >= 400 and urlPermitida(resposta.url, self._origens) and resposta.request.resource_type in {"document", "xhr", "fetch", "script", "stylesheet"} else None)

    def _registrarEvento(self, categoria: str, url: str, observacao: str) -> None:
        severidade = "alta" if categoria == "console" else "media"
        self._adicionarAchado(severidade, categoria, "Erro observado durante interação", url, None,
                              _sanitizarTexto(observacao), [f"Abrir {_urlRelatorio(url)}"], "media")

    def _adicionarAchado(self, severidade: str, categoria: str, titulo: str, url: str | None,
                         esperado: str | None, observado: str | None, passos: list[str], confianca: str,
                         pagina=None) -> None:
        assert self._relatorio is not None
        urlSegura = _urlRelatorio(url) if url else None
        chave = (categoria, titulo, urlSegura or "")
        if chave in self._achadosConhecidos:
            return
        self._achadosConhecidos.add(chave)
        artefato = self._capturarTela(pagina, f"achado-{len(self._relatorio.achados) + 1}") if pagina is not None else None
        self._relatorio.achados.append(AchadoAplicacao(
            severidade=severidade,
            categoria=categoria,
            titulo=_sanitizarTexto(titulo),
            url=urlSegura,
            esperado=_sanitizarTexto(esperado) if esperado else None,
            observado=_sanitizarTexto(observado) if observado else None,
            passosReproducao=passos,
            confianca=confianca,
            artefato=artefato,
        ))

    def _capturarTela(self, pagina, nome: str) -> str | None:
        if pagina is None or self._diretorioExecucao is None or not self.configuracao.capturarTelas:
            return None
        alvo = self._diretorioExecucao / f"{re.sub(r'[^a-zA-Z0-9_-]', '-', nome)[:60]}.png"
        try:
            pagina.screenshot(
                path=str(alvo),
                full_page=False,
                animations="disabled",
                timeout=min(5000, self.configuracao.limiteAcaoMs),
                mask=[pagina.locator("input, textarea, [data-sensitive], [data-private]")],
            )
            relativo = alvo.relative_to(self.raizProjeto).as_posix()
            if self._relatorio is not None and relativo not in self._relatorio.artefatos:
                self._relatorio.artefatos.append(relativo)
            return relativo
        except Exception:
            return None

    def _assinaturaPagina(self, pagina) -> str:
        texto = pagina.evaluate("() => `${location.pathname}|${document.title}|${(document.body?.innerText || '').slice(0,3000)}`")
        return hashlib.sha256(texto.encode("utf-8", errors="replace")).hexdigest()

    def _chaveUrl(self, url: str) -> str:
        partes = urlsplit(url)
        return urlunsplit((partes.scheme.lower(), partes.netloc.lower(), partes.path or "/", "", ""))

    def _chaveControle(self, url: str, controle: dict) -> str:
        return "|".join((self._chaveUrl(url), str(controle.get("papel", "")), _sanitizarTexto(controle.get("nome")), str(controle.get("duplicado", 0))))

    def _ignorarControle(self, identificador: str, nome: str, url: str, passos: list[str], motivo: str, status: str = "ignorado") -> None:
        assert self._relatorio is not None
        self._relatorio.controlesIgnorados += 1
        self._relatorio.itens.append(ItemCoberturaAplicacao(
            identificador=identificador, tipo="controle", nome=nome, url=_urlRelatorio(url),
            status=status, observacao=motivo, passos=passos,
        ))

    def _cancelado(self) -> bool:
        return bool(self.cancelamento is not None and self.cancelamento.is_set())

    def _esgotado(self) -> bool:
        return self._acoesExecutadas >= self.configuracao.acoesMaximas or time.monotonic() >= self._fimLimite

    def _limitar(self, mensagem: str) -> None:
        if self._relatorio is not None and mensagem not in self._relatorio.limitacoes:
            self._relatorio.limitacoes.append(_sanitizarTexto(mensagem, 500))

    def _determinarStatus(self) -> str:
        assert self._relatorio is not None
        if self._cancelado():
            return "cancelado"
        if self._relatorio.paginasVisitadas == 0:
            return "bloqueado"
        if self._relatorio.limitacoes or self._relatorio.controlesIgnorados:
            return "parcial"
        return "concluido"

    def _finalizar(self, status: str) -> RelatorioExploracaoAplicacao:
        assert self._relatorio is not None
        self._relatorio.status = status
        self._relatorio.fim = datetime.now(timezone.utc)
        itensControle = [item for item in self._relatorio.itens if item.tipo == "controle"]
        exercitados = sum(item.status in {"aprovado", "falhou", "inconclusivo"} for item in itensControle)
        totalAssertivas = self._relatorio.assertivasConfiguradas
        self._relatorio.percentualExecucao = round(exercitados * 100 / len(itensControle), 1) if itensControle else None
        self._relatorio.percentualAssertivo = round(self._relatorio.assertivasAprovadas * 100 / totalAssertivas, 1) if totalAssertivas else None
        fontes = {item.fonteExpectativa for item in self._relatorio.itens if item.fonteExpectativa}
        self._relatorio.fontesExpectativa = sorted(fontes)
        if self._diretorioExecucao is not None:
            caminhoRelatorio = self._diretorioExecucao / "relatorio.json"
            relativo = caminhoRelatorio.relative_to(self.raizProjeto).as_posix()
            self._relatorio.artefatos.append(relativo)
            try:
                caminhoRelatorio.write_text(
                    json.dumps(self._relatorio.model_dump(mode="json"), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                    newline="\n",
                )
            except OSError:
                self._relatorio.artefatos.remove(relativo)
                self._limitar("Não foi possível gravar relatorio.json.")
        event("tool.browser_app.finished", status=status, pages=self._relatorio.paginasVisitadas,
              controls=self._relatorio.controlesExercitados, findings=len(self._relatorio.achados))
        return self._relatorio
