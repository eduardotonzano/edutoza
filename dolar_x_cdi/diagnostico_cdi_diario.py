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

from fontes import PontoSerie, SERIE_DOLAR, carregar_serie, ErroFonteDados
from calculo import calcular_janela

# Constantes locais (não importadas de fontes.SERIE_CDI): esse script compara
# as duas séries entre si, então precisa dos dois códigos fixos mesmo depois
# que fontes.SERIE_CDI passou a apontar pra 12 (resultado deste diagnóstico).
SERIE_CDI_DIARIA_CANDIDATA = 12
SERIE_CDI_MENSAL_ANTIGA = 4391

# A versão da 4391 (mensal) hoje em produção corta a janela pros últimos
# anos*12 pontos (evita contar 13 meses por causa do corte inclusivo nas
# duas pontas) — reproduzido aqui à mão pra comparar com o que está no ar,
# já que calcular_janela() (calculo.py) não tem mais esse corte (só fazia
# sentido pra série mensal, e o projeto todo já assume CDI diário agora).
MESES_ANO_4391 = 12


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
          f"(≈1 = diário; ≈30 = mensal, como a {SERIE_CDI_MENSAL_ANTIGA})")
    print("Primeiros 5 pontos:")
    for p in diaria[:5]:
        print(f"  {p.data}  {p.valor}")
    print("Últimos 5 pontos:")
    for p in diaria[-5:]:
        print(f"  {p.data}  {p.valor}")

    print(f"\nConsultando SGS {SERIE_CDI_MENSAL_ANTIGA} (mensal, já em uso) de {inicio} a {hoje}...")
    try:
        mensal = carregar_serie(SERIE_CDI_MENSAL_ANTIGA, inicio, data_final=hoje, permitir_cache=False)
    except ErroFonteDados as exc:
        print(f"\nERRO ao consultar a série {SERIE_CDI_MENSAL_ANTIGA}: {exc}")
        return 1

    print(f"\n=== COMPARAÇÃO: {SERIE_CDI_DIARIA_CANDIDATA} composta por mês  x  {SERIE_CDI_MENSAL_ANTIGA} (mês já pronto) ===")
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
              f"|  série {SERIE_CDI_MENSAL_ANTIGA} = {oficial:7.4f}%  |  diferença = {delta:+.4f}p.p.")

    # O que a linha do CDI mostraria HOJE se usasse a série diária em vez de
    # esperar o mês fechar — só o mês corrente, composto até o último dia disponível.
    mes_corrente = (hoje.year, hoje.month)
    if mes_corrente in grupos_diarios:
        pontos_corrente = grupos_diarios[mes_corrente]
        print(f"\n=== Mês corrente ({mes_corrente[0]}-{mes_corrente[1]:02d}) via série diária ===")
        print(f"{len(pontos_corrente)} dias disponíveis, de {pontos_corrente[0].data} a {pontos_corrente[-1].data}")
        print(f"acumulado parcial do mês: {_compoe(pontos_corrente):.4f}%")
        if mes_corrente in mensal_por_mes:
            print(f"(a série 4391 já tem um ponto pra esse mês também: {mensal_por_mes[mes_corrente]:.4f}% "
                  f"— parece publicar um valor parcial do mês corrente, não só o mês fechado)")
        else:
            print("(a série 4391 ainda não tem nenhum ponto pra esse mês — só aparece quando fecha, ou quando publica um parcial)")

    # Reproduz a janela "1 ano" tal como o documento gera: termina em D-2 (hoje
    # menos 2 dias), ancorada na última cotação do dólar disponível — igual
    # a `_gerar()` em gerar_documento.py. Existe pra comparar, com dado real
    # do BCB, o valor que a janela de 1 ano dá com cada fonte de CDI (a 4391
    # mensal, já em produção, e a 12 diária, candidata a substituí-la) — foi
    # assim que se confirmou que a 4391 vinha subestimando o CDI de 1 ano
    # (faltava o(s) mês(es) mais recente(s), ainda não fechado(s) na 4391,
    # já que D-2 passou a ser diário e não mais preso ao fechamento do CDI).
    print(f"\nConsultando SGS {SERIE_DOLAR} (dólar) de {inicio} a {hoje}...")
    try:
        dolar = carregar_serie(SERIE_DOLAR, inicio, data_final=hoje, permitir_cache=False)
    except ErroFonteDados as exc:
        print(f"\nERRO ao consultar a série {SERIE_DOLAR}: {exc}")
        return 1

    data_fim_d2 = min(dolar[-1].data, hoje - dt.timedelta(days=2))
    print(f"\n=== Janela 'em uso' (1 ano), terminando em D-2 = {data_fim_d2} ===")

    janela_diaria = calcular_janela("1 ano", 1, dolar, diaria, data_fim_d2)
    if janela_diaria and janela_diaria.serie_cdi:
        print(f"CDI (série {SERIE_CDI_DIARIA_CANDIDATA}, diária) acumulado 1 ano: "
              f"{janela_diaria.serie_cdi[-1][1]:.2f}%  "
              f"(último ponto usado: {janela_diaria.serie_cdi[-1][0]})")
    else:
        print(f"CDI (série {SERIE_CDI_DIARIA_CANDIDATA}, diária): não deu pra calcular a janela (dados insuficientes).")

    # Reproduz à mão a lógica que está em produção agora (calculo.py antes
    # desta rodada): corta os pontos da 4391 dentro da janela de 1 ano e
    # mantém só os últimos 12 (anos*MESES_ANO), pra não contar 13 meses por
    # causa do corte inclusivo nas duas pontas.
    try:
        data_alvo_inicio = dt.date(data_fim_d2.year - 1, data_fim_d2.month, data_fim_d2.day)
    except ValueError:
        data_alvo_inicio = dt.date(data_fim_d2.year - 1, data_fim_d2.month, data_fim_d2.day - 1)
    pontos_mensal_janela = [p for p in mensal if data_alvo_inicio <= p.data <= data_fim_d2]
    if len(pontos_mensal_janela) > MESES_ANO_4391:
        pontos_mensal_janela = pontos_mensal_janela[-MESES_ANO_4391:]

    if len(pontos_mensal_janela) >= 2:
        ultimo_ponto_mensal = pontos_mensal_janela[-1].data
        atraso_dias = (data_fim_d2 - ultimo_ponto_mensal).days
        print(f"CDI (série {SERIE_CDI_MENSAL_ANTIGA}, mensal, lógica hoje em produção) acumulado 1 ano: "
              f"{_compoe(pontos_mensal_janela):.2f}%  "
              f"({len(pontos_mensal_janela)} meses, último ponto usado: {ultimo_ponto_mensal}, "
              f"{atraso_dias} dias antes de D-2)")
        if atraso_dias > 20:
            print(f"  -> a série 4391 só publica o mês quando ele fecha; com {atraso_dias} dias de atraso,")
            print(f"     falta compor ~1 mês inteiro de CDI que a série diária (12) já tem — é isso que")
            print(f"     faz a janela de 1 ano sair menor que o valor real.")
    else:
        print(f"CDI (série {SERIE_CDI_MENSAL_ANTIGA}, mensal): não deu pra calcular a janela (dados insuficientes).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
