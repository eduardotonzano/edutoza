"""Resumo de IA: um RESUMO da propria noticia em 1 paragrafo (+ etiqueta de impacto).

Coordenador de dois backends GRATUITOS (nada de API paga):
  - Google Gemini (aqui) = PRINCIPAL, se GEMINI_API_KEY existir (gratuito).
  - Claude Code / Haiku (resumo_claude.py) = RESERVA, se CLAUDE_CODE_OAUTH_TOKEN existir
    (roda pela ASSINATURA Pro/Max do dono, sem custo de API a parte).

Funciona em 2 passes: 1) Gemini por item (em paralelo) ate a cota gratuita estourar;
2) Claude Code/Haiku EM LOTES cobre o que sobrou. A etapa toda e limitada por tempo
(IA_BUDGET). O que nao for resumido usa o titulo no PDF.

Saida: resumo (1 paragrafo com os fatos da noticia, sem opiniao/analise).
"""

import os, json, time, threading, requests
from concurrent.futures import ThreadPoolExecutor, as_completed

import resumo_claude

# --- Gemini (principal) ---
MODELOS = ["gemini-2.5-flash-lite", "gemini-2.0-flash-lite", "gemini-2.5-flash",
           "gemini-flash-latest", "gemini-2.0-flash"]
_URL = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
_SCHEMA = {"type": "object", "properties": {"resumo": {"type": "string"}},
           "required": ["resumo"]}

WORKERS = 2
TIMEOUT = 30
IA_BUDGET = 420                # teto de tempo (s) p/ a etapa inteira (Gemini + Claude Code)
MAX_FALHAS = 8                 # falhas seguidas do Gemini -> passa p/ a reserva
LOTE_CLAUDE = 6                # noticias por chamada do CLI do Claude Code
LIMITE_HAIKU = 40              # teto de noticias/dia resumidas pelo Haiku (poupa a assinatura)
PAUSA_GEMINI = 0.5             # s entre chamadas do Gemini (respeita o limite do plano gratis)

ATIVADO = bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"))


def _prompt(nome, titulo, texto):
    return (f"Empresa/ativo: {nome}.\nNOTICIA:\nTITULO: {titulo}\nTEXTO: {texto}\n\n"
            'Responda em portugues, SOMENTE com um JSON com a chave exata "resumo": um RESUMO '
            "da propria noticia, em 1 paragrafo (3 a 5 frases), com os fatos principais (o que "
            "aconteceu, numeros, contexto). Apenas os fatos, sem opiniao, analise ou recomendacao.")


def _prompt_lote(itens):
    """Pede um JSON com a lista de resultados NA MESMA ORDEM (usado pelo Claude Code)."""
    blocos = []
    for i, n in enumerate(itens, 1):
        texto = (n.get("corpo", "") or "").strip()[:1500] or n.get("titulo", "")
        blocos.append(f"--- NOTICIA {i} ---\nEMPRESA: {n['nome']}\n"
                      f"TITULO: {n['titulo']}\nTEXTO: {texto}")
    corpo = "\n\n".join(blocos)
    return (f"Abaixo ha {len(itens)} noticias.\n\n{corpo}\n\n"
            "Responda em portugues, SOMENTE com um JSON valido (sem texto fora dele) neste "
            'formato:\n{"itens": [{"resumo": "..."}]}\n'
            f"A lista deve ter EXATAMENTE {len(itens)} objetos, NA MESMA ORDEM das noticias. "
            'Em cada objeto: "resumo"=um resumo da propria noticia em 1 paragrafo (3 a 5 '
            "frases) com os fatos principais, apenas os fatos, sem opiniao/analise/recomendacao.")


def _resumir_gemini(chave, nome, titulo, corpo):
    """Tenta cada modelo Gemini. Retorna (resumo, 200) ou (None, status)."""
    texto = (corpo or "").strip()[:3000] or titulo
    body = {"contents": [{"parts": [{"text": _prompt(nome, titulo, texto)}]}],
            "generationConfig": {"responseMimeType": "application/json", "responseSchema": _SCHEMA,
                                 "maxOutputTokens": 2048, "temperature": 0.2}}
    ultimo = "?"
    for modelo in MODELOS:
        # Ate 2 tentativas por modelo: em 429 (limite de taxa) ou erro de conexao, espera e
        # tenta de novo antes de pular para o proximo modelo (aproveita melhor a cota gratis).
        for tentativa in range(2):
            try:
                r = requests.post(_URL.format(m=modelo), params={"key": chave}, json=body, timeout=TIMEOUT)
                if r.status_code == 200:
                    cand = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                    d = json.loads(cand)
                    return (d.get("resumo", "") or "").strip(), 200
                ultimo = r.status_code
                if r.status_code == 429 and tentativa == 0:
                    time.sleep(2)               # backoff e tenta o mesmo modelo 1x
                    continue
                break                            # outro erro -> proximo modelo
            except Exception as e:
                ultimo = str(e)[:30]
                if tentativa == 0:
                    time.sleep(1)
                    continue
    return None, ultimo


def _passe_gemini(finais, chave, t0):
    """Passe 1: Gemini por item, em paralelo. Para apos MAX_FALHAS seguidas ou no budget."""
    pendentes = [n for n in finais if not n.get("resumo_ia")]
    parar = threading.Event()
    falhas = {"n": 0}
    feitos = {"n": 0}
    trava = threading.Lock()

    def tarefa(n):
        if parar.is_set():
            return n, None, None
        time.sleep(PAUSA_GEMINI)   # ritmo: evita rajada que dispara 429 no plano gratis
        f, st = _resumir_gemini(chave, n["nome"], n["titulo"], n.get("corpo", ""))
        return n, f, st

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futuros = [ex.submit(tarefa, n) for n in pendentes]
        for fut in as_completed(futuros):
            n, f, st = fut.result()
            with trava:
                if f:
                    n["resumo_ia"] = f
                    feitos["n"] += 1
                    falhas["n"] = 0
                elif st is not None:
                    falhas["n"] += 1
                    if falhas["n"] >= MAX_FALHAS and not parar.is_set():
                        print("  IA: Gemini esgotado/limite; passando para o Claude Code")
                        parar.set()
                if time.time() - t0 > IA_BUDGET:
                    parar.set()
    return feitos["n"]


def _passe_claude(finais, t0):
    """Passe 2: Claude Code/Haiku em lotes p/ o que ficou sem resumo. Reserva da assinatura."""
    pendentes = [n for n in finais if not n.get("resumo_ia")]
    if not pendentes:
        return 0
    # Teto diario: o Haiku roda pela assinatura Pro/Max (cota semanal); limita quantas
    # noticias ele cobre por dia para nao pesar. O que passar do teto fica sem resumo de IA
    # (no PDF cai para o proprio titulo).
    if len(pendentes) > LIMITE_HAIKU:
        print(f"  IA: Claude Code limitado a {LIMITE_HAIKU}/{len(pendentes)} pendentes (teto diario)")
        pendentes = pendentes[:LIMITE_HAIKU]
    feitos = falhas = 0
    for i in range(0, len(pendentes), LOTE_CLAUDE):
        if time.time() - t0 > IA_BUDGET:
            print("  IA: tempo esgotado; encerrando o Claude Code")
            break
        lote = pendentes[i:i + LOTE_CLAUDE]
        res, st = resumo_claude.resumir_lote(lote, _prompt_lote)
        if not res:
            falhas += 1
            if st == "sem-cli" or falhas >= 3:
                print(f"  IA: Claude Code indisponivel (status {st}); encerrando")
                break
            continue
        falhas = 0
        for n, resumo in zip(lote, res):
            if resumo:
                n["resumo_ia"] = resumo
                feitos += 1
    return feitos


def preencher_resumos(finais):
    """Preenche resumo_ia/otimista/cetico/impacto. Gemini principal + Claude Code reserva,
    limitado por tempo. Retorna nº de itens resumidos."""
    gk = os.environ.get("GEMINI_API_KEY")
    usa_claude = resumo_claude.ATIVADO
    if (not gk and not usa_claude) or not finais:
        return 0

    t0 = time.time()
    g = _passe_gemini(finais, gk, t0) if gk else 0
    c = _passe_claude(finais, t0) if (usa_claude and time.time() - t0 < IA_BUDGET) else 0

    total = g + c
    print(f"  IA: {total}/{len(finais)} resumos (Gemini {g} | Claude Code {c})")
    return total
