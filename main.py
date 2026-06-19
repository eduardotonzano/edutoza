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
from coleta import coletar_candidatos, baixar_corpos, validar_todos, norm, precisa_corpo
from rss_news import coletar_feeds_tier1, coletar_yahoo
from google_news import coletar_google
from news_api import coletar_api
from fato_relevante import buscar_fatos_relevantes
from sec_edgar import buscar_fatos_sec
from ri_scraping import raspar_ris
from excel import gerar_excel
from pdf_digest import gerar_pdf
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

    print("2/6 Coletando imprensa (GDELT + Google News + RSS Tier 1 + Yahoo + API)...")
    from coleta import FONTES_ESPECIALIZADAS, FEEDS_ESPECIALIZADOS
    print(f"    Fontes especializadas: {len(FONTES_ESPECIALIZADAS)} dominios na allowlist, "
          f"{len(FEEDS_ESPECIALIZADOS)} feeds RSS (renda fixa/credito/rating)")
    emissores_lista = list(gdelt_reg.values())
    candidatos = {}
    if os.environ.get("PULAR_GDELT"):
        print("    GDELT PULADO (PULAR_GDELT setado p/ teste)")
    else:
        candidatos.update(coletar_candidatos(gdelt_reg))      # imprensa global (GDELT)
    candidatos.update(coletar_google(emissores_lista))        # Google News por empresa
    candidatos.update(coletar_feeds_tier1(gdelt_reg))         # feeds RSS Tier 1
    candidatos.update(coletar_yahoo(emissores_lista))         # Yahoo Finance por ticker
    candidatos.update(coletar_api(gdelt_reg))                 # API NewsData (opcional)
    print(f"    {len(candidatos)} candidatos unicos no pool de imprensa")

    print("3/6 Baixando corpos (so quando preciso) e validando relevancia...")
    # Baixa o corpo so dos itens com nome AMBIGUO no titulo (precisam de contexto); os
    # demais validam pelo titulo. Evita centenas de downloads e acelera o run.
    precisam = {l: c for l, c in candidatos.items() if precisa_corpo(c["titulo"], gdelt_reg)}
    print(f"    {len(precisam)}/{len(candidatos)} precisam de corpo (nome ambiguo)")
    corpos = baixar_corpos(precisam)
    imprensa_finais, sem_corpo, fora_janela = validar_todos(candidatos, corpos, gdelt_reg)
    cobertos = len(Counter(n["nome"] for n in imprensa_finais))
    print(f"    {len(imprensa_finais)} noticias validadas | "
          f"{cobertos} emissores cobertos ({fora_janela} fora da janela de 24h)")

    print(f"4/6 Fatos relevantes (CVM {len(cvm_em)} | SEC {len(us_em)} | RI {len(ri_em)})...")
    fatos_cvm = buscar_fatos_relevantes(cvm_em)
    print(f"    CVM: {len(fatos_cvm)} fatos relevantes/comunicados")
    fatos_sec = buscar_fatos_sec(us_em)
    print(f"    SEC: {len(fatos_sec)} filings (8-K/6-K) nas ultimas 24h")
    fatos_ri = raspar_ris(ri_em)
    print(f"    RI: {len(fatos_ri)} releases raspados")

    finais = _dedup(fatos_sec + fatos_cvm + fatos_ri + imprensa_finais)
    finais.sort(key=lambda x: (str(x["ticker"]), -x["data_obj"].timestamp()))
    print(f"    {len(finais)} itens apos juntar e deduplicar")

    print("5/6 Resumindo com IA (Gemini + Claude Code/Haiku reserva, 2 analistas)...")
    if IA_ATIVA:
        preencher_resumos(finais)
    else:
        print("    (pulado: nenhuma chave de IA configurada)")

    print("6/6 Gerando Excel e PDF...")
    arq, n_not, n_mon = gerar_excel(alvos, finais, args.saida)
    print(f"    Excel: {arq}")
    try:
        pdf = gerar_pdf(finais, "Principais_Noticias_24h.pdf")
        print(f"    PDF: {pdf}")
    except Exception as e:
        print(f"    PDF falhou (seguindo sem ele): {str(e)[:80]}")

    print("\n--- MATCHES (confira a qualidade) ---")
    for n in finais:
        prem = "*" if n.get("premium") else " "
        print(f"{prem}[{str(n['ticker'])[:14]:14}] {n['nome'][:20]:20} | rel {n['relevancia']} | {n['fonte'][:22]}")
        print(f"   {n['titulo'][:74]}")


if __name__ == "__main__":
    main()
