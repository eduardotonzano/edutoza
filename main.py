"""Pipeline: carteira(340 ativos) -> emissores -> [GDELT + CVM + SEC + RI] -> Excel.

Uso:
    python main.py --carteira carteira_completa.csv --saida relatorio.xlsx

Le carteira_completa.csv (colunas ATIVO,TIPO,MOEDA,CATEGORIA), mapeia cada ativo ao seu
EMISSOR (mapeamento.py / emissores.py), monitora cada emissor em varias fontes gratuitas e
gera um Excel que lista TODOS os ativos com status (noticia encontrada / sem noticia hoje /
sem noticia aplicavel).
"""

import argparse, os
from collections import Counter

from emissores import EMISSORES
from mapeamento import mapear_carteira
from coleta import coletar_candidatos, baixar_corpos, validar_todos, norm
from rss_news import coletar_feeds_tier1, coletar_yahoo
from news_api import coletar_api
from fato_relevante import buscar_fatos_relevantes
from sec_edgar import buscar_fatos_sec
from ri_scraping import raspar_ris
from excel import gerar_excel
from resumo_ia import preencher_resumos, ATIVADO as IA_ATIVA


def _dedup(itens):
    """Remove duplicatas por link e por (emissor+titulo), preferindo maior relevancia
    (oficial CVM/SEC=10 > RI=8 > GDELT). Mantem a 1a ocorrencia de cada."""
    itens = sorted(itens, key=lambda x: -x.get("relevancia", 0))
    vistos_link, vistos_tit, out = set(), set(), []
    for it in itens:
        link = it.get("link", "")
        tit = norm(f"{it.get('nome','')} {it.get('titulo','')}")
        if link and link in vistos_link:
            continue
        if tit in vistos_tit:
            continue
        if link:
            vistos_link.add(link)
        vistos_tit.add(tit)
        out.append(it)
    return out


def main():
    ap = argparse.ArgumentParser(description="Monitor de noticias da carteira (toda a base)")
    ap.add_argument("--carteira", default="carteira_completa.csv",
                    help="CSV da base (colunas ATIVO,TIPO,MOEDA,CATEGORIA)")
    ap.add_argument("--saida", default=None, help="nome do Excel de saida (opcional)")
    args = ap.parse_args()

    print("1/6 Lendo a base e mapeando ativo -> emissor...")
    alvos = mapear_carteira(args.carteira)
    n_aplic = len([a for a in alvos if a["news_applicable"]])
    print(f"    {len(alvos)} ativos | {n_aplic} com emissor monitoravel")

    # Subconjuntos do registro (por NOME de exibicao, p/ casar com as outras fontes).
    gdelt_reg = {c["nome"]: c for c in EMISSORES.values() if c["news_applicable"] and c.get("busca")}
    cvm_em = [c for c in EMISSORES.values() if c["news_applicable"] and c.get("cvm_aliases")]
    us_em  = [c for c in EMISSORES.values() if c["news_applicable"] and (c.get("sec_cik") or c.get("sec_ticker"))]
    ri_em  = [c for c in EMISSORES.values() if c.get("ri_url")]

    print("2/6 Coletando imprensa (GDELT + RSS Tier 1 + API)...")
    candidatos = {}
    if os.environ.get("PULAR_GDELT"):
        print("    GDELT PULADO (PULAR_GDELT setado p/ teste)")
    else:
        candidatos.update(coletar_candidatos(gdelt_reg))      # imprensa global (GDELT)
    candidatos.update(coletar_feeds_tier1(gdelt_reg))         # feeds RSS Tier 1 (confiavel)
    candidatos.update(coletar_api(gdelt_reg))                 # API NewsData (opcional)
    print(f"    {len(candidatos)} candidatos unicos no pool de imprensa")

    print("3/6 Baixando corpos e validando relevancia...")
    corpos = baixar_corpos(candidatos)
    imprensa_finais, sem_corpo, fora_janela = validar_todos(candidatos, corpos, gdelt_reg)
    yahoo_finais = coletar_yahoo(list(gdelt_reg.values()))    # Yahoo por ticker (pre-atribuido)
    cobertos = len(Counter(n["nome"] for n in imprensa_finais + yahoo_finais))
    print(f"    {len(imprensa_finais)} validadas + {len(yahoo_finais)} Yahoo | "
          f"{cobertos} emissores cobertos ({sem_corpo} sem corpo, {fora_janela} fora da janela)")

    print(f"4/6 Fatos relevantes (CVM {len(cvm_em)} | SEC {len(us_em)} | RI {len(ri_em)})...")
    fatos_cvm = buscar_fatos_relevantes(cvm_em)
    print(f"    CVM: {len(fatos_cvm)} fatos relevantes/comunicados")
    fatos_sec = buscar_fatos_sec(us_em)
    print(f"    SEC: {len(fatos_sec)} filings (8-K/6-K) nas ultimas 24h")
    fatos_ri = raspar_ris(ri_em)
    print(f"    RI: {len(fatos_ri)} releases raspados")

    finais = _dedup(fatos_sec + fatos_cvm + fatos_ri + imprensa_finais + yahoo_finais)
    finais.sort(key=lambda x: (str(x["ticker"]), -x["data_obj"].timestamp()))
    print(f"    {len(finais)} itens apos juntar e deduplicar")

    print("5/6 Resumindo com IA (Google Gemini)...")
    if IA_ATIVA:
        n_res = preencher_resumos(finais)
        print(f"    {n_res} resumos gerados")
    else:
        print("    (pulado: GEMINI_API_KEY nao configurada)")

    print("6/6 Gerando Excel...")
    arq, n_not, n_mon = gerar_excel(alvos, finais, args.saida)
    print(f"    Pronto: {arq}")

    print("\n--- MATCHES (confira a qualidade) ---")
    for n in finais:
        prem = "*" if n.get("premium") else " "
        print(f"{prem}[{str(n['ticker'])[:14]:14}] {n['nome'][:20]:20} | rel {n['relevancia']} | {n['fonte'][:22]}")
        print(f"   {n['titulo'][:74]}")


if __name__ == "__main__":
    main()
