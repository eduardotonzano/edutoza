"""Resumo de IA com DOIS analistas (otimista x cetico) por noticia.

Coordenador de dois backends:
  - Claude Haiku (resumo_claude.py) = PRINCIPAL, se ANTHROPIC_API_KEY existir (pago).
  - Google Gemini (aqui) = RESERVA gratuita, se GEMINI_API_KEY existir.
Para cada noticia tenta o Claude; se falhar, cai para o Gemini. A etapa e LIMITADA por
tempo (IA_BUDGET) e por cooldown (apos varias falhas seguidas de um provedor, para de usa-lo)
para nunca travar o run. O que nao for resumido usa o titulo no PDF.

Saida (4 campos): resumo (fato neutro), otimista (analista bull), cetico (analista bear),
impacto (Positivo/Negativo/Neutro + justificativa).
"""

import os, json, time, threading, requests
from concurrent.futures import ThreadPoolExecutor, as_completed

import resumo_claude

# --- Gemini (reserva) ---
MODELOS = ["gemini-2.5-flash-lite", "gemini-2.0-flash-lite", "gemini-2.5-flash",
           "gemini-flash-latest", "gemini-2.0-flash"]
_URL = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
_SCHEMA = {"type": "object", "properties": {
    "resumo": {"type": "string"}, "otimista": {"type": "string"},
    "cetico": {"type": "string"}, "impacto": {"type": "string"}},
    "required": ["resumo", "otimista", "cetico", "impacto"]}

WORKERS = 2
TIMEOUT = 30
IA_BUDGET = 180                # teto de tempo (s) p/ a etapa inteira
MAX_FALHAS = 8                 # falhas seguidas de um provedor -> para de usa-lo (cooldown)

ATIVADO = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("GEMINI_API_KEY"))


def _prompt(nome, titulo, texto):
    return (f"Empresa: {nome}.\nNOTICIA:\nTITULO: {titulo}\nTEXTO: {texto}\n\n"
            "Responda em portugues, SOMENTE com um JSON com estas chaves exatas:\n"
            '- "resumo": 1 frase neutra com o fato principal (sem opiniao).\n'
            '- "otimista": parecer de um analista OTIMISTA sobre a tese de investimento '
            f'em {nome} (por que e bom), 1 frase.\n'
            '- "cetico": parecer de um analista CETICO (riscos/contraponto), 1 frase.\n'
            '- "impacto": comece com Positivo, Negativo ou Neutro, + meia frase de justificativa.')


def _resumir_gemini(chave, nome, titulo, corpo):
    """Tenta cada modelo Gemini uma vez. Retorna (fields4, 200) ou (None, status)."""
    texto = (corpo or "").strip()[:3000] or titulo
    body = {"contents": [{"parts": [{"text": _prompt(nome, titulo, texto)}]}],
            "generationConfig": {"responseMimeType": "application/json", "responseSchema": _SCHEMA,
                                 "maxOutputTokens": 2048, "temperature": 0.2}}
    ultimo = "?"
    for modelo in MODELOS:
        try:
            r = requests.post(_URL.format(m=modelo), params={"key": chave}, json=body, timeout=TIMEOUT)
            if r.status_code == 200:
                cand = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                d = json.loads(cand)
                return ((d.get("resumo", "") or "").strip(), (d.get("otimista", "") or "").strip(),
                        (d.get("cetico", "") or "").strip(), (d.get("impacto", "") or "").strip()), 200
            ultimo = r.status_code
        except Exception as e:
            ultimo = str(e)[:30]
    return None, ultimo


def preencher_resumos(finais):
    """Preenche resumo_ia/otimista/cetico/impacto de cada noticia. Claude principal +
    Gemini reserva, limitado por tempo e cooldown. Retorna nº de itens resumidos."""
    ck = os.environ.get("ANTHROPIC_API_KEY")
    gk = os.environ.get("GEMINI_API_KEY")
    if (not ck and not gk) or not finais:
        return 0

    t0 = time.time()
    parar = threading.Event()
    claude_stop = threading.Event()
    gem_stop = threading.Event()
    if not ck:
        claude_stop.set()
    if not gk:
        gem_stop.set()

    def tarefa(n):
        if parar.is_set():
            return n, None, None, None, None
        nome, titulo, corpo = n["nome"], n["titulo"], n.get("corpo", "")
        cstatus = gstatus = None
        if ck and not claude_stop.is_set():
            f, st = resumo_claude.resumir(ck, nome, titulo, corpo, _prompt)
            if f:
                return n, f, "claude", None, None
            cstatus = st
        if gk and not gem_stop.is_set():
            f, st = _resumir_gemini(gk, nome, titulo, corpo)
            if f:
                return n, f, "gemini", cstatus, None
            gstatus = st
        return n, None, None, cstatus, gstatus

    feitos = {"claude": 0, "gemini": 0}
    cl_falhas = gm_falhas = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futuros = [ex.submit(tarefa, n) for n in finais]
        for fut in as_completed(futuros):
            n, fields, prov, cstatus, gstatus = fut.result()
            if fields:
                n["resumo_ia"], n["otimista"], n["cetico"], n["impacto"] = fields
                feitos[prov] += 1
            # cooldown do Claude: erro de credito/chave (401/403) para na hora
            if cstatus is not None:
                cl_falhas += 1
                if cstatus in (401, 403) or cl_falhas >= MAX_FALHAS:
                    if not claude_stop.is_set():
                        print(f"  IA: Claude indisponivel (status {cstatus}); usando Gemini")
                    claude_stop.set()
            elif prov == "claude":
                cl_falhas = 0
            if gstatus is not None:
                gm_falhas += 1
                if gm_falhas >= MAX_FALHAS and not gem_stop.is_set():
                    print("  IA: Gemini esgotado/limite; parando os resumos")
                    gem_stop.set()
            elif prov == "gemini":
                gm_falhas = 0
            if (claude_stop.is_set() and gem_stop.is_set()) or (time.time() - t0 > IA_BUDGET):
                parar.set()

    total = feitos["claude"] + feitos["gemini"]
    print(f"  IA: {total}/{len(finais)} resumos (Claude {feitos['claude']} | Gemini {feitos['gemini']})")
    return total
