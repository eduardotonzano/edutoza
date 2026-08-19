# Dados de amostra (NÃO são dados do BCB)

`dolar_amostra.csv` e `cdi_amostra.csv` contêm a série histórica diária (2006–2026) que
já vinha na planilha original enviada pelo usuário (`dolar_x_cdi._auto__comparação.xlsm`),
com dados de terminal Bloomberg (`BRL REGN Curncy` para o dólar, CDI anualizado).

Servem **apenas** para gerar um PDF de demonstração do layout (`gerar_documento.py --amostra`)
quando não há acesso à internet para consultar o Banco Central em tempo real — por exemplo,
dentro de um sandbox com rede restrita. O PDF gerado nesse modo é marcado com um aviso
"AMOSTRA — dados de demonstração" no cabeçalho para não ser confundido com o documento oficial.

O modo padrão (sem `--amostra`) busca os dados reais e oficiais direto no Banco Central do
Brasil (ver `fontes.py`) e não usa esses arquivos.
