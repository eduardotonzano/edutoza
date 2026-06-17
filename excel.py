"""Geracao do relatorio Excel com 3 abas: NOTICIAS, RESUMO POR ATIVO, SEM COBERTURA."""

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from collections import Counter
from datetime import datetime

_HF   = Font(name="Arial", bold=True, color="FFFFFF", size=11)
_HFILL= PatternFill("solid", start_color="1F3864")
_CTR  = Alignment(horizontal="center", vertical="center", wrap_text=True)
_LFT  = Alignment(horizontal="left", vertical="center", wrap_text=True)
_THIN = Side(style="thin", color="CCCCCC")
_BD   = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_FA   = PatternFill("solid", start_color="EBF1F8")
_FB   = PatternFill("solid", start_color="FFFFFF")
_FSEM = PatternFill("solid", start_color="FFE0E0")


def _cab(ws, cols, larg):
    for c, t in enumerate(cols, 1):
        x = ws.cell(row=1, column=c, value=t)
        x.font=_HF; x.fill=_HFILL; x.alignment=_CTR; x.border=_BD
    for c, l in enumerate(larg, 1):
        ws.column_dimensions[get_column_letter(c)].width = l
    ws.row_dimensions[1].height = 22
    ws.freeze_panes = "A2"


def gerar_excel(noticias_finais, empresas, caminho=None):
    contagem   = Counter(n["nome"] for n in noticias_finais)
    ativos_sem = [n for n in empresas if contagem.get(n, 0) == 0]

    wb = Workbook()

    # Aba 1: NOTICIAS
    ws1 = wb.active; ws1.title = "NOTICIAS"
    _cab(ws1, ["DATA","TICKER","NOME","TITULO","FONTE","LINK","RELEVANCIA","RESUMO IA","IMPACTO"],
         [18,14,22,60,20,45,12,55,15])
    ta=None; grp=True
    for i, n in enumerate(noticias_finais, 2):
        if n["ticker"] != ta: grp = not grp; ta = n["ticker"]
        fill = _FA if grp else _FB
        for c, v in enumerate([n["data"],n["ticker"],n["nome"],n["titulo"],n["fonte"],
                               n["link"],n["relevancia"],n["resumo_ia"],n["impacto"]], 1):
            x = ws1.cell(row=i, column=c, value=v)
            x.font=Font(name="Arial",size=10); x.fill=fill; x.border=_BD; x.alignment=_LFT
        if n["link"]:
            ws1.cell(row=i, column=6).hyperlink = n["link"]
            ws1.cell(row=i, column=6).font = Font(name="Arial", size=10, color="0563C1", underline="single")

    # Aba 2: RESUMO POR ATIVO
    ws2 = wb.create_sheet("RESUMO POR ATIVO")
    _cab(ws2, ["TICKER","NOME","N NOTICIAS","MELHOR FONTE","COBERTURA"], [14,28,14,22,16])
    mf = {}
    for n in noticias_finais:
        mf.setdefault(n["nome"], n["fonte"])
    for i, nome in enumerate(empresas, 2):
        q = contagem.get(nome, 0)
        fill = _FSEM if q == 0 else (_FA if i % 2 == 0 else _FB)
        cob = "Com cobertura" if q > 0 else "Sem noticia"
        for c, v in enumerate([empresas[nome]["ticker"], nome, q, mf.get(nome, "-"), cob], 1):
            x = ws2.cell(row=i, column=c, value=v)
            x.font=Font(name="Arial",size=10); x.fill=fill; x.border=_BD; x.alignment=_LFT

    # Aba 3: SEM COBERTURA
    if ativos_sem:
        ws3 = wb.create_sheet("SEM COBERTURA")
        _cab(ws3, ["TICKER","NOME","OBSERVACAO"], [14,28,50])
        for i, nome in enumerate(ativos_sem, 2):
            for c, v in enumerate([empresas[nome]["ticker"], nome,
                                   "Sem noticia relevante nas ultimas 24h"], 1):
                x = ws3.cell(row=i, column=c, value=v)
                x.font=Font(name="Arial",size=10); x.fill=_FSEM; x.border=_BD; x.alignment=_LFT

    if caminho is None:
        caminho = f"Noticias_Carteira_{datetime.now().strftime('%d%m%Y_%H%M')}.xlsx"
    wb.save(caminho)
    return caminho, len(noticias_finais), len(contagem)
