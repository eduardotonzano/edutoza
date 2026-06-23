"""Consulta o Fundos.NET (fnet / B3) - documentos recentes de FIIs e FIDCs.

E o canal OFICIAL onde fundos imobiliarios e FIDCs publicam fato relevante, comunicado,
rendimento e relatorios - quase em tempo real. Usado pelo ALERTA intraday (alerta.py), nao
pelo relatorio diario. Qualquer falha de rede/formato e silenciosa (retorna []).

Estrategia: baixa os documentos mais recentes (ja vem ordenado por data de entrega desc),
filtra os das ultimas `janela_min` e casa o nome do fundo (descricaoFundo) com os tokens da
nossa base (FIIs do registro + FIDCs da carteira). Sem CNPJ: casa por nome.
"""

import time, requests, unicodedata
from datetime import datetime, timezone, timedelta

URL = "https://fnet.bmfbovespa.com.br/fnet/publico/pesquisarGerenciadorDocumentosDados"
DOC = "https://fnet.bmfbovespa.com.br/fnet/publico/exibirDocumento?id={id}&cvm=true"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
           "Accept": "application/json, text/javascript, */*; q=0.01",
           "X-Requested-With": "XMLHttpRequest",
           "Referer": "https://fnet.bmfbovespa.com.br/fnet/publico/abrirGerenciadorDocumentosCVM"}
TIMEOUT = (8, 30)
TENTATIVAS = 3
BACKOFF = (2, 4)
BRT = timezone(timedelta(hours=-3))
# tipoFundo no fnet: 1 = FII, 2 = FIDC (cobre os dois tipos que monitoramos).
TIPOS = {"1": "FII", "2": "FIDC"}


def _norm(t):
    return " ".join(unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore")
                    .decode("ascii").lower().split())


def _data(s):
    """dataEntrega do fnet vem como 'dd/MM/yyyy HH:mm' (horario de Brasilia)."""
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).replace(tzinfo=BRT).astimezone(timezone.utc)
        except Exception:
            continue
    return None


def buscar_fnet(tokens, janela_min=90, paginas=2, por_pagina=100):
    """tokens: lista de (token_norm, rotulo, ticker). Retorna itens no formato do relatorio
    (mesma estrutura de fato_relevante) para os docs das ultimas `janela_min` cujo nome do
    fundo contenha algum token. Falha -> []."""
    limite = datetime.now(timezone.utc) - timedelta(minutes=janela_min)
    itens, vistos = [], set()
    for tipo, rotulo_tipo in TIPOS.items():
        for p in range(paginas):
            params = {"d": 1, "s": p * por_pagina, "l": por_pagina,
                      "o[0][dataEntrega]": "desc", "tipoFundo": tipo}
            linhas = None
            for tent in range(TENTATIVAS):
                try:
                    r = requests.get(URL, params=params, headers=HEADERS, timeout=TIMEOUT)
                    if r.status_code == 200 and r.text.strip():
                        linhas = r.json().get("data", []) or []
                        break
                    print(f"  fnet HTTP {r.status_code} ({rotulo_tipo} p{p}) tent {tent+1}/{TENTATIVAS}")
                except Exception as e:
                    print(f"  fnet erro ({rotulo_tipo} p{p}) tent {tent+1}/{TENTATIVAS}: {str(e)[:50]}")
                if tent < TENTATIVAS - 1:
                    time.sleep(BACKOFF[min(tent, len(BACKOFF) - 1)])
            if linhas is None:
                continue
            if not linhas:
                continue
            parou = False
            for d in linhas:
                desc = _norm(d.get("descricaoFundo", ""))
                dt = _data(d.get("dataEntrega", ""))
                if dt is None:
                    continue
                if dt < limite:           # ordenado desc -> daqui pra frente e tudo antigo
                    parou = True
                    break
                alvo = next(((rot, tk) for tok, rot, tk in tokens if tok and tok in desc), None)
                if not alvo:
                    continue
                doc_id = str(d.get("id") or "")
                if not doc_id or doc_id in vistos:
                    continue
                vistos.add(doc_id)
                rot, tk = alvo
                categoria = (d.get("categoriaDocumento") or d.get("tipoDocumento") or "Documento").strip()
                tipo_doc = (d.get("tipoDocumento") or "").strip()
                titulo = f"[{rotulo_tipo}] {categoria}" + (f" - {tipo_doc}" if tipo_doc and tipo_doc != categoria else "")
                itens.append({
                    "id_fnet": doc_id,
                    "data": dt.astimezone(BRT).strftime("%d/%m %H:%M"), "data_obj": dt,
                    "ticker": tk or "-", "nome": rot,
                    "titulo": f"{titulo} - {rot}"[:200],
                    "fonte": "CVM/Fundos.NET", "premium": True,
                    "link": DOC.format(id=doc_id),
                    "score": 10, "relevancia": 10, "resumo_ia": "", "impacto": "",
                    "corpo": f"{titulo} do fundo {rot} (fonte oficial CVM/Fundos.NET).",
                })
            if parou:
                break
    print(f"  fnet: {len(itens)} documentos novos (ultimos {janela_min} min) dos nossos fundos")
    return itens
