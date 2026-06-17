"""Resumo e impacto de cada noticia via Claude Haiku (claude-haiku-4-5).

Opcional: so roda se a variavel de ambiente ANTHROPIC_API_KEY existir. Sem chave,
preencher_resumos() vira um no-op (as colunas RESUMO IA / IMPACTO ficam vazias)
e o pipeline continua normalmente. Falha por noticia e silenciosa (nao derruba o run).
"""

import os, json
from concurrent.futures import ThreadPoolExecutor, as_completed

MODELO  = "claude-haiku-4-5"   # rapido e barato, ideal para sumarizacao
WORKERS = 4                    # resumos simultaneos
ATIVADO = bool(os.environ.get("ANTHROPIC_API_KEY"))

# Estrutura de saida garantida (structured outputs) - so resumo + impacto.
_SCHEMA = {
    "type": "object",
    "properties": {
        "resumo":  {"type": "string"},
        "impacto": {"type": "string"},
    },
    "required": ["resumo", "impacto"],
    "additionalProperties": False,
}


def _resumir_um(client, nome, titulo, corpo):
    """Chama o Haiku para uma noticia. Retorna (resumo, impacto) ou ('','') em falha."""
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
    try:
        r = client.messages.create(
            model=MODELO,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
            output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
        )
        txt = next(b.text for b in r.content if b.type == "text")
        d = json.loads(txt)
        return (d.get("resumo", "") or "").strip(), (d.get("impacto", "") or "").strip()
    except Exception as e:
        print(f"  IA falhou em '{titulo[:40]}': {str(e)[:60]}")
        return "", ""


def preencher_resumos(finais):
    """Preenche resumo_ia e impacto de cada noticia (em paralelo). No-op sem API key.
    Retorna a quantidade de resumos gerados com sucesso."""
    if not ATIVADO or not finais:
        return 0
    import anthropic
    client = anthropic.Anthropic()   # le ANTHROPIC_API_KEY do ambiente

    def tarefa(n):
        return n, _resumir_um(client, n["nome"], n["titulo"], n.get("corpo", ""))

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
