"""Dicionario das empresas da carteira (base CADM - acoes/BDRs).

Estrutura de cada empresa:
  busca    - termo usado na consulta ao GDELT (opcional; default = forte[0] ou nome)
  forte    - nomes inequivocos (se aparece, e a empresa; aceita direto)
  fraco    - nomes ambiguos (curtos/comuns; so valem com termo de contexto junto)
  contexto - termos de setor/produto/executivo que confirmam a empresa
  ticker   - codigo na B3 / BDR (default; pode ser sobrescrito pela planilha)

Nomes ambiguos em portugues (Vale, Vamos, Brasil, TIM) ficam em 'fraco' e exigem
contexto, para manter o principio de ZERO falso positivo.
"""

EMPRESAS = {
 "Alphabet": {"busca":"Alphabet Google","forte":["alphabet inc","alphabet's","google llc"],"fraco":["alphabet","google"],
   "contexto":["google","android","youtube","gemini","sundar pichai","search","anuncios","ads","cloud","waymo"],"ticker":"GOGL34"},
 "Alupar": {"busca":"Alupar transmissao","forte":["alupar"],"fraco":[],
   "contexto":["transmissao","energia","linhas de transmissao","geracao","aneel","leilao"],"ticker":"ALUP11"},
 "Anima Educacao": {"busca":"Anima Educacao","forte":["anima educacao","anima educação"],"fraco":["anima"],
   "contexto":["educacao","ensino superior","universidade","faculdade","inspirali","medicina","alunos","mensalidade"],"ticker":"ANIM3"},
 "Automob": {"busca":"Automob concessionaria","forte":["automob","grupo automob"],"fraco":[],
   "contexto":["concessionaria","veiculos","carros","revenda","seminovos","automoveis","montadora"],"ticker":"AMOB3"},
 "BR Partners": {"busca":"BR Partners banco","forte":["br partners"],"fraco":[],
   "contexto":["banco de investimento","assessoria","m&a","fusoes","aquisicoes","mercado de capitais"],"ticker":"BRBI11"},
 "Banco do Brasil": {"busca":"Banco do Brasil","forte":["banco do brasil"],"fraco":[],
   "contexto":["banco","credito","agronegocio","lucro","dividendos","estatal","inadimplencia","carteira de credito"],"ticker":"BBAS3"},
 "BTG Pactual": {"busca":"BTG Pactual","forte":["btg pactual"],"fraco":["btg"],
   "contexto":["banco","investimento","gestao de recursos","andre esteves","wealth","credito"],"ticker":"BPAC11"},
 "Cemig": {"busca":"Cemig energia","forte":["cemig"],"fraco":[],
   "contexto":["energia","eletrica","distribuicao","minas gerais","geracao","transmissao"],"ticker":"CMIG4"},
 "Copasa": {"busca":"Copasa saneamento","forte":["copasa"],"fraco":[],
   "contexto":["saneamento","agua","esgoto","minas gerais","concessao"],"ticker":"CSMG3"},
 "Copel": {"busca":"Copel energia","forte":["copel"],"fraco":[],
   "contexto":["energia","eletrica","parana","distribuicao","geracao","transmissao"],"ticker":"CPLE6"},
 "Cury": {"busca":"Cury construtora","forte":["cury construtora","cury s.a","cury"],"fraco":[],
   "contexto":["construtora","incorporadora","construcao","imoveis","habitacao","minha casa minha vida","lancamentos","vso"],"ticker":"CURY3"},
 "Metalurgica Gerdau": {"busca":"Gerdau siderurgica","forte":["metalurgica gerdau","gerdau"],"fraco":[],
   "contexto":["siderurgica","aco","steel","metalurgia","usina","minerio"],"ticker":"GOAU4"},
 "Iguatemi": {"busca":"Iguatemi shopping","forte":["iguatemi"],"fraco":[],
   "contexto":["shopping","shopping center","varejo","aluguel","empreendimento","abl","lojas"],"ticker":"IGTI11"},
 "Itausa": {"busca":"Itausa","forte":["itausa","itaúsa"],"fraco":[],
   "contexto":["holding","itau","dividendos","participacoes","investimentos","portfolio"],"ticker":"ITSA4"},
 "Marcopolo": {"busca":"Marcopolo onibus","forte":["marcopolo"],"fraco":[],
   "contexto":["onibus","carrocerias","veiculos","fabricante","exportacao","volare"],"ticker":"POMO4"},
 "Microsoft": {"busca":"Microsoft","forte":["microsoft"],"fraco":[],
   "contexto":["azure","windows","nadella","copilot","nuvem","cloud","software","xbox"],"ticker":"MSFT34"},
 "Nvidia": {"busca":"Nvidia","forte":["nvidia"],"fraco":[],
   "contexto":["chips","gpu","semicondutores","jensen huang","inteligencia artificial","data center","ia"],"ticker":"NVDC34"},
 "Oncoclinicas": {"busca":"Oncoclinicas","forte":["oncoclinicas","oncoclínicas"],"fraco":[],
   "contexto":["oncologia","cancer","saude","hospital","tratamento","clinicas"],"ticker":"ONCO3"},
 "Petrobras": {"busca":"Petrobras","forte":["petrobras"],"fraco":[],
   "contexto":["petroleo","combustivel","gas","pre-sal","refino","estatal","dividendos","barril","diesel","gasolina"],"ticker":"PETR4"},
 "PRIO": {"busca":"PRIO petroleo","forte":["prio","petrorio","petro rio"],"fraco":[],
   "contexto":["petroleo","oleo","campos","producao","barris","exploracao","offshore"],"ticker":"PRIO3"},
 "Randon": {"busca":"Randon implementos","forte":["randon"],"fraco":[],
   "contexto":["implementos","rodoviarios","autopecas","reboques","veiculos","frasle"],"ticker":"RAPT4"},
 "TIM": {"busca":"TIM telefonia Brasil","forte":["tim brasil","tim participacoes","tim s.a"],"fraco":["tim"],
   "contexto":["telecom","telefonia","5g","operadora","celular","banda larga","anatel"],"ticker":"TIMS3"},
 "Track&Field": {"busca":"Track Field varejo","forte":["track&field","track field","track & field"],"fraco":[],
   "contexto":["varejo","esportivo","moda","lojas","fitness","franquias"],"ticker":"TFCO4"},
 "Vale": {"busca":"Vale mineracao","forte":["vale s.a","vale s/a","mineradora vale"],"fraco":["vale"],
   "contexto":["mineracao","minerio","minerio de ferro","mineradora","niquel","carajas","barragem","commodities","pelotas"],"ticker":"VALE3"},
 "Vamos": {"busca":"Vamos locacao caminhoes","forte":["vamos locacao","vamos locadora"],"fraco":["vamos"],
   "contexto":["locacao","caminhoes","frota","veiculos pesados","seminovos","simpar","maquinas"],"ticker":"VAMO3"},
 "Vivara": {"busca":"Vivara joalheria","forte":["vivara"],"fraco":[],
   "contexto":["joalheria","joias","life","varejo","relogios","lojas"],"ticker":"VIVA3"},
 "WEG": {"busca":"WEG equipamentos","forte":["weg"],"fraco":[],
   "contexto":["motores","equipamentos eletricos","jaragua","industria","automacao","energia","exportacao"],"ticker":"WEGE3"},
 "Boa Safra": {"busca":"Boa Safra sementes","forte":["boa safra"],"fraco":[],
   "contexto":["sementes","soja","agro","agronegocio","plantio","graos"],"ticker":"SOJA3"},
}


def carregar_tickers(df_carteira):
    """Preenche o ticker de cada empresa a partir da planilha (colunas NOME e TICKER).
    Se a empresa nao estiver na planilha, mantem o ticker ja definido no dicionario."""
    mapa = {str(r.get("NOME", "")).strip(): str(r.get("TICKER", "")).strip()
            for _, r in df_carteira.iterrows()}
    for nome in EMPRESAS:
        if mapa.get(nome):
            EMPRESAS[nome]["ticker"] = mapa[nome]
        EMPRESAS[nome].setdefault("ticker", "?")
    return EMPRESAS
