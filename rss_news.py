"""Coleta de imprensa via RSS - fonte principal, confiavel e sem limite de IP.

Duas frentes:
  1) coletar_feeds_tier1(empresas): puxa feeds RSS de veiculos Tier 1 (InfoMoney, Exame,
     Valor/Globo, MoneyTimes, Brazil Journal, CNBC...), filtra 24h e pre-seleciona so as
     materias cujo TITULO cita alguma empresa monitorada. Devolve CANDIDATOS no mesmo
     formato do GDELT, para passar pelo mesmo baixar_corpos/validar_todos.
  2) coletar_yahoo(emissores): RSS do Yahoo Finance POR TICKER (PETR4.SA, AAPL...). Como
     a materia ja e da empresa, pre-atribui ao emissor (dispensa nome-no-titulo); aplica
     so 24h + anti-macro/filler. Devolve itens FINAIS prontos.

Sem dependencias externas (parser com xml.etree). Qualquer feed que falhe e ignorado
em silencio. Tudo respeita a janela de 24h e a curadoria Tier 1 (fonte_ok).
"""

import re, time, requests
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from coleta import (montar_candidato, fonte_ok, conta, norm, _eh_macro,
                    JANELA_HORAS, HEADERS)

TIMEOUT = 10
YAHOO_WORKERS = 6
YAHOO_BUDGET = 60
MAX_POR_TICKER = 3

# Feeds RSS de veiculos Tier 1 (todos batem com a allowlist em coleta.FONTES_ACEITAS).
# Se algum sair do ar / mudar de URL, e ignorado em silencio - lista facil de editar.
FEEDS = [
    "https://www.infomoney.com.br/feed/",
    "https://www.infomoney.com.br/mercados/feed/",
    "https://exame.com/feed/",
    "https://exame.com/invest/feed/",
    "https://www.moneytimes.com.br/feed/",
    "https://www.seudinheiro.com/feed/",
    "https://investnews.com.br/feed/",
    "https://braziljournal.com/feed/",
    "https://neofeed.com.br/feed/",
    "https://g1.globo.com/rss/g1/economia/",
    "https://www.cnnbrasil.com.br/economia/feed/",
    "https://www.suno.com.br/noticias/feed/",
]

# Feeds do Yahoo Finance por ticker (cobre as acoes/BDRs com ticker de bolsa).
_YAHOO = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={sym}&region={reg}&lang={lang}"


def _dominio(url):
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _data_rss(item, ns):
    """Extrai a data de um <item> RSS ou <entry> Atom. Retorna datetime UTC ou None."""
    for tag in ("pubDate", "{http://purl.org/dc/elements/1.1/}date"):
        el = item.find(tag)
        if el is not None and el.text:
            try:
                d = parsedate_to_datetime(el.text)
                return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
            except Exception:
                pass
    for tag in ("published", "updated"):
        el = item.find(f"{ns}{tag}")
        if el is not None and el.text:
            try:
                return datetime.fromisoformat(el.text.replace("Z", "+00:00"))
            except Exception:
                pass
    return None


def _link_rss(item, ns):
    el = item.find("link")
    if el is not None and (el.text or "").strip():
        return el.text.strip()
    el = item.find(f"{ns}link")          # Atom: <link href="...">
    if el is not None:
        return (el.get("href") or "").strip()
    return ""


def _parse_feed(xml_bytes):
    """Devolve lista de (titulo, link, data_obj) de um feed RSS/Atom. [] em falha."""
    try:
        root = ET.fromstring(xml_bytes)
    except Exception:
        return []
    ns = "{http://www.w3.org/2005/Atom}"
    itens = root.iter("item")
    out = []
    encontrou = False
    for it in itens:
        encontrou = True
        t = it.find("title")
        titulo = (t.text or "").strip() if t is not None else ""
        link = _link_rss(it, ns)
        data = _data_rss(it, ns)
        if titulo and link and data:
            out.append((titulo, link, data))
    if not encontrou:                     # Atom usa <entry>
        for it in root.iter(f"{ns}entry"):
            t = it.find(f"{ns}title")
            titulo = (t.text or "").strip() if t is not None else ""
            link = _link_rss(it, ns)
            data = _data_rss(it, ns)
            if titulo and link and data:
                out.append((titulo, link, data))
    return out


def _baixar_feed(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200 or not r.content:
            return []
        return _parse_feed(r.content)
    except Exception:
        return []


def coletar_feeds_tier1(empresas):
    """Puxa os feeds Tier 1 em paralelo, filtra 24h e pre-seleciona materias cujo titulo
    cita alguma empresa monitorada. Retorna {link: candidato}. Reusa fonte_ok/conta."""
    limite = datetime.now(timezone.utc) - timedelta(hours=JANELA_HORAS)
    nomes = []                                   # uniao de nomes p/ pre-filtro por titulo
    for cfg in empresas.values():
        nomes += cfg.get("forte", []) + cfg.get("fraco", [])
    nomes = list(set(nomes))

    candidatos = {}
    n_itens_total = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futuros = {ex.submit(_baixar_feed, u): u for u in FEEDS}
        for fut in as_completed(futuros):
            url = futuros[fut]
            try:
                itens = fut.result()
            except Exception:
                itens = []
            dom = _dominio(url)
            if not fonte_ok(dom):
                continue
            for titulo, link, data in itens:
                n_itens_total += 1
                if data < limite:
                    continue
                if link in candidatos:
                    continue
                if conta(titulo, nomes) == 0:        # titulo nao cita nenhuma empresa
                    continue
                candidatos[link] = montar_candidato(titulo, link, dom, data)
    print(f"  RSS feeds: {len(FEEDS)} feeds, {n_itens_total} itens lidos, "
          f"{len(candidatos)} candidatos (titulo cita empresa)")
    return candidatos


def _simbolo_yahoo(emissor):
    """Define o simbolo do Yahoo p/ o emissor: US usa sec_ticker; BR usa ticker+'.SA'."""
    sec = emissor.get("sec_ticker")
    if sec:
        return sec, "US", "en-US"
    tk = (emissor.get("ticker") or "").strip()
    if tk and tk not in ("-", "?") and tk[-1].isdigit():
        return f"{tk}.SA", "BR", "pt-BR"
    return None, None, None


def _raspar_yahoo(emissor):
    sym, reg, lang = _simbolo_yahoo(emissor)
    if not sym:
        return []
    limite = datetime.now(timezone.utc) - timedelta(hours=JANELA_HORAS)
    try:
        r = requests.get(_YAHOO.format(sym=sym, reg=reg, lang=lang),
                         headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200 or not r.content:
            return []
        itens = _parse_feed(r.content)
    except Exception:
        return []
    out = []
    for titulo, link, data in itens:
        if data < limite or _eh_macro(titulo):
            continue
        out.append({
            "data": data.strftime("%d/%m/%Y %H:%M"), "data_obj": data,
            "ticker": emissor.get("ticker", "-"), "nome": emissor["nome"],
            "titulo": titulo, "fonte": "finance.yahoo.com", "premium": False,
            "link": link, "score": 6, "relevancia": 6, "resumo_ia": "", "impacto": "",
            "corpo": "",
        })
        if len(out) >= MAX_POR_TICKER:
            break
    return out


def coletar_yahoo(emissores):
    """RSS do Yahoo Finance por ticker, pre-atribuido ao emissor. Lista de itens finais."""
    alvos = [e for e in emissores if _simbolo_yahoo(e)[0]]
    if not alvos:
        return []
    t0 = time.time()
    finais, n_ok = [], 0
    with ThreadPoolExecutor(max_workers=YAHOO_WORKERS) as ex:
        futuros = {ex.submit(_raspar_yahoo, e): e for e in alvos}
        for fut in as_completed(futuros):
            if time.time() - t0 > YAHOO_BUDGET:
                break
            try:
                itens = fut.result()
            except Exception:
                itens = []
            if itens:
                n_ok += 1
                finais.extend(itens)
    print(f"  RSS Yahoo: {len(alvos)} tickers, {len(finais)} noticias ({n_ok} tickers com noticia)")
    return finais
