# Monitor de Notícias da Carteira

Sistema que monitora notícias das últimas 24h para cada ativo de uma carteira de
investimentos, valida se a empresa é o **assunto real** da matéria (não apenas
citada de passagem) e gera um relatório em Excel.

## Para quem vai continuar este projeto (ex: Claude Code)

Este projeto nasceu de uma longa sessão de iteração. O dono é um estagiário de
research buy-side, **não-programador**, que precisa monitorar ~53 ativos (Brasil +
exterior) e hoje roda tudo no Google Colab. O objetivo é evoluir para algo mais
robusto e, idealmente, automatizado (rodar sozinho toda manhã).

### O que JÁ funciona (validado em lógica)
- Coleta por empresa via **GDELT DOC API** (gratuita, sem chave, busca dedicada
  por nome, últimas 24h). Trocada do Google News RSS porque o GDELT não bloqueia
  servidores de nuvem, permitindo rodar de graça no GitHub Actions.
- Validador de relevância em dois caminhos:
  - **A) protagonista:** empresa no título, primeira metade, idealmente com verbo de ação.
  - **B) corpo forte:** empresa não está no título mas aparece com força no corpo + contexto.
- Estrutura de nomes em 3 níveis por empresa: `forte` (inequívoco), `fraco`
  (ambíguo, exige contexto) e `contexto` (termos de setor/produto/executivo).
- Filtro de fontes por **blocklist** (barra fórum/spam) + bônus para fontes premium.
- Download em paralelo (ThreadPoolExecutor) com timeout real no request.
- Dedup por link E por título normalizado.
- Fallback: se o corpo não baixar, valida pelo título + resumo do RSS.
- Geração de Excel com 3 abas: NOTÍCIAS, RESUMO POR ATIVO, SEM COBERTURA.

### O que FALTA / PRÓXIMOS PASSOS (pendências reais)
1. **Calibração ao vivo:** a lógica foi testada em casos sintéticos, mas a coleta
   real (Google News + download dos portais) nunca foi medida com dados reais num
   ambiente com internet plena. Rodar, medir taxa de cobertura e de fallback, e
   ajustar `WORKERS`, `TIMEOUT` e os termos de `contexto` por empresa.
2. **Bloqueio de fontes:** muitos portais (WSJ, FT, Bloomberg) têm paywall e
   retornam corpo vazio → caem no fallback de resumo. Avaliar se o resumo é
   suficiente ou se vale integrar uma fonte paga.
3. **Camada de IA (opcional):** a decisão de relevância por regex tem limite. Uma
   etapa de LLM (Claude via API) julgando "esta notícia é sobre a empresa como
   ativo?" resolveria os casos ambíguos que o regex erra. O dono ainda não tem
   chave de API da Anthropic.
4. **Automação:** fazer rodar sozinho toda manhã (cron, GitHub Actions, ou
   Colab agendado) e entregar o resultado (e-mail/WhatsApp/Drive).
5. **Resumo por IA:** as colunas RESUMO IA e IMPACTO no Excel estão vazias,
   prontas para serem preenchidas por uma etapa de sumarização.

### Decisões de design importantes (não reverter sem pensar)
- O dono pediu explicitamente: **zero falso positivo** (nada de notícia que não é
  sobre a empresa), mas **com variedade** (não pode vir vazio). Esse equilíbrio é
  o coração do projeto e a fonte de quase toda a iteração.
- Match é sempre por **palavra inteira** (regex com fronteira), nunca substring —
  "CAT" não pode casar dentro de "location".
- Nomes ambíguos (Apple, Ford, Roche, BP, Merck) exigem termo de contexto para
  evitar falsos positivos (Harrison Ford, La Roche-Posay, Merck KGaA alemã).

## Estrutura dos arquivos
- `empresas.py`   — dicionário das 53 empresas (forte/fraco/contexto/ticker).
- `coleta.py`     — busca no Google News, download paralelo, validação.
- `excel.py`      — geração do relatório Excel.
- `main.py`       — orquestra tudo (lê carteira → coleta → valida → Excel).
- `requirements.txt` — dependências.

## Como rodar
```bash
pip install -r requirements.txt
python main.py --carteira Planilha_para_API.xlsx
```
A planilha precisa ter uma aba `CARTEIRA` com colunas `TICKER` e `NOME`.

## Automação (GitHub Actions) — roda sozinho toda manhã

O arquivo `.github/workflows/monitor.yml` faz o monitor rodar sozinho de
**segunda a sexta às 08:00 de Brasília** (11:00 UTC) e também pode ser
disparado a qualquer momento por um botão. O resultado (Excel) fica anexado
à execução para download.

### Como pegar o relatório (passo a passo)
1. Abra o repositório no GitHub e clique na aba **Actions** (no topo).
2. No menu da esquerda, clique em **Monitor de Notícias da Carteira**.
3. Clique na execução mais recente (a primeira da lista, com ✓ verde).
4. Role até o final, na seção **Artifacts**, e clique em **relatorio-noticias**
   para baixar o Excel.

### Rodar na hora (sem esperar a manhã)
Na aba **Actions** → **Monitor de Notícias da Carteira** → botão
**Run workflow** (canto direito) → **Run workflow**. Em ~1 minuto o relatório
aparece em **Artifacts**.

### Mudar o horário
No `monitor.yml`, na linha `cron: "0 11 * * 1-5"`, o `11` é a hora **em UTC**.
Brasília = UTC−3, então `11` = 08:00 daqui. Ex.: para 07:00 de Brasília, use `10`.

> ℹ️ **Sobre a fonte (GDELT):** a coleta usa o GDELT, que aceita requisições de
> servidores de nuvem — por isso roda de graça no GitHub Actions sem precisar de
> máquina sua ligada. O GDELT tem um limite informal de ~1 consulta a cada poucos
> segundos; por isso o código já espera 1s entre empresas (parâmetro `GDELT_PAUSA`
> em `coleta.py`). Se uma execução vier muito vazia, geralmente é só o GDELT ainda
> não ter indexado as matérias daquela manhã — rodar de novo mais tarde resolve.
