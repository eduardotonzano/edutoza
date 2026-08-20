/**
 * Worker (Cloudflare) do formulário "Dólar x CDI": serve a página (GET /) e,
 * quando alguém envia o e-mail (POST /solicitar), dispara o workflow do
 * GitHub Actions que gera o PDF com dados reais do BCB e manda por e-mail
 * pra quem pediu.
 *
 * Configuração (ver README.md nesta pasta para o passo a passo completo):
 *   - Secret GITHUB_TOKEN: token do GitHub (fine-grained, só permissão
 *     "Actions: Read and write" neste repositório).
 *   - KV namespace PEDIDOS_CDI: usado só pra limitar pedidos repetidos.
 */

const OWNER = "eduardotonzano";
const REPO = "edutoza";
const WORKFLOW_FILE = "dolar_x_cdi.yml";
const REF = "claude/affectionate-bardeen-o14bjm"; // branch padrão do repositório

const JANELA_LIMITE_SEGUNDOS = 180;

const REGEX_EMAIL = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/;
const REGEX_DATA = /^\d{4}-\d{2}-\d{2}$/;

const PAGINA_HTML = "<!doctype html>\n<html lang=\"pt-BR\">\n<head>\n<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n<title>D\u00f3lar x CDI</title>\n<style>\n  :root {\n    --navy: #001A33;\n    --ciano: #00C4E0;\n    --cinza-claro: #F5F7FA;\n    --cinza-borda: #E3E7ED;\n    --cinza-texto: #5B6472;\n    --vermelho: #C0392B;\n    --verde: #1E8449;\n  }\n  * { box-sizing: border-box; }\n  body {\n    margin: 0;\n    font-family: 'Poppins', 'Segoe UI', Arial, sans-serif;\n    background: var(--cinza-claro);\n    color: var(--navy);\n    min-height: 100vh;\n    display: flex;\n    align-items: center;\n    justify-content: center;\n    padding: 24px;\n  }\n  .cartao {\n    background: #fff;\n    border-radius: 12px;\n    box-shadow: 0 4px 24px rgba(0,26,51,0.08);\n    max-width: 440px;\n    width: 100%;\n    overflow: hidden;\n  }\n  .cabecalho {\n    background: var(--navy);\n    padding: 26px 32px;\n    text-align: center;\n  }\n  .cabecalho .marca {\n    color: #fff;\n    font-size: 20px;\n    font-weight: 700;\n    letter-spacing: 0.5px;\n  }\n  .cabecalho .marca .ponto { color: var(--ciano); }\n  .corpo { padding: 32px; }\n  h1 {\n    font-size: 20px;\n    margin: 0 0 6px;\n    color: var(--navy);\n  }\n  .subtitulo {\n    color: var(--cinza-texto);\n    font-size: 13.5px;\n    line-height: 1.55;\n    margin: 0 0 24px;\n  }\n  label {\n    display: block;\n    font-size: 12.5px;\n    font-weight: 600;\n    color: var(--navy);\n    margin-bottom: 6px;\n  }\n  input[type=\"email\"], input[type=\"date\"] {\n    width: 100%;\n    padding: 12px 14px;\n    border: 1.5px solid var(--cinza-borda);\n    border-radius: 8px;\n    font-size: 14px;\n    font-family: inherit;\n    color: var(--navy);\n    outline: none;\n    transition: border-color 0.15s;\n  }\n  input[type=\"email\"]:focus, input[type=\"date\"]:focus { border-color: var(--ciano); }\n  .campo { margin-top: 18px; }\n  .ajuda {\n    margin-top: 6px;\n    font-size: 11.5px;\n    color: var(--cinza-texto);\n    line-height: 1.5;\n  }\n  button {\n    width: 100%;\n    margin-top: 18px;\n    padding: 13px;\n    background: var(--navy);\n    color: #fff;\n    border: none;\n    border-radius: 8px;\n    font-size: 14.5px;\n    font-weight: 600;\n    font-family: inherit;\n    cursor: pointer;\n    transition: background 0.15s;\n  }\n  button:hover:not(:disabled) { background: #002a52; }\n  button:disabled { opacity: 0.6; cursor: default; }\n  .status {\n    margin-top: 16px;\n    padding: 12px 14px;\n    border-radius: 8px;\n    font-size: 13px;\n    line-height: 1.5;\n    display: none;\n  }\n  .status.ok { display: block; background: #EAF7EF; color: var(--verde); }\n  .status.erro { display: block; background: #FBEAE8; color: var(--vermelho); }\n  .rodape {\n    margin-top: 22px;\n    font-size: 11px;\n    color: var(--cinza-texto);\n    line-height: 1.5;\n    text-align: center;\n  }\n</style>\n</head>\n<body>\n  <div class=\"cartao\">\n    <div class=\"cabecalho\">\n      <span class=\"marca\">Multiplica<span class=\"ponto\">.</span></span>\n    </div>\n    <div class=\"corpo\">\n      <h1>Documento D\u00f3lar x CDI</h1>\n      <p class=\"subtitulo\">\n        Digite seu e-mail e receba o comparativo de rentabilidade acumulada\n        (d\u00f3lar x CDI, 1/5/10/20 anos) com dados oficiais do Banco Central \u2014\n        gerado na hora, chega em alguns minutos.\n      </p>\n      <form id=\"form-pedido\">\n        <label for=\"email\">Seu e-mail</label>\n        <input type=\"email\" id=\"email\" name=\"email\" placeholder=\"voce@exemplo.com\" required>\n        <div class=\"campo\">\n          <label for=\"data_fim\">Escolha a janela de tempo</label>\n          <input type=\"date\" id=\"data_fim\" name=\"data_fim\">\n          <div class=\"ajuda\">Data final da análise (opcional) — deixe em branco para usar o dado mais recente disponível. As janelas de 1, 5, 10 e 20 anos serão calculadas até essa data.</div>\n        </div>\n        <button type=\"submit\" id=\"botao\">Receber o PDF</button>\n      </form>\n      <div class=\"status\" id=\"status\"></div>\n      <div class=\"rodape\">\n        Dados p\u00fablicos do Banco Central do Brasil (SGS). O documento \u00e9 gerado\n        automaticamente a cada pedido \u2014 pode levar alguns minutos pra chegar.\n      </div>\n    </div>\n  </div>\n\n  <script>\n    const form = document.getElementById('form-pedido');\n    const botao = document.getElementById('botao');\n    const status = document.getElementById('status');\n    const campoData = document.getElementById('data_fim');\n    campoData.max = new Date().toISOString().slice(0, 10);\n\n    form.addEventListener('submit', async (ev) => {\n      ev.preventDefault();\n      const email = document.getElementById('email').value.trim();\n      const dataFim = campoData.value;\n      status.className = 'status';\n      status.textContent = '';\n      botao.disabled = true;\n      botao.textContent = 'Enviando pedido...';\n\n      try {\n        const resp = await fetch('/solicitar', {\n          method: 'POST',\n          headers: { 'Content-Type': 'application/json' },\n          body: JSON.stringify({ email, data_fim: dataFim }),\n        });\n        const dados = await resp.json().catch(() => ({}));\n\n        if (resp.ok) {\n          status.className = 'status ok';\n          status.textContent = 'Pedido recebido! O documento deve chegar no seu e-mail em alguns minutos.';\n          form.reset();\n        } else {\n          status.className = 'status erro';\n          status.textContent = dados.erro || 'N\u00e3o foi poss\u00edvel processar o pedido agora. Tente de novo em alguns minutos.';\n        }\n      } catch (e) {\n        status.className = 'status erro';\n        status.textContent = 'Falha de conex\u00e3o. Tente de novo em alguns instantes.';\n      } finally {\n        botao.disabled = false;\n        botao.textContent = 'Receber o PDF';\n      }\n    });\n  </script>\n</body>\n</html>\n";

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "GET" && url.pathname === "/") {
      return new Response(PAGINA_HTML, {
        headers: { "content-type": "text/html; charset=utf-8" },
      });
    }

    if (request.method === "POST" && url.pathname === "/solicitar") {
      return tratarPedido(request, env);
    }

    return new Response("Não encontrado", { status: 404 });
  },
};

async function tratarPedido(request, env) {
  let corpo;
  try {
    corpo = await request.json();
  } catch {
    return respostaErro("Pedido inválido.", 400);
  }

  const email = String(corpo?.email || "").trim().toLowerCase();
  if (!REGEX_EMAIL.test(email)) {
    return respostaErro("Digite um e-mail válido.", 400);
  }

  const dataFim = String(corpo?.data_fim || "").trim();
  if (dataFim && !REGEX_DATA.test(dataFim)) {
    return respostaErro("Data inválida.", 400);
  }

  const ip = request.headers.get("CF-Connecting-IP") || "desconhecido";

  const limitado = await estaLimitado(env, [`ip:${ip}`, `email:${email}`]);
  if (limitado) {
    return respostaErro(
      "Já recebemos um pedido seu há pouco tempo — aguarde alguns minutos e tente de novo.",
      429
    );
  }

  const resultado = await dispararWorkflow(env, email, dataFim);
  if (!resultado.ok) {
    return respostaErro(
      `Não foi possível iniciar a geração agora (${resultado.motivo}). Tente novamente em instantes.`,
      502
    );
  }

  await marcarPedido(env, [`ip:${ip}`, `email:${email}`]);

  return new Response(JSON.stringify({ ok: true }), {
    status: 200,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

async function estaLimitado(env, chaves) {
  if (!env.PEDIDOS_CDI) return false;
  for (const chave of chaves) {
    const visto = await env.PEDIDOS_CDI.get(chave);
    if (visto) return true;
  }
  return false;
}

async function marcarPedido(env, chaves) {
  if (!env.PEDIDOS_CDI) return;
  for (const chave of chaves) {
    await env.PEDIDOS_CDI.put(chave, "1", { expirationTtl: JANELA_LIMITE_SEGUNDOS });
  }
}

async function dispararWorkflow(env, email, dataFim) {
  if (!env.GITHUB_TOKEN) return { ok: false, motivo: "GITHUB_TOKEN não configurado no Worker" };

  let resp;
  try {
    resp = await fetch(
      `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW_FILE}/dispatches`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${env.GITHUB_TOKEN}`,
          Accept: "application/vnd.github+json",
          "Content-Type": "application/json",
          "User-Agent": "dolar-x-cdi-worker",
        },
        body: JSON.stringify({
          ref: REF,
          inputs: { email_destino: email, data_fim: dataFim || "" },
        }),
      }
    );
  } catch (exc) {
    return { ok: false, motivo: `falha de rede: ${exc}` };
  }

  if (resp.status === 204) {
    return { ok: true };
  }

  const corpo = await resp.text().catch(() => "");
  return { ok: false, motivo: `GitHub respondeu ${resp.status}: ${corpo.slice(0, 200)}` };
}

function respostaErro(mensagem, status) {
  return new Response(JSON.stringify({ erro: mensagem }), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}
