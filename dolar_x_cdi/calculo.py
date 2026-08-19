"""Cálculo das rentabilidades acumuladas: Dólar x CDI x CDI + spread.

Metodologia:
- Dólar (USD/BRL): retorno simples entre a cotação PTAX-venda no início e
  no fim da janela (P_fim / P_ini - 1).
- CDI: capitalização diária composta. A série do BCB pode vir anualizada
  (% a.a., ex.: 13,75) ou já em taxa diária (% a.d., ex.: 0,0511) —
  detectamos qual é pela ordem de grandeza dos valores (ver
  `_cdi_e_anualizado`) em vez de presumir, porque isso já mudou de um dia
  para o outro entre séries do SGS. Anualizada: fator_dia =
  (1 + cdi_%a.a./100)^(1/252). Diária: fator_dia = 1 + cdi_%a.d./100.
  Em ambos os casos, acumulado = produtório dos fatores diários na janela.
- CDI + spread (ex.: CDI + 4% a.a.): mesmo fator diário do CDI multiplicado
  por um fator extra (1 + spread)^(1/252) — combina os dois juros ao dia,
  igual à lógica já usada na planilha original.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from fontes import PontoSerie

DIAS_UTEIS_ANO = 252


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


def _cdi_e_anualizado(pontos: list[PontoSerie]) -> bool:
    """Detecta se a série do CDI veio anualizada (% a.a., tipicamente 2–20) ou
    já em taxa diária (% a.d., tipicamente < 1) — em vez de presumir a
    convenção de antemão. No Brasil, mesmo no piso histórico da Selic (2%
    a.a., em 2020), o CDI anualizado nunca chega perto de 1; e a taxa diária
    nunca chega perto de 1 mesmo nos picos de juros. A mediana separa bem
    os dois casos.
    """
    valores = sorted(p.valor for p in pontos)
    mediana = valores[len(valores) // 2]
    return mediana >= 1


def _serie_acumulada_cdi(pontos: list[PontoSerie], spread_aa: float = 0.0) -> list[tuple[dt.date, float]]:
    """Acumula o CDI dia a dia via fator composto.

    `spread_aa` é um adicional anual (ex.: 0.04 para CDI + 4% a.a.),
    aplicado como fator extra composto ao dia junto ao fator do CDI.
    """
    if not pontos:
        return []
    anualizado = _cdi_e_anualizado(pontos)
    fator_spread_dia = (1 + spread_aa) ** (1 / DIAS_UTEIS_ANO) if spread_aa else 1.0
    serie = []
    acumulado = 1.0
    for p in pontos:
        if anualizado:
            fator_dia = (1 + p.valor / 100) ** (1 / DIAS_UTEIS_ANO)
        else:
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
) -> JanelaResultado | None:
    """Calcula a rentabilidade acumulada de uma janela (ex.: últimos 5 anos).

    Retorna None se não houver dado suficiente (ex.: 20 anos atrás e a série
    ainda não cobre o período).
    """
    try:
        data_alvo_inicio = dt.date(data_fim.year - anos, data_fim.month, data_fim.day)
    except ValueError:  # 29/fev em ano não bissexto
        data_alvo_inicio = dt.date(data_fim.year - anos, data_fim.month, data_fim.day - 1)

    d_janela = _corta_janela(dolar, data_alvo_inicio, data_fim)
    c_janela = _corta_janela(cdi, data_alvo_inicio, data_fim)
    if len(d_janela) < 2 or len(c_janela) < 2:
        return None

    valores_cdi = sorted(p.valor for p in c_janela)
    print(f"[diagnóstico CDI] janela {rotulo}: {len(c_janela)} pontos, "
          f"min={valores_cdi[0]:.4f} mediana={valores_cdi[len(valores_cdi)//2]:.4f} "
          f"max={valores_cdi[-1]:.4f} -> anualizado={_cdi_e_anualizado(c_janela)}")

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


def indicadores_dolar(pontos: list[PontoSerie]) -> dict:
    """Indicadores complementares sobre a série do dólar em uma janela."""
    if len(pontos) < 2:
        return {}
    retornos_diarios = []
    for anterior, atual in zip(pontos, pontos[1:]):
        retornos_diarios.append(atual.valor / anterior.valor - 1)

    media = sum(retornos_diarios) / len(retornos_diarios)
    variancia = sum((r - media) ** 2 for r in retornos_diarios) / max(1, len(retornos_diarios) - 1)
    vol_anualizada = (variancia ** 0.5) * (DIAS_UTEIS_ANO ** 0.5) * 100

    maior_alta_dia = max(retornos_diarios) * 100
    maior_queda_dia = min(retornos_diarios) * 100

    pico = pontos[0].valor
    maior_drawdown = 0.0
    for p in pontos:
        pico = max(pico, p.valor)
        dd = (p.valor / pico - 1) * 100
        maior_drawdown = min(maior_drawdown, dd)

    return {
        "volatilidade_anualizada": vol_anualizada,
        "maior_alta_dia": maior_alta_dia,
        "maior_queda_dia": maior_queda_dia,
        "maior_queda_do_topo": maior_drawdown,
    }
