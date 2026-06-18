"""Coleta de imprensa POR EMPRESA via Google News RSS - o 'tratamento Yahoo' para todos.

Para cada emissor faz uma busca dirigida no Google News RSS ("<nome>" when:1d), que
agrega TODOS os sites por empresa (exatamente o que o Yahoo faz por ticker, mas aqui
para BR e global). Cada item traz <source url> (o veiculo real) -> filtramos Tier 1.
Os links do Google News sao redirecionados; reusa coleta.link_real para resolver.

Devolve CANDIDATOS no mesmo formato do pool (validar_todos exige o nome no titulo, o que
mantem a precisao). Pode dar 403 a partir de IP de datacenter; nesse caso falha em
silencio e as outras fontes seguram. Parser com xml.etree (sem dependencia externa).
"""

import time, requests
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, quote_plus
from concurrent.futures import ThreadPoolExecutor, as_completed

from coleta import montar_candidato, fonte_ok, link_real, JANELA_HORAS, HEADERS

TIMEOUT = 10
WORKERS = 8
BUDGET = 100        # teto de tempo (s) p/ a rodada inteira


def _url(nome, br):
    q = quote_plus(f'"{nome}" when:1d')
    if br:
        return f"https://news.google.com/rss/search?q={q}&hl=pt-BR&gl=BR&ceid=BR:pt-BR"
    return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en-US"


def _dom(url):
    try:
        return urlparse(url or "").netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _buscar_um(emissor):
    """Busca no Google News RSS pelo nome do emissor. Retorna lista de (titulo, link, fonte,
    data). Usa <source url> como veiculo (p/ filtro Tier 1) e resolve o link do Google."""
    nome = (emissor.get("forte") or [emissor.get("nome", "")])[0]
    if not nome:
        return []
    br = not emissor.get("sec_ticker")          # tem ticker da SEC => empresa US => en
    limite = datetime.now(timezone.utc) - timedelta(hours=JANELA_HORAS)
    try:
        r = requests.get(_url(nome, br), headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200 or not r.content:
            return []
        root = ET.fromstring(r.content)
    except Exception:
        return []
    out = []
    for it in root.iter("item"):
        t = it.find("title")
        titulo = (t.text or "").strip() if t is not None else ""
        lk = it.find("link")
        link = (lk.text or "").strip() if lk is not None else ""
        src = it.find("source")
        fonte = _dom(src.get("url")) if src is not None else ""
        pd = it.find("pubDate")
        try:
            data = parsedate_to_datetime(pd.text)
            data = data if data.tzinfo else data.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if not titulo or not link or data < limite:
            continue
        if not fonte_ok(fonte):                 # mantem Tier 1 estrito (pelo veiculo real)
            continue
        out.append((titulo, link_real(link), fonte, data))
    return out


def coletar_google(emissores):
    """Busca no Google News por empresa, em paralelo. Retorna {link: candidato}."""
    alvos = [e for e in emissores if (e.get("forte") or e.get("nome"))]
    if not alvos:
        return {}
    t0 = time.time()
    candidatos = {}
    n_ok = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futuros = {ex.submit(_buscar_um, e): e for e in alvos}
        for fut in as_completed(futuros):
            if time.time() - t0 > BUDGET:
                break
            try:
                itens = fut.result()
            except Exception:
                itens = []
            if itens:
                n_ok += 1
            for titulo, link, fonte, data in itens:
                if link and link not in candidatos:
                    candidatos[link] = montar_candidato(titulo, link, fonte, data)
    print(f"  Google News: {len(alvos)} empresas -> {len(candidatos)} candidatos Tier 1 "
          f"({n_ok} empresas com resultado)")
    return candidatos
