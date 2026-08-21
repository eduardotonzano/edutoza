"""Fontes oficiais de dados: Banco Central do Brasil (BCB).

Duas séries do SGS (Sistema Gerenciador de Séries Temporais do BCB),
gratuitas, sem chave de acesso, ambas genuinamente diárias:

- Dólar (USD/BRL): série 1 — "Taxa de câmbio - Livre - Dólar americano
  (venda) - diário". É a cotação oficial de fechamento (PTAX venda),
  a mesma referência usada em balanços, notas fiscais e contratos no Brasil.
  https://api.bcb.gov.br/dados/serie/bcdata.sgs.1/dados

- CDI: série 12 ("Taxa de juros - CDI"), a taxa diária em % ao dia.
  Confirmado por diagnóstico (ver `diagnostico_cdi_diario.py`): ~1 ponto por
  dia útil, e o acumulado de cada mês (compondo os dias) bate com o valor
  oficial já fechado da série 4391 (a que este projeto usava antes) com
  diferença de milésimos de ponto percentual — só ruído de arredondamento.
  A 4391 só publica quando o mês fecha; a 12 já tem o mês corrente
  acumulando dia a dia, o que deixa o CDI tão atualizado quanto o dólar.
  https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados

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
SERIE_CDI = 12         # CDI - taxa diária, % ao dia (ver diagnostico_cdi_diario.py)

URL_SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"

FONTE_DOLAR_NOME = "Banco Central do Brasil — PTAX (dólar venda), série SGS 1"
FONTE_CDI_NOME = "Banco Central do Brasil — CDI, série SGS 12"
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


def _janelas_de_ate_10_anos(data_inicial: dt.date, data_final: dt.date) -> list[tuple[dt.date, dt.date]]:
    """Quebra [data_inicial, data_final] em pedaços de até 10 anos.

    O SGS do BCB recusa (HTTP 406) consultas de séries diárias com janela
    maior que 10 anos — descoberto pelo corpo da resposta de erro, não por
    documentação. Isso é necessário sempre que a janela pedida (ex.: 20
    anos, para as comparações de longo prazo) passa desse limite.
    """
    janelas = []
    inicio = data_inicial
    while inicio <= data_final:
        try:
            fim = dt.date(inicio.year + 10, inicio.month, inicio.day) - dt.timedelta(days=1)
        except ValueError:  # 29/fev em ano não bissexto
            fim = dt.date(inicio.year + 10, inicio.month, inicio.day - 1) - dt.timedelta(days=1)
        fim = min(fim, data_final)
        janelas.append((inicio, fim))
        inicio = fim + dt.timedelta(days=1)
    return janelas


def carregar_serie(
    codigo: int,
    data_inicial: dt.date,
    data_final: Optional[dt.date] = None,
    permitir_cache: bool = True,
) -> list[PontoSerie]:
    """Carrega uma série do SGS/BCB cobrindo [data_inicial, data_final].

    Tenta a API oficial primeiro (em pedaços de até 10 anos — o limite do
    BCB para séries diárias); se falhar (sem rede, host bloqueado etc.) e
    houver cache local cobrindo o período, usa o cache.
    """
    data_final = data_final or dt.date.today()
    cache = _ler_cache(codigo) if permitir_cache else []

    try:
        novos: list[PontoSerie] = []
        for inicio_janela, fim_janela in _janelas_de_ate_10_anos(data_inicial, data_final):
            novos.extend(_consultar_bcb(codigo, inicio_janela, fim_janela))
        if not novos:
            raise ErroFonteDados(f"BCB SGS série {codigo} retornou vazio para o período pedido.")
        combinado = _mesclar(cache, novos)
        _gravar_cache(codigo, combinado)
        resultado = [p for p in combinado if data_inicial <= p.data <= data_final]
    except ErroFonteDados:
        cobertura = [p for p in cache if data_inicial <= p.data <= data_final]
        if not cobertura:
            raise
        resultado = cobertura

    return resultado
