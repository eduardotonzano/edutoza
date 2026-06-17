"""Fatos relevantes / comunicados ao mercado via CVM (dados.cvm.gov.br) - oficial e gratuito.

A CVM reune os fatos relevantes de TODAS as empresas brasileiras de capital aberto num
feed unico (IPE) - e o conteudo que os RIs publicam, sem precisar raspar 50 sites.
Robusto: qualquer falha de rede/formato e silenciosa (retorna []), nao derruba o run.

Cobertura: empresas BR da carteira (acoes + emissores de bonds/debentures/CDB/CRA...).
Emissores estrangeiros (US Govt, Citi, Oracle, etc.) sao tratados na etapa da SEC.
"""

import csv, io, unicodedata, requests
from datetime import datetime, timezone, timedelta

JANELA_HORAS = 24
TIMEOUT = 40
_ANO = datetime.now().year
IPE_URL = f"https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE/DADOS/ipe_cia_aberta_{_ANO}.csv"
CATEGORIAS = ("fato relevante", "comunicado ao mercado")


def _norm(t):
    return unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode("ascii").lower()

# Empresas BR da carteira -> tokens que aparecem no "Nome_Companhia" da CVM.
# (nome de exibicao, ticker, [aliases para casar no nome oficial da CVM])
ALVOS = [
    # --- Acoes ---
    ("Alupar", "ALUP11", ["alupar"]),
    ("Anima Educacao", "ANIM3", ["anima holding", "anima educacao", "anhanguera educacional"]),
    ("Automob", "AMOB3", ["automob"]),
    ("BR Partners", "BRBI11", ["br partners", "brbi"]),
    ("Banco do Brasil", "BBAS3", ["banco do brasil"]),
    ("BTG Pactual", "BPAC11", ["btg pactual"]),
    ("Cemig", "CMIG4", ["cemig", "energetica de minas gerais"]),
    ("Copasa", "CSMG3", ["copasa", "saneamento de minas gerais"]),
    ("Copel", "CPLE6", ["copel", "companhia paranaense de energia"]),
    ("Cury", "CURY3", ["cury"]),
    ("Metalurgica Gerdau", "GOAU4", ["gerdau"]),
    ("Iguatemi", "IGTI11", ["iguatemi"]),
    ("Itausa", "ITSA4", ["itausa"]),
    ("Marcopolo", "POMO4", ["marcopolo"]),
    ("Oncoclinicas", "ONCO3", ["oncoclinicas"]),
    ("Petrobras", "PETR4", ["petrobras", "petroleo brasileiro"]),
    ("PRIO", "PRIO3", ["prio", "petrorio", "petro rio"]),
    ("Randon", "RAPT4", ["randon"]),
    ("TIM", "TIMS3", ["tim s.a", "tim participacoes"]),
    ("Track&Field", "TFCO4", ["track", "track&field", "track field"]),
    ("Vale", "VALE3", ["vale s.a", "vale s/a"]),
    ("Vamos", "VAMO3", ["vamos locacao", "vamos brasil"]),
    ("Vivara", "VIVA3", ["vivara"]),
    ("WEG", "WEGE3", ["weg s.a", "weg equipamentos", "weg industrias"]),
    ("Boa Safra", "SOJA3", ["boa safra"]),
    # --- Emissores de bonds / debentures / CRA (empresas BR) ---
    ("Klabin", "Bond/CRA", ["klabin"]),
    ("Suzano", "Bond", ["suzano"]),
    ("Eletrobras", "Deb", ["eletrobras", "centrais eletricas brasileiras"]),
    ("CSN", "Deb", ["siderurgica nacional"]),
    ("Sabesp", "Deb", ["sabesp", "saneamento basico do estado de sao paulo"]),
    ("Localiza", "Deb", ["localiza"]),
    ("Movida", "Deb", ["movida"]),
    ("Neoenergia", "Deb", ["neoenergia"]),
    ("Ecorodovias", "Deb", ["ecorodovias"]),
    ("Enauta", "Deb", ["enauta", "brava energia"]),
    ("Simpar", "Deb", ["simpar"]),
    ("BRK Ambiental", "Deb", ["brk ambiental"]),
    ("Coelce / Enel CE", "Deb", ["coelce", "enel distribuicao ceara"]),
    ("Enel SP (Eletropaulo)", "Deb", ["eletropaulo", "enel distribuicao sao paulo"]),
    ("Elfa", "Deb", ["elfa"]),
    ("Aeris", "Deb", ["aeris"]),
    ("Raizen", "CRA", ["raizen"]),
    # --- Emissores de CDB / LCA / LCI (bancos BR) ---
    ("Itau Unibanco", "CDB", ["itau unibanco"]),
    ("Banco Pan", "CDB", ["banco pan"]),
    ("Banco BMG", "CDB", ["banco bmg", "bmg"]),
    ("Banco C6", "CDB/LCA", ["banco c6", "c6 bank"]),
    ("Banco Original", "CDB", ["banco original"]),
    ("Agibank", "CDB", ["agibank"]),
    ("Banco Inter", "LCI", ["banco inter", "inter &"]),
    ("Banco Fibra", "CDB", ["banco fibra"]),
    ("Banco BV", "LCA", ["banco bv", "banco votorantim", "bv s.a"]),
    ("PagBank / PagSeguro", "CDB", ["pagseguro", "pagbank"]),
    ("PicPay", "CDB", ["picpay"]),
    ("Neon", "CDB", ["neon"]),
]


def buscar_fatos_relevantes():
    """Baixa o IPE da CVM, filtra fatos relevantes/comunicados das ultimas 24h das
    empresas da carteira e retorna itens no formato do relatorio. [] em qualquer falha."""
    limite = datetime.now(timezone.utc) - timedelta(hours=JANELA_HORAS)
    try:
        r = requests.get(IPE_URL, timeout=TIMEOUT)
        if r.status_code != 200 or not r.content:
            print(f"  CVM HTTP {r.status_code}")
            return []
        texto = r.content.decode("latin-1", errors="ignore")
    except Exception as e:
        print(f"  CVM erro de rede: {str(e)[:80]}")
        return []

    leitor = csv.DictReader(io.StringIO(texto), delimiter=";")
    itens = []
    vistos = set()
    for linha in leitor:
        categoria = _norm(linha.get("Categoria", ""))
        if not any(c in categoria for c in CATEGORIAS):
            continue
        nome_cvm = _norm(linha.get("Nome_Companhia", ""))
        alvo = next(((disp, tk) for disp, tk, aliases in ALVOS
                     if any(a in nome_cvm for a in aliases)), None)
        if not alvo:
            continue
        ds = (linha.get("Data_Entrega") or linha.get("Data_Referencia") or "").strip()
        try:
            dt = datetime.strptime(ds[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except Exception:
            try:
                dt = datetime.strptime(ds[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except Exception:
                continue
        if dt < limite:
            continue
        disp, ticker = alvo
        assunto = (linha.get("Assunto") or linha.get("Tipo") or "Fato Relevante").strip()
        link = (linha.get("Link_Doc") or "").strip()
        chave = (disp, assunto[:60])
        if chave in vistos:
            continue
        vistos.add(chave)
        cat_label = "Fato Relevante" if "fato relevante" in categoria else "Comunicado ao Mercado"
        itens.append({
            "data": dt.strftime("%d/%m/%Y %H:%M"), "data_obj": dt,
            "ticker": ticker, "nome": disp,
            "titulo": f"[{cat_label}] {assunto}"[:200],
            "fonte": "CVM", "premium": True, "link": link,
            "score": 10, "relevancia": 10, "resumo_ia": "", "impacto": "",
            "corpo": f"{cat_label} da {disp}: {assunto}",
        })
    return itens
