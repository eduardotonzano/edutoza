# Agendador das 17h (chegar no horário exato)

> **STATUS: EM ESPERA.** A tentativa pelo cron-job.org deu **401** (token recusado pelo
> GitHub). Por ora o robô usa o **agendamento nativo do GitHub** (cron `50 19 * * *` ≈ 16:50
> BRT, fora do topo da hora p/ reduzir a fila) — chega todo dia, perto das 17h, mas o GitHub
> não garante o minuto exato. Este guia continua válido para quando você quiser cravar as 17h.

## Por que isso existe
O cron nativo do GitHub Actions **atrasa muito** no topo da hora (o e-mail chegava 20h–21h
em vez de 17h). A solução é um **agendador externo grátis** (cron-job.org) que chama o robô
via API exatamente às **17:00 de Brasília**. O job em si roda em ~2 min, então o e-mail chega
por volta das **17:02**.

> Já removi o cron do GitHub do robô (para não chegar um e-mail duplicado e atrasado).
> Falta só você fazer a configuração abaixo **uma vez**.

---

## Passo 1 — Gerar um token do GitHub (uma vez)
1. Acesse: https://github.com/settings/tokens?type=beta (Settings → Developer settings →
   **Fine-grained tokens** → **Generate new token**).
2. Preencha:
   - **Token name:** `edutoza-agendador`
   - **Expiration:** sem expiração (ou 1 ano — quando vencer, é só gerar outro).
   - **Repository access:** **Only select repositories** → escolha **`eduardotonzano/edutoza`**.
   - **Permissions** → **Repository permissions** → **Actions**: mude para **Read and write**.
     (Pode aparecer "Metadata: Read-only" automaticamente — tudo bem, deixe.)
3. **Generate token** e **copie** o token (começa com `github_pat_...`). Guarde — só aparece
   uma vez. Esse token **não** vai para o repositório; vai só no cron-job.org (passo 2).

## Passo 2 — Criar a conta e o job no cron-job.org (uma vez)
1. Crie uma conta grátis em https://cron-job.org e faça login.
2. **Create cronjob** e preencha:
   - **Title:** `Monitor Carteira 17h`
   - **URL:**
     ```
     https://api.github.com/repos/eduardotonzano/edutoza/actions/workflows/monitor.yml/dispatches
     ```
   - **Schedule:** todos os dias, **17:00**. Em **Timezone**, escolha **America/Sao_Paulo**.
     (Se o site não tiver fuso por job, use **20:00 UTC** — dá no mesmo, pois BRT = UTC−3.)
3. Abra as opções **avançadas** do job:
   - **Request method:** **POST**
   - **Request body:** (cole exatamente)
     ```
     {"ref":"main"}
     ```
   - **Headers** (adicione um por um — clique em "Add header"):
     | Key | Value |
     |-----|-------|
     | `Authorization` | `Bearer COLE_AQUI_O_TOKEN` |
     | `Accept` | `application/vnd.github+json` |
     | `X-GitHub-Api-Version` | `2022-11-28` |
     | `Content-Type` | `application/json` |
     | `User-Agent` | `edutoza-cron` |
4. **Salvar.**

## Passo 3 — Testar agora (opcional)
No cron-job.org, use **"Run now"** (ou "Test run"). Em ~2 min o e-mail deve chegar. Se o
cron-job.org mostrar resposta **HTTP 204**, deu certo (o GitHub responde 204 sem corpo).
Se der **401/403**, o token está errado ou sem a permissão **Actions: Read and write**
(refaça o passo 1). Se der **404**, confira a URL (repo/arquivo `monitor.yml`).

---

## Não chegou às 17h? Como descobrir o porquê
Há uma **rede de segurança** ativa: o agendamento nativo do GitHub também dispara (alvo 17h,
mas pode atrasar). Então o e-mail deve chegar de qualquer forma — só que, se o cron-job.org
não estiver disparando, ele pode vir atrasado. Para consertar o **horário exato**:

1. No cron-job.org, abra o job e veja a aba **"History"** (Histórico de execuções).
2. Olhe a **última execução** e o **status/código de resposta**:
   - **204** → funcionou (o GitHub aceitou). Se mesmo assim não chegou e-mail, o problema é
     outro (me avise) — mas normalmente 204 = ok.
   - **401 / 403** → problema no **token**: gere de novo um token *fine-grained* com
     **Repository → Actions: Read and write** no repo `edutoza` (Passo 1) e atualize o header
     `Authorization`.
   - **404** → **URL errada**: confira que está exatamente
     `https://api.github.com/repos/eduardotonzano/edutoza/actions/workflows/monitor.yml/dispatches`.
   - **vazio / "—" / não executou** → o job está **desativado** ou com **horário/fuso errado**.
     Confirme que o job está **Enabled**, horário **17:00** e fuso **America/Sao_Paulo**.
3. Confirme também o **corpo** `{"ref":"main"}` e o método **POST**.

Me diga qual status aparece no History que eu aponto a correção exata.

## Pronto
Com a rede de segurança do GitHub, o relatório das **últimas 24 horas** chega **todo dia**.
Quando o cron-job.org estiver confirmado (status 204 no History), me avise: eu **removo o
agendamento do GitHub** para você não receber 2 e-mails por dia e ficar só com o **17h02
cravado**. Para mudar o horário, edite o agendamento no cron-job.org.
