"""ALERTA INTRADAY (separado do relatorio diario das 17h).

Roda de tempos em tempos (a cada ~30 min) e avisa por e-mail, NA HORA, quando sai algo novo
das fontes OFICIAIS de fundos + RI das gestoras:
  - Fundos.NET (CVM/B3): fato relevante / rendimento / relatorio de FIIs e FIDCs (fundos_net.py)
  - RI das gestoras (best-effort, ri_scraping.py)

Mantem um ESTADO (alertas_estado.json) com o que ja foi avisado, para nao repetir. So
escreve corpo de e-mail e marca 'NOVOS' quando ha item inedito. Tudo com falha silenciosa.
"""

import os, csv, json, unicodedata
from datetime import datetime, timezone, timedelta

from emissores import EMISSORES
from fundos_net import buscar_fnet
from ri_scraping import raspar_ris

ESTADO = "alertas_estado.json"
CORPO = "alerta_corpo.html"
JANELA_MIN = int(os.environ.get("ALERTA_JANELA_MIN", "90"))   # cobre o intervalo + folga
BRT = timezone(timedelta(hours=-3))
_STOP = (" fidc", " fic ", " fic", " fundo", " fif", " fi ", " | ", " - ")


def _norm(t):
    return " ".join(unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore")
                    .decode("ascii").lower().split())


def _tokens_fundos(csv_path="carteira_completa.csv"):
    """Monta os tokens p/ casar no Fundos.NET: FIIs vem do registro (nome+ticker); FIDCs vem
    da carteira (token inicial do nome). Retorna lista (token_norm, rotulo, ticker)."""
    toks, vistos = [], set()
    # FIIs registrados (categoria FII): casa pelo nome de exibicao
    for c in EMISSORES.values():
        if c.get("categoria") == "FII":
            nome = c["forte"][1] if len(c.get("forte", [])) > 1 else c["nome"]
            t = _norm(nome)
            if t and t not in vistos:
                vistos.add(t); toks.append((t, c["nome"], c.get("ticker", "-")))
    # FIDCs da carteira: token inicial (ate o 1o marcador de tipo)
    try:
        with open(csv_path, encoding="utf-8") as f:
            for L in csv.DictReader(f):
                if (L.get("TIPO") or "").strip() != "FIDC":
                    continue
                a = (L.get("ATIVO") or "").strip()
                n = _norm(a)
                corte = len(n)
                for s in _STOP:
                    i = n.find(s)
                    if i > 0:
                        corte = min(corte, i)
                tok = " ".join(n[:corte].split()[:2]).strip()
                if len(tok) >= 4 and tok not in vistos:
                    vistos.add(tok); toks.append((tok, a, "-"))
    except Exception as e:
        print(f"  alerta: erro lendo carteira p/ FIDCs: {str(e)[:50]}")
    return toks


def _carregar_estado():
    try:
        with open(ESTADO, encoding="utf-8") as f:
            return set(json.load(f).get("vistos", []))
    except Exception:
        return set()


def _salvar_estado(vistos):
    try:
        # mantem os ultimos ~3000 para o arquivo nao crescer sem fim
        with open(ESTADO, "w", encoding="utf-8") as f:
            json.dump({"vistos": list(vistos)[-3000:]}, f)
    except Exception as e:
        print(f"  alerta: erro salvando estado: {str(e)[:50]}")


def _chave(it):
    return str(it.get("id_fnet") or it.get("link") or (it.get("nome", "") + it.get("titulo", "")))


def _html(novos):
    agora = datetime.now(timezone.utc).astimezone(BRT).strftime("%d/%m %H:%M")
    linhas = [f"<p>Novidades das ultimas {JANELA_MIN} min (gerado {agora} BRT):</p>"]
    for n in sorted(novos, key=lambda x: x.get("nome", "")):
        link = n.get("link", "")
        tit = n.get("titulo", "")
        fonte = n.get("fonte", "")
        data = n.get("data", "")
        a = f'<a href="{link}">{tit}</a>' if link else tit
        linhas.append(f"<p><b>{n.get('nome','')}</b><br>{a}<br>"
                      f"<small>{fonte} &middot; {data}</small></p>")
    return "\n".join(linhas)


def main():
    tokens = _tokens_fundos()
    print(f"  alerta: {len(tokens)} fundos vigiados (FII+FIDC)")

    itens = []
    itens += buscar_fnet(tokens, janela_min=JANELA_MIN)
    # RI das gestoras (best-effort): so emissores categoria Gestora com ri_url
    gestoras = [c for c in EMISSORES.values() if c.get("categoria") == "Gestora" and c.get("ri_url")]
    try:
        itens += raspar_ris(gestoras)
    except Exception as e:
        print(f"  alerta: RI gestoras falhou: {str(e)[:50]}")

    vistos = _carregar_estado()
    novos = []
    for it in itens:
        k = _chave(it)
        if k and k not in vistos:
            vistos.add(k); novos.append(it)

    print(f"  alerta: {len(itens)} itens coletados, {len(novos)} NOVOS")
    if novos:
        with open(CORPO, "w", encoding="utf-8") as f:
            f.write(_html(novos))
        _salvar_estado(vistos)
    else:
        _salvar_estado(vistos)

    # sinaliza p/ o workflow (saida 'novos' e arquivo-flag)
    gh = os.environ.get("GITHUB_OUTPUT")
    if gh:
        with open(gh, "a", encoding="utf-8") as f:
            f.write(f"novos={len(novos)}\n")


if __name__ == "__main__":
    main()
