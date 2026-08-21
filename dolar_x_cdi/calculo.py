"""Cálculo das rentabilidades acumuladas: Dólar x CDI x CDI + spread.

Metodologia:
- Dólar (USD/BRL): retorno simples entre a cotação PTAX-venda no início e
  no fim da janela (P_fim / P_ini - 1).
- CDI: série 12 do BCB ("Taxa de juros - CDI"), genuinamente diária (~1
  ponto por dia útil, em % ao dia — confirmado por diagnóstico, ver
  `diagnostico_cdi_diario.py`). A composição é direta, um fator por ponto:
  fator_dia = 1 + cdi_%dia/100, acumulado = produtório na janela — mesma
  lógica do dólar, só que dia a dia em vez de nível de preço.
- CDI + spread (ex.: CDI + 4% a.a.): mesmo fator diário do CDI multiplicado
  por um fator extra (1 + spread)^(1/252) — combina os dois juros ao dia.
- Dólar + spread (ex.: Dólar + 3,5% a.a.): mesma ideia, mas aplicada sobre a
  variação simples do dólar em vez de um fator acumulado ponto a ponto —
  fator extra (1 + spread)^(1/252) composto a cada pregão.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from fontes import PontoSerie


@dataclass
class JanelaResultado:
    rotulo: str
    anos: int
    data_inicio: dt.date
    data_fim: dt.date
    retorno_dolar: float
    retorno_dolar_spread: float
    retorno_cdi: float
    retorno_cdi_spread: float
    serie_dolar: list[tuple[dt.date, float]]   # retorno acumulado (%) dia a dia
    serie_dolar_spread: list[tuple[dt.date, float]]
    serie_cdi: list[tuple[dt.date, float]]
    serie_cdi_spread: list[tuple[dt.date, float]]


def _corta_janela(pontos: list[PontoSerie], inicio: dt.date, fim: dt.date) -> list[PontoSerie]:
    return [p for p in pontos if inicio <= p.data <= fim]


def _serie_acumulada_dolar(pontos: list[PontoSerie]) -> list[tuple[dt.date, float]]:
    if not pontos:
        return []
    base = pontos[0].valor
    return [(p.data, (p.valor / base - 1) * 100) for p in pontos]


DIAS_UTEIS_ANO = 252


def _serie_acumulada_dolar_spread(pontos: list[PontoSerie], spread_aa: float = 0.0) -> list[tuple[dt.date, float]]:
    """Dólar + spread: a mesma variação simples do dólar, com um adicional anual
    composto a cada pregão (ver nota de metodologia no topo do arquivo)."""
    if not pontos:
        return []
    base = pontos[0].valor
    fator_spread_dia = (1 + spread_aa) ** (1 / DIAS_UTEIS_ANO) if spread_aa else 1.0
    return [
        (p.data, ((p.valor / base) * (fator_spread_dia ** i) - 1) * 100)
        for i, p in enumerate(pontos)
    ]


def _serie_acumulada_cdi(pontos: list[PontoSerie], spread_aa: float = 0.0) -> list[tuple[dt.date, float]]:
    """Acumula o CDI dia a dia via fator composto (ver nota de metodologia
    no topo do arquivo).

    `spread_aa` é um adicional anual (ex.: 0.04 para CDI + 4% a.a.),
    aplicado como fator extra composto ao dia junto ao fator do CDI.
    """
    if not pontos:
        return []
    fator_spread_dia = (1 + spread_aa) ** (1 / DIAS_UTEIS_ANO) if spread_aa else 1.0
    serie = []
    acumulado = 1.0
    for p in pontos:
        fator_dia = 1 + p.valor / 100
        acumulado *= fator_dia * fator_spread_dia
        serie.append((p.data, (acumulado - 1) * 100))
    return serie


def calcular_janela(
    rotulo: str,
    anos: int,
    dolar: list[PontoSerie],
    cdi: list[PontoSerie],
    data_fim: dt.date,
    spread_aa: float = 0.04,
    spread_dolar_aa: float = 0.035,
) -> JanelaResultado | None:
    """Calcula a rentabilidade acumulada de uma janela (ex.: últimos 5 anos).

    Retorna None se não houver dado suficiente (ex.: 20 anos atrás e a série
    ainda não cobre o período).
    """
    try:
        data_alvo_inicio = dt.date(data_fim.year - anos, data_fim.month, data_fim.day)
    except ValueError:  # 29/fev em ano não bissexto
        data_alvo_inicio = dt.date(data_fim.year - anos, data_fim.month, data_fim.day - 1)

    c_janela = _corta_janela(cdi, data_alvo_inicio, data_fim)
    if len(c_janela) < 2:
        return None

    # Dólar e CDI são as duas séries diárias do BCB, mas nem sempre têm
    # exatamente o mesmo primeiro dia disponível na janela (ex.: histórico
    # começando em datas ligeiramente diferentes). Ancora o início do dólar
    # na mesma data do primeiro ponto do CDI já cortado, pra as duas séries
    # começarem juntas — sem isso, uma linha podia "nascer" antes da outra.
    d_janela = _corta_janela(dolar, c_janela[0].data, data_fim)
    if len(d_janela) < 2:
        return None

    serie_dolar = _serie_acumulada_dolar(d_janela)
    serie_dolar_spread = _serie_acumulada_dolar_spread(d_janela, spread_aa=spread_dolar_aa)
    serie_cdi = _serie_acumulada_cdi(c_janela, spread_aa=0.0)
    serie_cdi_spread = _serie_acumulada_cdi(c_janela, spread_aa=spread_aa)

    return JanelaResultado(
        rotulo=rotulo,
        anos=anos,
        data_inicio=d_janela[0].data,
        data_fim=d_janela[-1].data,
        retorno_dolar=serie_dolar[-1][1],
        retorno_dolar_spread=serie_dolar_spread[-1][1],
        retorno_cdi=serie_cdi[-1][1],
        retorno_cdi_spread=serie_cdi_spread[-1][1],
        serie_dolar=serie_dolar,
        serie_dolar_spread=serie_dolar_spread,
        serie_cdi=serie_cdi,
        serie_cdi_spread=serie_cdi_spread,
    )
