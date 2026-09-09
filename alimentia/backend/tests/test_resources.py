import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
from fastapi import FastAPI
from openpyxl import Workbook
from prisma import Prisma

from app.repositories.knowledge import sync_knowledge_sources
from app.routes.resources import router
from app.services import food_db
from app.services import rag_engine
from test_persistence import apply_sql


def _write_bam(path: Path, sheet_name='BAM 18.1.1', header_row=13, columns=None, rows=None):
    """Escribe un .xlsx de prueba con `header_row` filas antes del encabezado (1-based)."""
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


def _write_manifest(path: Path, sources=None, version='1.0'):
    path.write_text(json.dumps({'version': version, 'sources': sources or []}), encoding='utf-8')


class FoodDbTests(unittest.TestCase):
    def tearDown(self):
        food_db.reset_food_database_cache()

    def test_missing_file_is_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / 'BAM.xlsx'
            with patch.dict('os.environ', {'ALIMENTIA_FOOD_DB_PATH': str(missing)}):
                food_db.reset_food_database_cache()
                self.assertIsNone(food_db.load_food_database())
                self.assertEqual(food_db.food_database_status(),
                                  {'ready': False, 'fileFound': False, 'schemaValid': False,
                                   'sourceName': None, 'sourceVersion': None, 'publicationYear': None})
                self.assertEqual(food_db.get_exact_macros('pollo'), [])

    def test_unreadable_file_is_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad_file = Path(tmp) / 'BAM.xlsx'
            bad_file.write_text('this is not a real xlsx file')
            with patch.dict('os.environ', {'ALIMENTIA_FOOD_DB_PATH': str(bad_file)}):
                food_db.reset_food_database_cache()
                self.assertIsNone(food_db.load_food_database())
                status = food_db.food_database_status()
                self.assertTrue(status['fileFound'])
                self.assertFalse(status['schemaValid'])

    def test_wrong_sheet_name_is_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'BAM.xlsx'
            _write_bam(path, sheet_name='Otra hoja')
            with patch.dict('os.environ', {'ALIMENTIA_FOOD_DB_PATH': str(path)}):
                food_db.reset_food_database_cache()
                self.assertIsNone(food_db.load_food_database())
                status = food_db.food_database_status()
                self.assertTrue(status['fileFound'])
                self.assertFalse(status['schemaValid'])

    def test_wrong_columns_is_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'BAM.xlsx'
            _write_bam(path, columns=['nombre_del_alimento',
                       'energ_kcal', 'proteina', 'lipid_tot', 'carbohydrt'])
            with patch.dict('os.environ', {'ALIMENTIA_FOOD_DB_PATH': str(path)}):
                food_db.reset_food_database_cache()
                self.assertIsNone(food_db.load_food_database())
                status = food_db.food_database_status()
                self.assertTrue(status['fileFound'])
                self.assertFalse(status['schemaValid'])

    def test_valid_file_loads_and_returns_macros(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'BAM.xlsx'
            _write_bam(path)
            with patch.dict('os.environ', {'ALIMENTIA_FOOD_DB_PATH': str(path)}):
                food_db.reset_food_database_cache()
                df = food_db.load_food_database()
                self.assertIsNotNone(df)
                status = food_db.food_database_status()
                self.assertEqual(status, {'ready': True, 'fileFound': True, 'schemaValid': True,
                                  'sourceName': food_db.FOOD_SOURCE_NAME,
                                  'sourceVersion': food_db.FOOD_SOURCE_VERSION,
                                  'publicationYear': food_db.FOOD_SOURCE_PUBLICATION_YEAR})
                macros = food_db.get_exact_macros('pollo')
                self.assertEqual(len(macros), 1)
                self.assertEqual(macros[0]['kcal'], 165)


class RagEngineTests(unittest.TestCase):
    """Fase 3.5: el RAG solo procesa documentos declarados en el manifiesto."""

    def test_status_missing_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / 'does-not-exist'
            missing_manifest = Path(tmp) / 'manifest.json'
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_PATH': str(missing),
                                            'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(missing_manifest)}):
                status = rag_engine.knowledge_base_status()
                self.assertEqual(status, {'ready': False, 'documentCount': 0, 'pathConfigured': True,
                    'knowledgeBaseVersion': None, 'authorizedSourceCount': 0, 'indexedDocumentCount': 0})
                self.assertFalse(missing.exists())

    def test_status_empty_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / 'manifest.json'
            _write_manifest(manifest_path, sources=[])
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_PATH': tmp,
                                            'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(manifest_path)}):
                status = rag_engine.knowledge_base_status()
                self.assertEqual(status, {'ready': False, 'documentCount': 0, 'pathConfigured': True,
                    'knowledgeBaseVersion': '1.0', 'authorizedSourceCount': 0, 'indexedDocumentCount': 0})

    def test_status_unauthorized_document_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'guia.txt').write_text('contenido de prueba')
            manifest_path = Path(tmp) / 'manifest.json'
            _write_manifest(manifest_path, sources=[])  # nada autorizado todavía
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_PATH': tmp,
                                            'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(manifest_path)}):
                status = rag_engine.knowledge_base_status()
                self.assertFalse(status['ready'])
                self.assertEqual(status['documentCount'], 0)

    def test_status_authorized_document_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'guia.txt').write_text('contenido de prueba')
            manifest_path = Path(tmp) / 'manifest.json'
            _write_manifest(manifest_path, sources=[{'id': 'insp-guia-2015', 'name': 'Guía de prueba',
                'institution': 'INSP', 'version': '2015', 'file': 'guia.txt', 'type': 'GUIDELINE'}])
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_PATH': tmp,
                                            'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(manifest_path)}):
                status = rag_engine.knowledge_base_status()
                self.assertEqual(status, {'ready': True, 'documentCount': 1, 'pathConfigured': True,
                    'knowledgeBaseVersion': '1.0', 'authorizedSourceCount': 1, 'indexedDocumentCount': 1})

    def test_build_knowledge_base_creates_missing_folder_without_raising(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / 'pdfs'
            manifest_path = Path(tmp) / 'manifest.json'
            _write_manifest(manifest_path, sources=[])
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_PATH': str(missing),
                                            'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(manifest_path)}):
                result = rag_engine.build_knowledge_base(wait_for_qdrant=False)
                self.assertEqual(
                    result, {'status': 'no_documents', 'documentCount': 0})
                self.assertTrue(missing.exists())

    def test_build_knowledge_base_empty_folder_does_not_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / 'manifest.json'
            _write_manifest(manifest_path, sources=[])
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_PATH': tmp,
                                            'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(manifest_path)}):
                result = rag_engine.build_knowledge_base(wait_for_qdrant=False)
                self.assertEqual(
                    result, {'status': 'no_documents', 'documentCount': 0})

    def test_build_knowledge_base_ignores_unauthorized_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'unauthorized.txt').write_text('no debería procesarse jamás')
            manifest_path = Path(tmp) / 'manifest.json'
            _write_manifest(manifest_path, sources=[])
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_PATH': tmp,
                                            'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(manifest_path)}):
                result = rag_engine.build_knowledge_base(wait_for_qdrant=False)
                self.assertEqual(result, {'status': 'no_documents', 'documentCount': 0})


class PyPdfReaderTests(unittest.TestCase):
    """Un PDF escaneado sin capa de texto real (frecuente en documentos
    fotografiados) nunca debe terminar indexado como un chunk vacío -eso
    haría que `indexStatus` mintiera "INDEXED" para un documento inútil
    para RAG-. Descubierto durante la validación real Docker de esta
    corrección (sección 6/10)."""

    def test_documento_sin_texto_extraible_no_produce_document_vacio(self):
        fake_page = MagicMock()
        fake_page.extract_text.return_value = ""
        fake_reader = MagicMock()
        fake_reader.pages = [fake_page, fake_page]
        with patch.object(rag_engine.pypdf, 'PdfReader', return_value=fake_reader):
            documents = rag_engine._PyPdfReader().load_data("fake.pdf")
        self.assertEqual(documents, [])

    def test_documento_con_texto_real_produce_un_document(self):
        fake_page = MagicMock()
        fake_page.extract_text.return_value = "contenido real de la página"
        fake_reader = MagicMock()
        fake_reader.pages = [fake_page]
        with patch.object(rag_engine.pypdf, 'PdfReader', return_value=fake_reader):
            documents = rag_engine._PyPdfReader().load_data("fake.pdf")
        self.assertEqual(len(documents), 1)
        self.assertIn("contenido real", documents[0].text)


class SourceIndexingAdminTests(unittest.TestCase):
    """Administración de documentos: eliminación/conteo selectivo por fuente
    en Qdrant mediante filtro de metadata (sección 17). Qdrant se mockea
    aquí; la prueba real end-to-end vive en la validación Docker."""

    def test_count_source_chunks_coleccion_inexistente_devuelve_cero(self):
        fake_client = MagicMock()
        fake_client.collection_exists.return_value = False
        with patch.object(rag_engine.qdrant_client, 'QdrantClient', return_value=fake_client):
            self.assertEqual(rag_engine.count_source_chunks('cualquier-fuente'), 0)

    def test_count_source_chunks_usa_filtro_por_sourceid(self):
        fake_client = MagicMock()
        fake_client.collection_exists.return_value = True
        fake_client.count.return_value = SimpleNamespace(count=7)
        with patch.object(rag_engine.qdrant_client, 'QdrantClient', return_value=fake_client):
            count = rag_engine.count_source_chunks('mi-fuente')
        self.assertEqual(count, 7)
        kwargs = fake_client.count.call_args.kwargs
        self.assertEqual(kwargs['count_filter'].must[0].key, 'sourceId')
        self.assertEqual(kwargs['count_filter'].must[0].match.value, 'mi-fuente')

    def test_delete_source_chunks_sin_puntos_no_llama_delete(self):
        fake_client = MagicMock()
        fake_client.collection_exists.return_value = True
        fake_client.count.return_value = SimpleNamespace(count=0)
        with patch.object(rag_engine.qdrant_client, 'QdrantClient', return_value=fake_client):
            deleted = rag_engine.delete_source_chunks('sin-chunks')
        self.assertEqual(deleted, 0)
        fake_client.delete.assert_not_called()

    def test_delete_source_chunks_elimina_por_filtro_y_devuelve_conteo_previo(self):
        fake_client = MagicMock()
        fake_client.collection_exists.return_value = True
        fake_client.count.return_value = SimpleNamespace(count=4)
        with patch.object(rag_engine.qdrant_client, 'QdrantClient', return_value=fake_client):
            deleted = rag_engine.delete_source_chunks('mi-fuente')
        self.assertEqual(deleted, 4)
        fake_client.delete.assert_called_once()
        kwargs = fake_client.delete.call_args.kwargs
        self.assertEqual(kwargs['points_selector'].must[0].match.value, 'mi-fuente')

    def test_delete_source_chunks_propaga_error_real(self):
        """Nunca finge éxito: si Qdrant falla de verdad, el llamador debe enterarse."""
        fake_client = MagicMock()
        fake_client.collection_exists.return_value = True
        fake_client.count.return_value = SimpleNamespace(count=2)
        fake_client.delete.side_effect = RuntimeError('Qdrant caído')
        with patch.object(rag_engine.qdrant_client, 'QdrantClient', return_value=fake_client):
            with self.assertRaises(RuntimeError):
                rag_engine.delete_source_chunks('mi-fuente')

    def test_index_source_documento_ilegible_devuelve_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = {'id': 'fuente-x', 'name': 'Fuente X', 'path': Path(tmp) / 'no-existe.pdf'}
            result = rag_engine.index_source(source)
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['chunkCount'], 0)


class _FakeNode:
    def __init__(self, metadata, content, score=0.8):
        self.node = self
        self.metadata = metadata
        self._content = content
        self.score = score

    def get_content(self):
        return self._content


class _FakeRetriever:
    def __init__(self, nodes):
        self._nodes = nodes

    def retrieve(self, query):
        return self._nodes


class KnowledgeBaseScopeFilterTests(unittest.TestCase):
    """Sección 13: un documento fuera del alcance del MVP (adult_general) no
    debe alimentar un borrador general aunque el RAG lo recupere."""

    def test_chunk_fuera_de_alcance_se_descarta(self):
        service = rag_engine.KnowledgeBaseService()
        nodes = [_FakeNode(
            metadata={'sourceId': 'pediatria-2020', 'documentName': 'Guía pediátrica',
                      'scope': ['pediatric']}, content='contenido fuera de alcance')]
        with patch.object(rag_engine, 'HuggingFaceEmbedding', return_value=object()), \
                patch.object(service, '_retriever', return_value=_FakeRetriever(nodes)):
            results = service.search('cualquier consulta')
        self.assertEqual(results, [])

    def test_chunk_adult_general_se_conserva(self):
        service = rag_engine.KnowledgeBaseService()
        nodes = [_FakeNode(
            metadata={'sourceId': 'nom-043', 'documentName': 'NOM-043',
                      'scope': ['adult_general']}, content='contenido dentro de alcance')]
        with patch.object(rag_engine, 'HuggingFaceEmbedding', return_value=object()), \
                patch.object(service, '_retriever', return_value=_FakeRetriever(nodes)):
            results = service.search('cualquier consulta')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].sourceId, 'nom-043')

    def test_chunk_sin_scope_declarado_no_se_filtra(self):
        """Fuentes legadas (Fase 3.5/4/5) sin `scope` en su metadata no se restringen."""
        service = rag_engine.KnowledgeBaseService()
        nodes = [_FakeNode(
            metadata={'sourceId': 'legado', 'documentName': 'Fuente legada'},
            content='contenido sin scope declarado')]
        with patch.object(rag_engine, 'HuggingFaceEmbedding', return_value=object()), \
                patch.object(service, '_retriever', return_value=_FakeRetriever(nodes)):
            results = service.search('cualquier consulta')
        self.assertEqual(len(results), 1)


class ResourcesEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'resources.db'
        apply_sql(self.path)
        self.db = Prisma(datasource={'url': 'file:' + self.path.as_posix()})
        await self.db.connect()
        self.app = FastAPI()
        self.app.state.db = self.db
        self.app.include_router(router)
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url='http://test/api/v1/')
        food_db.reset_food_database_cache()

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.db.disconnect()
        self.temp.cleanup()
        food_db.reset_food_database_cache()

    async def test_resources_status_reports_missing_resources(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing_pdfs = Path(tmp) / 'pdfs'
            missing_bam = Path(tmp) / 'BAM.xlsx'
            missing_manifest = Path(tmp) / 'manifest.json'
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_PATH': str(missing_pdfs),
                                            'ALIMENTIA_FOOD_DB_PATH': str(missing_bam),
                                            'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(missing_manifest)}):
                response = await self.client.get('resources/status')
                self.assertEqual(response.status_code, 200)
                body = response.json()
                self.assertEqual(body['knowledgeBase'], {'ready': False, 'documentCount': 0, 'pathConfigured': True,
                    'knowledgeBaseVersion': None, 'authorizedSourceCount': 0, 'indexedDocumentCount': 0})
                self.assertEqual(body['foodDatabase'], {
                    'ready': False, 'fileFound': False, 'schemaValid': False,
                    'sourceName': None, 'sourceVersion': None, 'publicationYear': None})

    async def test_resources_status_reports_ready_resources(self):
        """Sección 32: indexedDocumentCount refleja KnowledgeSource real en
        base de datos (vía sync_knowledge_sources), no solo archivos en disco."""
        with tempfile.TemporaryDirectory() as tmp:
            pdfs_dir = Path(tmp) / 'pdfs'
            pdfs_dir.mkdir()
            (pdfs_dir / 'guia.txt').write_text('contenido')
            manifest_path = Path(tmp) / 'manifest.json'
            _write_manifest(manifest_path, sources=[{'id': 'insp-guia-2015', 'name': 'Guía de prueba',
                'institution': 'INSP', 'version': '2015', 'file': 'guia.txt', 'type': 'GUIDELINE'}])
            bam_path = Path(tmp) / 'BAM.xlsx'
            _write_bam(bam_path)
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_PATH': str(pdfs_dir),
                                            'ALIMENTIA_FOOD_DB_PATH': str(bam_path),
                                            'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(manifest_path)}):
                await sync_knowledge_sources(self.db, pdfs_dir)
                response = await self.client.get('resources/status')
                body = response.json()
                self.assertTrue(body['knowledgeBase']['ready'])
                self.assertEqual(body['knowledgeBase']['knowledgeBaseVersion'], '1.0')
                self.assertEqual(body['knowledgeBase']['indexedDocumentCount'], 1)
                self.assertTrue(body['foodDatabase']['ready'])

    async def test_resources_status_incluye_motor_de_calculo_y_llm(self):
        """Fase 6, sección 36: /resources/status expone calculationEngine y llm sin
        llamar realmente al proveedor LLM."""
        response = await self.client.get('resources/status')
        body = response.json()
        self.assertEqual(body['calculationEngine'], {'ready': True, 'rulesetVersion': '1.0'})
        self.assertTrue(body['llm']['configured'])
        self.assertIsInstance(body['llm']['modelName'], str)
        self.assertTrue(body['llm']['modelName'])

    async def test_ingest_pdfs_does_not_500_when_no_documents(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing_pdfs = Path(tmp) / 'pdfs'
            manifest_path = Path(tmp) / 'manifest.json'
            _write_manifest(manifest_path, sources=[])
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_PATH': str(missing_pdfs),
                                            'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(manifest_path)}):
                response = await self.client.post('ingest-pdfs')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['documentCount'], 0)


if __name__ == '__main__':
    unittest.main()
