"""Orquestra o pipeline completo: carteira -> coleta -> download -> validacao -> Excel.

Uso:
    python main.py --carteira Planilha_para_API.xlsx
    python main.py --carteira Planilha_para_API.xlsx --saida relatorio.xlsx

A planilha precisa ter uma aba CARTEIRA com colunas TICKER e NOME.
"""

import argparse
import pandas as pd

from empresas import EMPRESAS, carregar_tickers
from coleta import coletar_candidatos, baixar_corpos, validar_todos
from excel import gerar_excel


def main():
    ap = argparse.ArgumentParser(description="Monitor de noticias da carteira")
    ap.add_argument("--carteira", required=True, help="caminho do .xlsx com a aba CARTEIRA")
    ap.add_argument("--saida", default=None, help="nome do Excel de saida (opcional)")
    args = ap.parse_args()

    print("1/4 Lendo carteira...")
    df = pd.read_excel(args.carteira, sheet_name="CARTEIRA")
    empresas = carregar_tickers(df)
    print(f"    {len(empresas)} empresas carregadas")

    print("2/4 Coletando candidatos no Google News...")
    candidatos = coletar_candidatos(empresas)
    print(f"    {len(candidatos)} candidatos unicos")

    print("3/4 Baixando corpos em paralelo e validando relevancia...")
    corpos = baixar_corpos(candidatos)
    finais, sem_corpo = validar_todos(candidatos, corpos, empresas)

    from collections import Counter
    cont = Counter(n["nome"] for n in finais)
    print(f"    {len(finais)} noticias validadas | {len(cont)}/{len(empresas)} ativos cobertos")
    print(f"    ({sem_corpo} usaram resumo do RSS como fallback)")

    print("4/4 Gerando Excel...")
    arq, n_not, n_ativos = gerar_excel(finais, empresas, args.saida)
    print(f"    Pronto: {arq}")

    print("\n--- MATCHES (confira a qualidade) ---")
    for n in finais:
        prem = "*" if n["premium"] else " "
        print(f"{prem}[{n['ticker']:14}] {n['nome']:20} | rel {n['relevancia']} | {n['fonte'][:20]}")
        print(f"   {n['titulo'][:72]}")


if __name__ == "__main__":
    main()
