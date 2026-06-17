"""Coleta de noticias (GDELT DOC API), download paralelo e validacao de relevancia."""

import re, time, json, unicodedata, base64, requests, trafilatura
from datetime import datetime, timezone, timedelta
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

# ----- Parametros ajustaveis -----
MAX_POR_ATIVO = 4
WORKERS       = 12     # downloads simultaneos. Se houver bloqueio (429/403), reduza para 6.
TIMEOUT       = 8      # segundos por artigo
JANELA_HORAS  = 24
GDELT_URL     = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_WORKERS = 8      # buscas simultaneas no GDELT (paraleliza as 53 consultas)
GDELT_MAX     = 75     # artigos por empresa (max do GDELT e 250)

# LISTA BRANCA (allowlist): so noticias destas fontes Tier 1 sao aceitas. Qualquer
# dominio que nao bata com um destes termos e descartado (corta sites de "fulano
# comprou X acoes", agregadores e blogs). Edite a lista para incluir/excluir fontes.
FONTES_TIER1 = [
    # Agencias e imprensa financeira global
    "reuters", "bloomberg", "wsj.com", "wall street journal", "ft.com", "financial times",
    "cnbc", "economist", "barron", "marketwatch", "forbes.com", "fortune.com",
    "nytimes", "new york times", "washingtonpost", "theguardian", "guardian.co",
    "apnews", "associated press", "nikkei", "asia.nikkei", "axios", "businessinsider",
    "finance.yahoo", "yahoo finance", "oilprice",
    # Brasil
    "valor", "infomoney", "exame", "estadao", "folha.uol", "oglobo", "globo.com",
    "g1.globo", "braziljournal", "brazil journal", "pipelinevalor", "neofeed",
    "bloomberglinea", "moneytimes", "investnews", "capitalreset",
    # Mexico / America Latina / Espanha
    "elfinanciero", "eleconomista", "expansion", "reforma", "milenio", "cincodias",
    # Europa
    "handelsblatt", "lesechos", "lemonde", "boersen", "boerse", "ilsole24ore", "repubblica",
]
# TIER 1.5: fontes serias, porem nao-elite (imprensa financeira de 2a linha e trade
# press setorial). Aumentam a cobertura com ruido baixo. NAO inclui sites de "fulano
# comprou X acoes" nem PR wires. Para voltar ao Tier 1 estrito, basta esvaziar esta lista.
FONTES_TIER1_5 = [
    # Imprensa/analise financeira solida
    "seekingalpha", "investing.com", "benzinga", "marketscreener", "morningstar",
    "thestreet", "investors.com", "nasdaq.com", "zacks", "quartz", "qz.com",
    # Saude / pharma (BMY, Lilly, Merck, JNJ, Novartis, Roche, AbbVie, Sandoz)
    "statnews", "endpts", "endpoints", "fiercepharma", "fiercebiotech",
    # Auto / industria (Ford, BMW, Toyota, Caterpillar, ABB)
    "autonews", "automotivenews", "electrek", "insideevs",
    # Energia (BP, Chevron, Conoco, Marathon, Pemex, Cosan)
    "rigzone", "hartenergy", "upstreamonline", "spglobal",
    # Bancos
    "americanbanker",
    # Brasil
    "cnnbrasil", "suno.com", "seudinheiro", "einvestidor", "e-investidor",
    # Setor papel/celulose (Suzano)
    "pulpapernews", "risiinfo",
]
# Lista efetiva de fontes aceitas (Tier 1 + Tier 1.5).
FONTES_ACEITAS = FONTES_TIER1 + FONTES_TIER1_5

# Subconjunto "top" usado apenas como bonus de pontuacao (desempate).
FONTES_PREMIUM = ["reuters","bloomberg","cnbc","financial times","ft.com","wall street journal",
    "wsj","marketwatch","barron","forbes","fortune","valor","infomoney",
    "exame","oilprice","the guardian","nikkei","yahoo finance","economist","nytimes"]
VERBOS = ["reported","reports","posted","announced","announces","said","says","unveiled",
    "launched","launches","raised","raises","cut","cuts","named","appointed","acquired",
    "acquires","to acquire","bought","buys","sued","faces","beat","beats","missed","warned",
    "warns","plans","plunged","plunges","jumped","jumps","fell","rose","surged","slumped",
    "forecast","hiked","slashed","agreed","signed","filed","anunciou","reportou","registrou",
    "divulgou","disse","lancou","comprou","adquiriu","vendeu","nomeou","demitiu","processou",
    "elevou","cortou","reduziu","aprovou","assinou","planeja","superou","decepcionou"]
# Manchetes de mercado/macro: se o titulo bate com um destes termos, a noticia e
# sobre o cenario (bolsa/juros/indices), nao sobre a empresa -> rejeitada.
MACRO_TITULO = ["stock market today","market today","dow ","s&p 500","s & p 500","nasdaq",
    "ftse","stoxx","nikkei 225","ibovespa","ibov","stocks soar","stocks rally","stocks slip",
    "stocks fall","stocks rise","stocks jump","stocks climb","stocks drop","stocks slide",
    "stocks mixed","stocks higher","stocks lower","wall street","premarket","pre-market",
    "market wrap","markets wrap","futures","biggest analyst calls","analyst calls",
    "stocks to watch","stocks to buy","top stocks","best stocks","movers","market movers",
    "mercado hoje","bolsas","fechamento","ibc-br","payrolls","fed rate","rate decision",
    "rate cut","rate hike","cpi ","inflation data","jobs report","gdp ","economy for stock",
    "great economy","tariff","tariffs","live :","ao vivo","minuto a minuto",
    # macro/mercado em portugues
    "ibovespa","ibov","selic","copom","pregao","pregão","dolar","dólar","cambio","câmbio",
    "carteira recomendada","acoes para comprar","ações para comprar","melhores acoes",
    "melhores ações","onde investir","dividendos para receber","radar do mercado",
    "abertura de mercado","fechamento de mercado","bolsa sobe","bolsa cai","bolsa fecha"]
# Manchetes de "filler"/clickbait/promocional: nao sao noticia real da empresa.
FILLER_TITULO = ["invested in","worth this much","years ago would","5 years ago","10 years ago",
    "should you buy","is it time to buy","is a buy","a better buy","stock a buy","time to buy",
    "could more than double","here is why","heres why","this stock","best stock","top stock",
    "stocks to buy","motley fool","zacks rank","price target","shares sold","shares bought",
    "shares acquired","stake in","position in","hold rating","buy rating","sell rating",
    "shocking","you should know","reasons to","things to know","what to know","vs ."]
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
    """Baixa o artigo e extrai (texto, data_publicacao). data_pub e date ou None.
    Timeout real no request. Retorna ('', None) em falha."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200 or not r.text:
            return "", None
        dados = trafilatura.extract(r.text, output_format="json", with_metadata=True)
        if not dados:
            return "", None
        obj = json.loads(dados)
        texto = obj.get("text") or ""
        data_pub = None
        ds = obj.get("date")                      # formato 'YYYY-MM-DD'
        if ds:
            try: data_pub = datetime.strptime(ds[:10], "%Y-%m-%d").date()
            except Exception: data_pub = None
        return texto, data_pub
    except Exception:
        return "", None

def _eh_macro(titulo):
    """True se o titulo for de mercado/macro (bolsa, juros, indices) ou filler/clickbait."""
    t = norm(titulo)
    return any(m in t for m in MACRO_TITULO) or any(f in t for f in FILLER_TITULO)

def _n_empresas_no_titulo(titulo, empresas):
    """Quantas empresas DIFERENTES da carteira aparecem no titulo (detecta roundup)."""
    if not empresas: return 1
    return sum(1 for c in empresas.values() if conta(titulo, c["forte"] + c["fraco"]) > 0)

def validar(titulo, corpo, resumo, cfg, premium=False, empresas=None):
    """Noticia tem de ser SOBRE a empresa: o nome precisa estar no TITULO (nao so
    citado no corpo). Rejeita manchetes macro/mercado e roundups. Retorna score 0-10."""
    nomes = cfg["forte"] + cfg["fraco"]
    tl = norm(titulo)
    # 1) A empresa PRECISA estar no titulo (senao e citacao de passagem no corpo).
    if conta(titulo, nomes) == 0:
        return 0
    # 2) So nome ambiguo (fraco) no titulo -> exige termo de contexto (titulo+corpo).
    corpo_ok = bool(corpo and len(corpo) >= 200)
    full = titulo + " " + (corpo if corpo_ok else resumo)
    if conta(titulo, cfg["forte"]) == 0 and conta(full, cfg["contexto"]) == 0:
        return 0
    # 3) Rejeita manchete de mercado/macro (nao e noticia interna da empresa).
    if _eh_macro(titulo):
        return 0
    # 4) Rejeita roundup: titulo citando 3+ empresas diferentes da carteira.
    if _n_empresas_no_titulo(titulo, empresas) >= 3:
        return 0
    # 5) Pontuacao: empresa cedo no titulo + verbo de acao + contexto + premium.
    nome_total = conta(full, nomes)
    ctx = conta(full, cfg["contexto"])
    bp = 1 if premium else 0
    pos = min([tl.find(norm(n)) for n in nomes if norm(n) in tl] + [9999])
    cedo = pos <= len(tl) * 0.6
    tem_verbo = any(re.search(r'(?<![a-z])'+re.escape(norm(v))+r'(?![a-z])', tl) for v in VERBOS)
    score = 5 + (2 if cedo else 0) + (1 if tem_verbo else 0) + min(nome_total, 2) + min(ctx, 2) + bp
    return min(10, score)

def fonte_ok(fonte):
    """So aceita fontes Tier 1 / Tier 1.5 (allowlist). Sem fonte identificada -> rejeita."""
    f = norm(fonte)
    if not f: return False
    return any(t in f for t in FONTES_ACEITAS)

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
    """Consulta o GDELT DOC API para um termo (ultimas 24h). Retorna lista de artigos.
    O termo e usado como query do GDELT (palavras separadas = E logico)."""
    params = {"query": termo, "mode": "ArtList", "maxrecords": str(GDELT_MAX),
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
    """Busca no GDELT por empresa (em paralelo), dedup por link e titulo, janela de 24h."""
    limite = datetime.now(timezone.utc) - timedelta(hours=JANELA_HORAS)

    # 1) Dispara as buscas em paralelo. Usa o campo 'busca' (query dedicada) quando
    #    existir; senao, o primeiro nome forte; senao, o nome da empresa.
    resultados = {}
    with ThreadPoolExecutor(max_workers=GDELT_WORKERS) as ex:
        futuros = {ex.submit(buscar_gdelt,
                             cfg.get("busca") or (cfg["forte"][0] if cfg["forte"] else nome)): nome
                   for nome, cfg in empresas.items()}
        for fut in as_completed(futuros):
            nome = futuros[fut]
            try:
                resultados[nome] = fut.result()
            except Exception as e:
                print(f"  {nome}: erro {str(e)[:40]}")
                resultados[nome] = []

    # 2) Processa os resultados em ordem (dedup deterministico, sem threads).
    candidatos = {}
    titulos_vistos = set()
    for nome in empresas:
        for a in resultados.get(nome, []):
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
    return candidatos


def baixar_corpos(candidatos):
    """Baixa os corpos em paralelo. Retorna {link: (link_real, corpo, data_pub)}."""
    def tarefa(link):
        real = link_real(link)
        corpo, data_pub = baixar(real)
        return link, real, corpo, data_pub
    resultados = {}
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futuros = [ex.submit(tarefa, l) for l in candidatos]
        done = 0
        for fut in as_completed(futuros):
            link, real, corpo, data_pub = fut.result()
            resultados[link] = (real, corpo, data_pub)
            done += 1
            if done % 50 == 0:
                print(f"  {done}/{len(candidatos)} baixados ({time.time()-t0:.0f}s)")
    print(f"  download concluido em {time.time()-t0:.0f}s")
    return resultados


def validar_todos(candidatos, corpos, empresas):
    """Valida cada candidato e escolhe a empresa de maior score. Top N por ativo.
    Reforca a janela de 24h pela DATA DE PUBLICACAO real (quando disponivel)."""
    validadas = {}
    sem_corpo = 0
    fora_janela = 0
    limite_dia = (datetime.now(timezone.utc) - timedelta(hours=JANELA_HORAS)).date()
    for link, c in candidatos.items():
        real, corpo, data_pub = corpos.get(link, (link, "", None))
        # Corte por data de publicacao: se a materia for mais velha que a janela, descarta.
        if data_pub is not None and data_pub < limite_dia:
            fora_janela += 1
            continue
        if not corpo or len(corpo) < 200:
            sem_corpo += 1
        melhor = None
        for nome, cfg in empresas.items():
            score = validar(c["titulo"], corpo, c["resumo"], cfg,
                            premium=c["premium"], empresas=empresas)
            if score > 0 and (melhor is None or score > melhor["score"]):
                melhor = {"nome": nome, "ticker": cfg["ticker"], "score": score}
        if melhor:
            validadas[link] = {**c, "link": real, **melhor,
                               "relevancia": melhor["score"], "resumo_ia": "", "impacto": "",
                               "corpo": (corpo or "")[:3000]}

    por_ativo = defaultdict(list)
    for n in validadas.values():
        por_ativo[n["nome"]].append(n)
    finais = []
    for nome, lst in por_ativo.items():
        lst.sort(key=lambda x: (-x["score"], -x["data_obj"].timestamp()))
        finais.extend(lst[:MAX_POR_ATIVO])
    finais.sort(key=lambda x: (x["ticker"], -x["data_obj"].timestamp()))
    return finais, sem_corpo, fora_janela
