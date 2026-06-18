"""Coleta de imprensa via API de noticias com chave gratuita (NewsData.io) - opcional.

Espinha dorsal estavel (nao sofre bloqueio de IP como o GDELT). So roda se a variavel
NEWS_API_KEY existir (igual ao Gemini); sem ela vira no-op. Busca por NOME das empresas
(frases entre aspas, OR), filtra 24h + Tier 1 (fonte_ok) e devolve CANDIDATOS no mesmo
formato do GDELT, para passar pelo mesmo baixar_corpos/validar_todos.

Chave gratuita em https://newsdata.io (plano free). Cadastre como segredo NEWS_API_KEY.
"""

import os, random, requests
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

from coleta import montar_candidato, fonte_ok, JANELA_HORAS

API_KEY = os.environ.get("NEWS_API_KEY")
ATIVADO = bool(API_KEY)
URL = "https://newsdata.io/api/1/news"
BATCH = 5          # nomes de empresa por consulta (OR)
MAX_CALLS = 10     # teto de chamadas/dia (free tier ~200 creditos)
TIMEOUT = 20


def _dom(url):
    try:
        return urlparse(url or "").netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _queries(empresas, tamanho):
    nomes = [cfg["forte"][0] for cfg in empresas.values() if cfg.get("forte")]
    random.shuffle(nomes)   # rotaciona a cobertura entre os dias (free tier limita chamadas)
    grupos = [nomes[i:i + tamanho] for i in range(0, len(nomes), tamanho)]
    return [" OR ".join(f'"{n}"' for n in g) for g in grupos]


def coletar_api(empresas):
    """Consulta a NewsData.io por nomes das empresas. Retorna {link: candidato}.
    No-op (>{}) sem NEWS_API_KEY. Qualquer falha e silenciosa."""
    if not ATIVADO:
        print("  API: pulada (NEWS_API_KEY nao configurada)")
        return {}
    limite = datetime.now(timezone.utc) - timedelta(hours=JANELA_HORAS)
    candidatos = {}
    calls = erros = 0
    for q in _queries(empresas, BATCH):
        if calls >= MAX_CALLS:
            break
        calls += 1
        try:
            r = requests.get(URL, params={"apikey": API_KEY, "q": q, "language": "pt,en"},
                             timeout=TIMEOUT)
            if r.status_code != 200:
                erros += 1
                continue
            results = r.json().get("results") or []
        except Exception:
            erros += 1
            continue
        for a in results:
            link = (a.get("link") or "").strip()
            titulo = (a.get("title") or "").strip()
            if not link or not titulo or link in candidatos:
                continue
            ds = (a.get("pubDate") or "").strip()
            try:
                data = datetime.strptime(ds[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            except Exception:
                continue
            if data < limite:
                continue
            fonte = (a.get("source_id") or _dom(a.get("source_url")) or "").lower()
            if not fonte_ok(fonte):           # mantem Tier 1 estrito
                continue
            candidatos[link] = montar_candidato(titulo, link, fonte, data)
    print(f"  API: {calls} consultas, {erros} erros, {len(candidatos)} candidatos (Tier 1)")
    return candidatos
