"""ALERTA INTRADAY de fundos (e-mail), separado do relatorio das 17h.

Roda a cada ~30 min e avisa NA HORA quando sai noticia nova de um FII ou de uma GESTORA da
base. Como o Fundos.NET (B3) bloqueia o IP de datacenter do GitHub, o alerta usa as fontes
que JA sao alcancaveis e rapidas:
  - Google News por FII (ticker) e por gestora (nome)  -> google_news.coletar_google
  - Yahoo Finance por ticker de FII                    -> rss_news.coletar_yahoo
  - RI das gestoras (best-effort)                      -> ri_scraping.raspar_ris
A relevancia/atribuicao reusa coleta.validar_todos (nome/ticker no titulo + filtro
anti-opiniao das gestoras). Mantem ESTADO (cache) p/ nao repetir. So manda e-mail no inedito.
"""

import os, json, unicodedata
from datetime import datetime, timezone, timedelta

from emissores import EMISSORES
from coleta import validar_todos
from google_news import coletar_google
from rss_news import coletar_yahoo
from ri_scraping import raspar_ris

ESTADO = "alertas_estado.json"
CORPO = "alerta_corpo.html"
BRT = timezone(timedelta(hours=-3))


def _carregar_estado():
    try:
        with open(ESTADO, encoding="utf-8") as f:
            return set(json.load(f).get("vistos", []))
    except Exception:
        return set()


def _salvar_estado(vistos):
    try:
        with open(ESTADO, "w", encoding="utf-8") as f:
            json.dump({"vistos": list(vistos)[-4000:]}, f)
    except Exception as e:
        print(f"  alerta: erro salvando estado: {str(e)[:50]}")


def _chave(it):
    return str(it.get("link") or (it.get("nome", "") + "|" + it.get("titulo", "")))


def _html(novos):
    agora = datetime.now(timezone.utc).astimezone(BRT).strftime("%d/%m %H:%M")
    out = [f"<p>Novidades de fundos (gerado {agora} BRT):</p>"]
    for n in sorted(novos, key=lambda x: x.get("nome", "")):
        link, tit = n.get("link", ""), n.get("titulo", "")
        a = f'<a href="{link}">{tit}</a>' if link else tit
        out.append(f"<p><b>{n.get('nome','')}</b><br>{a}<br>"
                   f"<small>{n.get('fonte','')} &middot; {n.get('data','')}</small></p>")
    return "\n".join(out)


def main():
    alvos = [c for c in EMISSORES.values()
             if c.get("categoria") in ("FII", "Gestora") and c.get("news_applicable")]
    reg = {c["nome"]: c for c in alvos}
    print(f"  alerta: {len(alvos)} fundos/gestoras vigiados (via imprensa)")

    candidatos = {}
    candidatos.update(coletar_google(alvos))        # Google News por FII/gestora
    candidatos.update(coletar_yahoo(alvos))         # Yahoo por ticker de FII
    finais, _, _ = validar_todos(candidatos, {}, reg)

    gestoras = [c for c in alvos if c.get("categoria") == "Gestora" and c.get("ri_url")]
    try:
        ri = raspar_ris(gestoras)
    except Exception as e:
        print(f"  alerta: RI gestoras falhou: {str(e)[:50]}")
        ri = []

    itens = finais + ri
    vistos = _carregar_estado()
    novos = []
    for it in itens:
        k = _chave(it)
        if k and k not in vistos:
            vistos.add(k); novos.append(it)

    print(f"  alerta: {len(itens)} itens, {len(novos)} NOVOS")
    if novos:
        with open(CORPO, "w", encoding="utf-8") as f:
            f.write(_html(novos) + "\n")     # newline final (o passo do e-mail exige)
    _salvar_estado(vistos)

    gh = os.environ.get("GITHUB_OUTPUT")
    if gh:
        with open(gh, "a", encoding="utf-8") as f:
            f.write(f"novos={len(novos)}\n")


if __name__ == "__main__":
    main()
