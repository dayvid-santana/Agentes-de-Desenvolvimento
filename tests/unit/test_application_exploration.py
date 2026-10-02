"""Regressões da configuração e das fronteiras do explorador web."""
from pathlib import Path

import pytest
from pydantic import ValidationError

from dev_agent.config.models import ConfiguracaoTesteAplicacao, JornadaAplicacao, PassoJornadaAplicacao
from dev_agent.tools.application_exploration import FerramentaExploracaoAplicacao, origemHttp, urlPermitida


def test_origemHttp_normaliza_origem_e_rejeita_esquemas_e_credenciais():
    assert origemHttp("https://localhost/caminho") == "https://localhost:443"
    assert origemHttp("http://127.0.0.1:5173/rota") == "http://127.0.0.1:5173"
    assert origemHttp("javascript:alert(1)") is None
    assert origemHttp("https://usuario:senha@example.test") is None
    assert urlPermitida("http://localhost:5173/", {"http://localhost:5173"})
    assert not urlPermitida("http://localhost:5174/", {"http://localhost:5173"})


def test_configuracao_bloqueia_origem_remota_sem_allowlist_e_ambiente_de_teste():
    with pytest.raises(ValidationError):
        ConfiguracaoTesteAplicacao(urlBase="https://app.example.test")

    with pytest.raises(ValidationError):
        ConfiguracaoTesteAplicacao(
            urlBase="https://app.example.test",
            origensPermitidas=["https://app.example.test"],
        )

    configuracao = ConfiguracaoTesteAplicacao(
        urlBase="https://app.example.test",
        origensPermitidas=["https://app.example.test"],
        ambienteDeTesteConfirmado=True,
    )
    assert configuracao.urlBase == "https://app.example.test"


def test_configuracao_exige_reset_e_confirmacao_para_mudancas():
    with pytest.raises(ValidationError):
        ConfiguracaoTesteAplicacao(permitirMutacoes=True)

    with pytest.raises(ValidationError):
        ConfiguracaoTesteAplicacao(
            ambienteDeTesteConfirmado=True,
            permitirMutacoes=True,
        )

    configuracao = ConfiguracaoTesteAplicacao(
        ambienteDeTesteConfirmado=True,
        permitirMutacoes=True,
        comandoReset=["python", "scripts/reset_test_data.py"],
    )
    assert configuracao.permitirMutacoes


def test_jornada_valida_campos_e_exige_expectativa_de_url():
    jornada = JornadaAplicacao.model_validate({
        "nome": "Acesso",
        "objetivo": "Entrar e abrir o painel",
        "passos": [
            {"acao": "ir", "valor": "/login"},
            {"acao": "preencher", "alvo": "E-mail", "valor": "teste@example.invalid"},
            {"acao": "clicar", "alvo": "Entrar", "alteraEstado": True},
            {"acao": "ver_url", "valor": "/painel"},
        ],
    })
    assert len(jornada.passos) == 4

    with pytest.raises(ValidationError):
        PassoJornadaAplicacao(acao="ver_url")


class _RespostaHttp:
    status = 503

    @staticmethod
    def getheader(nome, padrao=""):
        return "text/plain" if nome == "Content-Type" else padrao

    @staticmethod
    def read(_tamanho):
        return b""


class _ConexaoHttp:
    def __init__(self, *_argumentos, **_opcoes):
        pass

    @staticmethod
    def request(*_argumentos, **_opcoes):
        pass

    @staticmethod
    def getresponse():
        return _RespostaHttp()

    @staticmethod
    def close():
        pass


def test_sem_aplicacao_detectada_retorna_relatorio_bloqueado_dentro_do_projeto(tmp_path: Path):
    configuracao = ConfiguracaoTesteAplicacao()
    ferramenta = FerramentaExploracaoAplicacao(
        tmp_path,
        configuracao,
        criadorConexaoHttp=_ConexaoHttp,
    )

    relatorio = ferramenta.executar("Explorar o sistema")

    assert relatorio.status == "bloqueado"
    assert "urlBase" in " ".join(relatorio.limitacoes)
    assert len(relatorio.artefatos) == 1
    artefato = tmp_path / relatorio.artefatos[0]
    assert artefato.is_file()
    assert artefato.resolve().is_relative_to(tmp_path.resolve())


class _RespostaBrowser:
    status = 200


class _LocalizadorBrowser:
    def __init__(self, seletores):
        self.seletores = seletores

    @staticmethod
    def inner_text(**_opcoes):
        return "Aplicação de teste"

    @staticmethod
    def evaluate_all(_script):
        return []


class _PaginaBrowser:
    def __init__(self):
        self.url = ""
        self.keyboard = self

    def on(self, *_argumentos):
        pass

    def goto(self, url, **_opcoes):
        self.url = url
        return _RespostaBrowser()

    def locator(self, seletor):
        return _LocalizadorBrowser(seletor)

    def evaluate(self, script):
        if "const visiveis" in script:
            return []
        if "document.querySelectorAll('button" in script:
            return 0
        if "larguraJanela" in script:
            return {"larguraJanela": 390, "larguraPagina": 390}
        if "document.body?.innerText" in script:
            return "assinatura-da-pagina"
        return None

    @staticmethod
    def wait_for_timeout(_tempo):
        pass

    @staticmethod
    def close():
        pass


class _ContextoBrowser:
    def __init__(self):
        self.pages = []
        self.rotas = []

    def route(self, padrao, decisao):
        self.rotas.append((padrao, decisao))

    def new_page(self):
        pagina = _PaginaBrowser()
        self.pages.append(pagina)
        return pagina

    @staticmethod
    def close():
        pass


class _NavegadorBrowser:
    def __init__(self):
        self.contextos = []

    def new_context(self, **_opcoes):
        contexto = _ContextoBrowser()
        self.contextos.append(contexto)
        return contexto

    @staticmethod
    def close():
        pass


class _MotorBrowser:
    def __init__(self):
        self.navegador = _NavegadorBrowser()

    def launch(self, **_opcoes):
        return self.navegador


class _PlaywrightBrowser:
    def __init__(self):
        self.chromium = _MotorBrowser()

    def __enter__(self):
        return self

    def __exit__(self, *_argumentos):
        pass


def test_exploracao_usa_playwright_injetado_e_grava_cobertura(tmp_path: Path):
    configuracao = ConfiguracaoTesteAplicacao(
        urlBase="http://localhost:5173/",
        viewports=[{"nome": "desktop", "largura": 1365, "altura": 900}],
    )
    ferramenta = FerramentaExploracaoAplicacao(
        tmp_path,
        configuracao,
        playwrightFactory=_PlaywrightBrowser,
        erroPlaywright=Exception,
        timeoutPlaywright=TimeoutError,
    )

    relatorio = ferramenta.executar("Explorar tela inicial")

    assert relatorio.status == "concluido"
    assert relatorio.paginasVisitadas == 1
    assert relatorio.itens[0].tipo == "pagina"
    assert relatorio.artefatos[-1].endswith("relatorio.json")


def test_relatorio_structurado_e_serializavel_no_contrato_do_agent():
    from datetime import datetime, timezone

    from dev_agent.core.models import RelatorioExploracaoAplicacao, SubAgentResult

    relatorio = RelatorioExploracaoAplicacao(
        identificadorExecucao="exec-1",
        objetivo="Explorar página inicial",
        status="bloqueado",
        inicio=datetime.now(timezone.utc),
    )
    resultado = SubAgentResult(agent="explorador_aplicacao", summary="bloqueado", relatorioAplicacao=relatorio)

    assert resultado.model_dump(mode="json")["relatorioAplicacao"]["status"] == "bloqueado"
