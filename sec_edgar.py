"""Fatos relevantes dos emissores dos EUA via SEC/EDGAR (data.sec.gov) - oficial e gratuito.

A SEC publica os 'material events' das empresas americanas no form 8-K (e 6-K para
emissores estrangeiros). O endpoint data.sec.gov e estavel a partir de IPs de datacenter
(exige um User-Agent com contato). Pegamos os 8-K/6-K das ultimas 24h dos emissores US da
carteira e devolvemos no MESMO formato dos outros (fato_relevante.py), para entrar em
'finais'. Qualquer falha e silenciosa (retorna [], nao derruba o run).
"""

import os, requests, time
from datetime import datetime, timezone, timedelta

JANELA_HORAS = 24
TIMEOUT = 20
# A SEC EXIGE um User-Agent com e-mail de contato real; sem isso devolve HTTP 403.
# O e-mail vem da variavel SEC_CONTACT (no workflow, do segredo MAIL_USERNAME), entao
# nao fica escrito no codigo. Fallback generico se a variavel nao existir.
_CONTATO = os.environ.get("SEC_CONTACT") or "monitor@example.com"
SEC_HEADERS = {"User-Agent": f"edutoza-portfolio-monitor {_CONTATO}",
               "Accept-Encoding": "gzip, deflate"}
_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik10}.json"
FORMS = {"8-K", "6-K"}


def carregar_mapa_cik():
    """Baixa company_tickers.json e retorna {TICKER: cik10}. {} em falha (best-effort)."""
    try:
        r = requests.get(_TICKERS_URL, headers=SEC_HEADERS, timeout=TIMEOUT)
        if r.status_code != 200:
            return {}
        dados = r.json()
        return {str(v["ticker"]).upper(): str(v["cik_str"]).zfill(10) for v in dados.values()}
    except Exception:
        return {}


def _resolver_cik(emissor, mapa):
    cik = emissor.get("sec_cik")
    if cik:
        return str(cik).zfill(10)
    tk = (emissor.get("sec_ticker") or "").upper()
    return mapa.get(tk)


def buscar_fatos_sec(emissores_us):
    """Para cada emissor US (com CIK/ticker), busca 8-K/6-K das ultimas 24h na SEC.
    `emissores_us`: lista de dicts do registro (campos nome, ticker, sec_ticker, sec_cik)."""
    if not emissores_us:
        return []
    limite = (datetime.now(timezone.utc) - timedelta(hours=JANELA_HORAS)).date()
    mapa = carregar_mapa_cik()
    itens = []
    n_cik, n_ok, n_falha = 0, 0, 0   # diagnostico de alcance
    ultimo_status = None
    for emissor in emissores_us:
        cik = _resolver_cik(emissor, mapa)
        if not cik:
            continue
        n_cik += 1
        try:
            r = requests.get(_SUBMISSIONS.format(cik10=cik), headers=SEC_HEADERS, timeout=TIMEOUT)
            ultimo_status = r.status_code
            if r.status_code != 200:
                n_falha += 1
                continue
            recent = (r.json().get("filings") or {}).get("recent") or {}
            n_ok += 1
        except Exception as e:
            n_falha += 1
            ultimo_status = str(e)[:40]
            continue
        forms = recent.get("form") or []
        datas = recent.get("filingDate") or []
        acc   = recent.get("accessionNumber") or []
        docs  = recent.get("primaryDocument") or []
        items_l = recent.get("items") or []
        descr = recent.get("primaryDocDescription") or []
        for i, form in enumerate(forms):
            if form not in FORMS:
                continue
            ds = datas[i] if i < len(datas) else ""
            try:
                dt = datetime.strptime(ds, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except Exception:
                continue
            if dt.date() < limite:
                continue
            acc_nd = (acc[i] if i < len(acc) else "").replace("-", "")
            doc = docs[i] if i < len(docs) else ""
            link = (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_nd}/{doc}"
                    if acc_nd else "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany")
            itens_cod = items_l[i] if i < len(items_l) else ""
            desc = descr[i] if i < len(descr) else ""
            corpo = (f"Filing {form} de {emissor['nome']} em {ds}. "
                     f"Itens: {itens_cod or '-'}. {desc}").strip()
            itens.append({
                "data": dt.strftime("%d/%m/%Y"), "data_obj": dt,
                "ticker": emissor.get("ticker") or emissor.get("sec_ticker") or "SEC",
                "nome": emissor["nome"],
                "titulo": f"[SEC {form}] {emissor['nome']} - itens {itens_cod or 's/ codigo'}"[:200],
                "fonte": "SEC/EDGAR", "premium": True, "link": link,
                "score": 10, "relevancia": 10, "resumo_ia": "", "impacto": "",
                "corpo": corpo,
            })
        time.sleep(0.2)   # cortesia com a SEC (limite informal ~10 req/s)
    print(f"  SEC diag: tickers_map={len(mapa)} cik_resolvidos={n_cik} "
          f"submissions_ok={n_ok} falhas={n_falha} ultimo_status={ultimo_status}")
    return itens
