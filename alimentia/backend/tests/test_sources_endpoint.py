"""Pruebas HTTP de fuentes de conocimiento (Fase 3.5; administración de
documentos: alta, eliminación, visualización, descarga, reintento)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import httpx
from fastapi import FastAPI
from prisma import Prisma

from app.repositories.knowledge import resolve_source_id, sync_knowledge_sources
from app.routes.knowledge import router
from app.services import rag_engine
from test_persistence import apply_sql

VALID_PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\ncontenido de prueba, no es un PDF real pero tiene la firma correcta\n%%EOF"


class SourcesEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'sources.db'
        apply_sql(self.path)
        self.db = Prisma(datasource={'url': 'file:' + self.path.as_posix()})
        await self.db.connect()
        self.app = FastAPI()
        self.app.state.db = self.db
        self.app.include_router(router)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url='http://test/api/v1/')

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.db.disconnect()
        self.temp.cleanup()

    async def test_sources_vacio_sin_fuentes_registradas(self):
        response = await self.client.get('sources')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    async def test_source_inexistente_devuelve_404(self):
        response = await self.client.get(f'sources/{uuid4()}')
        self.assertEqual(response.status_code, 404)

    async def test_fuente_sincronizada_desde_manifiesto_aparece_en_listado(self):
        with tempfile.TemporaryDirectory() as tmp:
            knowledge_dir = Path(tmp)
            (knowledge_dir / 'insp-2015.pdf').write_text('contenido de prueba')
            manifest_path = knowledge_dir / 'manifest.json'
            manifest_path.write_text(json.dumps({'version': '1.0', 'sources': [
                {'id': 'insp-tablas-2015', 'name': 'Tablas de composición de alimentos',
                 'institution': 'INSP', 'version': '2015', 'file': 'insp-2015.pdf', 'type': 'REFERENCE_TABLE'},
            ]}), encoding='utf-8')
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(manifest_path)}):
                synced = await sync_knowledge_sources(self.db, knowledge_dir)
                self.assertEqual(len(synced), 1)

            listed = await self.client.get('sources')
            self.assertEqual(listed.status_code, 200)
            body = listed.json()
            self.assertEqual(len(body), 1)
            self.assertEqual(body[0]['documentName'], 'Tablas de composición de alimentos')
            self.assertEqual(body[0]['institution'], 'INSP')
            self.assertEqual(body[0]['version'], '2015')
            self.assertEqual(body[0]['sourceType'], 'REFERENCE_TABLE')
            self.assertTrue(body[0]['isActive'])
            self.assertEqual(body[0]['originalFilename'], 'insp-2015.pdf')
            self.assertIsNotNone(body[0]['checksum'])

            fetched = await self.client.get(f"sources/{body[0]['id']}")
            self.assertEqual(fetched.status_code, 200)
            self.assertEqual(fetched.json()['id'], body[0]['id'])

    async def test_publication_year_del_manifiesto_se_persiste(self):
        with tempfile.TemporaryDirectory() as tmp:
            knowledge_dir = Path(tmp)
            (knowledge_dir / 'nom-043.pdf').write_text('contenido de prueba')
            manifest_path = knowledge_dir / 'manifest.json'
            manifest_path.write_text(json.dumps({'version': '1.0', 'sources': [
                {'id': 'nom-043', 'name': 'NOM-043-SSA2-2012', 'institution': 'Secretaría de Salud',
                 'file': 'nom-043.pdf', 'publicationYear': 2012, 'type': 'REGULATION'},
            ]}), encoding='utf-8')
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(manifest_path)}):
                await sync_knowledge_sources(self.db, knowledge_dir)

            listed = await self.client.get('sources')
            body = listed.json()
            self.assertEqual(len(body), 1)
            self.assertTrue(body[0]['publicationDate'].startswith('2012-01-01'))

    async def test_fuente_inactiva_no_se_sincroniza(self):
        with tempfile.TemporaryDirectory() as tmp:
            knowledge_dir = Path(tmp)
            (knowledge_dir / 'historica.pdf').write_text('contenido')
            manifest_path = knowledge_dir / 'manifest.json'
            manifest_path.write_text(json.dumps({'version': '1.0', 'sources': [
                {'id': 'historica', 'name': 'Histórica', 'file': 'historica.pdf', 'active': False},
            ]}), encoding='utf-8')
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(manifest_path)}):
                synced = await sync_knowledge_sources(self.db, knowledge_dir)
        self.assertEqual(synced, [])
        self.assertEqual(await self.db.knowledgesource.count(), 0)

    async def test_sync_es_idempotente_no_duplica(self):
        with tempfile.TemporaryDirectory() as tmp:
            knowledge_dir = Path(tmp)
            (knowledge_dir / 'insp-2015.pdf').write_text('contenido de prueba')
            manifest_path = knowledge_dir / 'manifest.json'
            manifest_path.write_text(json.dumps({'version': '1.0', 'sources': [
                {'id': 'insp-tablas-2015', 'name': 'Tablas de composición de alimentos', 'file': 'insp-2015.pdf'},
            ]}), encoding='utf-8')
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(manifest_path)}):
                await sync_knowledge_sources(self.db, knowledge_dir)
                await sync_knowledge_sources(self.db, knowledge_dir)
        self.assertEqual(await self.db.knowledgesource.count(), 1)

    async def test_sync_ignora_fuente_no_declarada_en_manifiesto(self):
        with tempfile.TemporaryDirectory() as tmp:
            knowledge_dir = Path(tmp)
            (knowledge_dir / 'no_declarado.pdf').write_text('contenido')
            manifest_path = knowledge_dir / 'manifest.json'
            manifest_path.write_text(json.dumps({'version': '1.0', 'sources': []}), encoding='utf-8')
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(manifest_path)}):
                synced = await sync_knowledge_sources(self.db, knowledge_dir)
        self.assertEqual(synced, [])
        self.assertEqual(await self.db.knowledgesource.count(), 0)

    async def test_resolve_source_id_slug_conocido_devuelve_uuid_real(self):
        """Fase 4, sección 3: el sourceId del manifiesto (slug) debe resolver al UUID real de KnowledgeSource."""
        with tempfile.TemporaryDirectory() as tmp:
            knowledge_dir = Path(tmp)
            (knowledge_dir / 'insp-2015.pdf').write_text('contenido de prueba')
            manifest_path = knowledge_dir / 'manifest.json'
            manifest_path.write_text(json.dumps({'version': '1.0', 'sources': [
                {'id': 'insp-tablas-2015', 'name': 'Tablas de composición de alimentos', 'file': 'insp-2015.pdf'},
            ]}), encoding='utf-8')
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(manifest_path)}):
                await sync_knowledge_sources(self.db, knowledge_dir)
                resolved = await resolve_source_id(self.db, 'insp-tablas-2015')
        source_row = await self.db.knowledgesource.find_first(where={'originalFilename': 'insp-2015.pdf'})
        self.assertEqual(resolved, source_row.id)
        # El slug del manifiesto nunca es, por sí mismo, un UUID válido de KnowledgeSource.
        self.assertNotEqual(resolved, 'insp-tablas-2015')

    async def test_resolve_source_id_slug_desconocido_devuelve_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / 'manifest.json'
            manifest_path.write_text(json.dumps({'version': '1.0', 'sources': []}), encoding='utf-8')
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(manifest_path)}):
                resolved = await resolve_source_id(self.db, 'slug-que-no-existe')
        self.assertIsNone(resolved)

    async def test_alta_via_http_multipart_devuelve_201(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdfs_dir = Path(tmp) / 'pdfs'
            manifest_path = Path(tmp) / 'manifest.json'
            manifest_path.write_text(json.dumps({'version': '1.0', 'sources': []}), encoding='utf-8')
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_PATH': str(pdfs_dir),
                                            'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(manifest_path)}), \
                    patch.object(rag_engine, 'index_source', return_value={'status': 'indexed', 'chunkCount': 4, 'message': None}):
                response = await self.client.post('sources', files={'file': ('guia.pdf', VALID_PDF, 'application/pdf')},
                    data={'name': 'Guía subida por HTTP', 'sourceType': 'GUIDELINE', 'institution': 'INSP'})
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertEqual(body['documentName'], 'Guía subida por HTTP')
        self.assertEqual(body['indexStatus'], 'INDEXED')
        self.assertTrue(body['isActive'])

    async def test_alta_via_http_extension_invalida_devuelve_422(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdfs_dir = Path(tmp) / 'pdfs'
            manifest_path = Path(tmp) / 'manifest.json'
            manifest_path.write_text(json.dumps({'version': '1.0', 'sources': []}), encoding='utf-8')
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_PATH': str(pdfs_dir),
                                            'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(manifest_path)}):
                response = await self.client.post('sources', files={'file': ('doc.txt', b'contenido', 'text/plain')},
                    data={'name': 'Documento', 'sourceType': 'GUIDELINE'})
        self.assertEqual(response.status_code, 422)

    async def test_alta_via_http_duplicado_devuelve_409(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdfs_dir = Path(tmp) / 'pdfs'
            manifest_path = Path(tmp) / 'manifest.json'
            manifest_path.write_text(json.dumps({'version': '1.0', 'sources': []}), encoding='utf-8')
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_PATH': str(pdfs_dir),
                                            'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(manifest_path)}), \
                    patch.object(rag_engine, 'index_source', return_value={'status': 'indexed', 'chunkCount': 1, 'message': None}):
                first = await self.client.post('sources', files={'file': ('a.pdf', VALID_PDF, 'application/pdf')},
                    data={'name': 'Original', 'sourceType': 'GUIDELINE'})
                self.assertEqual(first.status_code, 201, first.text)
                second = await self.client.post('sources', files={'file': ('b.pdf', VALID_PDF, 'application/pdf')},
                    data={'name': 'Duplicado', 'sourceType': 'GUIDELINE'})
        self.assertEqual(second.status_code, 409)
        self.assertIn('ya se encuentra registrado', second.json()['detail'])

    async def test_ver_y_descargar_documento_devuelve_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdfs_dir = Path(tmp) / 'pdfs'
            manifest_path = Path(tmp) / 'manifest.json'
            manifest_path.write_text(json.dumps({'version': '1.0', 'sources': []}), encoding='utf-8')
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_PATH': str(pdfs_dir),
                                            'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(manifest_path)}), \
                    patch.object(rag_engine, 'index_source', return_value={'status': 'indexed', 'chunkCount': 1, 'message': None}):
                created = await self.client.post('sources', files={'file': ('visible.pdf', VALID_PDF, 'application/pdf')},
                    data={'name': 'Documento visible', 'sourceType': 'GUIDELINE'})
                source_id = created.json()['id']

                inline = await self.client.get(f'sources/{source_id}/document')
                self.assertEqual(inline.status_code, 200)
                self.assertEqual(inline.headers['content-type'], 'application/pdf')
                self.assertIn('inline', inline.headers['content-disposition'])
                self.assertEqual(inline.content, VALID_PDF)

                download = await self.client.get(f'sources/{source_id}/download')
                self.assertEqual(download.status_code, 200)
                self.assertIn('attachment', download.headers['content-disposition'])
                self.assertEqual(download.content, VALID_PDF)

    async def test_documento_de_fuente_inexistente_devuelve_404(self):
        response = await self.client.get(f'sources/{uuid4()}/document')
        self.assertEqual(response.status_code, 404)

    async def test_eliminar_fuente_via_http_devuelve_204_y_desaparece_del_listado(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdfs_dir = Path(tmp) / 'pdfs'
            manifest_path = Path(tmp) / 'manifest.json'
            manifest_path.write_text(json.dumps({'version': '1.0', 'sources': []}), encoding='utf-8')
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_PATH': str(pdfs_dir),
                                            'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(manifest_path)}), \
                    patch.object(rag_engine, 'index_source', return_value={'status': 'indexed', 'chunkCount': 1, 'message': None}), \
                    patch.object(rag_engine, 'delete_source_chunks', return_value=1):
                created = await self.client.post('sources', files={'file': ('a.pdf', VALID_PDF, 'application/pdf')},
                    data={'name': 'A eliminar', 'sourceType': 'GUIDELINE'})
                source_id = created.json()['id']

                deleted = await self.client.delete(f'sources/{source_id}')
                self.assertEqual(deleted.status_code, 204)

                listed = await self.client.get('sources')
        self.assertEqual(listed.json(), [])

    async def test_eliminar_fuente_inexistente_devuelve_404(self):
        response = await self.client.delete(f'sources/{uuid4()}')
        self.assertEqual(response.status_code, 404)

    async def test_reindex_via_http(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdfs_dir = Path(tmp) / 'pdfs'
            manifest_path = Path(tmp) / 'manifest.json'
            manifest_path.write_text(json.dumps({'version': '1.0', 'sources': []}), encoding='utf-8')
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_PATH': str(pdfs_dir),
                                            'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(manifest_path)}), \
                    patch.object(rag_engine, 'index_source', return_value={'status': 'indexed', 'chunkCount': 1, 'message': None}):
                created = await self.client.post('sources', files={'file': ('a.pdf', VALID_PDF, 'application/pdf')},
                    data={'name': 'Reindexable', 'sourceType': 'GUIDELINE'})
                source_id = created.json()['id']
                response = await self.client.post(f'sources/{source_id}/reindex')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['indexStatus'], 'INDEXED')

    async def test_includeinactive_por_defecto_oculta_inactivas(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdfs_dir = Path(tmp) / 'pdfs'
            manifest_path = Path(tmp) / 'manifest.json'
            manifest_path.write_text(json.dumps({'version': '1.0', 'sources': []}), encoding='utf-8')
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_PATH': str(pdfs_dir),
                                            'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(manifest_path)}), \
                    patch.object(rag_engine, 'index_source', return_value={'status': 'indexed', 'chunkCount': 1, 'message': None}), \
                    patch.object(rag_engine, 'delete_source_chunks', return_value=1):
                created = await self.client.post('sources', files={'file': ('a.pdf', VALID_PDF, 'application/pdf')},
                    data={'name': 'Se desactivará', 'sourceType': 'GUIDELINE'})
                source_id = created.json()['id']
                patient = await self.db.patient.create(data={'name': 'Paciente', 'sex': 'female', 'age': 30})
                consultation = await self.db.nutritionconsultation.create(data={'patientId': patient.id})
                generation = await self.db.aigeneration.create(data={
                    'consultationId': consultation.id, 'modelProvider': 'fake', 'modelName': 'fake-model', 'status': 'SUCCESS'})
                await self.db.retrievedsource.create(data={
                    'generationId': generation.id, 'knowledgeSourceId': source_id, 'content': 'cita histórica'})
                await self.client.delete(f'sources/{source_id}')

                default_view = await self.client.get('sources')
                full_view = await self.client.get('sources', params={'includeInactive': 'true'})
        self.assertEqual(default_view.json(), [])
        self.assertEqual(len(full_view.json()), 1)
        self.assertFalse(full_view.json()[0]['isActive'])

    async def test_resolve_source_id_declarada_pero_no_sincronizada_devuelve_none(self):
        """Una fuente en el manifiesto cuyo archivo nunca se sincronizó no debe resolver a nada inventado."""
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / 'manifest.json'
            manifest_path.write_text(json.dumps({'version': '1.0', 'sources': [
                {'id': 'insp-tablas-2015', 'name': 'Tablas de composición de alimentos', 'file': 'insp-2015.pdf'},
            ]}), encoding='utf-8')
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(manifest_path)}):
                # Nunca se llamó sync_knowledge_sources: no hay KnowledgeSource en base de datos.
                resolved = await resolve_source_id(self.db, 'insp-tablas-2015')
        self.assertIsNone(resolved)


if __name__ == '__main__':
    unittest.main()
