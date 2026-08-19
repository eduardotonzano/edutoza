# Monitor de Notícias da Carteira

Sistema que monitora notícias das últimas 24h para cada ativo de uma carteira de
investimentos, valida se a empresa é o **assunto real** da matéria (não apenas
citada de passagem) e gera um relatório em Excel.

## Para quem vai continuar este projeto (ex: Claude Code)

Este projeto nasceu de uma longa sessão de iteração. O dono é um estagiário de
research buy-side, **não-programador**, que precisa monitorar ~28 ativos (Brasil +
exterior) e hoje roda tudo no Google Colab. O objetivo é evoluir para algo mais
robusto e, idealmente, automatizado (rodar sozinho toda manhã).

### O que JÁ funciona (validado em lógica)
- Coleta via **GDELT DOC API** (gratuita, sem chave, últimas 24h). Trocada do
  Google News RSS porque o GDELT aceita IPs de nuvem, permitindo rodar de graça
  no GitHub Actions. A coleta é feita em **poucas consultas em lote** (≈7 empresas
  por consulta, unidas por `OR`) em vez de 1 busca por empresa — o GDELT limita a
  taxa por IP e barra dezenas de buscas seguidas a partir do IP compartilhado do
  GitHub. A atribuição da notícia à empresa certa acontece depois, na validação
  (que exige o nome no título), então a precisão não muda.
- Validador de relevância focado em notícia **sobre a empresa** (não citação de passagem):
  - **Exige a empresa no TÍTULO** (nome forte; ou nome fraco + termo de contexto).
  - **Rejeita manchetes macro/mercado** (lista `MACRO_TITULO`: "Stocks Soar", "Dow/S&P/
    Nasdaq", "biggest analyst calls", "Fed rate", etc.).
  - **Rejeita roundups** (título citando 3+ empresas diferentes da carteira).
  - Pontua por posição da empresa no título + verbo de ação + contexto + fonte premium.
- Janela de 24h reforçada pela **data de publicação real** (extraída por trafilatura/
  htmldate), além do filtro de data do GDELT — corta matérias antigas re-indexadas.
- Estrutura de nomes em 3 níveis por empresa: `forte` (inequívoco), `fraco`
  (ambíguo, exige contexto) e `contexto` (termos de setor/produto/executivo).
- Filtro de fontes por **allowlist Tier 1 / Tier 1.5** (em `coleta.py`): só passa
  imprensa de primeira/segunda linha e trade press setorial; tudo fora da lista é
  descartado (corta sites de "fulano comprou X ações" e agregadores).
- Download em paralelo (ThreadPoolExecutor) com timeout real no request.
- Dedup por link E por título normalizado.
- Fallback: se o corpo não baixar, valida pelo título + resumo do RSS.
- Geração de Excel com 3 abas: NOTÍCIAS, RESUMO POR ATIVO, SEM COBERTURA.
- **Resumo por IA (Google Gemini, gratuito):** `resumo_ia.py` preenche as colunas
  RESUMO IA e IMPACTO de cada notícia via `gemini-2.0-flash` (free tier do Google AI
  Studio, sem custo). É **opcional** — só roda se a variável `GEMINI_API_KEY` existir;
  sem ela, as colunas ficam vazias e o resto roda normal. Falha por notícia é
  silenciosa (não derruba o run).

### O que FALTA / PRÓXIMOS PASSOS (pendências reais)
1. **Calibração ao vivo:** a lógica foi testada em casos sintéticos, mas a coleta
   real (Google News + download dos portais) nunca foi medida com dados reais num
   ambiente com internet plena. Rodar, medir taxa de cobertura e de fallback, e
   ajustar `WORKERS`, `TIMEOUT` e os termos de `contexto` por empresa.
2. **Bloqueio de fontes:** muitos portais (WSJ, FT, Bloomberg) têm paywall e
   retornam corpo vazio → caem no fallback de resumo. Avaliar se o resumo é
   suficiente ou se vale integrar uma fonte paga.
3. **IA na decisão de relevância (futuro):** hoje a IA só resume/avalia impacto
   (depois do filtro por regex). Uma etapa de LLM julgando "esta notícia é sobre a
   empresa como ativo?" poderia refinar os casos ambíguos que o regex ainda erra.
4. **Automação:** ✅ feito — GitHub Actions roda **todos os dias** às 17h e envia por e-mail.
5. **Resumo por IA:** ✅ feito — `resumo_ia.py` preenche RESUMO IA e IMPACTO com o
   Google Gemini, gratuito (precisa do segredo `GEMINI_API_KEY`; ver seção de automação).

### Decisões de design importantes (não reverter sem pensar)
- O dono pediu explicitamente: **zero falso positivo** (nada de notícia que não é
  sobre a empresa), mas **com variedade** (não pode vir vazio). Esse equilíbrio é
  o coração do projeto e a fonte de quase toda a iteração.
- Match é sempre por **palavra inteira** (regex com fronteira), nunca substring —
  "CAT" não pode casar dentro de "location".
- Nomes ambíguos (Apple, Ford, Roche, BP, Merck) exigem termo de contexto para
  evitar falsos positivos (Harrison Ford, La Roche-Posay, Merck KGaA alemã).

## Cobertura: TODA a base (340 ativos), monitorada por EMISSOR
O `carteira_completa.csv` (340 ativos: ações, BDRs, bonds, CDB, debêntures, CRA, LCA,
fundos, FIIs, títulos públicos…) é a fonte da verdade. Como um CDB ou uma debênture não
tem "notícia", o robô monitora o **emissor** por trás de cada ativo (o banco/empresa).
Vários ativos colapsam num só emissor (ex.: dezenas de CDBs do BTG → um emissor). O
relatório lista **todos os 340 ativos** com um STATUS: *notícia encontrada* / *sem notícia
hoje* / *sem notícia aplicável* (Tesouro/governo e fundos sem empresa pública).

### Fontes (todas gratuitas)
- **GDELT** — imprensa global/BR Tier 1 (notícia das últimas 24h), em lotes com `OR`.
- **CVM (dados.cvm.gov.br)** — fatos relevantes/comunicados oficiais de TODOS os emissores
  BR (feed IPE). Validado: ~900 filings/ano dos nossos emissores casam.
- **SEC/EDGAR (data.sec.gov)** — eventos materiais (8-K/6-K) dos emissores dos EUA
  (JPMorgan, Goldman, Oracle, Toyota, Broadcom…). Exige e-mail de contato no User-Agent
  (vem do segredo `MAIL_USERNAME` via `SEC_CONTACT`).
- **RI (best-effort)** — raspagem das páginas de Relações com Investidores dos emissores
  que tiverem `ri_url` no registro (aditivo; CVM/SEC continuam os canais autoritativos).

## Estrutura dos arquivos
- `carteira_completa.csv` — a base inteira (340 ativos: ATIVO, TIPO, MOEDA, CATEGORIA).
- `emissores.py`  — registro central de ~92 emissores (busca/forte/fraco/contexto, aliases
  da CVM, CIK/ticker da SEC, ri_url, `news_applicable`). Reaproveita `empresas.py`.
- `empresas.py`   — dicionário-base das 28 ações (busca/forte/fraco/contexto/ticker).
- `mapeamento.py` — liga cada um dos 340 ativos ao seu emissor.
- `coleta.py`     — GDELT (lotes com OR), download isolado em processos, validação.
- `fato_relevante.py` — fatos relevantes da CVM (IPE).
- `sec_edgar.py`  — fatos relevantes (8-K/6-K) da SEC/EDGAR.
- `ri_scraping.py`— raspagem best-effort das páginas de RI.
- `resumo_ia.py`  — resumo/impacto via Google Gemini (gratuito, opcional).
- `excel.py`      — relatório com abas NOTICIAS, CARTEIRA (340 ativos+status), EMISSORES.
- `main.py`       — orquestra: base → GDELT + CVM + SEC + RI → dedup → IA → Excel.
- `requirements.txt` — dependências.

### Para testar sem acionar o limite do GDELT
Na aba **Actions → Run workflow**, o campo **pular_gdelt = true** roda só as fontes
oficiais (CVM/SEC/RI), sem tocar no GDELT — útil para validar sem esperar o cooldown do IP.

## Como rodar
```bash
pip install -r requirements.txt
python main.py --carteira Planilha_para_API.xlsx
```
A planilha precisa ter uma aba `CARTEIRA` com colunas `TICKER` e `NOME`.

## Automação (GitHub Actions) — roda sozinho toda tarde e envia por e-mail

O arquivo `.github/workflows/monitor.yml` faz o monitor rodar sozinho **todos os
dias às 17:00 de Brasília** (20:00 UTC), olhando as notícias das **últimas 24
horas**. Ao terminar, ele **envia o Excel por e-mail** e também deixa uma cópia
anexada à execução (backup).

### Resumo por IA (Google Gemini, gratuito) — opcional
Para preencher as colunas **RESUMO IA** e **IMPACTO**, cadastre o segredo
`GEMINI_API_KEY` em **Settings → Secrets and variables → Actions → New repository
secret**. A chave é **gratuita**: pegue em https://aistudio.google.com → "Get API key"
(começa com `AIza...`). Sem ela, o robô pula a etapa de IA (colunas vazias) e o resto
roda normal. Usa o modelo `gemini-2.0-flash` (free tier, sem custo).

### Receber por e-mail (configurar uma vez só)
O envio usa o Gmail. Você precisa cadastrar dois "segredos" no repositório:
1. Crie uma **Senha de app** do Gmail (precisa ter a verificação em duas etapas
   ligada): conta Google → Segurança → "Senhas de app" → gere uma de 16 letras.
2. No repositório: **Settings → Secrets and variables → Actions → New repository
   secret** e crie estes dois:
   - `MAIL_USERNAME` = seu e-mail (ex.: `eduardotonzano@gmail.com`)
   - `MAIL_PASSWORD` = a senha de app de 16 letras (sem espaços)

Enquanto os segredos não existirem, o robô **pula** o envio (sem dar erro) e o
relatório fica só no backup (Artifacts). O e-mail vai para `eduardotonzano@gmail.com`
(definido na linha `to:` do `monitor.yml`).

### Pegar o relatório pelo site (backup, sem e-mail)
1. Abra o repositório no GitHub e clique na aba **Actions** (no topo).
2. No menu da esquerda, clique em **Monitor de Notícias da Carteira**.
3. Clique na execução mais recente (a primeira da lista, com ✓ verde).
4. Role até o final, na seção **Artifacts**, e clique em **relatorio-noticias**
   para baixar o Excel.

### Rodar na hora (sem esperar as 17h)
Na aba **Actions** → **Monitor de Notícias da Carteira** → botão
**Run workflow** (canto direito) → **Run workflow**.

### Mudar o horário
No `monitor.yml`, na linha `cron: "0 20 * * *"`, o `20` é a hora **em UTC**.
Brasília = UTC−3, então `20` = 17:00 daqui. Ex.: para 18:00 de Brasília, use `21`.

> ℹ️ **Sobre a fonte (GDELT) e o limite por IP:** a coleta usa o GDELT, que aceita
> requisições de servidores de nuvem — por isso roda de graça no GitHub Actions. O
> GDELT limita a taxa **por IP**: o IP do GitHub Actions é compartilhado por muita
> gente, então **rodar o monitor várias vezes seguidas** (vários "Run workflow" em
> sequência) coloca o IP em *cooldown* e o GDELT passa a responder `HTTP 429` (a
> coleta volta vazia). Isso **não acontece na operação normal** (1 execução por dia,
> ~4 consultas em lote). Se precisar testar manualmente, espere algumas horas entre
> execuções. Quando há 429, o robô **desiste rápido** (não trava) e segue o resto do
> pipeline; o e-mail é enviado mesmo assim, só com menos (ou nenhuma) notícia.
>
> ℹ️ **Sobre a CVM (fatos relevantes):** o passo 3.5 baixa o feed oficial de fatos
> relevantes em `dados.cvm.gov.br`. Esse host às vezes recusa conexões vindas de
> IPs de datacenter (timeout); por isso o passo tem timeout curto e é "melhor
> esforço" — se a CVM não responder, o robô apenas segue sem os fatos relevantes
> (sem derrubar o run).

---

# Dólar x CDI — documento de rentabilidade acumulada

Segundo sistema deste repositório (independente do monitor de notícias acima): gera
automaticamente um **PDF pronto para enviar**, comparando a variação do dólar (USD/BRL)
com o rendimento acumulado do CDI em 4 janelas de tempo (1, 5, 10 e 20 anos), com o
mesmo estilo visual (cores, fonte e logo) da Multiplica usado nas lâminas de fundos —
substitui a antiga planilha `dolar_x_cdi._auto__comparação.xlsm` (que dependia de dados
pagos do Bloomberg Terminal, hoje desatualizada) por um pipeline automático com **fontes
100% oficiais e gratuitas**.

## Fontes oficiais dos dados
Ambas do **Sistema Gerenciador de Séries Temporais (SGS)** do Banco Central do Brasil —
públicas, gratuitas, sem necessidade de cadastro ou chave de API:

| Dado | Série SGS | O que é |
|---|---|---|
| Dólar (USD/BRL) | [série 1](https://api.bcb.gov.br/dados/serie/bcdata.sgs.1/dados) | Taxa de câmbio Livre — dólar americano (venda), diária. É a cotação **PTAX-venda**, a referência oficial usada em balanços e contratos no Brasil. |
| CDI | [série 4391](https://api.bcb.gov.br/dados/serie/bcdata.sgs.4391/dados) | CDI anualizado, base 252 dias úteis (% a.a.), calculado pelo BCB a partir dos dados da B3. |

**Metodologia:** o dólar usa a variação simples entre a cotação de início e de fim de
cada janela; o CDI (e o "CDI + spread", uma linha de referência auxiliar) usa
capitalização diária composta — fator do dia = `(1 + CDI% a.a.)^(1/252)`, acumulado dia
a dia. Mesma lógica de composição que já existia na planilha original, só que a partir
de dados oficiais em vez do Bloomberg.

## Como usar
```bash
cd dolar_x_cdi
pip install -r requirements.txt
python gerar_documento.py                 # busca os dados reais no Banco Central
python gerar_documento.py --spread 0.05    # muda o "CDI + X%" de referência (padrão: 4%)
```
O PDF sai em `dolar_x_cdi/output/Dolar_x_CDI_<data>.pdf`.

**Pedir para o Claude gerar o documento:** basta pedir "elabore o documento Dólar x CDI"
(ou similar) numa conversa com o Claude Code neste repositório — ele roda o
`gerar_documento.py` e te devolve o PDF atualizado. Isso só funciona num ambiente com
acesso à internet livre (a sessão precisa alcançar `api.bcb.gov.br`); num sandbox com
rede restrita, rode `python gerar_documento.py --amostra` para gerar um PDF de
demonstração do layout (marcado em vermelho como amostra, com dados antigos da planilha
original só para validar o visual) — ou use a automação abaixo.

## Automação (GitHub Actions) — sem depender de sessão nenhuma
O arquivo `.github/workflows/dolar_x_cdi.yml` gera o documento sozinho, todo **dia 1 de
cada mês**, e manda por e-mail (reaproveita os mesmos segredos `MAIL_USERNAME` /
`MAIL_PASSWORD` já configurados para o monitor de notícias — ver seção de automação
acima). Como as janelas são de médio/longo prazo, não precisa rodar todo dia.
Para gerar na hora **quem tem acesso ao GitHub**: aba **Actions** → **Documento Dólar x
CDI** → **Run workflow**.

## Pedir por e-mail — sem precisar de GitHub nem de Claude
Pensado para qualquer pessoa do time que não tenha (ou não queira usar) conta no GitHub:
basta **mandar um e-mail** para o endereço configurado (o mesmo do monitor de notícias)
com uma destas frases no **assunto**: `dólar x cdi`, `dolar cdi` ou `gerar documento`
(não é sensível a acento/maiúscula). Em até ~15 minutos, o robô responde automaticamente
para quem pediu, com o PDF atualizado (dados oficiais do BCB) em anexo.

Como funciona (`.github/workflows/dolar_x_cdi_pedidos.yml` + `verificar_pedidos.py`):
a cada 15 minutos, um robô lê a caixa de entrada via IMAP procurando e-mails não lidos
com uma das frases-gatilho no assunto; para cada um, gera o documento na hora e responde
diretamente ao remetente com o PDF anexado (ou avisa se algo deu errado). Não precisa de
nenhuma dependência nova — usa só `imaplib`/`smtplib` da biblioteca padrão do Python, com
o mesmo login de app do Gmail já usado para enviar os e-mails do monitor de notícias.

> ⚠️ Qualquer pessoa que souber o endereço de e-mail e usar a frase certa no assunto
> consegue disparar uma geração — não há autenticação além disso. Adequado para uso
> interno de time; não divulgue o endereço publicamente. Limite de segurança: no máximo
> 5 pedidos processados por execução (a cada 15 min), pra não sobrecarregar em caso de
> uso indevido.

## Estrutura
- `fontes.py` — busca as duas séries no BCB (com cache local em `cache/`, para não
  depender de internet toda vez e continuar funcionando com o último dado se o BCB
  estiver fora do ar no momento).
- `calculo.py` — calcula a rentabilidade acumulada de cada janela (dólar, CDI, CDI+spread)
  e indicadores complementares (volatilidade, maior alta/queda, drawdown).
- `graficos.py` — gera os gráficos (matplotlib) no estilo visual da marca.
- `estilo.py` — paleta de cores, fonte e logo (extraídos das lâminas de exemplo).
- `modelo.html` + `documento.py` — monta o HTML e renderiza o PDF final (WeasyPrint).
- `gerar_documento.py` — ponto de entrada CLI (`--amostra`, `--spread`, `--saida`) e as
  funções reutilizáveis `gerar_a_partir_do_bcb` / `gerar_a_partir_de_amostra`.
- `verificar_pedidos.py` — lê pedidos por e-mail (IMAP) e responde com o PDF (ver seção
  "Pedir por e-mail" acima).
- `amostra/` — dados históricos (2006–2026) que já vinham na planilha original
  (Bloomberg), usados **só** no modo `--amostra` para testar o layout sem internet.
  Nunca usados no modo normal (que sempre busca o dado oficial mais recente no BCB).
