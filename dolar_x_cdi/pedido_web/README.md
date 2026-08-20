# Formulário web — peça o PDF sem escrever e-mail nenhum

Uma página com um campo de e-mail e um botão. A pessoa digita o e-mail, aperta o botão,
e o PDF "Dólar x CDI" (dados reais do BCB) chega na caixa dela em alguns minutos — sem
precisar saber compor e-mail, sem precisar de conta no GitHub.

Como funciona: um Worker da Cloudflare serve a página e, quando alguém envia o formulário,
dispara o workflow `dolar_x_cdi.yml` do GitHub Actions (o mesmo que já gera o documento),
passando o e-mail digitado como destino. O Worker guarda a credencial do GitHub com
segurança — ela nunca aparece na página nem no navegador de quem usa o formulário.

## Passo a passo (uma vez só)

**1. Criar conta na Cloudflare** (se ainda não tiver): https://dash.cloudflare.com/sign-up
— o plano gratuito é suficiente.

**2. Instalar a ferramenta de linha de comando (Wrangler)**, num terminal com Node.js instalado:
```bash
npm install -g wrangler
wrangler login
```
Isso abre o navegador pra você autorizar a Wrangler na sua conta Cloudflare.

**3. Criar o "banco" que impede pedidos repetidos** (limita a 1 pedido a cada 3 minutos
por pessoa/IP, pra ninguém spammar o formulário):
```bash
cd dolar_x_cdi/pedido_web
npx wrangler kv namespace create PEDIDOS_CDI
```
Isso imprime algo como:
```
[[kv_namespaces]]
binding = "PEDIDOS_CDI"
id = "a1b2c3d4e5f6..."
```
Copie o `id` e cole no arquivo `wrangler.toml` desta pasta, no lugar de
`COLE_AQUI_O_ID_DO_NAMESPACE`.

**4. Criar um token do GitHub** (só com a permissão mínima necessária):
- Acesse: https://github.com/settings/personal-access-tokens/new
- **Resource owner**: sua conta (`eduardotonzano`).
- **Repository access**: "Only select repositories" → escolha `edutoza`.
- **Permissions** → **Repository permissions** → **Actions**: "Read and write".
- Gere o token e **copie** (só aparece uma vez).

**5. Cadastrar o token no Worker** (nunca fica escrito em nenhum arquivo):
```bash
npx wrangler secret put GITHUB_TOKEN
```
Cole o token quando pedir.

**6. Publicar o Worker:**
```bash
npx wrangler deploy
```
Ao final, aparece a URL pública (algo como `https://dolar-x-cdi-pedido.SEU-USUARIO.workers.dev`)
— essa é a página pronta pra divulgar.

## Testar

Abra a URL publicada, digite um e-mail e clique em "Receber o PDF". Confira:
- A resposta na tela deve dizer "Pedido recebido!".
- Na aba **Actions** do repositório, deve aparecer uma execução nova de "Documento Dólar x CDI".
- Em alguns minutos, o PDF chega no e-mail digitado.

## Limites e segurança

- Máximo 1 pedido a cada 3 minutos por IP **e** por e-mail (o que vier primeiro barra o
  próximo) — evita que alguém spamme o formulário ou mande o PDF repetidamente pro e-mail
  de outra pessoa.
- O token do GitHub fica só no Worker (nunca no navegador, nunca no HTML, nunca no
  repositório) — quem usa a página não tem acesso a nenhuma credencial.
- O token tem permissão mínima: só "Actions: Read and write" nesse repositório específico,
  nada além disso (não consegue ler código, criar branches, etc.).

## Atualizar a página ou a lógica

Depois de editar `worker.js`, publique de novo com `npx wrangler deploy` — a mesma URL
passa a servir a versão nova.
