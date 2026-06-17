"""Coleta de noticias (GDELT DOC API), download paralelo e validacao de relevancia."""

import re, time, unicodedata, base64, requests, trafilatura
from datetime import datetime, timezone, timedelta
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

# ----- Parametros ajustaveis -----
MAX_POR_ATIVO = 4
WORKERS       = 12     # downloads simultaneos. Se houver bloqueio (429/403), reduza para 6.
TIMEOUT       = 8      # segundos por artigo
JANELA_HORAS  = 24
GDELT_URL     = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_PAUSA   = 1.0    # segundos entre consultas (respeita o rate limit do GDELT)
GDELT_MAX     = 75     # artigos por empresa (max do GDELT e 250)

FONTES_BLOQUEADAS = ["reddit","facebook","twitter","x.com","instagram","tiktok","youtube",
    "medium.com","quora","blogspot","wordpress.com","substack","tradingview",
    "stocktwits","wallmine","marketbeat"]
FONTES_PREMIUM = ["reuters","bloomberg","cnbc","financial times","ft.com","wall street journal",
    "wsj","marketwatch","barron","seeking alpha","forbes","fortune","valor","infomoney",
    "exame","oilprice","the guardian","nikkei","yahoo finance"]
VERBOS = ["reported","reports","posted","announced","announces","said","says","unveiled",
    "launched","launches","raised","raises","cut","cuts","named","appointed","acquired",
    "acquires","to acquire","bought","buys","sued","faces","beat","beats","missed","warned",
    "warns","plans","plunged","plunges","jumped","jumps","fell","rose","surged","slumped",
    "forecast","hiked","slashed","agreed","signed","filed","anunciou","reportou","registrou",
    "divulgou","disse","lancou","comprou","adquiriu","vendeu","nomeou","demitiu","processou",
    "elevou","cortou","reduziu","aprovou","assinou","planeja","superou","decepcionou"]
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def norm(t):
    return unicodedata.normalize('NFKD', t).encode('ascii','ignore').decode('ascii').lower()

def conta(texto, termos):
    tn = norm(texto); tot = 0
    for termo in termos:
        pad = r'(?<![a-z])' + re.escape(norm(termo)) + r'(?![a-z])'
        tot += len(re.findall(pad, tn))
    return tot

def link_real(url):
    """Decodifica o link real escondido na URL do Google News (base64)."""
    try:
        if "news.google.com" not in url:
            return url
        m = re.search(r'/articles/([^?]+)', url)
        if not m: return url
        enc = m.group(1) + "=" * (-len(m.group(1)) % 4)
        dec = base64.urlsafe_b64decode(enc).decode("latin-1", errors="ignore")
        urls = re.findall(r'https?://[^\s\x00-\x1f\\]+', dec)
        urls = [u for u in urls if "google.com" not in u and len(u) > 15]
        return urls[0] if urls else url
    except:
        return url

def baixar(url):
    """Baixa e extrai o texto do artigo. Timeout real no request. Retorna '' em falha."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200 or not r.text:
            return ""
        texto = trafilatura.extract(r.text)
        return texto if texto else ""
    except:
        return ""

def validar(titulo, corpo, resumo, cfg, premium=False):
    """Dois caminhos: A) protagonista no titulo; B) presenca forte no corpo.
    Fallback: usa titulo+resumo quando o corpo nao baixou. Retorna score 0-10."""
    nomes = cfg["forte"] + cfg["fraco"]
    corpo_ok = bool(corpo and len(corpo) >= 200)
    texto = corpo if corpo_ok else (titulo + " " + resumo)
    tl = norm(titulo); full = titulo + " " + texto
    tem_forte = conta(full, cfg["forte"]) > 0
    if not tem_forte and cfg["fraco"] and conta(full, cfg["contexto"]) == 0:
        return 0
    nome_total = conta(full, nomes)
    if nome_total == 0:
        return 0
    ctx = conta(full, cfg["contexto"])
    bp = 1 if premium else 0
    if conta(titulo, nomes) > 0:
        pos = min([tl.find(norm(n)) for n in nomes if norm(n) in tl] + [9999])
        if pos <= len(tl) * 0.6:
            tem_verbo = any(re.search(r'(?<![a-z])'+re.escape(norm(v))+r'(?![a-z])', tl) for v in VERBOS)
            return min(10, 6 + nome_total + (1 if tem_verbo else 0) + min(ctx,3) + bp)
    limiar = 3 if corpo_ok else 1
    if nome_total >= limiar:
        return min(10, 3 + nome_total + min(ctx,2) + bp)
    return 0

def fonte_ok(fonte):
    f = norm(fonte)
    if not f: return True
    return not any(b in f for b in FONTES_BLOQUEADAS)

def eh_premium(fonte):
    f = norm(fonte)
    return any(p in f for p in FONTES_PREMIUM)

def _data_gdelt(s):
    """Converte o seendate do GDELT (ex 20240617T120000Z) em datetime UTC."""
    try:
        return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return None

def buscar_gdelt(termo):
    """Consulta o GDELT DOC API para um termo (ultimas 24h). Retorna lista de artigos."""
    q = f'"{termo}"' if " " in termo else termo   # frase entre aspas casa o nome inteiro
    params = {"query": q, "mode": "ArtList", "maxrecords": str(GDELT_MAX),
              "timespan": f"{JANELA_HORAS}h", "format": "json", "sort": "datedesc"}
    try:
        r = requests.get(GDELT_URL, params=params, headers=HEADERS, timeout=TIMEOUT + 6)
        if r.status_code != 200 or not r.text.strip():
            return []
        try:
            data = r.json()   # GDELT as vezes responde texto de erro em vez de JSON
        except ValueError:
            return []
        return data.get("articles", []) or []
    except Exception:
        return []


def coletar_candidatos(empresas):
    """Busca no GDELT por empresa, dedup por link e por titulo, janela de 24h."""
    limite = datetime.now(timezone.utc) - timedelta(hours=JANELA_HORAS)
    candidatos = {}
    titulos_vistos = set()
    for nome, cfg in empresas.items():
        termo = cfg["forte"][0] if cfg["forte"] else nome
        try:
            artigos = buscar_gdelt(termo)
        except Exception as ex:
            print(f"  {nome}: erro {str(ex)[:40]}")
            artigos = []
        for a in artigos:
            titulo = (a.get("title") or "").strip()
            link   = (a.get("url") or "").strip()
            if not titulo or not link: continue
            chave = norm(titulo)
            if link in candidatos or chave in titulos_vistos: continue
            data = _data_gdelt(a.get("seendate", ""))
            if data is None or data < limite: continue
            fonte = (a.get("domain") or "").strip()
            if not fonte_ok(fonte): continue
            titulos_vistos.add(chave)
            candidatos[link] = {"titulo": titulo, "link": link,
                "resumo": "", "fonte": fonte,
                "premium": eh_premium(fonte),
                "data": data.strftime("%d/%m/%Y %H:%M"), "data_obj": data}
        time.sleep(GDELT_PAUSA)
    return candidatos


def baixar_corpos(candidatos):
    """Baixa todos os corpos em paralelo. Retorna {link: (link_real, corpo)}."""
    def tarefa(link):
        real = link_real(link)
        return link, real, baixar(real)
    resultados = {}
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futuros = [ex.submit(tarefa, l) for l in candidatos]
        done = 0
        for fut in as_completed(futuros):
            link, real, corpo = fut.result()
            resultados[link] = (real, corpo)
            done += 1
            if done % 50 == 0:
                print(f"  {done}/{len(candidatos)} baixados ({time.time()-t0:.0f}s)")
    print(f"  download concluido em {time.time()-t0:.0f}s")
    return resultados


def validar_todos(candidatos, corpos, empresas):
    """Valida cada candidato e escolhe a empresa de maior score. Top N por ativo."""
    validadas = {}
    sem_corpo = 0
    for link, c in candidatos.items():
        real, corpo = corpos.get(link, (link, ""))
        if not corpo or len(corpo) < 200:
            sem_corpo += 1
        melhor = None
        for nome, cfg in empresas.items():
            score = validar(c["titulo"], corpo, c["resumo"], cfg, premium=c["premium"])
            if score > 0 and (melhor is None or score > melhor["score"]):
                melhor = {"nome": nome, "ticker": cfg["ticker"], "score": score}
        if melhor:
            validadas[link] = {**c, "link": real, **melhor,
                               "relevancia": melhor["score"], "resumo_ia": "", "impacto": ""}

    por_ativo = defaultdict(list)
    for n in validadas.values():
        por_ativo[n["nome"]].append(n)
    finais = []
    for nome, lst in por_ativo.items():
        lst.sort(key=lambda x: (-x["score"], -x["data_obj"].timestamp()))
        finais.extend(lst[:MAX_POR_ATIVO])
    finais.sort(key=lambda x: (x["ticker"], -x["data_obj"].timestamp()))
    return finais, sem_corpo
