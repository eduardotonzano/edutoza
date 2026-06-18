# Monitor de Notícias da Carteira — Como Funciona

Documento explicativo do robô que monitora notícias e fatos relevantes de toda a
carteira de investimentos e envia um relatório por e-mail, **todos os dias às 17h**,
de forma **automática e gratuita**.

---

## 1. O que é, em uma frase

Um robô que, todo dia, varre as notícias e os comunicados oficiais das **últimas 24
horas** de **todos os ativos da carteira (340 ativos)** e manda um Excel organizado
por e-mail — destacando o que realmente é sobre cada empresa, com um resumo feito
por inteligência artificial.

Não precisa de computador ligado, não tem mensalidade e roda sozinho na nuvem.

---

## 2. O problema que ele resolve

Acompanhar manualmente o que sai de ~340 papéis (ações, BDRs, bonds, CDBs,
debêntures, fundos, etc.) é inviável. As dificuldades típicas:

- **Volume**: notícia demais, a maior parte irrelevante (cenário macro, "dicas de
  ações", repercussão de bolsa).
- **Falso positivo**: matérias que só *citam* a empresa de passagem.
- **Fontes ruins**: agregadores e sites de baixa qualidade.
- **Fato relevante oficial**: o que a empresa comunica ao mercado (CVM/SEC) muitas
  vezes não vira "notícia de jornal" no mesmo dia.

O robô ataca tudo isso com filtros de relevância e com as **fontes oficiais** dos
reguladores.

---

## 3. Cobertura: TODA a base, monitorada por EMISSOR

A base tem **340 ativos**. A sacada principal é: um **CDB**, uma **debênture** ou um
**bond** não geram "notícia" — quem gera é a **empresa/banco que emitiu** o papel.
Então o robô monitora o **emissor** por trás de cada ativo.

- Vários ativos colapsam num mesmo emissor (ex.: dezenas de CDBs do BTG → um emissor
  "BTG Pactual"; ação + bond + debênture da Petrobras → "Petrobras").
- Resultado: os 340 ativos se resumem a **~92 emissores monitorados**.
- Uma notícia/fato de um emissor **acende todos os ativos dele** no relatório.
- O que **não** tem empresa pública por trás (Tesouro/governo, fundos multimercado,
  cripto) aparece marcado como **"sem notícia aplicável"** — nada é escondido; tudo
  aparece no relatório, cada item com seu status.

---

## 4. De onde vêm as informações (as fontes — todas gratuitas)

| Fonte | O que traz | Abrangência |
|------|------------|-------------|
| **GDELT** | Notícias da imprensa Tier 1 (Reuters, Bloomberg, Valor, Exame, etc.) das últimas 24h | Global + Brasil |
| **CVM** (regulador brasileiro) | Fatos relevantes e comunicados ao mercado **oficiais** | Emissores BR (~59) |
| **SEC / EDGAR** (regulador dos EUA) | Eventos materiais oficiais (formulários 8-K e 6-K) | Emissores dos EUA (~19) |
| **RI** (sites de Relações com Investidores) | Releases publicados pelas próprias empresas | Complemento, ~75 empresas |

**Por que essas fontes?**
- **GDELT** é gratuito e aceita acesso a partir de servidores de nuvem (o Google
  News, por exemplo, bloqueia) — por isso roda de graça no GitHub.
- **CVM e SEC são os canais oficiais e uniformes**: entregam o que *toda* empresa é
  obrigada a divulgar, do mesmo jeito para todas. É a base garantida da cobertura.
- **RI** é um complemento "melhor esforço": cadastramos a página de RI de todas as
  empresas que têm uma, mas muitos sites carregam por JavaScript/bloqueiam robôs, então
  rendem pouco — e tudo bem, porque o fato relevante oficial já vem pela CVM/SEC.

---

## 5. Como o robô decide o que é relevante

Para evitar lixo e falso positivo, cada notícia passa por filtros:

1. **A empresa precisa estar no TÍTULO** (não basta ser citada no corpo).
2. **Nomes ambíguos** (ex.: "Vale", "TIM", "Vamos") só valem com um **termo de
   contexto** do setor junto (mineração, telecom, locação…).
3. **Rejeita manchete de mercado/macro** (bolsa, juros, "ações para comprar",
   Ibovespa, Fed, etc.) — o foco é notícia **da empresa**, não do cenário.
4. **Rejeita "listões"** (matéria citando 3+ empresas diferentes).
5. **Só fontes Tier 1 / Tier 1.5** (lista branca de veículos sérios).
6. **Confere a data de publicação real** para respeitar a janela de 24h.
7. **Fatos relevantes da CVM/SEC entram direto** (são oficiais, relevância máxima).

---

## 6. O resumo por Inteligência Artificial

Cada item recebe duas colunas preenchidas pelo **Google Gemini** (gratuito):
- **RESUMO IA**: 1–2 frases com o fato principal, sem opinião.
- **IMPACTO**: começa com *Positivo / Negativo / Neutro* para a tese de investimento,
  com meia frase de justificativa.

É opcional: se a chave do Gemini não estiver configurada, essas colunas ficam vazias
e o resto roda normal.

---

## 7. O relatório (Excel com 3 abas)

1. **NOTICIAS** — cada notícia/fato do dia: data, emissor, título, fonte, link,
   relevância, resumo IA e impacto.
2. **CARTEIRA** — **os 340 ativos**, cada um com STATUS:
   - 🟢 **Notícia encontrada**
   - 🔴 **Sem notícia hoje**
   - ⚪ **Sem notícia aplicável** (Tesouro/governo, fundos sem empresa pública)
3. **EMISSORES** — visão por emissor monitorado, com a contagem de notícias.

---

## 8. Como você recebe

- **E-mail automático todos os dias às 17h (horário de Brasília)** para o endereço
  configurado, com o arquivo `relatorio.xlsx` anexado.
- **Backup**: toda execução também guarda o Excel na própria página do projeto
  (aba *Actions* → execução → *Artifacts*), por 90 dias.
- **Rodar na hora** (sem esperar as 17h): aba *Actions* → *Run workflow*.

---

## 9. Onde tudo isso roda (e por que é grátis)

- Roda no **GitHub Actions** — os servidores gratuitos do GitHub na nuvem.
- Um "agendador" (cron) dispara o robô às 20h UTC (= 17h de Brasília) todo dia.
- Custo: **zero**. Todas as fontes e ferramentas usadas têm camada gratuita.

**Configuração feita uma única vez** (segredos guardados com segurança no projeto,
nunca no código):
- `MAIL_USERNAME` / `MAIL_PASSWORD` — e-mail e "senha de app" do Gmail para o envio.
- `GEMINI_API_KEY` — chave gratuita do Google AI Studio para o resumo de IA.

---

## 10. Limites honestos (o que esperar)

- **GDELT tem limite por IP**: como o IP do GitHub é compartilhado, rodar muitas vezes
  seguidas coloca a coleta de notícias em "descanso" temporário (volta sozinha). Na
  operação normal (1x/dia) isso não acontece.
- **Sites de RI**: muitos bloqueiam robôs ou carregam por JavaScript, então a raspagem
  direta rende pouco. Por isso a cobertura de fatos relevantes é garantida pelos canais
  **oficiais** (CVM/SEC), que cobrem todas as empresas igualmente.
- **CVM**: a fonte oficial pode, esporadicamente, recusar conexão de servidor de nuvem;
  nesse caso o robô segue sem ela naquele dia (sem travar) e ela volta no dia seguinte.
- **Filosofia**: melhor **zero falso positivo** (nada que não seja sobre a empresa) do
  que volume. Em dias calmos, o relatório pode vir enxuto — isso é proposital.

---

## 11. Resumo de uma linha

Um robô gratuito, na nuvem, que todo dia às 17h cruza **imprensa (GDELT)** + **fatos
relevantes oficiais (CVM no Brasil e SEC nos EUA)** + **sites de RI** de **todos os 340
ativos da carteira**, resume com IA e manda um Excel por e-mail — com filtro rígido de
relevância para evitar ruído.

---

### Apêndice técnico (para quem for mexer no código)

- `carteira_completa.csv` — a base (340 ativos: ATIVO, TIPO, MOEDA, CATEGORIA).
- `emissores.py` — registro dos ~92 emissores (termos de busca, apelidos da CVM,
  CIK/ticker da SEC, URL de RI, se gera notícia).
- `empresas.py` — base das 28 ações (termos de busca e contexto).
- `mapeamento.py` — liga cada um dos 340 ativos ao seu emissor.
- `coleta.py` — coleta GDELT (consultas em lote), download e validação de relevância.
- `fato_relevante.py` — fatos relevantes da CVM.
- `sec_edgar.py` — eventos materiais (8-K/6-K) da SEC/EDGAR.
- `ri_scraping.py` — raspagem best-effort das páginas de RI.
- `resumo_ia.py` — resumo/impacto via Google Gemini.
- `excel.py` — gera o relatório (abas NOTICIAS, CARTEIRA, EMISSORES).
- `main.py` — orquestra tudo e deduplica (oficial > RI > imprensa).
- `.github/workflows/monitor.yml` — o agendamento diário e o envio do e-mail.
