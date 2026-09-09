"""Pruebas de la abstracción de base alimentaria (Fase 3.5). Sin base de datos."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook

from app.services import food_db


def _write_bam(path: Path, sheet_name='BAM 18.1.1', header_row=13, columns=None, rows=None):
    columns = columns if columns is not None else food_db.REQUIRED_COLUMNS
    rows = rows if rows is not None else [
        ['1001', 'POLLO PECHUGA SIN PIEL', 165, 31, 3.6, 0],
        ['1002', 'ARROZ BLANCO COCIDO', 130, 2.7, 0.3, 28],
    ]
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name
    for i in range(1, header_row):
        ws.append([f'nota {i}'])
    ws.append(columns)
    for row in rows:
        ws.append(row)
    wb.save(path)


class BamExcelFoodDatabaseTests(unittest.TestCase):
    def tearDown(self):
        food_db.reset_food_database_cache()

    def test_adapter_bam_ausente(self):
        adapter = food_db.BamExcelFoodDatabase()
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / 'BAM.xlsx'
            with patch.dict('os.environ', {'ALIMENTIA_FOOD_DB_PATH': str(missing)}):
                food_db.reset_food_database_cache()
                self.assertFalse(adapter.is_available())
                self.assertEqual(adapter.search('pollo'), [])
                status = adapter.status()
                self.assertFalse(status['ready'])
                self.assertFalse(status['fileFound'])

    def test_adapter_bam_valido(self):
        adapter = food_db.BamExcelFoodDatabase()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'BAM.xlsx'
            _write_bam(path)
            with patch.dict('os.environ', {'ALIMENTIA_FOOD_DB_PATH': str(path)}):
                food_db.reset_food_database_cache()
                self.assertTrue(adapter.is_available())
                status = adapter.status()
                self.assertEqual(status, {
                    'ready': True, 'fileFound': True, 'schemaValid': True,
                    'sourceName': food_db.FOOD_SOURCE_NAME,
                    'sourceVersion': food_db.FOOD_SOURCE_VERSION,
                    'publicationYear': food_db.FOOD_SOURCE_PUBLICATION_YEAR,
                })

    def test_mapeo_a_food_nutrient_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'BAM.xlsx'
            _write_bam(path)
            with patch.dict('os.environ', {'ALIMENTIA_FOOD_DB_PATH': str(path)}):
                food_db.reset_food_database_cache()
                records = food_db.search('pollo')
                self.assertEqual(len(records), 1)
                record = records[0]
                self.assertIsInstance(record, food_db.FoodNutrientRecord)
                self.assertEqual(record.id, f'{food_db.FOOD_SOURCE_ID}:1001')
                self.assertEqual(record.name, 'POLLO PECHUGA SIN PIEL')
                self.assertEqual(record.normalizedName, 'pollo pechuga sin piel')
                self.assertEqual(record.energyKcal, 165.0)
                self.assertEqual(record.proteinG, 31.0)
                self.assertEqual(record.fatG, 3.6)
                self.assertEqual(record.carbohydratesG, 0.0)
                self.assertEqual(record.sourceId, food_db.FOOD_SOURCE_ID)
                self.assertEqual(record.sourceVersion, food_db.FOOD_SOURCE_VERSION)
                self.assertIsNotNone(record.sourceReference)
                # Todos los nutrientes son numéricos.
                for field in ('energyKcal', 'proteinG', 'carbohydratesG', 'fatG'):
                    self.assertIsInstance(getattr(record, field), float)

    def test_get_exact_macros_legacy_delega_en_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'BAM.xlsx'
            _write_bam(path)
            with patch.dict('os.environ', {'ALIMENTIA_FOOD_DB_PATH': str(path)}):
                food_db.reset_food_database_cache()
                legacy = food_db.get_exact_macros('pollo')
                self.assertEqual(legacy, [{
                    'alimento': 'POLLO PECHUGA SIN PIEL', 'kcal': 165.0,
                    'proteina_g': 31.0, 'lipidos_g': 3.6, 'carbohidratos_g': 0.0,
                }])

    def test_get_food_database_service_devuelve_instancia_funcional(self):
        service = food_db.get_food_database_service()
        self.assertIsInstance(service, food_db.FoodDatabaseService)
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / 'BAM.xlsx'
            with patch.dict('os.environ', {'ALIMENTIA_FOOD_DB_PATH': str(missing)}):
                food_db.reset_food_database_cache()
                self.assertFalse(service.is_available())
                self.assertEqual(service.search('cualquier cosa'), [])

    def test_nombres_duplicados_generan_ids_distintos(self):
        # El BAM real tiene nombres repetidos (distinto codigomex2, p.ej. dos
        # entradas "ACEITE, DE CANOLA"): el id debe basarse en el código, no
        # en el nombre, para no colisionar.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'BAM.xlsx'
            _write_bam(path, rows=[
                ['1003', 'ACEITE, DE CANOLA', 884, 0, 100, 0],
                ['1004', 'ACEITE, DE CANOLA', 884, 0, 100, 0],
            ])
            with patch.dict('os.environ', {'ALIMENTIA_FOOD_DB_PATH': str(path)}):
                food_db.reset_food_database_cache()
                records = food_db.search('canola', limit=5)
                self.assertEqual(len(records), 2)
                self.assertEqual({r.id for r in records}, {
                    f'{food_db.FOOD_SOURCE_ID}:1003', f'{food_db.FOOD_SOURCE_ID}:1004'})

    def test_busqueda_insensible_a_acentos(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'BAM.xlsx'
            _write_bam(path, rows=[['2001', 'PLATANO TABASCO', 89, 1.1, 0.3, 23]])
            with patch.dict('os.environ', {'ALIMENTIA_FOOD_DB_PATH': str(path)}):
                food_db.reset_food_database_cache()
                # La query lleva acento; el dato real en BAM no lo tiene.
                records = food_db.search('PLÁTANO')
                self.assertEqual(len(records), 1)
                self.assertEqual(records[0].name, 'PLATANO TABASCO')

    def test_valores_nd_se_excluyen_sin_inventar_dato(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'BAM.xlsx'
            _write_bam(path, rows=[['3001', 'TEQUESQUITE', 10, None, 0, 0]])
            with patch.dict('os.environ', {'ALIMENTIA_FOOD_DB_PATH': str(path)}):
                food_db.reset_food_database_cache()
                self.assertEqual(food_db.search('tequesquite'), [])


REAL_BAM_PATH = None
for candidate in (Path('/app/data/tables/BAM.xlsx'),
                   Path(__file__).resolve().parents[2] / 'data' / 'tables' / 'BAM.xlsx'):
    if candidate.exists():
        REAL_BAM_PATH = candidate
        break


@unittest.skipUnless(REAL_BAM_PATH, 'BAM.xlsx real no disponible en este entorno')
class RealBamSearchTests(unittest.TestCase):
    """Verifica el BAM.xlsx real (no una tabla sintética): sección 3-6 de la
    etapa de integración de recursos reales previa a Fase 6."""

    def setUp(self):
        self._patcher = patch.dict('os.environ', {'ALIMENTIA_FOOD_DB_PATH': str(REAL_BAM_PATH)})
        self._patcher.start()
        food_db.reset_food_database_cache()

    def tearDown(self):
        self._patcher.stop()
        food_db.reset_food_database_cache()

    def test_bam_real_reporta_listo(self):
        status = food_db.food_database_status()
        self.assertTrue(status['ready'])
        self.assertEqual(status['sourceName'], food_db.FOOD_SOURCE_NAME)
        self.assertEqual(status['sourceVersion'], '18.1.1')
        self.assertEqual(status['publicationYear'], 2021)

    def _assert_real_match(self, query, expected_substring):
        records = food_db.search(query, limit=5)
        self.assertTrue(records, f'sin resultados reales para "{query}"')
        for record in records:
            self.assertIsInstance(record, food_db.FoodNutrientRecord)
            self.assertIn(expected_substring, food_db._strip_accents(record.name))
            self.assertGreater(record.energyKcal, 0)
            self.assertGreaterEqual(record.proteinG, 0)
            self.assertGreaterEqual(record.carbohydratesG, 0)
            self.assertGreaterEqual(record.fatG, 0)
            self.assertTrue(record.id.startswith(f'{food_db.FOOD_SOURCE_ID}:'))

    def test_bam_real_canola(self):
        self._assert_real_match('canola', 'canola')

    def test_bam_real_manzana(self):
        self._assert_real_match('manzana', 'manzana')

    def test_bam_real_avena(self):
        self._assert_real_match('avena', 'avena')

    def test_bam_real_pollo(self):
        self._assert_real_match('pollo', 'pollo')

    def test_bam_real_tortilla(self):
        self._assert_real_match('tortilla', 'tortilla')


if __name__ == '__main__':
    unittest.main()
