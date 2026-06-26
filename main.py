"""Pipeline: carteira(340 ativos) -> emissores -> [GDELT + CVM + SEC + RI] -> Excel.

Uso:
    python main.py --carteira carteira_completa.csv --saida relatorio.xlsx

Le carteira_completa.csv (colunas ATIVO,TIPO,MOEDA,CATEGORIA), mapeia cada ativo ao seu
EMISSOR (mapeamento.py / emissores.py), monitora cada emissor em varias fontes gratuitas e
gera um Excel que lista TODOS os ativos com status (noticia encontrada / sem noticia hoje /
sem noticia aplicavel).
"""

import argparse, os, re
from collections import Counter, defaultdict

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


def _stem(w):
    """Stemming simples de plural: tira o 's' final de palavras longas (probe/probes,
    price/prices) p/ que variacoes do mesmo titulo casem no dedup."""
    return w[:-1] if len(w) > 4 and w.endswith("s") else w

# Palavras vazias (pt+en) e genericas que nao ajudam a distinguir uma noticia de outra.
# Guardadas ja na forma "stem" (sem plural), pois a assinatura tambem e stemada.
_STOP_DEDUP = {_stem(w) for w in (
    "para com sem que dos das nos nas uma uns por pra sobre como mais menos esta este isso "
    "via seu sua suas seus pelo pela ainda apenas pode deve "
    "the for and new its out has was are but not over with from that this into your they "
    "will have what when about than then diz disse apos ante entre").split()}
_GENERICO_DEDUP = {_stem(w) for w in (
    "empresa empresas acao acoes mercado comunicado fato relevante noticia balanco hoje "
    "ano mes dia anos bilhoes milhoes bilhao milhao reais company stock shares market today").split()}


def _assinatura(titulo, nome):
    """Conjunto de palavras significativas do titulo (3+ letras OU numeros, ja stemadas),
    sem o nome do emissor, stopwords/genericos e o sufixo de fonte (' - Exame'). Usado p/
    achar a MESMA noticia vinda de varios veiculos. Mantem 'CRI', '535', '365' (sinais
    fortes do fato) que antes eram descartados por terem <4 letras."""
    t = norm(titulo)
    t = re.sub(r"\s+[-|]\s+[^-|]{1,30}$", "", t)          # tira o sufixo do veiculo
    nome_toks = {_stem(w) for w in re.findall(r"[a-z0-9]{3,}", norm(nome))}
    sig = set()
    for w in re.findall(r"[a-z0-9]{3,}", t):
        w = _stem(w)
        if w not in _STOP_DEDUP and w not in _GENERICO_DEDUP and w not in nome_toks:
            sig.add(w)
    return sig


def _mesma_historia(a, b):
    """True se duas assinaturas representam a mesma noticia (coef. de sobreposicao alto)."""
    if len(a) < 3 or len(b) < 3:
        return False
    inter = len(a & b)
    return inter >= 3 and inter / min(len(a), len(b)) >= 0.5


def _dedup(itens):
    """Remove duplicatas, preferindo maior relevancia (oficial CVM/SEC=10 > RI=8 > GDELT):
      1) por link e por (emissor+titulo) exatos;
      2) "fuzzy": a MESMA historia do mesmo emissor vinda de varios veiculos (titulos
         parecidos, links diferentes) - ex.: 3 manchetes do mesmo fato. Nao se aplica entre
         dois itens OFICIAIS (cada fato relevante e unico); um item de imprensa que apenas
         repita um oficial e descartado."""
    itens = sorted(itens, key=lambda x: -x.get("relevancia", 0))
    vistos_link, vistos_tit, out = set(), set(), []
    sigs_por_nome = defaultdict(list)
    for it in itens:
        link = it.get("link", "")
        nome = it.get("nome", "")
        tit = norm(f"{nome} {it.get('titulo','')}")
        if link and link in vistos_link:
            continue
        if tit in vistos_tit:
            continue
        oficial = str(it.get("fonte", "")).startswith(("CVM", "SEC", "RI/"))
        sig = _assinatura(it.get("titulo", ""), nome)
        if not oficial and sig and any(_mesma_historia(sig, s) for s in sigs_por_nome[nome]):
            continue
        if link:
            vistos_link.add(link)
        vistos_tit.add(tit)
        sigs_por_nome[nome].append(sig)
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

    print("5/6 Resumindo com IA (Gemini + Claude Code/Haiku reserva; resumo de 1 paragrafo)...")
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
