"""Fontes oficiais de dados: Banco Central do Brasil (BCB).

Duas séries do SGS (Sistema Gerenciador de Séries Temporais do BCB),
gratuitas, sem chave de acesso:

- Dólar (USD/BRL): série 1 — "Taxa de câmbio - Livre - Dólar americano
  (venda) - diário". É a cotação oficial de fechamento (PTAX venda),
  a mesma referência usada em balanços, notas fiscais e contratos no Brasil.
  https://api.bcb.gov.br/dados/serie/bcdata.sgs.1/dados

- CDI: série 4391 — "Taxa de juros - CDI anualizada base 252". Publicada
  diariamente pelo BCB a partir dos dados da B3/CETIP, já anualizada
  (% a.a., base 252 dias úteis) — mesma convenção usada para compor o
  fator diário (1 + CDI)^(1/252).
  https://api.bcb.gov.br/dados/serie/bcdata.sgs.4391/dados

Os dados baixados são gravados em cache local (CSV) em `cache/`, para que
o documento possa ser regenerado sem tornar a chamar o BCB toda vez, e para
que o sistema continue funcionando (com o último dado disponível) se a rede
estiver indisponível no momento da geração.
"""
from __future__ import annotations

import csv
import datetime as dt
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests

PASTA_CACHE = Path(__file__).parent / "cache"
PASTA_CACHE.mkdir(exist_ok=True)

SERIE_DOLAR = 1        # Dólar americano (venda) - diário (PTAX)
SERIE_CDI = 4391       # CDI anualizada base 252 (% a.a.)

URL_SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"

FONTE_DOLAR_NOME = "Banco Central do Brasil — PTAX (dólar venda), série SGS 1"
FONTE_CDI_NOME = "Banco Central do Brasil — CDI anualizada base 252, série SGS 4391"
FONTE_URL = "https://www3.bcb.gov.br/sgspub/localizarseries/localizarSeries.do"


class ErroFonteDados(RuntimeError):
    """Erro ao consultar uma fonte oficial de dados."""


@dataclass
class PontoSerie:
    data: dt.date
    valor: float


def _cache_path(codigo: int) -> Path:
    return PASTA_CACHE / f"sgs_{codigo}.csv"


def _ler_cache(codigo: int) -> list[PontoSerie]:
    caminho = _cache_path(codigo)
    if not caminho.exists():
        return []
    pontos = []
    with caminho.open(newline="", encoding="utf-8") as f:
        for linha in csv.DictReader(f):
            pontos.append(
                PontoSerie(
                    data=dt.date.fromisoformat(linha["data"]),
                    valor=float(linha["valor"]),
                )
            )
    return sorted(pontos, key=lambda p: p.data)


def _gravar_cache(codigo: int, pontos: list[PontoSerie]) -> None:
    caminho = _cache_path(codigo)
    with caminho.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["data", "valor"])
        for p in sorted(pontos, key=lambda x: x.data):
            w.writerow([p.data.isoformat(), p.valor])


def _mesclar(existentes: list[PontoSerie], novos: list[PontoSerie]) -> list[PontoSerie]:
    por_data = {p.data: p for p in existentes}
    for p in novos:
        por_data[p.data] = p
    return sorted(por_data.values(), key=lambda p: p.data)


def _consultar_bcb(codigo: int, data_inicial: dt.date, data_final: dt.date) -> list[PontoSerie]:
    """Consulta o SGS do BCB para uma série no intervalo informado.

    Lança ErroFonteDados se a rede/host não responder — quem chama decide
    se cai para o cache local (ver `carregar_serie`).
    """
    params = {
        "formato": "json",
        "dataInicial": data_inicial.strftime("%d/%m/%Y"),
        "dataFinal": data_final.strftime("%d/%m/%Y"),
    }
    # O 406 do gateway do BCB não mudou com nenhuma variação de headers testada até
    # agora — o mais provável é bloqueio (intermitente) de IPs de datacenter, o
    # mesmo comportamento já visto com a CVM neste projeto (ver README). Contra
    # isso, headers sozinhos não resolvem; o que ajuda é tentar de novo (o runner
    # do GitHub Actions pode sair por um IP diferente numa nova tentativa) e, se
    # persistir, mostrar o corpo da resposta do BCB — que deve indicar o motivo
    # real — em vez de só repetir "406 Not Acceptable" às cegas.
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate",
    }
    url = URL_SGS.format(codigo=codigo)
    tentativas = 4
    atrasos = [3, 6, 12]  # segundos entre tentativas (backoff)
    ultimo_erro: Exception | None = None
    for tentativa in range(tentativas):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=30)
            if resp.status_code != 200:
                corpo = resp.text[:300].replace("\n", " ")
                raise ErroFonteDados(
                    f"BCB SGS série {codigo} devolveu HTTP {resp.status_code}: {corpo!r}"
                )
            dados = resp.json()
            break
        except Exception as exc:  # rede indisponível, host recusou, JSON inválido...
            ultimo_erro = exc
            if tentativa < tentativas - 1:
                time.sleep(atrasos[tentativa])
    else:
        raise ErroFonteDados(f"Falha ao consultar BCB SGS série {codigo}: {ultimo_erro}") from ultimo_erro

    pontos = []
    for item in dados:
        try:
            data = dt.datetime.strptime(item["data"], "%d/%m/%Y").date()
            valor = float(item["valor"].replace(",", "."))
        except (KeyError, ValueError):
            continue
        pontos.append(PontoSerie(data=data, valor=valor))
    return pontos


def carregar_serie(
    codigo: int,
    data_inicial: dt.date,
    data_final: Optional[dt.date] = None,
    permitir_cache: bool = True,
) -> list[PontoSerie]:
    """Carrega uma série do SGS/BCB cobrindo [data_inicial, data_final].

    Tenta a API oficial primeiro; se falhar (sem rede, host bloqueado etc.)
    e houver cache local cobrindo o período, usa o cache — sinalizando o
    fato para quem chamou através do valor de retorno de `origem`.
    """
    data_final = data_final or dt.date.today()
    cache = _ler_cache(codigo) if permitir_cache else []

    try:
        novos = _consultar_bcb(codigo, data_inicial, data_final)
        if not novos:
            raise ErroFonteDados(f"BCB SGS série {codigo} retornou vazio para o período pedido.")
        combinado = _mesclar(cache, novos)
        _gravar_cache(codigo, combinado)
        return [p for p in combinado if data_inicial <= p.data <= data_final]
    except ErroFonteDados:
        cobertura = [p for p in cache if data_inicial <= p.data <= data_final]
        if cobertura:
            return cobertura
        raise
