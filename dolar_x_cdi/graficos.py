"""Geração dos gráficos (matplotlib) no estilo visual Multiplica."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter

from calculo import JanelaResultado
from estilo import CORES_GRAFICO, CORES_GRAFICO_PB, NAVY, CIANO, CINZA_TEXTO, CINZA_BORDA

plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["axes.edgecolor"] = CINZA_BORDA
plt.rcParams["text.color"] = NAVY
plt.rcParams["axes.labelcolor"] = CINZA_TEXTO
plt.rcParams["xtick.color"] = CINZA_TEXTO
plt.rcParams["ytick.color"] = CINZA_TEXTO


def _fmt_pct(v, _pos=None) -> str:
    return f"{v:.0f}%".replace("-", "−")


def _fmt_pct_label(v: float) -> str:
    s = f"{v:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")
    return s


def _fmt_spread(v: float) -> str:
    """0.04 -> '4%', 0.035 -> '3,5%' (sem casa decimal supérflua)."""
    s = f"{v * 100:.1f}".rstrip("0").rstrip(".")
    return s.replace(".", ",") + "%"


# Tamanho da figura e margens do eixo (fixos pros 4 gráficos, ver nota mais
# abaixo sobre por que não usar tight_layout) — usados também pra converter
# valor de dado em posição vertical em pontos, no espaçamento dos rótulos.
_FIG_W, _FIG_H = 7.6, 4.79
_AX_TOP, _AX_BOTTOM = 0.86, 0.30


def grafico_janela(
    janela: JanelaResultado,
    caminho_saida: Path,
    spread_cdi_aa: float = 0.04,
    spread_dolar_aa: float = 0.035,
    mostrar_spread: bool = True,
    preto_branco: bool = False,
) -> None:
    """Um gráfico de linha: rentabilidade acumulada do Dólar x CDI (x spreads) na janela.

    `preto_branco` troca a paleta navy/ciano por tons de cinza (ver CORES_GRAFICO_PB
    em estilo.py), pra uma versão do documento pensada pra impressão em P&B — a
    diferenciação entre as linhas já não depende de cor, só de tom e traço.
    """
    cores = CORES_GRAFICO_PB if preto_branco else CORES_GRAFICO
    cor_titulo = "#1A1A1A" if preto_branco else NAVY
    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), dpi=200)

    xs_d = [d for d, _ in janela.serie_dolar]
    ys_d = [v for _, v in janela.serie_dolar]
    xs_c = [d for d, _ in janela.serie_cdi]
    ys_c = [v for _, v in janela.serie_cdi]

    ax.plot(xs_d, ys_d, color=cores["dolar"], linewidth=2.4, label="Dólar (USD/BRL)", zorder=3)
    ax.plot(xs_c, ys_c, color=cores["cdi"], linewidth=2.4, label="CDI", zorder=3)

    if mostrar_spread and janela.serie_dolar_spread:
        xs_ds = [d for d, _ in janela.serie_dolar_spread]
        ys_ds = [v for _, v in janela.serie_dolar_spread]
        ax.plot(xs_ds, ys_ds, color=cores["dolar_spread"], linewidth=2.2,
                 linestyle=":", dash_capstyle="round",
                 label=f"Dólar + {_fmt_spread(spread_dolar_aa)} a.a.", zorder=2)

    if mostrar_spread and janela.serie_cdi_spread:
        xs_s = [d for d, _ in janela.serie_cdi_spread]
        ys_s = [v for _, v in janela.serie_cdi_spread]
        ax.plot(xs_s, ys_s, color=cores["cdi_spread"], linewidth=1.7,
                 linestyle="--", label=f"CDI + {_fmt_spread(spread_cdi_aa)} a.a.", zorder=2)

    ax.axhline(0, color=CINZA_BORDA, linewidth=1, zorder=1)

    ax.set_title(janela.rotulo, fontsize=17, fontweight="bold", color=cor_titulo, loc="left", pad=12)
    ax.yaxis.set_major_formatter(FuncFormatter(_fmt_pct))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=5))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%y"))
    ax.tick_params(labelsize=12)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.margins(x=0.12)
    ax.legend(loc="upper center", fontsize=10.5, frameon=False, ncol=2,
              bbox_to_anchor=(0.5, -0.15), columnspacing=1.4, handlelength=1.8)

    # Margens fixas (em vez de tight_layout, que recalcula sozinho por gráfico)
    # — cada janela tem rótulos do eixo Y de largura diferente (ex.: "20%" vs
    # "1.500%"), e o tight_layout ajusta a margem esquerda pra caber cada um,
    # o que fazia o título e o eixo começarem numa posição horizontal diferente
    # em cada gráfico. Com margem fixa, título e eixo alinham entre os 4.
    fig.subplots_adjust(left=0.145, right=0.83, top=_AX_TOP, bottom=_AX_BOTTOM)

    # Rótulo do valor final de cada linha. O CDI (mensal) e o dólar (diário)
    # não terminam exatamente na mesma data — o mês do CDI fecha no dia 1º,
    # o dólar no último pregão —, então usar o x de cada série deixava os
    # rótulos espalhados horizontalmente em vez de alinhados numa coluna;
    # ancora todos na data final da janela (a mais recente das duas).
    #
    # Cada rótulo fica colado no valor real da sua linha — só é empurrado
    # pra baixo (o mínimo necessário) quando colidiria com o rótulo de cima,
    # em vez de sempre espaçados por um passo fixo (que deixava os rótulos
    # "boiando" longe da linha quando os valores já estavam bem separados).
    x_rotulo = janela.data_fim
    candidatos = []
    if ys_d:
        candidatos.append((ys_d[-1], cores["dolar"]))
    if ys_c:
        candidatos.append((ys_c[-1], cores["cdi"]))
    if mostrar_spread and janela.serie_dolar_spread:
        candidatos.append((ys_ds[-1], cores["dolar_spread"]))
    if mostrar_spread and janela.serie_cdi_spread:
        candidatos.append((ys_s[-1], cores["cdi_spread"]))
    candidatos.sort(key=lambda c: -c[0])

    ymin, ymax = ax.get_ylim()
    faixa = ymax - ymin
    altura_eixo_pt = (_AX_TOP - _AX_BOTTOM) * _FIG_H * 72
    pt_por_unidade = altura_eixo_pt / faixa if faixa else 0
    gap_minimo_pt = 15

    y_anterior_pt = None
    for valor, cor in candidatos:
        y_pt = (valor - ymin) * pt_por_unidade
        if y_anterior_pt is not None:
            y_pt = min(y_pt, y_anterior_pt - gap_minimo_pt)
        y_anterior_pt = y_pt
        deslocamento = y_pt - (valor - ymin) * pt_por_unidade
        ax.annotate(_fmt_pct_label(valor), (x_rotulo, valor),
                     textcoords="offset points", xytext=(5, 3 + deslocamento), fontsize=11,
                     color=cor, fontweight="bold", ha="left")

    fig.savefig(caminho_saida, transparent=True)
    plt.close(fig)
