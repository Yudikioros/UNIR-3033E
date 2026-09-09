"""
Base alimentaria del dominio (Fase 3.5).

BAM.xlsx es un adaptador legado, no un requisito del dominio. El resto del
sistema debe depender de `get_food_database_service()` (FoodDatabaseService),
nunca del nombre del archivo ni de sus columnas en español. Ver PHASE3_5.md
para cómo sustituirlo por una fuente oficial.
"""
import logging
import os
import threading
import unicodedata
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import pandas as pd
from pydantic import BaseModel

# Usamos el logger nativo de FastAPI para asegurar que se imprima
logger = logging.getLogger("uvicorn.error")

SHEET_NAME = "BAM 18.1.1"
HEADER_ROW = 12  # fila 13 de Excel (header=12, base cero)
REQUIRED_COLUMNS = ["codigomex2", "nombre_del_alimento",
                     "energ_kcal", "protein", "lipid_tot", "carbohydrt"]

FOOD_SOURCE_ID = "bam-legacy"
FOOD_SOURCE_NAME = "Base de Alimentos de México"
FOOD_SOURCE_VERSION = "18.1.1"
FOOD_SOURCE_PUBLICATION_YEAR = 2021


def _strip_accents(value: str) -> str:
    """Normaliza para comparación: sin acentos, sin mayúsculas. No altera el dato original."""
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(c for c in normalized if not unicodedata.combining(c)).casefold()

_lock = threading.Lock()
_cache = {"loaded": False, "df": None,
          "file_found": False, "schema_valid": False}


def _excel_path() -> Path:
    return Path(os.getenv("ALIMENTIA_FOOD_DB_PATH", "/app/data/tables/BAM.xlsx"))


def _read_food_database(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=SHEET_NAME, header=HEADER_ROW)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"Faltan columnas requeridas en BAM.xlsx: {', '.join(missing)}")
    return df.dropna(subset=["nombre_del_alimento"])


def load_food_database(force: bool = False) -> Optional[pd.DataFrame]:
    """Carga BAM.xlsx de forma segura. Nunca lanza excepciones; cachea el resultado."""
    with _lock:
        if _cache["loaded"] and not force:
            return _cache["df"]

        path = _excel_path()

        if not path.exists():
            logger.warning(
                "Base de Alimentos de México (BAM.xlsx) no configurada todavía en %s. "
                "La base alimentaria queda marcada como no disponible.", path)
            _cache.update(loaded=True, df=None,
                           file_found=False, schema_valid=False)
            return None

        try:
            df = _read_food_database(path)
        except ValueError as exc:
            logger.error(
                "BAM.xlsx encontrado en %s pero con hoja/columnas inválidas: %s", path, exc)
            _cache.update(loaded=True, df=None,
                           file_found=True, schema_valid=False)
            return None
        except Exception as exc:
            logger.error(
                "No fue posible leer BAM.xlsx en %s: %s", path, exc)
            _cache.update(loaded=True, df=None,
                           file_found=True, schema_valid=False)
            return None

        logger.info(
            "Base de Alimentos de México (BAM) cargada correctamente desde %s.", path)
        _cache.update(loaded=True, df=df, file_found=True, schema_valid=True)
        return df


def reset_food_database_cache() -> None:
    """Uso exclusivo en pruebas: fuerza una nueva lectura en la siguiente llamada."""
    with _lock:
        _cache.update(loaded=False, df=None,
                       file_found=False, schema_valid=False)


def food_database_status() -> dict:
    load_food_database()
    return {
        "ready": _cache["schema_valid"],
        "fileFound": _cache["file_found"],
        "schemaValid": _cache["schema_valid"],
        "sourceName": FOOD_SOURCE_NAME if _cache["schema_valid"] else None,
        "sourceVersion": FOOD_SOURCE_VERSION if _cache["schema_valid"] else None,
        "publicationYear": FOOD_SOURCE_PUBLICATION_YEAR if _cache["schema_valid"] else None,
    }


class FoodNutrientRecord(BaseModel):
    """DTO normalizado del dominio (Fase 3.5). Toda fuente alimentaria debe producir esto."""
    id: str
    name: str
    normalizedName: str
    portionQuantity: Optional[float] = None
    portionUnit: Optional[str] = None
    energyKcal: float
    proteinG: float
    carbohydratesG: float
    fatG: float
    fiberG: Optional[float] = None
    smaeGroup: Optional[str] = None
    smaeEquivalent: Optional[str] = None
    sourceId: str
    sourceVersion: str
    sourceReference: Optional[str] = None


def search(food_query: str, limit: int = 3) -> list[FoodNutrientRecord]:
    """Busca un alimento y devuelve registros normalizados con su procedencia.

    Insensible a acentos y mayúsculas: el BAM real mezcla ambas convenciones
    (82 nombres acentuados de 2045) y una búsqueda literal como "PLÁTANO"
    debe encontrar entradas escritas "PLATANO...".
    """
    df_bam = load_food_database()
    if df_bam is None:
        return []

    needle = _strip_accents(food_query)
    normalized_names = df_bam['nombre_del_alimento'].map(
        lambda v: _strip_accents(v) if isinstance(v, str) else "")
    match = df_bam[normalized_names.str.contains(needle, na=False, regex=False)].copy()

    if match.empty:
        return []

    # Filas con nutrientes requeridos en ND (nulo): no hay dato numérico que
    # devolver y no se inventa uno. Se excluyen del resultado, no se rellenan.
    required = ['energ_kcal', 'protein', 'lipid_tot', 'carbohydrt']
    match = match.dropna(subset=required)
    if match.empty:
        return []

    # TRUCO: Ordenamos por la longitud del nombre para que 'Pollo' traiga
    # 'POLLO, ALA' antes que 'ALIMENTO PARA BEBÉ CON POLLO'
    match['len'] = match['nombre_del_alimento'].str.len()
    match = match.sort_values(by='len')

    records = []
    for _, row in match.head(limit).iterrows():
        name = row['nombre_del_alimento'].strip()
        code = str(row['codigomex2']).strip()
        records.append(FoodNutrientRecord(
            id=f"{FOOD_SOURCE_ID}:{code}", name=name, normalizedName=_strip_accents(name),
            energyKcal=float(row['energ_kcal']), proteinG=float(row['protein']),
            carbohydratesG=float(row['carbohydrt']), fatG=float(row['lipid_tot']),
            sourceId=FOOD_SOURCE_ID, sourceVersion=FOOD_SOURCE_VERSION,
            sourceReference='BAM.xlsx (hoja "BAM 18.1.1")',
        ))
    return records


def get_exact_macros(food_query: str, limit: int = 3) -> list:
    """Ruta heredada usada por generate-draft; delega en la interfaz normalizada."""
    return [{
        "alimento": record.name,
        "kcal": record.energyKcal,
        "proteina_g": record.proteinG,
        "lipidos_g": record.fatG,
        "carbohidratos_g": record.carbohydratesG,
    } for record in search(food_query, limit)]


class FoodDatabaseService(ABC):
    """Interfaz que debe implementar cualquier fuente alimentaria del dominio.

    El resto del sistema depende de esta interfaz (vía `get_food_database_service()`),
    nunca directamente de BAM.xlsx ni de ningún otro archivo concreto.
    """

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def search(self, query: str, limit: int = 3) -> list[FoodNutrientRecord]: ...

    @abstractmethod
    def status(self) -> dict: ...


class BamExcelFoodDatabase(FoodDatabaseService):
    """Adapta el BAM.xlsx heredado del prototipo al contrato FoodDatabaseService.

    No es la fuente oficial del MVP: es un adaptador reemplazable. Si el
    archivo no existe o es inválido, `is_available()` es False y `search()`
    devuelve una lista vacía; nunca detiene el arranque.
    """
    source_id = FOOD_SOURCE_ID
    source_version = FOOD_SOURCE_VERSION

    def is_available(self) -> bool:
        return load_food_database() is not None

    def status(self) -> dict:
        return food_database_status()

    def search(self, query: str, limit: int = 3) -> list[FoodNutrientRecord]:
        return search(query, limit)


_food_database_service: FoodDatabaseService = BamExcelFoodDatabase()


def get_food_database_service() -> FoodDatabaseService:
    """Punto único de acceso del dominio a la base alimentaria (no usar BAM.xlsx directamente)."""
    return _food_database_service
