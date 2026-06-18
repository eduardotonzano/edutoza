"""Resumo e impacto de cada noticia via Google Gemini (gemini-2.0-flash) - GRATUITO.

Usa a API do Google AI Studio (free tier generoso, sem cartao). Opcional: so roda se
a variavel de ambiente GEMINI_API_KEY existir. Sem a chave, preencher_resumos() vira
um no-op (colunas RESUMO IA / IMPACTO ficam vazias) e o pipeline continua. Falha por
noticia e silenciosa (nao derruba o run). Pegue a chave em https://aistudio.google.com.
"""

import os, json, time, threading, requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# Tenta os modelos nesta ordem; comeca pelos "lite" (cota/RPM maior no free tier) p/
# aguentar o volume de noticias sem estourar o limite de velocidade. 404/429 -> proximo.
MODELOS = ["gemini-2.5-flash-lite", "gemini-2.0-flash-lite", "gemini-2.5-flash",
           "gemini-flash-latest", "gemini-2.0-flash"]
WORKERS = 2                    # resumos simultaneos (poucos: respeita o RPM do free tier)
RODADAS = 2                    # rodadas de re-tentativa por item (curto p/ nao travar)
TIMEOUT = 30
IA_BUDGET = 150                # teto de tempo (s) p/ a etapa de IA inteira
MAX_FALHAS_SEGUIDAS = 8        # apos N falhas seguidas, assume cota esgotada e para (cooldown)
ATIVADO = bool(os.environ.get("GEMINI_API_KEY"))
_URL = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"

# Saida estruturada garantida (JSON) - so resumo + impacto.
_SCHEMA = {
    "type": "object",
    "properties": {
        "resumo":  {"type": "string"},
        "impacto": {"type": "string"},
    },
    "required": ["resumo", "impacto"],
}


def _resumir_um(chave, nome, titulo, corpo):
    """Chama o Gemini para uma noticia. Retorna (resumo, impacto) ou ('','') em falha."""
    texto = (corpo or "").strip()[:3000] or titulo
    prompt = (
        f"Voce e um analista de research buy-side. A noticia abaixo e sobre a empresa "
        f"{nome} (um ativo da carteira).\n\n"
        f"TITULO: {titulo}\n\nTEXTO: {texto}\n\n"
        "Responda em portugues, de forma objetiva e curta:\n"
        "- resumo: 1 a 2 frases com o fato principal, sem opiniao.\n"
        f"- impacto: comece com 'Positivo', 'Negativo' ou 'Neutro' para a tese de "
        f"investimento em {nome}, seguido de meia frase de justificativa."
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": _SCHEMA,
            # Folga grande: os modelos 2.5 "pensam" antes de responder e o pensamento
            # consome o orcamento; com pouco teto o JSON volta cortado ("Unterminated
            # string"). 2048 deixa espaco para o raciocinio + o JSON completo.
            "maxOutputTokens": 2048,
            "temperature": 0.2,
        },
    }
    # Varias rodadas pela lista de modelos, com espera entre elas: sob rate limit (429)
    # ou erro de conexao, re-tenta ate conseguir, em vez de desistir na primeira.
    for rodada in range(RODADAS):
        for modelo in MODELOS:
            try:
                r = requests.post(_URL.format(m=modelo), params={"key": chave},
                                  json=body, timeout=TIMEOUT)
                if r.status_code == 200:
                    cand = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                    d = json.loads(cand)
                    return ((d.get("resumo", "") or "").strip(),
                            (d.get("impacto", "") or "").strip())
                # 404 = modelo indisponivel; 429/503 = limite/sobrecarga -> proximo modelo
            except Exception:
                continue
        if rodada < RODADAS - 1:
            time.sleep(2 * (rodada + 1))           # backoff so entre rodadas
    return "", ""


def preencher_resumos(finais):
    """Preenche resumo_ia e impacto de cada noticia (em paralelo). No-op sem GEMINI_API_KEY.
    LIMITADO: para apos IA_BUDGET segundos OU apos MAX_FALHAS_SEGUIDAS falhas seguidas
    (cota do free tier esgotada) - assim nunca trava o run. O que nao for resumido cai para
    o titulo no PDF. Retorna a quantidade de resumos gerados com sucesso."""
    chave = os.environ.get("GEMINI_API_KEY")
    if not chave or not finais:
        return 0
    t0 = time.time()
    parar = threading.Event()           # sinaliza cota esgotada/tempo estourado p/ as threads

    def tarefa(n):
        if parar.is_set():
            return n, ("", "")
        return n, _resumir_um(chave, n["nome"], n["titulo"], n.get("corpo", ""))

    feitos = 0
    falhas_seguidas = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futuros = [ex.submit(tarefa, n) for n in finais]
        for fut in as_completed(futuros):
            n, (resumo, impacto) = fut.result()
            n["resumo_ia"] = resumo
            n["impacto"]   = impacto
            if resumo:
                feitos += 1
                falhas_seguidas = 0
            else:
                falhas_seguidas += 1
            # Para de insistir se a cota parece esgotada ou o tempo estourou (itens
            # restantes ficam sem resumo e usam o titulo no PDF).
            if falhas_seguidas >= MAX_FALHAS_SEGUIDAS and not parar.is_set():
                print(f"  IA: {MAX_FALHAS_SEGUIDAS} falhas seguidas (cota/limite); parando os resumos")
                parar.set()
            if time.time() - t0 > IA_BUDGET and not parar.is_set():
                print(f"  IA: tempo de {IA_BUDGET}s atingido; parando os resumos")
                parar.set()
    return feitos
