# Dados de amostra (NÃO são dados do BCB)

`dolar_amostra.csv` (diário) e `cdi_amostra.csv` (mensal, um ponto por mês) contêm a série
histórica 2006–2026 que já vinha na planilha original enviada pelo usuário
(`dolar_x_cdi._auto__comparação.xlsm`), com dados de terminal Bloomberg (`BRL REGN Curncy`
para o dólar, CDI anualizado — depois reamostrado para mensal, ver abaixo).

O CDI aqui é mensal (não diário) de propósito, pra bater com o formato real que a série
4391 do BCB devolve na prática (~1 ponto por mês, apesar do nome "anualizada base 252" no
catálogo do SGS — ver a nota de metodologia no topo de `calculo.py`). Os dados diários
anualizados originais da planilha foram compostos por mês para gerar esses valores.

Servem **apenas** para gerar um PDF de demonstração do layout (`gerar_documento.py --amostra`)
quando não há acesso à internet para consultar o Banco Central em tempo real — por exemplo,
dentro de um sandbox com rede restrita. O PDF gerado nesse modo é marcado com um aviso
"AMOSTRA — dados de demonstração" no cabeçalho para não ser confundido com o documento oficial.

O modo padrão (sem `--amostra`) busca os dados reais e oficiais direto no Banco Central do
Brasil (ver `fontes.py`) e não usa esses arquivos.
