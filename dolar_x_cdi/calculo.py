"""Cálculo das rentabilidades acumuladas: Dólar x CDI x CDI + spread.

Metodologia:
- Dólar (USD/BRL): retorno simples entre a cotação PTAX-venda no início e
  no fim da janela (P_fim / P_ini - 1).
- CDI: apesar do nome "CDI anualizada base 252", a série 4391 do BCB devolve
  na prática ~1 ponto por MÊS (confirmado batendo os valores com o histórico
  real da Selic e pela contagem de pontos por janela, que bate exatamente
  com anos×12+1) — cada ponto é a variação do CDI naquele mês (ex.: 1,16 =
  +1,16% no mês). A composição é direta, um fator por ponto:
  fator_mes = 1 + cdi_%mes/100, acumulado = produtório na janela.
- CDI + spread (ex.: CDI + 4% a.a.): mesmo fator mensal do CDI multiplicado
  por um fator extra (1 + spread)^(1/12) — combina os dois juros ao mês.
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
    retorno_cdi: float
    retorno_cdi_spread: float
    serie_dolar: list[tuple[dt.date, float]]   # retorno acumulado (%) dia a dia
    serie_cdi: list[tuple[dt.date, float]]
    serie_cdi_spread: list[tuple[dt.date, float]]


def _fechamento_por_data(pontos: list[PontoSerie]) -> dict[dt.date, float]:
    return {p.data: p.valor for p in pontos}


def _corta_janela(pontos: list[PontoSerie], inicio: dt.date, fim: dt.date) -> list[PontoSerie]:
    return [p for p in pontos if inicio <= p.data <= fim]


def _acha_data_inicio_disponivel(pontos: list[PontoSerie], alvo: dt.date) -> dt.date | None:
    """Primeiro pregão com data >= alvo (a série só tem dias úteis)."""
    candidatos = [p.data for p in pontos if p.data >= alvo]
    return min(candidatos) if candidatos else None


def _serie_acumulada_dolar(pontos: list[PontoSerie]) -> list[tuple[dt.date, float]]:
    if not pontos:
        return []
    base = pontos[0].valor
    return [(p.data, (p.valor / base - 1) * 100) for p in pontos]


MESES_ANO = 12


def _serie_acumulada_cdi(pontos: list[PontoSerie], spread_aa: float = 0.0) -> list[tuple[dt.date, float]]:
    """Acumula o CDI mês a mês via fator composto (ver nota de metodologia
    no topo do arquivo sobre por que é mensal, não diário).

    `spread_aa` é um adicional anual (ex.: 0.04 para CDI + 4% a.a.),
    aplicado como fator extra composto ao mês junto ao fator do CDI.
    """
    if not pontos:
        return []
    fator_spread_mes = (1 + spread_aa) ** (1 / MESES_ANO) if spread_aa else 1.0
    serie = []
    acumulado = 1.0
    for p in pontos:
        fator_mes = 1 + p.valor / 100
        acumulado *= fator_mes * fator_spread_mes
        serie.append((p.data, (acumulado - 1) * 100))
    return serie


def calcular_janela(
    rotulo: str,
    anos: int,
    dolar: list[PontoSerie],
    cdi: list[PontoSerie],
    data_fim: dt.date,
    spread_aa: float = 0.04,
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
    # O corte acima é inclusivo nas duas pontas; com dado mensal isso pega um mês
    # a mais do que o pedido (ex.: 13 meses pra janela de "1 ano"), porque o ponto
    # na borda de início já é um retorno mensal cheio, não um nível de preço como
    # o dólar. Mantém só os anos*12 meses mais recentes.
    max_pontos_cdi = anos * MESES_ANO
    if len(c_janela) > max_pontos_cdi:
        c_janela = c_janela[-max_pontos_cdi:]
    if len(c_janela) < 2:
        return None

    # O dólar (diário) começa exatamente em data_alvo_inicio, mas o CDI (mensal,
    # depois do corte acima) só tem seu primeiro ponto um pouco depois — sem
    # alinhar os dois, a linha do dólar no gráfico "nasce" antes da linha do CDI.
    # Ancora o início do dólar na mesma data do primeiro ponto do CDI já cortado,
    # pra as duas séries começarem juntas (e cobrirem o mesmo período de verdade).
    d_janela = _corta_janela(dolar, c_janela[0].data, data_fim)
    if len(d_janela) < 2:
        return None

    serie_dolar = _serie_acumulada_dolar(d_janela)
    serie_cdi = _serie_acumulada_cdi(c_janela, spread_aa=0.0)
    serie_cdi_spread = _serie_acumulada_cdi(c_janela, spread_aa=spread_aa)

    return JanelaResultado(
        rotulo=rotulo,
        anos=anos,
        data_inicio=d_janela[0].data,
        data_fim=d_janela[-1].data,
        retorno_dolar=serie_dolar[-1][1],
        retorno_cdi=serie_cdi[-1][1],
        retorno_cdi_spread=serie_cdi_spread[-1][1],
        serie_dolar=serie_dolar,
        serie_cdi=serie_cdi,
        serie_cdi_spread=serie_cdi_spread,
    )
