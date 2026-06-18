"""Raspagem best-effort das paginas de RI (Relacoes com Investidores) dos emissores.

Para cada emissor que tem `ri_url` no registro, baixa a pagina de comunicados/releases e
procura links cujo texto seja de release ('fato relevante', 'comunicado ao mercado',
'press release'...) E que tenham uma data recente (hoje/ontem) por perto. Emite no MESMO
formato dos outros (fato_relevante.py) para entrar em 'finais'.

E ADITIVO e best-effort: cada site tem HTML diferente (e alguns sao JS/PDF/anti-bot), entao
muitos emissores nao renderao nada - tudo bem. Os canais oficiais (CVM no BR, SEC nos EUA)
sao os autoritativos; a RI complementa. Falhas sao silenciosas e o tempo total e limitado.
"""

import re, time, requests, unicodedata
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

RI_TIMEOUT = 8
RI_WORKERS = 6
RI_BUDGET  = 90      # teto de tempo (s) p/ a raspagem inteira
JANELA_HORAS = 24
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

_PALAVRAS = ["fato relevante", "comunicado ao mercado", "comunicado", "press release",
             "material fact", "aviso aos acionistas", "release", "imprensa"]
_MESES = ["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto",
          "setembro", "outubro", "novembro", "dezembro"]
_A_TAG = re.compile(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)
_TAGS  = re.compile(r"<[^>]+>")


def _norm(t):
    return unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode("ascii").lower()


def _datas_recentes():
    """Strings de data de hoje e ontem em formatos comuns para casar no HTML."""
    hoje = datetime.now(timezone.utc)
    ontem = hoje - timedelta(hours=JANELA_HORAS)
    fmts = set()
    for d in (hoje, ontem):
        fmts.add(d.strftime("%d/%m/%Y"))
        fmts.add(d.strftime("%Y-%m-%d"))
        fmts.add(d.strftime("%d/%m"))
        fmts.add(f"{int(d.strftime('%d'))} de {_MESES[d.month - 1]}")
    return fmts


def _abs_url(base, href):
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    m = re.match(r"(https?://[^/]+)", base)
    raiz = m.group(1) if m else base
    return raiz + (href if href.startswith("/") else "/" + href)


def _raspar_um(emissor):
    """Baixa a RI de um emissor e devolve itens-padrao recentes. [] em qualquer falha."""
    url = emissor.get("ri_url")
    if not url:
        return []
    try:
        r = requests.get(url, headers=HEADERS, timeout=RI_TIMEOUT)
        if r.status_code != 200 or not r.text:
            return []
        html = r.text
    except Exception:
        return []

    datas = _datas_recentes()
    agora = datetime.now(timezone.utc)
    itens, vistos = [], set()
    for m in _A_TAG.finditer(html):
        href, bruto = m.group(1), m.group(2)
        texto = _TAGS.sub(" ", bruto)
        texto = " ".join(texto.split())
        tn = _norm(texto)
        if not texto or len(texto) < 6:
            continue
        if not any(p in tn for p in _PALAVRAS):
            continue
        # janela de HTML ao redor do link para procurar uma data recente
        ini = max(0, m.start() - 240)
        janela = html[ini:m.end() + 120]
        if not any(d in janela for d in datas):
            continue
        chave = tn[:80]
        if chave in vistos:
            continue
        vistos.add(chave)
        itens.append({
            "data": agora.strftime("%d/%m/%Y"), "data_obj": agora,
            "ticker": emissor.get("ticker", "-"), "nome": emissor["nome"],
            "titulo": f"[RI] {texto}"[:200],
            "fonte": f"RI/{emissor['nome']}"[:30], "premium": True,
            "link": _abs_url(url, href),
            "score": 8, "relevancia": 8, "resumo_ia": "", "impacto": "",
            "corpo": f"Release na pagina de RI da {emissor['nome']}: {texto}",
        })
        if len(itens) >= 3:        # no maximo 3 por emissor
            break
    return itens


def raspar_ris(emissores_com_ri):
    """Raspa em paralelo as RIs dos emissores que tem ri_url. Limitado por RI_BUDGET."""
    alvos = [e for e in emissores_com_ri if e.get("ri_url")]
    if not alvos:
        return []
    t0 = time.time()
    resultados = []
    with ThreadPoolExecutor(max_workers=RI_WORKERS) as ex:
        futuros = {ex.submit(_raspar_um, e): e for e in alvos}
        for fut in as_completed(futuros):
            if time.time() - t0 > RI_BUDGET:
                break
            try:
                resultados.extend(fut.result() or [])
            except Exception:
                pass
    return resultados
