import pandas as pd
import logging

# Usamos el logger nativo de FastAPI para asegurar que se imprima
logger = logging.getLogger("uvicorn.error")

EXCEL_PATH = "/app/data/tables/BAM.xlsx"

try:
    df_bam = pd.read_excel(EXCEL_PATH, sheet_name='BAM 18.1.1', header=12)
    df_bam = df_bam.dropna(subset=['nombre_del_alimento'])
    logger.info("✅ Base de Alimentos de México (BAM) cargada matemáticamente.")
except Exception as e:
    logger.error(f"❌ Error cargando BAM.xlsx: {e}")
    df_bam = None


def get_exact_macros(food_query: str, limit: int = 3) -> list:
    """Busca un alimento y devuelve sus macronutrientes oficiales."""
    if df_bam is None:
        return []

    # Busca la palabra clave
    match = df_bam[df_bam['nombre_del_alimento'].str.contains(
        food_query, case=False, na=False)].copy()

    if match.empty:
        return []

    # TRUCO: Ordenamos por la longitud del nombre para que 'Pollo' traiga
    # 'POLLO, ALA' antes que 'ALIMENTO PARA BEBÉ CON POLLO'
    match['len'] = match['nombre_del_alimento'].str.len()
    match = match.sort_values(by='len')

    results = []
    for _, row in match.head(limit).iterrows():
        results.append({
            "alimento": row['nombre_del_alimento'].strip(),
            "kcal": row['energ_kcal'],
            "proteina_g": row['protein'],
            "lipidos_g": row['lipid_tot'],
            "carbohidratos_g": row['carbohydrt']
        })
    return results
