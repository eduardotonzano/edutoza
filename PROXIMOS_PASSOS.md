# Próximos passos / pendências

Lista do que ficou para fazer depois. Nada aqui quebra o robô: ele **continua rodando
todo dia às 17h e mandando o e-mail normalmente** — só que, até o item 1 ser feito, o
resumo de IA usa **apenas o Gemini** (grátis), e em dias cheios algumas notícias podem
ficar sem resumo quando a cota grátis do Gemini acaba.

---

## 1) (VOCÊ) Ativar o resumo de IA grátis com o Haiku — cadastrar o token da assinatura

**Por quê:** com isso o resumo dos 2 analistas (otimista x cético) chega perto de 100% das
notícias, usando o **Haiku pela sua assinatura Pro/Max** (sem pagar API da Anthropic). O
código já está pronto e publicado; só falta o token.

**Passo a passo (uma única vez):**

1. **Gerar o token** — no seu computador, abra um terminal:
   - Instale o Node (se não tiver): https://nodejs.org (versão LTS).
   - Instale o Claude Code:
     ```
     npm install -g @anthropic-ai/claude-code
     ```
   - Gere o token:
     ```
     claude setup-token
     ```
   - Faça login na conta **Pro/Max**. Ele devolve um **token longo** (algo como
     `sk-ant-oat...`). **Copie.**

2. **Cadastrar no GitHub** — em https://github.com/eduardotonzano/edutoza :
   - **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.
   - **Name:** `CLAUDE_CODE_OAUTH_TOKEN` (exatamente assim).
   - **Secret:** cole o token → **Add secret**.

3. **Me avisar** para eu disparar um teste. No log deve aparecer
   `IA: ~102/102 ... (Gemini X | Claude Code Y)` e o PDF chega com resumo + analista
   otimista/cético em quase todas as notícias.

> Mantenha o segredo `GEMINI_API_KEY` cadastrado — o Gemini continua sendo o **principal**
> (grátis) e o Haiku só cobre o que sobrar.

---

## 2) (DECISÃO) Limitar quantas notícias/dia o Haiku resume?

**Por quê:** o Haiku no robô consome a **cota da sua assinatura** Pro/Max (que tem limites
semanais). Em dias com muitas notícias (100+), isso pode pesar. Como o Gemini vem primeiro,
o Haiku só pega o resto — mas, se quiser, dá para colocar um **teto diário** (ex.: "Haiku
resume no máximo 40 notícias/dia") para não gastar demais a assinatura.

**Decisão pendente:** quer esse teto? Se sim, qual número? (Eu configuro em 1 linha.)

---

## 3) (OPCIONAL) 4ª fonte de notícias — NewsData.io (grátis)

**Por quê:** hoje a imprensa vem de GDELT + Google News + RSS Tier 1 + Yahoo. A NewsData.io
é uma fonte extra grátis (com chave). Se cadastrar, entra automático; sem ela, é ignorada.

**Como:** pegar a chave em https://newsdata.io e cadastrar como segredo `NEWS_API_KEY`
(mesmo caminho do item 1).

---

## 4) (CONHECIDO) CVM instável a partir do GitHub

Em alguns dias o servidor de dados da CVM (`dados.cvm.gov.br`) recusa conexão do
datacenter do GitHub e os "fatos relevantes" da CVM vêm zerados naquele dia. É
intermitente e costuma voltar sozinho. A SEC (EUA) e a raspagem de RI cobrem a camada
oficial enquanto isso. Sem ação necessária agora — só registrando.

---

_Última atualização: 19/06/2026._
