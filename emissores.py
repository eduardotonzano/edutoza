"""Registro central de EMISSORES monitoraveis da carteira.

Cada ativo da carteira (acao, bond, CDB, debenture, LCA, CRA...) e emitido por uma
empresa/banco/governo. Em vez de tentar buscar "noticia" de um CDB especifico (que nao
existe), monitoramos o EMISSOR por tras dele. Varios ativos colapsam no mesmo emissor
(ex.: dezenas de CDBs do BTG -> um emissor "BTG Pactual").

Estrutura de cada emissor:
  nome            - nome de exibicao
  busca           - query do GDELT (palavras = E logico); None se nao busca noticia
  forte/fraco     - nomes para o validador (forte = inequivoco; fraco = ambiguo, exige contexto)
  contexto        - termos de setor/produto/executivo que confirmam o emissor
  cvm_aliases     - tokens que casam no "Nome_Companhia" do feed da CVM (BR)
  sec_ticker/sec_cik - identificacao na SEC/EDGAR (emissores dos EUA); CIK resolvido em runtime se None
  ri_url          - pagina de RI/releases para raspagem (best-effort); None desliga
  categoria       - rotulo livre (Banco, Energia, Tech US...)
  aliases         - tokens usados para casar o NOME DO ATIVO -> este emissor (em mapeamento.py)
  news_applicable - False para governo/Tesouro e emissores sem noticia de imprensa (financeiras
                    pequenas, securitizadoras). Esses ativos aparecem no relatorio como
                    "sem noticia aplicavel" (nada e descartado).

EMISSORES e montado reaproveitando o dict EMPRESAS (empresas.py) + emissores extra (bancos,
corporates e nomes dos EUA dos bonds). Nao duplica busca/forte/fraco/contexto das 28 acoes.
"""

from empresas import EMPRESAS

# Metadados extra para as 28 acoes/BDRs ja definidas em EMPRESAS (CVM/SEC/RI/aliases p/ mapeamento).
_META_ACOES = {
 "Alphabet":          dict(categoria="Tech US", sec_ticker="GOOGL", sec_cik="0001652044", cvm_aliases=[], aliases=["alphabet"]),
 "Microsoft":         dict(categoria="Tech US", sec_ticker="MSFT",  sec_cik="0000789019", cvm_aliases=[], aliases=["microsoft"]),
 "Nvidia":            dict(categoria="Tech US", sec_ticker="NVDA",  sec_cik="0001045810", cvm_aliases=[], aliases=["nvidia","nvda"]),
 "Alupar":            dict(categoria="Energia", cvm_aliases=["alupar"], aliases=["alupar"]),
 "Anima Educacao":    dict(categoria="Educacao", cvm_aliases=["anima holding","anima educacao","anhanguera educacional"], aliases=["anima"]),
 "Automob":           dict(categoria="Varejo auto", cvm_aliases=["automob"], aliases=["automob"]),
 "BR Partners":       dict(categoria="Banco", cvm_aliases=["br partners","brbi"], aliases=["br partners"]),
 "Banco do Brasil":   dict(categoria="Banco", cvm_aliases=["banco do brasil"], aliases=["banco do brasil","brasil on"]),
 "BTG Pactual":       dict(categoria="Banco", cvm_aliases=["btg pactual"], aliases=["btg pactual","btg pac","btgp"]),
 "Cemig":             dict(categoria="Energia", cvm_aliases=["cemig","energetica de minas gerais"], aliases=["cemig"]),
 "Copasa":            dict(categoria="Saneamento", cvm_aliases=["copasa","saneamento de minas gerais"], aliases=["copasa"]),
 "Copel":             dict(categoria="Energia", cvm_aliases=["copel","companhia paranaense de energia"], aliases=["copel"]),
 "Cury":              dict(categoria="Construcao", cvm_aliases=["cury"], aliases=["cury"]),
 "Metalurgica Gerdau":dict(categoria="Siderurgia", cvm_aliases=["gerdau"], aliases=["gerdau","gtl trade finance"]),
 "Iguatemi":          dict(categoria="Shoppings", cvm_aliases=["iguatemi"], aliases=["iguatemi"]),
 "Itausa":            dict(categoria="Holding", cvm_aliases=["itausa"], aliases=["itausa"]),
 "Marcopolo":         dict(categoria="Industria", cvm_aliases=["marcopolo"], aliases=["marcopolo"]),
 "Oncoclinicas":      dict(categoria="Saude", cvm_aliases=["oncoclinicas"], aliases=["oncoclinicas"]),
 "Petrobras":         dict(categoria="Petroleo", cvm_aliases=["petrobras","petroleo brasileiro"], aliases=["petrobras"]),
 "PRIO":              dict(categoria="Petroleo", cvm_aliases=["prio","petrorio","petro rio"], aliases=["prio","petrorio","petro rio"]),
 "Randon":            dict(categoria="Industria", cvm_aliases=["randon"], aliases=["randon"]),
 "TIM":               dict(categoria="Telecom", cvm_aliases=["tim s.a","tim participacoes"], aliases=["tim on","tim part"]),
 "Track&Field":       dict(categoria="Varejo", cvm_aliases=["track","track&field","track field"], aliases=["track field"]),
 "Vale":              dict(categoria="Mineracao", cvm_aliases=["vale s.a","vale s/a"], aliases=["vale on","vale s.a","vale overseas"]),
 "Vamos":             dict(categoria="Locacao", cvm_aliases=["vamos locacao","vamos brasil"], aliases=["vamos on","vamos loc"]),
 "Vivara":            dict(categoria="Varejo", cvm_aliases=["vivara"], aliases=["vivara"]),
 "WEG":               dict(categoria="Industria", cvm_aliases=["weg s.a","weg equipamentos","weg industrias"], aliases=["weg on","weg s.a","weg equip"]),
 "Boa Safra":         dict(categoria="Agro", cvm_aliases=["boa safra"], aliases=["boa safra"]),
}

# Emissores EXTRA (nao sao as 28 acoes): bancos/corporates BR de credito + nomes dos EUA.
# Campos minimos: nome, busca, forte, fraco, contexto, cvm_aliases, sec_*, ri_url, categoria,
# aliases, news_applicable.
def _e(nome, busca=None, forte=None, fraco=None, contexto=None, cvm_aliases=None,
       sec_ticker=None, sec_cik=None, ri_url=None, categoria="", aliases=None,
       news_applicable=True):
    return {"nome": nome, "busca": busca, "forte": forte or [], "fraco": fraco or [],
            "contexto": contexto or [], "cvm_aliases": cvm_aliases or [],
            "sec_ticker": sec_ticker, "sec_cik": sec_cik, "ri_url": ri_url,
            "categoria": categoria, "aliases": aliases or [], "news_applicable": news_applicable}

_EXTRA = {
 # --- Corporates BR (debentures / CRA / bonds) ---
 "Klabin":        _e("Klabin", "Klabin celulose papel", ["klabin"], [], ["celulose","papel","embalagens"], ["klabin"], categoria="Papel/Celulose", aliases=["klabin"]),
 "Suzano":        _e("Suzano", "Suzano celulose", ["suzano"], [], ["celulose","papel","eucalipto"], ["suzano"], categoria="Papel/Celulose", aliases=["suzano"]),
 "Eletrobras":    _e("Eletrobras", "Eletrobras energia", ["eletrobras"], [], ["energia","eletrica","hidreletrica"], ["eletrobras","centrais eletricas brasileiras"], categoria="Energia", aliases=["eletrobras","centrais eletricas brasileiras"]),
 "CSN":           _e("CSN", "CSN siderurgica", ["siderurgica nacional"], ["csn"], ["aco","siderurgia","minerio"], ["siderurgica nacional"], categoria="Siderurgia", aliases=["siderurgica nacional"]),
 "Sabesp":        _e("Sabesp", "Sabesp saneamento", ["sabesp"], [], ["saneamento","agua","esgoto"], ["sabesp","saneamento basico do estado de sao paulo"], categoria="Saneamento", aliases=["sabesp"]),
 "Localiza":      _e("Localiza", "Localiza aluguel carros", ["locacao das americas"], ["localiza"], ["locacao","aluguel de carros","frota","seminovos","rent a car","movi3","rent3"], ["localiza","locacao das americas"], categoria="Locacao", aliases=["localiza","locacao das americas"]),
 "Movida":        _e("Movida", "Movida locacao", [], ["movida"], ["locacao","aluguel de carros","frota","seminovos","movi3","gtf"], ["movida"], categoria="Locacao", aliases=["movida"]),
 "Neoenergia":    _e("Neoenergia", "Neoenergia energia", ["neoenergia"], [], ["energia","eletrica","distribuicao"], ["neoenergia"], categoria="Energia", aliases=["neoenergia"]),
 "Ecorodovias":   _e("Ecorodovias", "Ecorodovias concessoes rodovias", ["ecorodovias"], [], ["concessao","rodovias","pedagio"], ["ecorodovias"], categoria="Infraestrutura", aliases=["ecorodovias"]),
 "Enauta":        _e("Enauta / Brava", "Enauta Brava petroleo", ["enauta","brava energia"], [], ["petroleo","oleo","offshore","exploracao"], ["enauta","brava energia"], categoria="Petroleo", aliases=["enauta","brava energia"]),
 "Simpar":        _e("Simpar", "Simpar logistica", ["simpar"], [], ["logistica","holding","jsl","vamos","movida"], ["simpar"], categoria="Holding", aliases=["simpar"]),
 "BRK Ambiental": _e("BRK Ambiental", "BRK Ambiental saneamento", ["brk ambiental"], [], ["saneamento","agua","esgoto"], ["brk ambiental"], categoria="Saneamento", aliases=["brk ambiental"]),
 "Coelce":        _e("Coelce / Enel CE", "Enel Ceara energia", ["coelce"], [], ["energia","eletrica","distribuicao","ceara"], ["coelce","enel distribuicao ceara"], categoria="Energia", aliases=["coelce"]),
 "Enel SP":       _e("Enel SP (Eletropaulo)", "Enel Sao Paulo energia", ["eletropaulo"], [], ["energia","eletrica","distribuicao","sao paulo"], ["eletropaulo","enel distribuicao sao paulo"], categoria="Energia", aliases=["eletropaulo"]),
 "Elfa":          _e("Elfa Medicamentos", "Elfa medicamentos distribuidora", ["elfa medicamentos"], ["elfa"], ["medicamentos","saude","distribuidora"], ["elfa"], categoria="Saude", aliases=["elfa"]),
 "Aeris":         _e("Aeris Energia", "Aeris energia eolica", ["aeris"], [], ["eolica","pas","energia","turbinas"], ["aeris"], categoria="Energia", aliases=["aeris"]),
 "Raizen":        _e("Raizen", "Raizen combustivel etanol", ["raizen"], [], ["combustivel","etanol","acucar","energia"], ["raizen"], categoria="Energia", aliases=["raizen"]),
 "Telefonica":    _e("Telefonica Brasil (Vivo)", "Telefonica Brasil Vivo telecom", ["telefonica brasil"], ["vivo"], ["telecom","telefonia","5g","operadora"], ["telefonica brasil","telecomunicacoes de sao paulo"], categoria="Telecom", aliases=["telef brasil","telefonica brasil"]),
 "Axia Energia":  _e("Axia Energia", "Axia Energia", ["axia energia"], [], ["energia","eletrica"], ["axia"], categoria="Energia", aliases=["axia energia"]),
 # --- Bancos BR (CDB / LCA / LCI / LF) ---
 "Itau Unibanco": _e("Itau Unibanco", "Itau Unibanco banco", ["itau unibanco"], [], ["banco","credito","lucro","dividendos"], ["itau unibanco"], categoria="Banco", aliases=["itau unibanco","itauunibanco"]),
 "Bradesco":      _e("Banco Bradesco", "Banco Bradesco", ["bradesco"], [], ["banco","credito","seguros","lucro"], ["bradesco"], categoria="Banco", aliases=["bradesco"]),
 "Banco Pan":     _e("Banco Pan", "Banco Pan", ["banco pan"], [], ["banco","credito","financiamento"], ["banco pan"], categoria="Banco", aliases=["banco pan"]),
 "Banco BMG":     _e("Banco BMG", "Banco BMG", ["banco bmg"], ["bmg"], ["banco","consignado","credito"], ["banco bmg","bmg"], categoria="Banco", aliases=["banco bmg"]),
 "Banco C6":      _e("Banco C6", "C6 Bank banco", ["banco c6","c6 bank"], [], ["banco digital","fintech","credito"], ["banco c6","c6 bank"], categoria="Banco", aliases=["banco c6"]),
 "Banco Original":_e("Banco Original", "Banco Original", ["banco original"], [], ["banco digital","fintech","credito"], ["banco original"], categoria="Banco", aliases=["banco original"]),
 "Agibank":       _e("Agibank", "Agibank banco", ["agibank"], [], ["banco","consignado","credito"], ["agibank"], categoria="Banco", aliases=["agibank"]),
 "Banco Inter":   _e("Banco Inter", "Banco Inter", ["banco inter"], [], ["banco digital","fintech","credito","super app"], ["banco inter","inter &"], categoria="Banco", aliases=["banco inter"]),
 "Banco Fibra":   _e("Banco Fibra", "Banco Fibra", ["banco fibra"], [], ["banco","credito","middle market"], ["banco fibra"], categoria="Banco", aliases=["banco fibra"]),
 "Banco BV":      _e("Banco BV", "Banco BV votorantim", ["banco bv","banco votorantim"], [], ["banco","financiamento","veiculos","credito"], ["banco bv","banco votorantim","bv s.a"], categoria="Banco", aliases=["banco bv"]),
 "PagBank":       _e("PagBank / PagSeguro", "PagBank PagSeguro", ["pagseguro","pagbank"], [], ["pagamentos","maquininha","fintech","banco digital"], ["pagseguro","pagbank"], categoria="Pagamentos", aliases=["pagbank","pagseguro"]),
 "PicPay":        _e("PicPay", "PicPay", ["picpay"], [], ["pagamentos","carteira digital","fintech"], ["picpay"], categoria="Pagamentos", aliases=["picpay"]),
 "Neon":          _e("Neon", "Neon banco digital", ["neon pagamentos","neon financeira"], ["neon"], ["banco digital","fintech","conta digital"], ["neon"], categoria="Banco", aliases=["neon"]),
 "BNDES":         _e("BNDES", "BNDES banco desenvolvimento", ["bndes"], [], ["banco de desenvolvimento","financiamento","credito","investimento"], ["bndes","banco nacional de desenvolvimento"], categoria="Banco", aliases=["bndes"]),
 # --- Financeiras pequenas / securitizadoras / agro (sem noticia de imprensa: so listadas) ---
 "Banco Digimais":_e("Banco Digimais", news_applicable=False, categoria="Banco", aliases=["digimais"]),
 "Lebes":         _e("Lebes Financeira", news_applicable=False, categoria="Financeira", aliases=["lebes"]),
 "Pefisa":        _e("Pefisa (Pernambucanas)", news_applicable=False, categoria="Financeira", aliases=["pefisa"]),
 "CNH Capital":   _e("Banco CNH Capital", news_applicable=False, categoria="Financeira", aliases=["cnh capital"]),
 "Eco Securitizadora": _e("Eco Securitizadora / Ecoagro", news_applicable=False, categoria="Securitizadora", aliases=["eco securitizadora","ecoagro"]),
 "Opea":          _e("Opea Securitizadora", news_applicable=False, categoria="Securitizadora", aliases=["opea"]),
 "Provincia":     _e("Provincia Securitizadora", news_applicable=False, categoria="Securitizadora", aliases=["provincia"]),
 "Agrofito":      _e("Agrofito", news_applicable=False, categoria="Agro", aliases=["agrofito"]),
 "Coopernorte":   _e("Coopernorte", news_applicable=False, categoria="Agro", aliases=["coopernorte"]),
 "Avantiagro":    _e("Avantiagro", news_applicable=False, categoria="Agro", aliases=["avantiagro","avanti multiplica"]),
 "Cafe Brasil":   _e("Cafe Brasil", news_applicable=False, categoria="Agro", aliases=["cafe brasil"]),
 "Syagri":        _e("Syagri", news_applicable=False, categoria="Agro", aliases=["syagri"]),
 "Toagro":        _e("Toagro", news_applicable=False, categoria="Agro", aliases=["toagro"]),
 # --- Emissores dos EUA / exterior (bonds + acoes diretas em "Outros") ---
 "JPMorgan":      _e("JPMorgan Chase", "JPMorgan Chase bank", ["jpmorgan","jp morgan","j.p. morgan"], [], ["bank","wall street","dimon","investment bank"], sec_ticker="JPM", sec_cik="0000019617", categoria="Banco US", aliases=["jpmorgan","j.p morgan","jp morgan"]),
 "Goldman Sachs": _e("Goldman Sachs", "Goldman Sachs bank", ["goldman sachs"], [], ["bank","wall street","investment bank"], sec_ticker="GS", sec_cik="0000886982", categoria="Banco US", aliases=["goldman sachs"]),
 "Morgan Stanley":_e("Morgan Stanley", "Morgan Stanley bank", ["morgan stanley"], [], ["bank","wall street","wealth management"], sec_ticker="MS", sec_cik="0000895421", categoria="Banco US", aliases=["morgan stanley"]),
 "Citigroup":     _e("Citigroup", "Citigroup bank", ["citigroup","citibank"], [], ["bank","wall street"], sec_ticker="C", sec_cik="0000831001", categoria="Banco US", aliases=["citigroup"]),
 "Wells Fargo":   _e("Wells Fargo", "Wells Fargo bank", ["wells fargo"], [], ["bank","wall street"], sec_ticker="WFC", sec_cik="0000072971", categoria="Banco US", aliases=["wells fargo"]),
 "Barclays":      _e("Barclays", "Barclays bank", ["barclays"], [], ["bank","london","investment bank"], sec_ticker="BCS", categoria="Banco UK", aliases=["barclays"]),
 "UBS":           _e("UBS Group", "UBS Group bank", ["ubs group","ubs ag"], ["ubs"], ["bank","switzerland","wealth management","credit suisse"], sec_ticker="UBS", categoria="Banco Suica", aliases=["ubs group","ubs ag"]),
 "Oracle":        _e("Oracle", "Oracle software cloud", [], ["oracle"], ["software","cloud","database","ellison","erp","data center","orcl","fusion","cerner"], sec_ticker="ORCL", sec_cik="0001341439", categoria="Tech US", aliases=["oracle"]),
 "Occidental":    _e("Occidental Petroleum", "Occidental Petroleum oil", ["occidental petroleum","occidental"], [], ["oil","petroleum","crude","permian"], sec_ticker="OXY", sec_cik="0000797468", categoria="Petroleo US", aliases=["occidental petroleum","occidental"]),
 "Toyota":        _e("Toyota Motor", "Toyota Motor cars", ["toyota motor","toyota"], [], ["cars","automaker","vehicles","hybrid"], sec_ticker="TM", sec_cik="0001094517", categoria="Auto", aliases=["toyota motor"]),
 "Amazon":        _e("Amazon", "Amazon ecommerce AWS", ["amazon.com","amazon inc"], ["amazon"], ["ecommerce","aws","cloud","bezos","jassy","prime"], sec_ticker="AMZN", sec_cik="0001018724", categoria="Tech US", aliases=["amazon"]),
 "Broadcom":      _e("Broadcom", "Broadcom semiconductors", ["broadcom"], [], ["semiconductors","chips","vmware","ai"], sec_ticker="AVGO", sec_cik="0001730168", categoria="Tech US", aliases=["broadcom"]),
 "Eli Lilly":     _e("Eli Lilly", "Eli Lilly pharma", ["eli lilly"], ["lilly"], ["pharma","drug","obesity","mounjaro","zepbound","diabetes"], sec_ticker="LLY", sec_cik="0000059478", categoria="Pharma US", aliases=["eli lilly","lly"]),
 "ExxonMobil":    _e("ExxonMobil", "ExxonMobil oil", ["exxonmobil","exxon mobil","exxon"], [], ["oil","petroleum","crude","gas"], sec_ticker="XOM", sec_cik="0000034088", categoria="Petroleo US", aliases=["exxon mobil","exxon","xom"]),
 "DoorDash":      _e("DoorDash", "DoorDash delivery", ["doordash"], [], ["delivery","food delivery","gig economy"], sec_ticker="DASH", categoria="Tech US", aliases=["doordash"]),
 "JBS":           _e("JBS", "JBS carnes alimentos", ["jbs"], [], ["meat","carnes","frigorifico","alimentos","seara"], cvm_aliases=["jbs"], sec_ticker="JBS", categoria="Alimentos", aliases=["jbs"]),
 # --- Governo / nao aplicavel (listados no relatorio como "sem noticia aplicavel") ---
 "US Treasury":   _e("Tesouro dos EUA", news_applicable=False, categoria="Governo US", aliases=["united states govt","us govt"]),
 "Tesouro":       _e("Tesouro Nacional / BACEN", news_applicable=False, categoria="Governo BR", aliases=["bacen","tesouro nacional"]),
}

# ----------------------------------------------------------------------------
# FIIs (fundos imobiliarios) - monitorados POR TICKER (XXXX11). O alias casa o nome
# embaralhado do ativo na base; forte = [ticker, nome] (a noticia de FII costuma trazer o
# ticker no titulo). ticker XXXX11 -> Yahoo (XXXX11.SA) + Google News por ticker.
# Os marcados "(confirmar)" sao melhor-palpite do ticker; se estiver errado, apenas nao casa
# noticia (nao gera falso positivo) - o dono confirma depois.
# ----------------------------------------------------------------------------
_FII_CTX = ["fii", "fundo imobiliario", "fundos imobiliarios", "rendimento", "dividendo",
            "cota", "cotas", "imovel", "imoveis", "cri", "logistica", "shopping", "lajes",
            "galpao", "vacancia", "aquisicao", "locacao"]
_FIIS = [
    # (ticker, nome, alias_no_ativo)
    ("XPML11", "XP Malls", "xp malls"),
    ("XPLG11", "XP Log", "xp log"),
    ("XPCI11", "XP Credito Imobiliario", "xp cred"),
    ("HGCR11", "CSHG Recebiveis", "hgcr"),
    ("KNSC11", "Kinea Securities", "kinea sc"),
    ("LVBI11", "VBI Logistica", "lvbi"),
    ("PVBI11", "VBI Prime Properties", "pvbi"),
    ("BROF11", "BTG Corporate Office", "brof"),
    ("GGRC11", "GGR Covepi Renda", "ggrcovep"),
    ("TGAR11", "TG Ativo Real", "tg ativo"),
    ("TRXF11", "TRX Real Estate", "trx real"),
    ("SAPI11", "FII SAPI11", "sapi11"),
    # melhor-palpite (confirmar o ticker):
    ("VISC11", "Vinci Shopping Centers", "vinci sc"),
    ("RZTR11", "Riza Terrax", "riza tx"),
    ("GARE11", "Guardian Real Estate", "guardian"),
    ("VGIP11", "Valora CRI IPCA", "valoraip"),
    ("RBRR11", "RBR Rendimento High Grade", "rbr pcri"),
]
for _tk, _nome, _alias in _FIIS:
    _EXTRA[f"FII {_tk}"] = {**_e(f"{_nome} ({_tk})", busca=f"{_nome} fundo imobiliario",
        forte=[_tk, _nome], contexto=_FII_CTX, aliases=[_alias], categoria="FII"),
        "ticker": _tk}

# ----------------------------------------------------------------------------
# GESTORAS de fundos (multimercado / RF / FIDC) - monitoradas pelo NOME da gestora. Noticia
# por fundo praticamente nao existe; a noticia relevante e da casa (M&A, saida de socio,
# fechamento de fundo, problema regulatorio). Aplica-se o MESMO filtro anti-opiniao dos
# bancos (categoria "Gestora" em coleta.validar) p/ nao entrar "o que a gestora acha".
# ----------------------------------------------------------------------------
_GEST_CTX = ["fundo", "fundos", "gestora", "gestao de recursos", "asset", "asset management",
             "multimercado", "cotas", "patrimonio", "investidores"]
_GESTORAS = [
    # (nome, [aliases que casam o nome do fundo no ativo])
    ("Absolute Investimentos", ["absolute"]),
    ("Kapitalo", ["kapitalo"]),
    ("ASA Investments", ["asa hedge"]),
    ("Ibiuna Investimentos", ["ibiuna"]),
    ("Kinea Investimentos", ["kinea atlas", "kinea andes"]),
    ("Quantitas", ["quantitas"]),
    ("Vinland Capital", ["vinland"]),
    ("Hashdex", ["hashdex"]),
    ("ARX Investimentos", ["arx fuji"]),
    ("AZ Quest", ["az quest"]),
    ("Sparta", ["sparta max"]),
    ("Western Asset", ["western asset"]),
    ("Real Investor", ["real investor"]),
    ("Solis Investimentos", ["solis capital"]),
    ("Planner", ["planner fundo"]),
    ("Porto Seguro", ["porto seguro fundo"]),
    ("SulAmerica Investimentos", ["sul america prev"]),
    ("XP Asset", ["xp referenciado", "xp credito estruturado"]),
]
for _nome, _aliases in _GESTORAS:
    _EXTRA[f"Gestora {_nome}"] = _e(_nome, busca=f"{_nome} gestora fundos",
        forte=[_nome], contexto=_GEST_CTX, aliases=_aliases, categoria="Gestora")


def _campos_acao(nome):
    cfg = EMPRESAS[nome]
    meta = _META_ACOES.get(nome, {})
    return {
        "nome": nome,
        "busca": cfg.get("busca"),
        "forte": cfg.get("forte", []),
        "fraco": cfg.get("fraco", []),
        "contexto": cfg.get("contexto", []),
        "cvm_aliases": meta.get("cvm_aliases", []),
        "sec_ticker": meta.get("sec_ticker"),
        "sec_cik": meta.get("sec_cik"),
        "ri_url": meta.get("ri_url"),
        "categoria": meta.get("categoria", "Acao"),
        "aliases": meta.get("aliases", []),
        "news_applicable": True,
        "ticker": cfg.get("ticker", "?"),
    }


# Paginas de RI (Relacoes com Investidores) de cada emissor, para a raspagem best-effort
# (ri_scraping.py). TODAS as empresas da base recebem a sua, mesmo tratamento. Emissores
# sem RI publica (financeiras pequenas, securitizadoras, agro de capital fechado, fintechs
# privadas como PicPay/Neon, e governos) ficam sem url - a CVM/SEC ja cobre o que filarem.
# Editar aqui e simples: chave do emissor -> URL da pagina de comunicados/fatos relevantes.
RI_URLS = {
    # --- BDRs dos EUA ---
    "Alphabet": "https://abc.xyz/investor/", "Microsoft": "https://www.microsoft.com/en-us/investor",
    "Nvidia": "https://investor.nvidia.com/",
    # --- Acoes / BDRs BR ---
    "Alupar": "https://ri.alupar.com.br/", "Anima Educacao": "https://ri.animaeducacao.com.br/",
    "Automob": "https://ri.automob.com.br/", "BR Partners": "https://ri.brpartners.com.br/",
    "Banco do Brasil": "https://ri.bb.com.br/", "BTG Pactual": "https://ri.btgpactual.com/",
    "Cemig": "https://ri.cemig.com.br/", "Copasa": "https://ri.copasa.com.br/",
    "Copel": "https://ri.copel.com/", "Cury": "https://ri.cury.net/",
    "Metalurgica Gerdau": "https://ri.gerdau.com/", "Iguatemi": "https://ri.iguatemi.com.br/",
    "Itausa": "https://www.itausa.com.br/", "Marcopolo": "https://ri.marcopolo.com.br/",
    "Oncoclinicas": "https://ri.grupooncoclinicas.com/", "Petrobras": "https://www.investidorpetrobras.com.br/",
    "PRIO": "https://ri.prio3.com.br/", "Randon": "https://ri.randoncorp.com/",
    "TIM": "https://ri.tim.com.br/", "Track&Field": "https://ri.trackandfield.com.br/",
    "Vale": "https://vale.com/investidores", "Vamos": "https://ri.grupovamos.com.br/",
    "Vivara": "https://ri.vivara.com.br/", "WEG": "https://ri.weg.net/",
    "Boa Safra": "https://ri.boasafrasementes.com.br/",
    # --- Corporates BR (debentures / CRA / bonds) ---
    "Klabin": "https://ri.klabin.com.br/", "Suzano": "https://ri.suzano.com.br/",
    "Eletrobras": "https://ri.eletrobras.com/", "CSN": "https://ri.csn.com.br/",
    "Sabesp": "https://ri.sabesp.com.br/", "Localiza": "https://ri.localiza.com/",
    "Movida": "https://ri.movida.com.br/", "Neoenergia": "https://ri.neoenergia.com/",
    "Ecorodovias": "https://ri.ecorodovias.com.br/", "Enauta": "https://ri.bravaenergia.com/",
    "Simpar": "https://ri.simpar.com.br/", "BRK Ambiental": "https://www.ri.brkambiental.com.br/",
    "Coelce": "https://www.enel.com.br/pt/investidores.html", "Enel SP": "https://www.enel.com.br/pt/investidores.html",
    "Elfa": "https://ri.grupoelfa.com.br/", "Aeris": "https://www.ri.aerisenergy.com.br/",
    "Raizen": "https://ri.raizen.com.br/", "Telefonica": "https://ri.telefonica.com.br/",
    "Axia Energia": "https://ri.axiaenergia.com.br/",
    # --- Bancos BR ---
    "Itau Unibanco": "https://www.itau.com.br/relacoes-com-investidores/",
    "Bradesco": "https://www.bradescori.com.br/", "Banco Pan": "https://ri.bancopan.com.br/",
    "Banco BMG": "https://ri.bancobmg.com.br/", "Banco Original": "https://bancooriginal.com.br/relacoes/",
    "Agibank": "https://ri.agibank.com.br/", "Banco Inter": "https://investors.inter.co/",
    "Banco Fibra": "https://www.bancofibra.com.br/", "Banco BV": "https://www.bv.com.br/relacoes-com-investidores",
    "PagBank": "https://investors.pagseguro.com/", "BNDES": "https://www.bndes.gov.br/wps/portal/site/home/relacoes-com-investidores",
    "Banco C6": "https://www.c6bank.com.br/institucional/",
    # --- Emissores dos EUA / exterior ---
    "JPMorgan": "https://www.jpmorganchase.com/ir", "Goldman Sachs": "https://www.goldmansachs.com/investor-relations/",
    "Morgan Stanley": "https://www.morganstanley.com/about-us-ir", "Citigroup": "https://www.citigroup.com/global/investors",
    "Wells Fargo": "https://www.wellsfargo.com/about/investor-relations/", "Barclays": "https://home.barclays/investor-relations/",
    "UBS": "https://www.ubs.com/global/en/investor-relations.html", "Oracle": "https://investor.oracle.com/",
    "Occidental": "https://www.oxy.com/investors/", "Toyota": "https://global.toyota/en/ir/",
    "Amazon": "https://ir.aboutamazon.com/", "Broadcom": "https://investors.broadcom.com/",
    "Eli Lilly": "https://investor.lilly.com/", "ExxonMobil": "https://corporate.exxonmobil.com/investors",
    "DoorDash": "https://ir.doordash.com/", "JBS": "https://ri.jbs.com.br/",
}


def construir_registro():
    """Monta o dict EMISSORES {chave: campos}. Reaproveita as 28 acoes de EMPRESAS e
    acrescenta os emissores extra. A 'chave' e usada como issuer_key no mapeamento.
    Aplica RI_URLS (pagina de RI de cada emissor) por cima."""
    reg = {}
    for nome in EMPRESAS:
        reg[nome] = _campos_acao(nome)
    for chave, campos in _EXTRA.items():
        campos.setdefault("ticker", "-")
        reg[chave] = campos
    for chave, url in RI_URLS.items():
        if chave in reg:
            reg[chave]["ri_url"] = url
    return reg


EMISSORES = construir_registro()
