"""Identidade visual (Multiplica) usada no documento Dólar x CDI.

Cores extraídas por amostragem de pixel das lâminas de exemplo
(Global_Bonds_Factsheet, HOD_Global_10_Factsheet, Total_Return_Factsheet).
"""
from pathlib import Path

PASTA_ASSETS = Path(__file__).parent / "assets"

# Paleta
NAVY = "#001A33"          # header, tabelas, texto principal
NAVY_TEXTO = "#0B1F3A"    # variante de texto em corpo (mesma família)
CIANO = "#00C4E0"         # títulos de seção, linha de destaque, barras negativas
CIANO_CLARO = "#5FD8EA"   # tons auxiliares em gráficos
VERMELHO = "#C0392B"      # variação negativa
CINZA_CLARO = "#F5F7FA"   # fundo de caixas laterais
CINZA_BORDA = "#E3E7ED"   # bordas sutis
CINZA_TEXTO = "#5B6472"   # texto secundário
BRANCO = "#FFFFFF"

FONTE = "'Poppins', 'Segoe UI', Arial, sans-serif"

LOGO_BRANCO = PASTA_ASSETS / "logo_multiplica_branco.png"
LOGO_NAVY = PASTA_ASSETS / "logo_multiplica_navy.png"

# Cores para os gráficos (matplotlib) — mesma paleta do documento
CORES_GRAFICO = {
    "dolar": NAVY,
    "cdi": CIANO,
    "cdi_spread": "#8FA3B8",  # cinza-azulado, linha de referência auxiliar
}
