"""Backend de resumo via Claude Code (Haiku) em modo headless - RESERVA gratuita.

Em vez da API paga da Anthropic, invoca o CLI do Claude Code
(`claude -p ... --model claude-haiku-4-5 --output-format json`), autenticado pela ASSINATURA
Pro/Max do dono atraves da env CLAUDE_CODE_OAUTH_TOKEN (gerada com `claude setup-token`).
Gera, por noticia, a visao de DOIS analistas (otimista x cetico) + resumo + impacto.

So fica ATIVADO se CLAUDE_CODE_OAUTH_TOKEN existir E o binario `claude` estiver no PATH.
Trabalha em LOTES (varias noticias por chamada) para diluir o custo de subir o processo do
CLI. Qualquer falha devolve (None, motivo); o coordenador (resumo_ia.py) usa o Gemini como
principal e este como reserva.
"""

import os, json, re, shutil, subprocess

MODELO = "claude-haiku-4-5"
TIMEOUT = 120  # segundos por chamada do CLI (um lote)
ATIVADO = bool(os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")) and bool(shutil.which("claude"))


def _extrai_json(t):
    """Extrai um objeto OU lista JSON da resposta (tolerante a texto em volta)."""
    if not t:
        return None
    try:
        return json.loads(t)
    except Exception:
        pass
    for padrao in (r"\{.*\}", r"\[.*\]"):
        m = re.search(padrao, t, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                continue
    return None


def _chamar_cli(prompt, timeout=TIMEOUT):
    """Roda o Claude Code headless. Retorna (texto_do_modelo, None) ou (None, motivo)."""
    if not shutil.which("claude"):
        return None, "sem-cli"
    # Apenas geracao de texto (sem ferramentas): --max-turns 1 garante uma unica resposta
    # e o timeout do subprocess e a rede de seguranca. NAO usamos
    # --dangerously-skip-permissions: o job roda sozinho sobre noticias de fontes externas,
    # entao nao concedemos acesso a ferramentas/sistema ao agente.
    cmd = ["claude", "-p", prompt, "--model", MODELO,
           "--output-format", "json", "--max-turns", "1"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                              env={**os.environ})
    except subprocess.TimeoutExpired:
        return None, "timeout"
    except Exception as e:
        return None, str(e)[:40]
    if proc.returncode != 0:
        return None, f"rc{proc.returncode}:{(proc.stderr or '')[:60]}"
    env = _extrai_json(proc.stdout)
    if isinstance(env, dict) and "result" in env:   # envelope --output-format json
        return env.get("result") or "", None
    if proc.stdout:                                  # fallback: texto direto
        return proc.stdout, None
    return None, "vazio"


def _campos(o):
    return ((o.get("resumo", "") or "").strip(), (o.get("otimista", "") or "").strip(),
            (o.get("cetico", "") or "").strip(), (o.get("impacto", "") or "").strip())


def resumir_lote(itens, prompt_lote_fn, timeout=TIMEOUT):
    """Resume varias noticias numa unica chamada do CLI.

    itens: lista de dicts (nome/titulo/corpo). prompt_lote_fn(itens) monta o pedido pedindo
    um JSON com a lista de resultados NA MESMA ORDEM. Retorna (lista_de_tuplas, 200) onde
    cada elemento e (resumo, otimista, cetico, impacto) ou None; ou (None, motivo) em falha.
    """
    if not itens:
        return [], 200
    texto, err = _chamar_cli(prompt_lote_fn(itens), timeout)
    if texto is None:
        return None, err
    d = _extrai_json(texto)
    arr = None
    if isinstance(d, dict):
        arr = d.get("itens") or d.get("resumos") or d.get("results")
    elif isinstance(d, list):
        arr = d
    if not isinstance(arr, list):
        return None, "parse"
    out = []
    for i in range(len(itens)):
        o = arr[i] if i < len(arr) and isinstance(arr[i], dict) else None
        out.append(_campos(o) if o else None)
    return out, 200
