"""Resumo e impacto de cada noticia via Google Gemini (gemini-2.0-flash) - GRATUITO.

Usa a API do Google AI Studio (free tier generoso, sem cartao). Opcional: so roda se
a variavel de ambiente GEMINI_API_KEY existir. Sem a chave, preencher_resumos() vira
um no-op (colunas RESUMO IA / IMPACTO ficam vazias) e o pipeline continua. Falha por
noticia e silenciosa (nao derruba o run). Pegue a chave em https://aistudio.google.com.
"""

import os, json, requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# Tenta os modelos nesta ordem; usa o primeiro que responder (404/429 -> proximo).
# Todos sao gratuitos no free tier do Google AI Studio. Edite a ordem se quiser.
MODELOS = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-flash-latest",
           "gemini-2.0-flash-lite", "gemini-2.0-flash"]
WORKERS = 3                    # resumos simultaneos
TIMEOUT = 30
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
    for modelo in MODELOS:                         # tenta cada modelo; 404/429 -> proximo
        try:
            r = requests.post(_URL.format(m=modelo), params={"key": chave},
                              json=body, timeout=TIMEOUT)
            if r.status_code in (404, 429):
                continue
            if r.status_code != 200:
                print(f"  IA HTTP {r.status_code} ({modelo}): {r.text[:150]}")
                continue
            cand = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            d = json.loads(cand)
            return (d.get("resumo", "") or "").strip(), (d.get("impacto", "") or "").strip()
        except Exception as e:
            print(f"  IA erro ({modelo}) em '{titulo[:30]}': {str(e)[:70]}")
            continue
    print(f"  IA: nenhum modelo respondeu para '{titulo[:35]}'")
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
