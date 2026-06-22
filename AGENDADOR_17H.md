# Agendador das 17h (chegar no horário exato)

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

## Pronto
A partir daí, o relatório das **últimas 24 horas** chega todo dia ~**17h02** (Brasília),
no horário certo. Para mudar o horário, é só editar o agendamento no cron-job.org —
não precisa mexer no código.
