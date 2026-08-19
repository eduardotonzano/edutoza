#!/usr/bin/env python3
"""Ponto de entrada: gera o documento PDF "Dólar x CDI" atualizado.

Uso:
    python gerar_documento.py                 # busca dados reais no BCB
    python gerar_documento.py --amostra        # usa dados de amostra (sem internet),
                                                # gera um PDF marcado como demonstração
    python gerar_documento.py --spread 0.05    # muda o spread do "CDI + X%" (padrão 4%)

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


def _gerar(dolar: list[PontoSerie], cdi: list[PontoSerie], spread_aa: float,
           amostra: bool, caminho_saida: Path | None) -> Path:
    data_fim = min(dolar[-1].data, cdi[-1].data)

    janelas = []
    series_dolar_por_janela = {}
    for anos in JANELAS_ANOS:
        rotulo = f"{anos} ano" + ("" if anos == 1 else "s")
        resultado = calcular_janela(rotulo, anos, dolar, cdi, data_fim, spread_aa=spread_aa)
        if resultado is None:
            print(f"[aviso] dados insuficientes para a janela de {anos} anos — pulando.")
            continue
        janelas.append(resultado)
        try:
            data_alvo = dt.date(data_fim.year - anos, data_fim.month, data_fim.day)
        except ValueError:
            data_alvo = dt.date(data_fim.year - anos, data_fim.month, data_fim.day - 1)
        series_dolar_por_janela[rotulo] = [p for p in dolar if data_alvo <= p.data <= data_fim]

    if not janelas:
        raise RuntimeError("nenhuma janela pôde ser calculada — dados insuficientes.")

    return gerar_documento(janelas, series_dolar_por_janela, spread_aa,
                            caminho_saida=caminho_saida, amostra=amostra)


def gerar_a_partir_do_bcb(spread_aa: float = 0.04, caminho_saida: Path | None = None) -> Path:
    """Busca dólar e CDI oficiais no Banco Central e gera o PDF. Levanta ErroFonteDados
    se o BCB estiver inacessível (sem internet, host fora do ar etc.)."""
    hoje = dt.date.today()
    inicio_busca = dt.date(hoje.year - 21, hoje.month, 1)
    dolar = carregar_serie(SERIE_DOLAR, inicio_busca)
    cdi = carregar_serie(SERIE_CDI, inicio_busca)
    return _gerar(dolar, cdi, spread_aa, amostra=False, caminho_saida=caminho_saida)


def gerar_a_partir_de_amostra(spread_aa: float = 0.04, caminho_saida: Path | None = None) -> Path:
    """Gera o PDF com os dados de demonstração locais (sem consultar o BCB)."""
    dolar = _carregar_csv_amostra("dolar_amostra.csv")
    cdi = _carregar_csv_amostra("cdi_amostra.csv")
    return _gerar(dolar, cdi, spread_aa, amostra=True, caminho_saida=caminho_saida)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--amostra", action="store_true",
                         help="usa dados de demonstração locais em vez de consultar o BCB (para testar o layout sem internet)")
    parser.add_argument("--spread", type=float, default=0.04,
                         help="spread anual do 'CDI + X%%' de referência, ex.: 0.04 para CDI + 4%% (padrão: 0.04)")
    parser.add_argument("--saida", type=Path, default=None, help="caminho do PDF de saída (padrão: output/Dolar_x_CDI_<data>.pdf)")
    args = parser.parse_args()

    try:
        if args.amostra:
            print("[amostra] usando dados locais de demonstração (não são dados oficiais do BCB).")
            caminho = gerar_a_partir_de_amostra(args.spread, args.saida)
        else:
            print("Consultando o Banco Central do Brasil (SGS)...")
            caminho = gerar_a_partir_do_bcb(args.spread, args.saida)
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
