"""Backend de resumo via Claude Haiku (API da Anthropic) - PRINCIPAL (pago).

Gera, para cada noticia, a visao de DOIS analistas (otimista x cetico) + resumo + impacto.
So roda se ANTHROPIC_API_KEY existir. Uma falha devolve (None, status) e o coordenador
(resumo_ia.py) cai para o Gemini (gratuito) como reserva.
"""

import os, json, re, requests

MODELO = "claude-haiku-4-5"
URL = "https://api.anthropic.com/v1/messages"
TIMEOUT = 40
ATIVADO = bool(os.environ.get("ANTHROPIC_API_KEY"))


def _extrai_json(t):
    """Extrai o objeto JSON da resposta (tolerante a texto em volta)."""
    try:
        return json.loads(t)
    except Exception:
        pass
    m = re.search(r"\{.*\}", t or "", re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None


def resumir(chave, nome, titulo, corpo, prompt_fn):
    """Chama o Claude Haiku. Retorna ((resumo, otimista, cetico, impacto), 200) ou
    (None, status) em falha. `prompt_fn(nome, titulo, texto)` monta o pedido (compartilhado
    com o backend Gemini, para a saida ser identica)."""
    texto = (corpo or "").strip()[:3000] or titulo
    body = {
        "model": MODELO,
        "max_tokens": 600,
        "system": ("Voce e uma mesa de research buy-side com dois analistas. "
                   "Responda SOMENTE com um JSON valido, sem texto fora do JSON."),
        "messages": [{"role": "user", "content": prompt_fn(nome, titulo, texto)}],
    }
    try:
        r = requests.post(URL, headers={"x-api-key": chave,
                                        "anthropic-version": "2023-06-01",
                                        "content-type": "application/json"},
                          json=body, timeout=TIMEOUT)
        if r.status_code != 200:
            return None, r.status_code
        txt = r.json()["content"][0]["text"]
        d = _extrai_json(txt)
        if not d:
            return None, "parse"
        return ((d.get("resumo", "") or "").strip(), (d.get("otimista", "") or "").strip(),
                (d.get("cetico", "") or "").strip(), (d.get("impacto", "") or "").strip()), 200
    except Exception as e:
        return None, str(e)[:40]
