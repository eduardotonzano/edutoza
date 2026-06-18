"""Gera o PDF 'Principais Noticias das ultimas 24h' a partir dos resumos de IA.

Documento para compartilhar: capa com a janela (em horario de Brasilia), depois TODAS as
noticias agrupadas por emissor; cada item traz titulo, fonte + horario + relevancia,
RESUMO IA, IMPACTO e link. Usa reportlab (puro Python). Se a noticia nao tiver resumo de
IA, cai para o proprio titulo (para nada ficar em branco).
"""

from datetime import datetime, timezone, timedelta
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable

from coleta import BRT, fmt_brt

JANELA_HORAS = 24


def _estilos():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("Capa", fontName="Helvetica-Bold", fontSize=20, leading=24,
                         textColor=colors.HexColor("#1F3864"), spaceAfter=4))
    s.add(ParagraphStyle("Sub", fontName="Helvetica", fontSize=10, leading=14,
                         textColor=colors.HexColor("#555555"), spaceAfter=10))
    s.add(ParagraphStyle("Emissor", fontName="Helvetica-Bold", fontSize=13, leading=16,
                         textColor=colors.HexColor("#1F3864"), spaceBefore=12, spaceAfter=2))
    s.add(ParagraphStyle("Titulo", fontName="Helvetica-Bold", fontSize=10.5, leading=13,
                         spaceBefore=6, spaceAfter=1))
    s.add(ParagraphStyle("Meta", fontName="Helvetica-Oblique", fontSize=8, leading=10,
                         textColor=colors.HexColor("#777777"), spaceAfter=2))
    s.add(ParagraphStyle("Corpo", fontName="Helvetica", fontSize=9.5, leading=12, spaceAfter=1))
    s.add(ParagraphStyle("Link", fontName="Helvetica", fontSize=8, leading=10,
                         textColor=colors.HexColor("#0563C1"), spaceAfter=4))
    return s


def _imp_cor(impacto):
    i = (impacto or "").lower()
    if i.startswith("positiv"): return "#1B7F37"
    if i.startswith("negativ"): return "#B00020"
    return "#555555"


def gerar_pdf(finais, caminho="Principais_Noticias_24h.pdf"):
    s = _estilos()
    agora = datetime.now(timezone.utc)
    ini = fmt_brt(agora - timedelta(hours=JANELA_HORAS))
    fim = fmt_brt(agora)
    doc = SimpleDocTemplate(caminho, pagesize=A4, topMargin=1.5*cm, bottomMargin=1.5*cm,
                            leftMargin=1.6*cm, rightMargin=1.6*cm,
                            title="Principais Noticias das ultimas 24h")
    fluxo = [
        Paragraph("Principais Noticias das ultimas 24h", s["Capa"]),
        Paragraph(f"Janela: {ini} a {fim} (horario de Brasilia) &nbsp;|&nbsp; "
                  f"{len(finais)} noticias", s["Sub"]),
        HRFlowable(width="100%", color=colors.HexColor("#1F3864"), spaceAfter=6),
    ]
    if not finais:
        fluxo.append(Paragraph("Sem noticias relevantes na janela.", s["Corpo"]))
        doc.build(fluxo)
        return caminho

    # Agrupa por emissor preservando a ordem de entrada (ja vem ordenado por ticker/data).
    grupos, ordem = {}, []
    for n in finais:
        k = n["nome"]
        if k not in grupos:
            grupos[k] = []; ordem.append(k)
        grupos[k].append(n)

    for nome in ordem:
        itens = grupos[nome]
        tk = str(itens[0].get("ticker") or "-")
        fluxo.append(Paragraph(escape(f"{nome}  ({tk})"), s["Emissor"]))
        for n in itens:
            resumo = (n.get("resumo_ia") or "").strip() or n.get("titulo", "")
            otimista = (n.get("otimista") or "").strip()
            cetico = (n.get("cetico") or "").strip()
            impacto = (n.get("impacto") or "").strip()
            fluxo.append(Paragraph(escape(n.get("titulo", "")), s["Titulo"]))
            fluxo.append(Paragraph(
                escape(f"{n.get('fonte','')}  •  {n.get('data','')}  •  relevancia {n.get('relevancia','')}"),
                s["Meta"]))
            fluxo.append(Paragraph(escape(resumo), s["Corpo"]))
            if otimista:
                fluxo.append(Paragraph(
                    f'<b><font color="#1B7F37">Analista otimista:</font></b> {escape(otimista)}', s["Corpo"]))
            if cetico:
                fluxo.append(Paragraph(
                    f'<b><font color="#B00020">Analista cetico:</font></b> {escape(cetico)}', s["Corpo"]))
            if impacto:
                fluxo.append(Paragraph(
                    f'<b><font color="{_imp_cor(impacto)}">Impacto:</font></b> {escape(impacto)}',
                    s["Corpo"]))
            link = (n.get("link") or "").strip()
            if link:
                fluxo.append(Paragraph(f'<link href="{escape(link)}">{escape(link[:90])}</link>', s["Link"]))
    doc.build(fluxo)
    return caminho
