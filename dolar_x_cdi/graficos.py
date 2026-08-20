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
    fig, ax = plt.subplots(figsize=(5.8, 4.6), dpi=200)

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

    # Rótulo do valor final de cada linha. As três linhas terminam bem perto
    # umas das outras (mesma data final), então em vez de um deslocamento
    # vertical fixo por série — que gruda os textos quando a ordem das linhas
    # muda de gráfico pra gráfico —, ordena pelo valor final e empilha de
    # cima pra baixo, sempre na mesma ordem em que as linhas aparecem no eixo.
    candidatos = []
    if ys_d:
        candidatos.append((ys_d[-1], xs_d[-1], CORES_GRAFICO["dolar"]))
    if ys_c:
        candidatos.append((ys_c[-1], xs_c[-1], CORES_GRAFICO["cdi"]))
    if mostrar_spread and janela.serie_cdi_spread:
        candidatos.append((ys_s[-1], xs_s[-1], CORES_GRAFICO["cdi_spread"]))

    for posicao, (valor, x, cor) in enumerate(sorted(candidatos, key=lambda c: -c[0])):
        ax.annotate(_fmt_pct_label(valor), (x, valor),
                     textcoords="offset points", xytext=(4, 2 - posicao * 11), fontsize=8,
                     color=cor, fontweight="bold", ha="left")

    ax.set_title(janela.rotulo, fontsize=12, fontweight="bold", color=NAVY, loc="left", pad=10)
    ax.yaxis.set_major_formatter(FuncFormatter(_fmt_pct))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=5))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%y"))
    ax.tick_params(labelsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.margins(x=0.1)
    ax.legend(loc="upper center", fontsize=7.5, frameon=False, ncol=3,
              bbox_to_anchor=(0.5, -0.16))

    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(caminho_saida, transparent=True)
    plt.close(fig)
