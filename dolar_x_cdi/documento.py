"""Monta e renderiza o documento PDF Dólar x CDI a partir dos cálculos."""
from __future__ import annotations

import base64
import datetime as dt
from pathlib import Path

from jinja2 import Template
from weasyprint import HTML

from calculo import JanelaResultado, indicadores_dolar
from fontes import FONTE_DOLAR_NOME, FONTE_CDI_NOME
from graficos import grafico_janela, grafico_resumo_barras
import estilo

PASTA_BASE = Path(__file__).parent
PASTA_SAIDA = PASTA_BASE / "output"
PASTA_TMP = PASTA_BASE / "output" / ".tmp_graficos"

MESES_PT = [
    "", "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def _fmt_pct(v: float) -> str:
    sinal = "-" if v < 0 else ""
    s = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{sinal}{s}%"


def _fmt_data_extenso(d: dt.date) -> str:
    return f"{d.day:02d} de {MESES_PT[d.month]} de {d.year}"


def _fmt_data_curta(d: dt.date) -> str:
    return d.strftime("%d/%m/%Y")


def _uri_arquivo(caminho: Path) -> str:
    dados = caminho.read_bytes()
    b64 = base64.b64encode(dados).decode("ascii")
    ext = caminho.suffix.lstrip(".")
    tipo = "png" if ext == "png" else ext
    return f"data:image/{tipo};base64,{b64}"


def _leitura_rapida(j: JanelaResultado) -> str:
    dif = j.retorno_dolar - j.retorno_cdi
    if j.retorno_dolar > j.retorno_cdi:
        vencedor = "o dólar superou o CDI"
    else:
        vencedor = "o CDI superou o dólar"
    return (
        f"no período, {vencedor} em {_fmt_pct(abs(dif))} "
        f"(dólar {_fmt_pct(j.retorno_dolar)} vs. CDI {_fmt_pct(j.retorno_cdi)})."
    )


def gerar_documento(
    janelas: list[JanelaResultado],
    series_dolar_por_janela: dict[str, list],
    spread_aa: float,
    caminho_saida: Path | None = None,
    amostra: bool = False,
) -> Path:
    """Gera os gráficos e renderiza o PDF final. Retorna o caminho do arquivo gerado."""
    PASTA_SAIDA.mkdir(exist_ok=True)
    PASTA_TMP.mkdir(parents=True, exist_ok=True)

    dados_janelas = []
    for j in janelas:
        caminho_grafico = PASTA_TMP / f"grafico_{j.anos}a.png"
        grafico_janela(j, caminho_grafico)

        ind = indicadores_dolar(series_dolar_por_janela[j.rotulo])

        dados_janelas.append({
            "rotulo": j.rotulo,
            "retorno_dolar": j.retorno_dolar,
            "retorno_dolar_fmt": _fmt_pct(j.retorno_dolar),
            "retorno_cdi": j.retorno_cdi,
            "retorno_cdi_fmt": _fmt_pct(j.retorno_cdi),
            "retorno_cdi_spread": j.retorno_cdi_spread,
            "retorno_cdi_spread_fmt": _fmt_pct(j.retorno_cdi_spread),
            "grafico_uri": _uri_arquivo(caminho_grafico),
            "vol_fmt": _fmt_pct(ind.get("volatilidade_anualizada", 0.0)) if ind else "—",
            "alta_dia_fmt": _fmt_pct(ind.get("maior_alta_dia", 0.0)) if ind else "—",
            "queda_dia_fmt": _fmt_pct(ind.get("maior_queda_dia", 0.0)) if ind else "—",
            "drawdown_fmt": _fmt_pct(ind.get("maior_queda_do_topo", 0.0)) if ind else "—",
            "leitura": _leitura_rapida(j),
        })

    caminho_resumo = PASTA_TMP / "grafico_resumo.png"
    grafico_resumo_barras(janelas, caminho_resumo)

    data_ref = max(j.data_fim for j in janelas)
    agora = dt.datetime.now()

    contexto = {
        "fonte": estilo.FONTE,
        "navy": estilo.NAVY,
        "ciano": estilo.CIANO,
        "vermelho": estilo.VERMELHO,
        "cinza_claro": estilo.CINZA_CLARO,
        "cinza_borda": estilo.CINZA_BORDA,
        "cinza_texto": estilo.CINZA_TEXTO,
        "branco": estilo.BRANCO,
        "logo_branco_uri": _uri_arquivo(estilo.LOGO_BRANCO),
        "logo_navy_uri": _uri_arquivo(estilo.LOGO_NAVY),
        "mes_referencia": f"{MESES_PT[data_ref.month]}/{str(data_ref.year)[2:]}",
        "data_referencia_extenso": _fmt_data_extenso(data_ref),
        "data_referencia_curta": _fmt_data_curta(data_ref),
        "spread_fmt": f"{spread_aa * 100:.0f}%",
        "fonte_dolar_nome": FONTE_DOLAR_NOME,
        "fonte_cdi_nome": FONTE_CDI_NOME,
        "janelas": dados_janelas,
        "grafico_resumo_uri": _uri_arquivo(caminho_resumo),
        "gerado_em": agora.strftime("%d/%m/%Y às %H:%M"),
        "amostra": amostra,
    }

    template = Template((PASTA_BASE / "modelo.html").read_text(encoding="utf-8"))
    html_final = template.render(**contexto)

    if caminho_saida is None:
        prefixo = "AMOSTRA_Dolar_x_CDI" if amostra else "Dolar_x_CDI"
        caminho_saida = PASTA_SAIDA / f"{prefixo}_{data_ref.isoformat()}.pdf"

    HTML(string=html_final, base_url=str(PASTA_BASE)).write_pdf(caminho_saida)

    for arquivo in PASTA_TMP.glob("*.png"):
        arquivo.unlink()

    return caminho_saida
