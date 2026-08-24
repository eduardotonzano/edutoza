# Dados de amostra (NÃO são dados do BCB)

`dolar_amostra.csv` e `cdi_amostra.csv` (ambos diários) contêm a série histórica 2006–2026
que já vinha na planilha original enviada pelo usuário (`dolar_x_cdi._auto__comparação.xlsm`),
com dados de terminal Bloomberg (`BRL REGN Curncy` para o dólar, CDI anualizado).

O CDI aqui é diário, pra bater com o formato real da série 12 do BCB (ver a nota de
metodologia no topo de `fontes.py` e `calculo.py`) — até 2026-08 este arquivo era mensal
(reamostrado a partir do dado diário original da planilha), pra bater com a série 4391
usada até então; foi reamostrado para diário (taxa achatada dentro de cada mês, já que o
CDI real varia pouco dentro do mês) quando o projeto passou a usar a série 12.

Servem **apenas** para gerar um PDF de demonstração do layout (`gerar_documento.py --amostra`)
quando não há acesso à internet para consultar o Banco Central em tempo real — por exemplo,
dentro de um sandbox com rede restrita.

**Atenção:** o PDF gerado nesse modo NÃO tem mais nenhuma marca visual de "amostra" no
documento em si (o aviso que existia no cabeçalho foi removido numa reformulação do layout
e nunca foi restaurado) — o único indício de que é um PDF de demonstração é o nome do
arquivo, que sai prefixado com `AMOSTRA_`. Cuidado ao compartilhar um PDF gerado com
`--amostra`: sem o nome do arquivo, não dá pra distinguir do documento oficial.

O modo padrão (sem `--amostra`) busca os dados reais e oficiais direto no Banco Central do
Brasil (ver `fontes.py`) e não usa esses arquivos.
