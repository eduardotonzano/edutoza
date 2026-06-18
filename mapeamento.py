"""Mapeia cada ativo da carteira (carteira_completa.csv) para o seu EMISSOR.

O nome do ativo costuma trazer o emissor embutido, ex.:
  "BONDS - JPMORGAN CHASE & CO - PRE - 22/10/2034"  -> JPMorgan
  "CDB - BANCO BMG - PRE - 01/06/2026"              -> Banco BMG
  "PETROBRAS   PN      N2"                           -> Petrobras

Estrategia: normaliza o nome (sem acento, minusculo, espacos colapsados) e procura o
emissor cujo algum 'alias' aparece como substring. Alias mais longo vence (evita casar
um pedaco generico). Sem match -> issuer_key None -> "sem noticia aplicavel" no relatorio.
"""

import csv, unicodedata
from emissores import EMISSORES


def _norm(t):
    t = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode("ascii").lower()
    return " ".join(t.split())   # colapsa espacos multiplos (nomes vem com padding)


# Lista (alias_norm, issuer_key) ordenada do alias mais longo p/ o mais curto.
_INDICE = sorted(
    [(_norm(a), chave) for chave, campos in EMISSORES.items() for a in campos.get("aliases", [])],
    key=lambda x: -len(x[0]),
)


def emissor_do_ativo(ativo):
    """Retorna a issuer_key do emissor do ativo, ou None se nenhum alias casar."""
    alvo = _norm(ativo)
    for alias, chave in _INDICE:
        if alias and alias in alvo:
            return chave
    return None


def mapear_carteira(caminho_csv):
    """Le carteira_completa.csv e retorna lista de dicts, um por ativo:
       {ativo, tipo, moeda, categoria, issuer_key, emissor, news_applicable}."""
    alvos = []
    with open(caminho_csv, encoding="utf-8") as f:
        for linha in csv.DictReader(f):
            ativo = (linha.get("ATIVO") or "").strip()
            if not ativo:
                continue
            chave = emissor_do_ativo(ativo)
            campos = EMISSORES.get(chave) if chave else None
            alvos.append({
                "ativo": ativo,
                "tipo": (linha.get("TIPO") or "").strip(),
                "moeda": (linha.get("MOEDA") or "").strip(),
                "categoria": (linha.get("CATEGORIA") or "").strip(),
                "issuer_key": chave,
                "emissor": campos["nome"] if campos else "-",
                "news_applicable": bool(campos and campos.get("news_applicable")),
            })
    return alvos
