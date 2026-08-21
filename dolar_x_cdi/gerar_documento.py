#!/usr/bin/env python3
"""Ponto de entrada: gera o documento PDF "Dólar x CDI" atualizado.

Uso:
    python gerar_documento.py                 # busca dados reais no BCB
    python gerar_documento.py --amostra        # usa dados de amostra (sem internet),
                                                # gera um PDF marcado como demonstração
    python gerar_documento.py --spread 0.05    # muda o spread do "CDI + X%" (padrão 4%)
    python gerar_documento.py --spread-dolar 0.03  # muda o spread do "Dólar + X%" (padrão 3,5%)
    python gerar_documento.py --pb             # gráficos em tons de cinza (impressão em P&B)

O documento sai em `output/Dolar_x_CDI_<data>.pdf` (ou `AMOSTRA_...` no modo --amostra).

As funções `gerar_a_partir_do_bcb` e `gerar_a_partir_de_amostra` também podem ser
chamadas diretamente por outro script Python (ver `verificar_pedidos.py`, que gera o
documento sob demanda a partir de pedidos por e-mail).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from calculo import calcular_janela
from documento import gerar_documento
from fontes import (
    ErroFonteDados,
    PontoSerie,
    SERIE_DOLAR,
    SERIE_CDI,
    carregar_serie,
)

PASTA_AMOSTRA = Path(__file__).parent / "amostra"
JANELAS_ANOS = [1, 5, 10, 20]


def _carregar_csv_amostra(nome: str) -> list[PontoSerie]:
    caminho = PASTA_AMOSTRA / nome
    pontos = []
    with caminho.open(newline="", encoding="utf-8") as f:
        for linha in csv.DictReader(f):
            pontos.append(PontoSerie(data=dt.date.fromisoformat(linha["data"]), valor=float(linha["valor"])))
    return pontos


def _fim_do_mes(d: dt.date) -> dt.date:
    """Último dia do mês de `d`."""
    if d.month == 12:
        return dt.date(d.year, 12, 31)
    return dt.date(d.year, d.month + 1, 1) - dt.timedelta(days=1)


def _gerar(dolar: list[PontoSerie], cdi: list[PontoSerie], spread_aa: float,
           amostra: bool, caminho_saida: Path | None,
           data_fim_desejada: dt.date | None = None,
           spread_dolar_aa: float = 0.035,
           preto_branco: bool = False) -> Path:
    # O CDI (mensal) tem seu último ponto datado no dia 1º do mês que ele
    # representa (ex.: 01/07 = todo o mês de julho, já fechado) — não no
    # último dia. Usar essa data crua aqui subestimaria em ~1 mês até onde
    # os dados realmente vão, e cortaria o dólar (diário) bem antes do que
    # precisava, mesmo já tendo dado mais recente disponível.
    data_fim = min(dolar[-1].data, _fim_do_mes(cdi[-1].data))
    if data_fim_desejada is not None:
        # Nunca passa do último dado real disponível — se a pessoa escolher uma
        # data futura (ou um dia sem publicação ainda), cai pro dado mais recente.
        data_fim = min(data_fim, data_fim_desejada)

    janelas = []
    for anos in JANELAS_ANOS:
        rotulo = f"{anos} ano" + ("" if anos == 1 else "s")
        resultado = calcular_janela(rotulo, anos, dolar, cdi, data_fim,
                                     spread_aa=spread_aa, spread_dolar_aa=spread_dolar_aa)
        if resultado is None:
            print(f"[aviso] dados insuficientes para a janela de {anos} anos — pulando.")
            continue
        janelas.append(resultado)

    if not janelas:
        raise RuntimeError("nenhuma janela pôde ser calculada — dados insuficientes.")

    return gerar_documento(janelas, spread_aa, spread_dolar_aa,
                           caminho_saida=caminho_saida, amostra=amostra, preto_branco=preto_branco)


def _validar_data_fim(bruta: str | None) -> dt.date | None:
    """Converte a string "AAAA-MM-DD" (formato do <input type=date>) numa data.
    Levanta ValueError com mensagem amigável se o formato for inválido."""
    if not bruta:
        return None
    try:
        return dt.date.fromisoformat(bruta.strip())
    except ValueError:
        raise ValueError(f"data final inválida: {bruta!r} (esperado AAAA-MM-DD)") from None


def _diagnostico_cdi(cdi: list[PontoSerie]) -> None:
    """Mostra amostras do CDI cru ao longo do tempo, pra ver se a escala dos
    valores muda entre trechos antigos e recentes da série (o que já causou
    número final errado numa versão anterior, mesmo com dado real do BCB)."""
    if not cdi:
        print("[diagnóstico CDI] série vazia.")
        return
    hoje = cdi[-1].data
    marcos = [("mais antigo", cdi[0])]
    for anos_atras in (15, 10, 5, 1):
        alvo = hoje.replace(year=hoje.year - anos_atras) if hoje.month != 2 or hoje.day != 29 else hoje.replace(year=hoje.year - anos_atras, day=28)
        candidato = next((p for p in cdi if p.data >= alvo), None)
        if candidato:
            marcos.append((f"~{anos_atras} anos atrás", candidato))
    marcos.append(("mais recente", cdi[-1]))
    print(f"[diagnóstico CDI] {len(cdi)} pontos, de {cdi[0].data} a {cdi[-1].data}")
    for rotulo, p in marcos:
        print(f"  {rotulo}: {p.data} = {p.valor}")


def gerar_a_partir_do_bcb(spread_aa: float = 0.04, caminho_saida: Path | None = None,
                          data_fim_desejada: dt.date | None = None,
                          spread_dolar_aa: float = 0.035,
                          preto_branco: bool = False) -> Path:
    """Busca dólar e CDI oficiais no Banco Central e gera o PDF. Levanta ErroFonteDados
    se o BCB estiver inacessível (sem internet, host fora do ar etc.).

    `data_fim_desejada`, se informada, faz as janelas (1/5/10/20 anos) terminarem
    nessa data em vez de na mais recente disponível (ex.: pedido pelo formulário
    web, onde a pessoa escolhe a data final da análise)."""
    referencia = data_fim_desejada or dt.date.today()
    inicio_busca = dt.date(referencia.year - 21, referencia.month, 1)
    dolar = carregar_serie(SERIE_DOLAR, inicio_busca, data_final=data_fim_desejada)
    cdi = carregar_serie(SERIE_CDI, inicio_busca, data_final=data_fim_desejada)
    _diagnostico_cdi(cdi)
    return _gerar(dolar, cdi, spread_aa, amostra=False, caminho_saida=caminho_saida,
                  data_fim_desejada=data_fim_desejada, spread_dolar_aa=spread_dolar_aa,
                  preto_branco=preto_branco)


def gerar_a_partir_de_amostra(spread_aa: float = 0.04, caminho_saida: Path | None = None,
                              data_fim_desejada: dt.date | None = None,
                              spread_dolar_aa: float = 0.035,
                              preto_branco: bool = False) -> Path:
    """Gera o PDF com os dados de demonstração locais (sem consultar o BCB)."""
    dolar = _carregar_csv_amostra("dolar_amostra.csv")
    cdi = _carregar_csv_amostra("cdi_amostra.csv")
    return _gerar(dolar, cdi, spread_aa, amostra=True, caminho_saida=caminho_saida,
                  data_fim_desejada=data_fim_desejada, spread_dolar_aa=spread_dolar_aa,
                  preto_branco=preto_branco)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--amostra", action="store_true",
                         help="usa dados de demonstração locais em vez de consultar o BCB (para testar o layout sem internet)")
    parser.add_argument("--spread", type=float, default=0.04,
                         help="spread anual do 'CDI + X%%' de referência, ex.: 0.04 para CDI + 4%% (padrão: 0.04)")
    parser.add_argument("--spread-dolar", type=float, default=0.035, dest="spread_dolar",
                         help="spread anual do 'Dólar + X%%' de referência, ex.: 0.035 para Dólar + 3,5%% (padrão: 0.035)")
    parser.add_argument("--saida", type=Path, default=None, help="caminho do PDF de saída (padrão: output/Dolar_x_CDI_<data>.pdf)")
    parser.add_argument("--data-fim", type=str, default=None,
                         help="data final desejada para as janelas, formato AAAA-MM-DD "
                              "(padrão: dado mais recente disponível)")
    parser.add_argument("--pb", action="store_true", dest="preto_branco",
                         help="gera os gráficos em tons de cinza, otimizados pra impressão em preto e branco")
    args = parser.parse_args()

    try:
        data_fim_desejada = _validar_data_fim(args.data_fim)
    except ValueError as exc:
        print(f"ERRO: {exc}")
        return 1

    try:
        if args.amostra:
            print("[amostra] usando dados locais de demonstração (não são dados oficiais do BCB).")
            caminho = gerar_a_partir_de_amostra(args.spread, args.saida, data_fim_desejada,
                                                args.spread_dolar, args.preto_branco)
        else:
            print("Consultando o Banco Central do Brasil (SGS)...")
            caminho = gerar_a_partir_do_bcb(args.spread, args.saida, data_fim_desejada,
                                            args.spread_dolar, args.preto_branco)
    except ErroFonteDados as exc:
        print(f"\nERRO: não foi possível obter os dados oficiais do BCB.\n  {exc}\n")
        print("Isso normalmente significa que este ambiente não tem acesso à internet")
        print("(ex.: sandbox com rede restrita). Rode este script numa máquina com internet")
        print("livre, ou use o workflow do GitHub Actions (.github/workflows/dolar_x_cdi.yml),")
        print("ou rode com --amostra para gerar um PDF de demonstração do layout.")
        return 1
    except RuntimeError as exc:
        print(f"ERRO: {exc}")
        return 1

    print(f"\nDocumento gerado: {caminho}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
