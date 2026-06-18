"""Fatos relevantes / comunicados ao mercado via CVM (dados.cvm.gov.br) - oficial e gratuito.

A CVM reune os fatos relevantes de TODAS as empresas brasileiras de capital aberto num
feed unico (IPE) - e o conteudo que os RIs publicam, sem precisar raspar 50 sites.
Robusto: qualquer falha de rede/formato e silenciosa (retorna []), nao derruba o run.

Cobertura: empresas BR da carteira (acoes + emissores de bonds/debentures/CDB/CRA...).
Emissores estrangeiros (US Govt, Citi, Oracle, etc.) sao tratados na etapa da SEC.
"""

import csv, io, zipfile, unicodedata, requests
from datetime import datetime, timezone, timedelta

JANELA_HORAS = 24
# (connect, read): a CVM as vezes nao responde a partir de IPs de datacenter (GitHub).
# Timeout curto para nao travar o run quando o host estiver inacessivel.
TIMEOUT = (8, 20)
_ANO = datetime.now().year
_BASE = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE/DADOS"
# A CVM serve esse dataset como .zip (com o .csv dentro). Tentamos .zip e .csv por robustez.
IPE_URLS = [
    f"{_BASE}/ipe_cia_aberta_{_ANO}.zip",
    f"{_BASE}/ipe_cia_aberta_{_ANO}.csv",
]
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


def buscar_fatos_relevantes(emissores=None):
    """Baixa o IPE da CVM, filtra fatos relevantes/comunicados das ultimas 24h das
    empresas da carteira e retorna itens no formato do relatorio. [] em qualquer falha.

    `emissores` (opcional): lista de dicts do registro (emissores.py) com campos
    nome/ticker/cvm_aliases. Se informado, os ALVOS sao montados a partir dela (cobre
    todos os emissores BR da base). Sem isso, usa a lista fixa ALVOS (compatibilidade)."""
    if emissores:
        alvos = [(e["nome"], e.get("ticker", "-"), e["cvm_aliases"])
                 for e in emissores if e.get("cvm_aliases")]
    else:
        alvos = ALVOS
    limite = datetime.now(timezone.utc) - timedelta(hours=JANELA_HORAS)
    texto = None
    for url in IPE_URLS:
        try:
            r = requests.get(url, timeout=TIMEOUT)
        except Exception as e:
            print(f"  CVM erro de rede ({url.rsplit('/', 1)[-1]}): {str(e)[:60]}")
            continue
        if r.status_code != 200 or not r.content:
            print(f"  CVM HTTP {r.status_code} ({url.rsplit('/', 1)[-1]})")
            continue
        try:
            if url.endswith(".zip"):
                zf = zipfile.ZipFile(io.BytesIO(r.content))
                nome_csv = next((n for n in zf.namelist() if n.lower().endswith(".csv")), None)
                if not nome_csv:
                    print(f"  CVM zip sem csv ({url.rsplit('/', 1)[-1]})")
                    continue
                texto = zf.read(nome_csv).decode("latin-1", errors="ignore")
            else:
                texto = r.content.decode("latin-1", errors="ignore")
        except Exception as e:
            print(f"  CVM erro lendo arquivo ({url.rsplit('/', 1)[-1]}): {str(e)[:60]}")
            continue
        if texto:
            break
    if not texto:
        return []

    leitor = csv.DictReader(io.StringIO(texto), delimiter=";")
    itens = []
    vistos = set()
    n_linhas = 0
    n_categoria = 0
    for linha in leitor:
        n_linhas += 1
        categoria = _norm(linha.get("Categoria", ""))
        if not any(c in categoria for c in CATEGORIAS):
            continue
        n_categoria += 1
        nome_cvm = _norm(linha.get("Nome_Companhia", ""))
        alvo = next(((disp, tk) for disp, tk, aliases in alvos
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
    print(f"  CVM diag: {n_linhas} linhas no IPE, {n_categoria} fatos/comunicados, {len(itens)} dos nossos emissores (24h)")
    return itens
