"""Coleta de noticias (GDELT DOC API), download paralelo e validacao de relevancia."""

import re, time, json, unicodedata, base64, random, requests, trafilatura
from datetime import datetime, timezone, timedelta
from collections import defaultdict, Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool

# ----- Parametros ajustaveis -----
MAX_POR_ATIVO = 4
WORKERS       = 8      # downloads simultaneos (processos isolados). Reduza p/ 4 se houver bloqueio.
TIMEOUT       = 8      # segundos por artigo
JANELA_HORAS  = 24
GDELT_URL     = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_MAX     = 250    # artigos por consulta (250 = teto do GDELT DOC API)
GDELT_RETRIES = 3      # tentativas por LOTE quando o GDELT vier erro (throttle/429)
GDELT_PAUSA   = 6      # segundos entre lotes (o GDELT limita ~1 req a cada poucos seg)
GDELT_BATCH   = 7      # empresas por lote: poucas consultas (OR) evitam o limite de taxa
GDELT_BUDGET  = 240    # teto de tempo (s) p/ a coleta GDELT: se estourar, segue com o parcial

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

# ----- Fontes especializadas por classe de ativo (renda fixa / credito / bonds) -----
# Carregadas de fontes_especializadas.json (ao lado deste modulo). Para CADA fonte da
# lista, o DOMINIO entra na allowlist (assim a manchete dela passa, inclusive das pagas,
# quando aparece via Google News/GDELT). As que tem RSS de verdade viram FEEDS_ESPECIALIZADOS
# (consumidos pelo rss_news). Se o arquivo faltar/quebrar, segue com listas vazias (o robo
# nunca para por causa disso).
import os as _os
from urllib.parse import urlparse as _urlparse

def _carregar_fontes_especializadas():
    """Le fontes_especializadas.json e devolve (dominios, feeds_rss). Tolerante a erro."""
    caminho = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                            "fontes_especializadas.json")
    dominios, feeds = [], []
    try:
        with open(caminho, encoding="utf-8") as fh:
            dados = json.load(fh)
        for fonte in dados.get("fontes", []):
            base = (fonte.get("url_base") or "").strip()
            if base:
                dom = _urlparse(base).netloc.lower().replace("www.", "")
                if dom:                       # ja e ascii/minusculo (compativel com fonte_ok)
                    dominios.append(dom)
            rss = (fonte.get("rss") or "").strip()
            # So feeds RSS reais: http(s) e sem placeholder (ex.: o template {DATA} do SEC).
            if rss.startswith("http") and "{" not in rss:
                feeds.append(rss)
    except Exception as e:
        print(f"  (fontes_especializadas.json nao carregado: {str(e)[:60]})")
    return dominios, feeds

FONTES_ESPECIALIZADAS, FEEDS_ESPECIALIZADOS = _carregar_fontes_especializadas()
# Os dominios especializados tambem valem como fontes aceitas na curadoria.
FONTES_ACEITAS = FONTES_ACEITAS + [d for d in FONTES_ESPECIALIZADAS if d not in FONTES_ACEITAS]

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
    "market wrap","markets wrap","biggest analyst calls","analyst calls",
    "stocks to watch","stocks to buy","top stocks","best stocks","market movers",
    "mercado hoje","bolsas","fechamento","ibc-br","payrolls","fed rate","rate decision",
    "rate cut","rate hike","cpi ","inflation data","jobs report","gdp ","economy for stock",
    "great economy","live :","ao vivo","minuto a minuto",
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
    "shocking","you should know","reasons to","things to know","what to know",
    # promocional / produto / institucional / local (nao e noticia de mercado da empresa)
    "credit cards","switch bonus","cashback","melhor cartao","vagas gratuitas",
    "inscricoes abertas","concurso publico","feira noturna","policia civil",
    "policia militar","habitat shapes","zoo orbs"]

# Manchetes de CHAMADA DE ANALISTA / RATING: quando um BANCO aparece no titulo porque ELE
# esta dando recomendacao/preco-alvo/rating de OUTRA empresa, a noticia e sobre a empresa
# avaliada, nao sobre o banco -> rejeitada PARA O BANCO (ver validar). Termos PT + EN.
ANALISTA_TITULO = [
    # Portugues
    "preco-alvo", "preco alvo", "recomendacao", "rebaixa", "rebaixou", "rebaixaram",
    "inicia cobertura", "retoma cobertura", "reitera compra", "reitera venda",
    "reitera recomendacao", "potencial de valorizacao", "ve potencial", "projeta alta de",
    "projeta queda", "corta preco", "reduz preco", "eleva preco", "aumenta preco",
    "elevou o preco", "cortou o preco", "reduziu o preco",
    # Ingles
    "price target", "target price", "raises target", "cuts target", "lowers target",
    "boosts target", "trims target", "raises pt", "cuts pt", "lifts pt", "lowers pt",
    "downgrade", "downgrades", "downgraded", "upgrade", "upgrades", "upgraded",
    "initiates coverage", "initiated coverage", "reinstates coverage", "resumes coverage",
    "outperform", "underperform", "overweight", "underweight", "buy rating", "sell rating",
    "hold rating", "neutral rating", "equal weight", "market perform", "top pick", "top picks",
    # genericos (pegam variantes "trims its target", "cuts X PT to", "cuts stock rating"...).
    # So se aplicam a emissor BANCO (ver validar) e com excecao de agencia de rating.
    "target", "rating", "pt to", "reiterates", "initiates", "trims", "lifts", "raises pt"]
# Agencias de rating: se o titulo cita uma agencia, quem foi avaliado e o proprio banco
# (ex.: "Moody's rebaixa o JPMorgan") -> NAO e chamada do banco sobre terceiro -> mantem.
AGENCIAS_RATING = ["fitch", "moody", "s&p", "s & p", "standard & poor", "austin rating",
    "lf rating", "dbrs", "sr rating"]

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Horario de Brasilia (UTC-3 fixo; o Brasil nao tem horario de verao desde 2019). Todas as
# datas internas sao tz-aware em UTC; a EXIBICAO (Excel/PDF/log) converte para BRT.
BRT = timezone(timedelta(hours=-3))

def fmt_brt(dt):
    """Formata um datetime (tz-aware) no horario de Brasilia: 'dd/mm HH:MM'."""
    try:
        return dt.astimezone(BRT).strftime("%d/%m %H:%M")
    except Exception:
        return ""


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

def _eh_call_de_research(titulo):
    """True se o titulo for uma chamada de analista/rating (preco-alvo, upgrade, downgrade,
    recomendacao...). Se citar uma AGENCIA de rating, retorna False (ai o avaliado e o
    proprio banco - e noticia legitima dele). Usado para tirar do BANCO as noticias em que
    ele apenas opina/avalia OUTRA empresa."""
    t = norm(titulo)
    if any(a in t for a in AGENCIAS_RATING):
        return False
    return any(term in t for term in ANALISTA_TITULO)

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
    # 1b) Se o emissor e um BANCO e o titulo e uma chamada de analista/rating (preco-alvo,
    # upgrade/downgrade, recomendacao...), a noticia e sobre a empresa AVALIADA, nao sobre o
    # banco -> rejeita para o banco. (Quando uma AGENCIA avalia o banco, _eh_call_de_research
    # devolve False e a noticia do banco e mantida.)
    if cfg.get("categoria", "").startswith("Banco") and _eh_call_de_research(titulo):
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

def buscar_gdelt(termo, maxrecords=GDELT_MAX):
    """Consulta o GDELT DOC API para uma query (ultimas 24h). Retorna lista de artigos.
    A query pode combinar empresas com OR, ex: '(Petrobras) OR (Vale mineracao)'.
    O GDELT limita a taxa de requisicoes: quando vier 429/erro, tenta de novo com
    backoff. Levanta a ultima excecao se TODAS as tentativas falharem."""
    params = {"query": termo, "mode": "ArtList", "maxrecords": str(maxrecords),
              "timespan": f"{JANELA_HORAS}h", "format": "json", "sort": "datedesc"}
    ultimo_erro = None
    for tentativa in range(GDELT_RETRIES):
        try:
            r = requests.get(GDELT_URL, params=params, headers=HEADERS, timeout=TIMEOUT + 6)
            if r.status_code == 200 and r.text.strip():
                try:
                    data = r.json()   # GDELT as vezes responde texto de erro em vez de JSON
                except ValueError:
                    data = None
                if data is not None:
                    return data.get("articles", []) or []
                ultimo_erro = "resposta nao-JSON"
            else:
                ultimo_erro = f"HTTP {r.status_code}"
                # 429 = o IP esta em cooldown no GDELT (tipico apos varias execucoes
                # seguidas). Re-tentar nao adianta e so trava o run -> desiste rapido.
                if r.status_code == 429:
                    raise RuntimeError("HTTP 429 (GDELT em cooldown para este IP)")
        except RuntimeError:
            raise
        except Exception as e:
            ultimo_erro = str(e)[:60]
        if tentativa < GDELT_RETRIES - 1:
            time.sleep(GDELT_PAUSA)
    if ultimo_erro:
        raise RuntimeError(ultimo_erro)
    return []


def _montar_lotes(empresas, tamanho):
    """Agrupa as empresas em lotes e monta uma query OR por lote. Cada empresa vira um
    grupo de FRASES EXATAS (entre aspas) unidas por OR, ex.: ("banco do brasil" OR "bb").
    Frase entre aspas = busca o nome exato (recall alto + precisao); NAO usa o campo
    'busca' antigo (que era E de palavras soltas e derrubava quase tudo). O setor fica
    so na validacao (validar)."""
    termos = []
    for nome, cfg in empresas.items():
        nomes = cfg.get("forte") or [nome]
        partes = " OR ".join(f'"{n}"' for n in nomes[:3])   # ate 3 variantes do nome
        termos.append(f"({partes})")
    lotes = [termos[i:i + tamanho] for i in range(0, len(termos), tamanho)]
    return [" OR ".join(l) for l in lotes]


def montar_candidato(titulo, link, fonte, data_obj, resumo=""):
    """Cria um candidato no formato que baixar_corpos/validar_todos esperam.
    Usado pelas fontes de imprensa (GDELT, RSS, API) para alimentar o mesmo pool."""
    return {"titulo": titulo, "link": link, "resumo": resumo, "fonte": fonte,
            "premium": eh_premium(fonte),
            "data": fmt_brt(data_obj), "data_obj": data_obj}


def coletar_candidatos(empresas):
    """Coleta no GDELT em POUCAS consultas (lotes com OR), dedup por link e titulo,
    janela de 24h. O GDELT limita a taxa por IP (HTTP 429); 28 buscas separadas a
    partir do IP compartilhado do GitHub eram barradas. Agrupando ~7 empresas por
    consulta caem para ~4 requisicoes, dentro do limite. A atribuicao da noticia a
    empresa certa e feita depois, no validar_todos (exige o nome no titulo)."""
    limite = datetime.now(timezone.utc) - timedelta(hours=JANELA_HORAS)
    queries = _montar_lotes(empresas, GDELT_BATCH)
    random.shuffle(queries)   # ordem aleatoria: um 429 no meio nao penaliza sempre os mesmos

    artigos = []
    n_erros = 0
    feitos = 0
    t0 = time.time()
    for i, q in enumerate(queries):
        if time.time() - t0 > GDELT_BUDGET:
            print(f"  GDELT: orcamento de tempo atingido ({GDELT_BUDGET}s); {feitos}/{len(queries)} lotes feitos")
            break
        try:
            artigos.extend(buscar_gdelt(q, maxrecords=GDELT_MAX))
            feitos += 1
        except Exception as e:
            n_erros += 1
            msg = str(e)[:50]
            print(f"  GDELT erro no lote {i + 1}/{len(queries)}: {msg}")
            # Se o IP esta em cooldown (429), os outros lotes tambem vao falhar:
            # nao adianta insistir, encerra a coleta e segue com o que tiver.
            if "429" in msg:
                print("  GDELT: IP em cooldown; pulando os lotes restantes")
                break
        if i < len(queries) - 1:
            time.sleep(GDELT_PAUSA)
    print(f"  GDELT: {feitos}/{len(queries)} lotes ok, {len(artigos)} artigos brutos, {n_erros} erros")

    # Dedup por link e por titulo normalizado; aplica janela de 24h e allowlist de fontes.
    candidatos = {}
    titulos_vistos = set()
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
        candidatos[link] = montar_candidato(titulo, link, fonte, data)
    return candidatos


def precisa_corpo(titulo, empresas):
    """True se o titulo cita um nome AMBIGUO (fraco) de alguma empresa SEM um nome forte
    junto — esses precisam do corpo para confirmar o contexto. Quando ha nome forte no
    titulo, a validacao passa sem corpo; assim baixamos o corpo so quando importa."""
    for cfg in empresas.values():
        if conta(titulo, cfg["forte"]) == 0 and conta(titulo, cfg.get("fraco", [])) > 0:
            return True
    return False


def _baixar_tarefa(link):
    """Tarefa de download rodada em PROCESSO isolado (resiste a crash nativo do parser)."""
    real = link_real(link)
    corpo, data_pub = baixar(real)
    return link, real, corpo, data_pub


def baixar_corpos(candidatos):
    """Baixa os corpos em PROCESSOS isolados. Se o parser (lxml/trafilatura) abortar
    com crash nativo num artigo, o processo morre mas o run continua com o resto.
    Retorna {link: (link_real, corpo, data_pub)}."""
    resultados = {l: (l, "", None) for l in candidatos}   # default = sem corpo
    resolvidos = set()
    t0 = time.time()
    for tentativa in range(3):                             # ate 3 passadas; recupera apos crash
        pendentes = [l for l in candidatos if l not in resolvidos]
        if not pendentes:
            break
        try:
            with ProcessPoolExecutor(max_workers=WORKERS) as ex:
                futuros = {ex.submit(_baixar_tarefa, l): l for l in pendentes}
                for fut in as_completed(futuros):
                    l = futuros[fut]
                    try:
                        link, real, corpo, data_pub = fut.result()
                        resultados[link] = (real, corpo, data_pub)
                    except Exception:
                        pass
                    resolvidos.add(l)
        except BrokenProcessPool:
            print(f"  aviso: parser abortou num artigo (passada {tentativa+1}); seguindo com o resto")
    pulados = len(candidatos) - len(resolvidos)
    print(f"  download concluido em {time.time()-t0:.0f}s "
          f"({len(resolvidos)}/{len(candidatos)} ok, {pulados} pulados)")
    return resultados


def validar_todos(candidatos, corpos, empresas):
    """Valida cada candidato e escolhe a empresa de maior score. Top N por ativo.
    Janela de 24h pelo TIMESTAMP exato de publicacao (data_obj, em UTC) - igual para
    todas as fontes. O corpo (quando baixado) so serve para confirmar contexto/IA."""
    validadas = {}
    sem_corpo = 0
    fora_janela = 0
    limite = datetime.now(timezone.utc) - timedelta(hours=JANELA_HORAS)
    for link, c in candidatos.items():
        real, corpo, data_pub = corpos.get(link, (link, "", None))
        # Corte exato pela janela de 24h, pelo horario de publicacao (data_obj).
        if c.get("data_obj") is None or c["data_obj"] < limite:
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
