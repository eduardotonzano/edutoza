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
from estilo import CORES_GRAFICO, NAVY, CIANO, CINZA_TEXTO, CINZA_BORDA

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


def grafico_janela(janela: JanelaResultado, caminho_saida: Path, mostrar_spread: bool = True) -> None:
    """Um gráfico de linha: rentabilidade acumulada do Dólar x CDI (x CDI+spread) na janela."""
    fig, ax = plt.subplots(figsize=(5.6, 3.25), dpi=200)

    xs_d = [d for d, _ in janela.serie_dolar]
    ys_d = [v for _, v in janela.serie_dolar]
    xs_c = [d for d, _ in janela.serie_cdi]
    ys_c = [v for _, v in janela.serie_cdi]

    ax.plot(xs_d, ys_d, color=CORES_GRAFICO["dolar"], linewidth=1.8, label="Dólar (USD/BRL)", zorder=3)
    ax.plot(xs_c, ys_c, color=CORES_GRAFICO["cdi"], linewidth=1.8, label="CDI", zorder=3)

    if mostrar_spread and janela.serie_cdi_spread:
        xs_s = [d for d, _ in janela.serie_cdi_spread]
        ys_s = [v for _, v in janela.serie_cdi_spread]
        ax.plot(xs_s, ys_s, color=CORES_GRAFICO["cdi_spread"], linewidth=1.3,
                 linestyle="--", label="CDI + 4% a.a.", zorder=2)

    ax.axhline(0, color=CINZA_BORDA, linewidth=1, zorder=1)

    # rótulo do valor final de cada linha
    if ys_d:
        ax.annotate(_fmt_pct_label(ys_d[-1]), (xs_d[-1], ys_d[-1]),
                     textcoords="offset points", xytext=(4, 2), fontsize=8,
                     color=CORES_GRAFICO["dolar"], fontweight="bold", ha="left")
    if ys_c:
        ax.annotate(_fmt_pct_label(ys_c[-1]), (xs_c[-1], ys_c[-1]),
                     textcoords="offset points", xytext=(4, -10), fontsize=8,
                     color=CORES_GRAFICO["cdi"], fontweight="bold", ha="left")

    ax.set_title(janela.rotulo, fontsize=12, fontweight="bold", color=NAVY, loc="left", pad=10)
    ax.yaxis.set_major_formatter(FuncFormatter(_fmt_pct))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=5))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%y"))
    ax.tick_params(labelsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.margins(x=0.08)
    ax.legend(loc="upper center", fontsize=7.5, frameon=False, ncol=3,
              bbox_to_anchor=(0.5, -0.16))

    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(caminho_saida, transparent=True)
    plt.close(fig)


def grafico_resumo_barras(janelas: list[JanelaResultado], caminho_saida: Path) -> None:
    """Gráfico de barras horizontais comparando o retorno acumulado por janela."""
    fig, ax = plt.subplots(figsize=(11.6, 2.6), dpi=200)

    rotulos = [j.rotulo for j in janelas]
    dolar = [j.retorno_dolar for j in janelas]
    cdi = [j.retorno_cdi for j in janelas]

    y = range(len(janelas))
    altura = 0.32

    barras_d = ax.barh([i + altura / 2 for i in y], dolar, height=altura,
                        color=CORES_GRAFICO["dolar"], label="Dólar (USD/BRL)")
    barras_c = ax.barh([i - altura / 2 for i in y], cdi, height=altura,
                        color=CORES_GRAFICO["cdi"], label="CDI")

    for barras in (barras_d, barras_c):
        for b in barras:
            largura = b.get_width()
            cor = CINZA_TEXTO
            ax.annotate(_fmt_pct_label(largura),
                        (largura, b.get_y() + b.get_height() / 2),
                        textcoords="offset points",
                        xytext=(6 if largura >= 0 else -6, 0),
                        va="center", ha="left" if largura >= 0 else "right",
                        fontsize=8.5, color=cor, fontweight="bold")

    ax.set_yticks(list(y))
    ax.set_yticklabels(rotulos, fontsize=9.5)
    ax.axvline(0, color=NAVY, linewidth=1)
    ax.xaxis.set_major_formatter(FuncFormatter(_fmt_pct))
    ax.tick_params(axis="x", labelsize=8)
    ax.tick_params(axis="y", pad=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    # Espaço extra nas duas pontas: sem isso, o rótulo de valor de uma barra
    # negativa curta (ex.: dólar em -8%, numa janela onde o eixo vai até 600%
    # por causa do CDI) fica colado no rótulo da categoria à esquerda.
    ax.margins(x=0.22)
    ax.invert_yaxis()
    ax.legend(loc="upper center", fontsize=8.5, frameon=False, ncol=2, bbox_to_anchor=(0.5, 1.28))

    fig.tight_layout()
    fig.savefig(caminho_saida, transparent=True)
    plt.close(fig)
