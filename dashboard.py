"""Dashboard HTML das noticias das ultimas 24h, segmentado por CLASSE DE ATIVO.

Resolve o problema de as acoes (muito noticiadas) ofuscarem FIIs, gestoras e renda fixa numa
lista unica. Gera UM arquivo .html autossuficiente (CSS + JS inline) que vai como ANEXO do
e-mail: abre offline no navegador, com barra de resumo, filtros por classe e busca por texto.

A classe de cada noticia sai de dado que ja existe: a categoria do emissor em emissores.py
(via o nome de exibicao que a noticia carrega) e a fonte (CVM/SEC/RI = oficial). Sem dado novo.
"""

import html
from datetime import datetime, timezone, timedelta

from emissores import EMISSORES
from coleta import fmt_brt

JANELA_HORAS = 24

# nome de exibicao do emissor -> categoria (emissores.py e keyed pela chave interna, mas a
# noticia carrega o campo "nome" = nome de exibicao; este indice cruza os dois).
_CAT_POR_NOME = {c.get("nome", ""): c.get("categoria", "") for c in EMISSORES.values()}

_OFICIAL_PREFIXOS = ("CVM", "SEC", "RI/")

# (chave do bucket, slug p/ data-attr/filtro, titulo exibido). Ordem = ordem na pagina.
BUCKETS = [
    ("Oficiais",          "oficiais", "Fatos Relevantes (oficiais CVM / SEC / RI)"),
    ("Acoes & Empresas",  "acoes",    "Acoes & Empresas"),
    ("FIIs",              "fiis",     "FIIs (Fundos Imobiliarios)"),
    ("Gestoras / Fundos", "gestoras", "Gestoras / Fundos"),
]
_SLUG = {chave: slug for chave, slug, _ in BUCKETS}


def _oficial(item):
    return str(item.get("fonte", "")).startswith(_OFICIAL_PREFIXOS)


def classe_do_item(item):
    """Bucket (classe de ativo) de uma noticia. Oficiais primeiro; depois pela categoria do
    emissor (FII / Gestora / setor de acao)."""
    if _oficial(item):
        return "Oficiais"
    cat = _CAT_POR_NOME.get(item.get("nome", ""), "")
    if cat == "FII":
        return "FIIs"
    if cat == "Gestora":
        return "Gestoras / Fundos"
    return "Acoes & Empresas"


def _grupos_por_emissor(itens):
    """Agrupa por emissor e ordena emissores pela maior relevancia (igual ao PDF)."""
    grupos, ordem = {}, []
    for n in itens:
        k = n.get("nome", "-")
        if k not in grupos:
            grupos[k] = []; ordem.append(k)
        grupos[k].append(n)
    for k in grupos:
        grupos[k].sort(key=lambda x: -int(x.get("relevancia") or 0))
    ordem.sort(key=lambda k: -int(grupos[k][0].get("relevancia") or 0))
    return [(k, grupos[k]) for k in ordem]


def _card(item, slug):
    titulo = item.get("titulo", "") or ""
    link = (item.get("link") or "").strip()
    resumo = (item.get("resumo_ia") or "").strip() or titulo
    fonte = item.get("fonte", "") or ""
    data = item.get("data", "") or ""
    rel = item.get("relevancia", "")
    busca = html.escape(f"{item.get('nome','')} {titulo} {fonte}".lower(), quote=True)
    tit_html = (f'<a href="{html.escape(link, quote=True)}" target="_blank" rel="noopener">'
                f'{html.escape(titulo)}</a>') if link else html.escape(titulo)
    selo = '<span class="selo">OFICIAL</span>' if _oficial(item) else ""
    return (
        f'<div class="card" data-classe="{slug}" data-q="{busca}">'
        f'<div class="ctit">{tit_html}</div>'
        f'<div class="cmeta">{html.escape(fonte)} &middot; {html.escape(data)} '
        f'&middot; <b>rel {html.escape(str(rel))}</b> {selo}</div>'
        f'<div class="cresumo">{html.escape(resumo)}</div>'
        f'</div>'
    )


def _secao(chave, slug, titulo, itens):
    n = len(itens)
    partes = [f'<section class="secao" id="sec-{slug}" data-classe="{slug}">',
              f'<h2>{html.escape(titulo)} <span class="cont">{n}</span></h2>']
    for nome, grupo in _grupos_por_emissor(itens):
        tk = str(grupo[0].get("ticker") or "-")
        setor = _CAT_POR_NOME.get(nome, "")
        tag = (f' <span class="setor">{html.escape(setor)}</span>'
               if slug == "acoes" and setor else "")
        partes.append('<div class="grupo">')
        partes.append(f'<h3>{html.escape(nome)} <span class="tk">({html.escape(tk)})</span>{tag}</h3>')
        for item in grupo:
            partes.append(_card(item, slug))
        partes.append('</div>')
    partes.append('</section>')
    return "\n".join(partes)


_CSS = """
* { box-sizing: border-box; }
body { font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 0;
       background: #f4f6fa; color: #1c2530; }
header { background: #1F3864; color: #fff; padding: 18px 22px; }
header h1 { margin: 0 0 4px; font-size: 20px; }
header .sub { font-size: 13px; opacity: .85; }
.barra { position: sticky; top: 0; z-index: 10; background: #fff; padding: 10px 22px;
         border-bottom: 1px solid #e1e6ee; display: flex; flex-wrap: wrap; gap: 8px;
         align-items: center; }
.fbtn { border: 1px solid #c9d2e0; background: #fff; color: #1F3864; border-radius: 16px;
        padding: 6px 13px; font-size: 13px; cursor: pointer; }
.fbtn.on { background: #1F3864; color: #fff; border-color: #1F3864; }
.fbtn .b { opacity: .7; font-weight: 400; }
#busca { margin-left: auto; border: 1px solid #c9d2e0; border-radius: 16px; padding: 6px 13px;
         font-size: 13px; min-width: 200px; }
main { padding: 8px 22px 40px; max-width: 1000px; margin: 0 auto; }
.secao { margin-top: 22px; }
.secao h2 { font-size: 16px; color: #1F3864; border-bottom: 2px solid #1F3864;
            padding-bottom: 5px; }
.secao .cont { background: #1F3864; color: #fff; border-radius: 10px; font-size: 12px;
               padding: 1px 8px; margin-left: 6px; vertical-align: middle; }
#sec-oficiais h2 { color: #8a5a00; border-color: #d39a2a; }
#sec-oficiais .cont { background: #d39a2a; }
.grupo { background: #fff; border: 1px solid #e1e6ee; border-radius: 8px; padding: 10px 14px;
         margin: 10px 0; }
.grupo h3 { margin: 0 0 6px; font-size: 14px; color: #14223a; }
.grupo h3 .tk { color: #6b7890; font-weight: 400; }
.setor { background: #eef2f8; color: #41506b; border-radius: 8px; font-size: 11px;
         padding: 1px 7px; margin-left: 4px; }
.card { border-top: 1px solid #eef1f6; padding: 8px 0; }
.card:first-of-type { border-top: 0; }
.ctit { font-size: 13.5px; font-weight: 600; line-height: 1.35; }
.ctit a { color: #14223a; text-decoration: none; }
.ctit a:hover { text-decoration: underline; }
.cmeta { font-size: 11px; color: #7a8699; margin: 2px 0; }
.selo { background: #d39a2a; color: #fff; border-radius: 6px; font-size: 10px;
        padding: 1px 6px; margin-left: 4px; }
.cresumo { font-size: 12.5px; color: #3a4658; line-height: 1.4; }
.vazio { color: #7a8699; font-size: 13px; padding: 16px 0; }
footer { text-align: center; color: #9aa5b5; font-size: 11px; padding: 20px; }
"""

_JS = """
function aplicar(){
  var q=(document.getElementById('busca').value||'').toLowerCase().trim();
  var cls=window.__classe||'todas';
  document.querySelectorAll('.card').forEach(function(c){
    var ok=(cls==='todas'||c.dataset.classe===cls)&&(!q||c.dataset.q.indexOf(q)>=0);
    c.style.display=ok?'':'none';
  });
  ['.grupo','.secao'].forEach(function(sel){
    document.querySelectorAll(sel).forEach(function(g){
      var vis=Array.prototype.filter.call(g.querySelectorAll('.card'),
              function(c){return c.style.display!=='none';}).length;
      g.style.display=vis?'':'none';
    });
  });
}
function filtrar(cls,btn){
  window.__classe=cls;
  document.querySelectorAll('.fbtn').forEach(function(b){b.classList.remove('on');});
  if(btn) btn.classList.add('on');
  aplicar();
}
"""


def gerar_dashboard_html(finais, alvos=None, caminho="Dashboard_Noticias_24h.html"):
    """Gera o dashboard .html com TODAS as noticias captadas, agrupadas por classe de ativo.
    `finais` = lista de noticias (dicts padrao); `alvos` aceito por simetria (nao usado hoje)."""
    agora = datetime.now(timezone.utc)
    ini = fmt_brt(agora - timedelta(hours=JANELA_HORAS))
    fim = fmt_brt(agora)
    total = len(finais)

    # Distribui em buckets preservando a ordem ja calculada em finais.
    por_bucket = {chave: [] for chave, _, _ in BUCKETS}
    for item in finais:
        por_bucket[classe_do_item(item)].append(item)

    # Barra de filtros (so mostra botao de bucket que tem item) + busca.
    botoes = [f'<button class="fbtn on" onclick="filtrar(\'todas\',this)">Todas '
              f'<span class="b">{total}</span></button>']
    for chave, slug, titulo in BUCKETS:
        n = len(por_bucket[chave])
        if n:
            rotulo = titulo.split(" (")[0]
            botoes.append(f'<button class="fbtn" onclick="filtrar(\'{slug}\',this)">'
                          f'{html.escape(rotulo)} <span class="b">{n}</span></button>')
    barra = ('<div class="barra">' + "".join(botoes) +
             '<input id="busca" type="search" placeholder="Buscar emissor ou titulo..." '
             'oninput="aplicar()" autocomplete="off"></div>')

    corpo = []
    for chave, slug, titulo in BUCKETS:
        itens = por_bucket[chave]
        if itens:
            corpo.append(_secao(chave, slug, titulo, itens))
    corpo_html = "\n".join(corpo) if corpo else '<p class="vazio">Sem noticias na janela de 24h.</p>'

    doc = f"""<!DOCTYPE html>
<html lang="pt-br"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Noticias da Carteira - ultimas 24h</title>
<style>{_CSS}</style></head>
<body>
<header>
  <h1>Noticias da Carteira &mdash; ultimas 24h</h1>
  <div class="sub">Janela: {html.escape(ini)} a {html.escape(fim)} (horario de Brasilia)
       &nbsp;|&nbsp; {total} noticias captadas</div>
</header>
{barra}
<main>
{corpo_html}
</main>
<footer>Gerado automaticamente. Use os filtros acima para ver cada classe de ativo isoladamente.</footer>
<script>{_JS}</script>
</body></html>"""

    with open(caminho, "w", encoding="utf-8") as f:
        f.write(doc)
    return caminho
