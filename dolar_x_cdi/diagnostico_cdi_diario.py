#!/usr/bin/env python3
"""Diagnóstico (só leitura, não gera PDF nem manda e-mail): verifica se a série
SGS 12 do BCB ("Taxa de juros - CDI", candidata a CDI diário de verdade) tem
o formato esperado — um ponto por dia útil, em % ao dia — e bate com a série
4391 (já em uso, mensal) quando os dias de um mês são compostos juntos.

Existe pra decidir com segurança se dá pra trocar (ou complementar) a 4391
pela 12 e assim deixar a linha do CDI tão atualizada quanto a do dólar
(hoje a 4391 só tem o último mês já fechado). Não mexe em nada da geração
do documento — só imprime o que a API realmente devolve.

Uso: python diagnostico_cdi_diario.py
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fontes import PontoSerie, SERIE_CDI, carregar_serie, ErroFonteDados

SERIE_CDI_DIARIA_CANDIDATA = 12


def _compoe(pontos: list[PontoSerie]) -> float:
    """Retorno acumulado (%) compondo um fator por ponto (1 + valor/100)."""
    acumulado = 1.0
    for p in pontos:
        acumulado *= 1 + p.valor / 100
    return (acumulado - 1) * 100


def _agrupa_por_mes(pontos: list[PontoSerie]) -> dict[tuple[int, int], list[PontoSerie]]:
    grupos: dict[tuple[int, int], list[PontoSerie]] = {}
    for p in pontos:
        chave = (p.data.year, p.data.month)
        grupos.setdefault(chave, []).append(p)
    return grupos


def main() -> int:
    hoje = dt.date.today()
    inicio = hoje - dt.timedelta(days=400)  # ~13 meses, dá pra comparar vários meses fechados

    print(f"Consultando SGS {SERIE_CDI_DIARIA_CANDIDATA} (candidata a CDI diário) de {inicio} a {hoje}...")
    try:
        diaria = carregar_serie(SERIE_CDI_DIARIA_CANDIDATA, inicio, data_final=hoje, permitir_cache=False)
    except ErroFonteDados as exc:
        print(f"\nERRO ao consultar a série {SERIE_CDI_DIARIA_CANDIDATA}: {exc}")
        return 1

    print(f"\n=== SÉRIE {SERIE_CDI_DIARIA_CANDIDATA} — formato bruto ===")
    print(f"{len(diaria)} pontos, de {diaria[0].data} a {diaria[-1].data}")
    dias_uteis_no_periodo = (diaria[-1].data - diaria[0].data).days
    print(f"média de {dias_uteis_no_periodo / max(1, len(diaria) - 1):.2f} dias corridos entre pontos "
          f"(≈1 = diário; ≈30 = mensal, como a {SERIE_CDI})")
    print("Primeiros 5 pontos:")
    for p in diaria[:5]:
        print(f"  {p.data}  {p.valor}")
    print("Últimos 5 pontos:")
    for p in diaria[-5:]:
        print(f"  {p.data}  {p.valor}")

    print(f"\nConsultando SGS {SERIE_CDI} (mensal, já em uso) de {inicio} a {hoje}...")
    try:
        mensal = carregar_serie(SERIE_CDI, inicio, data_final=hoje, permitir_cache=False)
    except ErroFonteDados as exc:
        print(f"\nERRO ao consultar a série {SERIE_CDI}: {exc}")
        return 1

    print(f"\n=== COMPARAÇÃO: {SERIE_CDI_DIARIA_CANDIDATA} composta por mês  x  {SERIE_CDI} (mês já pronto) ===")
    grupos_diarios = _agrupa_por_mes(diaria)
    mensal_por_mes = {(p.data.year, p.data.month): p.valor for p in mensal}

    meses = sorted(set(grupos_diarios) & set(mensal_por_mes))
    if not meses:
        print("Nenhum mês em comum pra comparar — janelas não se sobrepõem.")
    for ano, mes in meses:
        pontos_mes = grupos_diarios[(ano, mes)]
        composto = _compoe(pontos_mes)
        oficial = mensal_por_mes[(ano, mes)]
        delta = composto - oficial
        print(f"  {ano}-{mes:02d}: {len(pontos_mes):2d} dias compostos = {composto:7.4f}%  "
              f"|  série {SERIE_CDI} = {oficial:7.4f}%  |  diferença = {delta:+.4f}p.p.")

    # O que a linha do CDI mostraria HOJE se usasse a série diária em vez de
    # esperar o mês fechar — só o mês corrente, composto até o último dia disponível.
    mes_corrente = (hoje.year, hoje.month)
    if mes_corrente in grupos_diarios:
        pontos_corrente = grupos_diarios[mes_corrente]
        print(f"\n=== Mês corrente ({mes_corrente[0]}-{mes_corrente[1]:02d}) via série diária ===")
        print(f"{len(pontos_corrente)} dias disponíveis, de {pontos_corrente[0].data} a {pontos_corrente[-1].data}")
        print(f"acumulado parcial do mês: {_compoe(pontos_corrente):.4f}%")
        print("(a série 4391 não teria NENHUM ponto pra esse mês ainda — só aparece quando fecha)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
