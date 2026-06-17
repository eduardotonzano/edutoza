"""Resumo e impacto de cada noticia via Google Gemini (gemini-2.0-flash) - GRATUITO.

Usa a API do Google AI Studio (free tier generoso, sem cartao). Opcional: so roda se
a variavel de ambiente GEMINI_API_KEY existir. Sem a chave, preencher_resumos() vira
um no-op (colunas RESUMO IA / IMPACTO ficam vazias) e o pipeline continua. Falha por
noticia e silenciosa (nao derruba o run). Pegue a chave em https://aistudio.google.com.
"""

import os, json, time, requests
from concurrent.futures import ThreadPoolExecutor, as_completed

MODELO  = "gemini-1.5-flash"   # gratuito e amplamente liberado no free tier (15 req/min)
WORKERS = 3                    # resumos simultaneos
TIMEOUT = 30
TENTATIVAS = 3                 # re-tenta em caso de 429 (limite por minuto)
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
            "maxOutputTokens": 500,
            "temperature": 0.2,
        },
    }
    for tentativa in range(TENTATIVAS):
        try:
            r = requests.post(_URL.format(m=MODELO), params={"key": chave},
                              json=body, timeout=TIMEOUT)
            if r.status_code == 429:               # limite por minuto -> espera e re-tenta
                if tentativa < TENTATIVAS - 1:
                    time.sleep(12 * (tentativa + 1))
                    continue
                print(f"  IA 429 (quota) em '{titulo[:35]}': {r.text[:200]}")
                return "", ""
            if r.status_code != 200:
                print(f"  IA HTTP {r.status_code} em '{titulo[:35]}': {r.text[:200]}")
                return "", ""
            cand = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            d = json.loads(cand)
            return (d.get("resumo", "") or "").strip(), (d.get("impacto", "") or "").strip()
        except Exception as e:
            print(f"  IA falhou em '{titulo[:35]}': {str(e)[:80]}")
            return "", ""
    return "", ""


def preencher_resumos(finais):
    """Preenche resumo_ia e impacto de cada noticia (em paralelo). No-op sem GEMINI_API_KEY.
    Retorna a quantidade de resumos gerados com sucesso."""
    chave = os.environ.get("GEMINI_API_KEY")
    if not chave or not finais:
        return 0

    def tarefa(n):
        return n, _resumir_um(chave, n["nome"], n["titulo"], n.get("corpo", ""))

    feitos = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futuros = [ex.submit(tarefa, n) for n in finais]
        for fut in as_completed(futuros):
            n, (resumo, impacto) = fut.result()
            n["resumo_ia"] = resumo
            n["impacto"]   = impacto
            if resumo:
                feitos += 1
    return feitos
