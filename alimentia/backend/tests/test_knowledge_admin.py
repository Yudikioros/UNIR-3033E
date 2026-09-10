"""
Pruebas de administración de documentos RAG (alta, eliminación, reintento).

Nunca depende de Qdrant/embeddings reales: `rag_engine.index_source` y
`rag_engine.delete_source_chunks` se mockean aquí. La prueba real end-to-end
contra Qdrant vive en la validación Docker (no en esta suite).
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from prisma import Prisma

from app.repositories import knowledge as knowledge_repo
from app.services import knowledge_admin, knowledge_manifest, knowledge_storage, rag_engine
from app.services.knowledge_admin import KnowledgeAdminError
from test_persistence import apply_sql

VALID_PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\ncontenido de prueba, no es un PDF real pero tiene la firma correcta\n%%EOF"


class KnowledgeAdminTestBase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'knowledge_admin.db'
        apply_sql(self.path)
        self.db = Prisma(datasource={'url': 'file:' + self.path.as_posix()})
        await self.db.connect()

        self.workdir = tempfile.TemporaryDirectory()
        self.pdfs_dir = Path(self.workdir.name) / 'pdfs'
        self.pdfs_dir.mkdir()
        self.manifest_path = Path(self.workdir.name) / 'manifest.json'
        self.manifest_path.write_text(json.dumps({'version': '1.0', 'sources': []}), encoding='utf-8')
        self.env_patch = patch.dict('os.environ', {
            'ALIMENTIA_KNOWLEDGE_PATH': str(self.pdfs_dir),
            'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(self.manifest_path),
        })
        self.env_patch.start()

    async def asyncTearDown(self):
        self.env_patch.stop()
        self.workdir.cleanup()
        await self.db.disconnect()
        self.temp.cleanup()

    def _manifest(self) -> dict:
        return json.loads(self.manifest_path.read_text(encoding='utf-8'))


class AddSourceTests(KnowledgeAdminTestBase):
    async def test_alta_valida_queda_indexada_y_sincronizada(self):
        with patch.object(rag_engine, 'index_source', return_value={'status': 'indexed', 'chunkCount': 3, 'message': None}):
            result = await knowledge_admin.add_source(
                self.db, file_bytes=VALID_PDF, upload_filename='Mi Guía.pdf', content_type='application/pdf',
                name='Mi Guía de Prueba', institution='INSP', version='2024', source_type='GUIDELINE',
                publication_date='2024-01-01')

        self.assertEqual(result.documentName, 'Mi Guía de Prueba')
        self.assertEqual(result.indexStatus, 'INDEXED')
        self.assertTrue(result.isActive)
        self.assertIsNotNone(result.manifestSourceId)
        self.assertIsNotNone(result.checksum)

        # ARCHIVO FÍSICO
        row = await knowledge_repo.get_source_row(self.db, result.id)
        stored_path = knowledge_storage.resolve_stored_path(row.storedFilename)
        self.assertTrue(stored_path.exists())
        self.assertEqual(stored_path.read_bytes(), VALID_PDF)

        # MANIFEST
        manifest = self._manifest()
        self.assertEqual(len(manifest['sources']), 1)
        self.assertEqual(manifest['sources'][0]['id'], row.manifestSourceId)
        self.assertEqual(manifest['sources'][0]['file'], row.storedFilename)
        self.assertTrue(manifest['sources'][0]['active'])

    async def test_extension_invalida_rechazada(self):
        with self.assertRaises(KnowledgeAdminError) as ctx:
            await knowledge_admin.add_source(
                self.db, file_bytes=b'contenido cualquiera', upload_filename='documento.txt', content_type='text/plain',
                name='Documento inválido', institution=None, version=None, source_type='GUIDELINE', publication_date=None)
        self.assertEqual(ctx.exception.status, 422)
        self.assertEqual(await self.db.knowledgesource.count(), 0)

    async def test_mime_invalido_rechazado(self):
        with self.assertRaises(KnowledgeAdminError) as ctx:
            await knowledge_admin.add_source(
                self.db, file_bytes=VALID_PDF, upload_filename='documento.pdf', content_type='application/octet-stream',
                name='Documento', institution=None, version=None, source_type='GUIDELINE', publication_date=None)
        self.assertEqual(ctx.exception.status, 422)

    async def test_archivo_vacio_rechazado(self):
        with self.assertRaises(KnowledgeAdminError) as ctx:
            await knowledge_admin.add_source(
                self.db, file_bytes=b'', upload_filename='vacio.pdf', content_type='application/pdf',
                name='Documento', institution=None, version=None, source_type='GUIDELINE', publication_date=None)
        self.assertEqual(ctx.exception.status, 422)

    async def test_firma_pdf_invalida_rechazada(self):
        """Sección 34: no se acepta un archivo solo porque termina en .pdf."""
        with self.assertRaises(KnowledgeAdminError) as ctx:
            await knowledge_admin.add_source(
                self.db, file_bytes=b'esto no es un PDF real', upload_filename='falso.pdf', content_type='application/pdf',
                name='Documento', institution=None, version=None, source_type='GUIDELINE', publication_date=None)
        self.assertEqual(ctx.exception.status, 422)
        self.assertEqual(await self.db.knowledgesource.count(), 0)
        self.assertEqual(self._manifest()['sources'], [])

    async def test_sin_contenido_extraible_revierte_igual_que_un_error(self):
        """Un PDF escaneado sin texto real (rag_engine.index_source devuelve
        "no_content") nunca debe quedar marcado como disponible -se revierte
        igual que un error de indexación (encontrado en la validación Docker)."""
        with patch.object(rag_engine, 'index_source',
                           return_value={'status': 'no_content', 'chunkCount': 0, 'message': 'El documento no produjo contenido extraíble.'}):
            with self.assertRaises(KnowledgeAdminError) as ctx:
                await knowledge_admin.add_source(
                    self.db, file_bytes=VALID_PDF, upload_filename='escaneado.pdf', content_type='application/pdf',
                    name='Documento escaneado sin texto', institution=None, version=None, source_type='GUIDELINE',
                    publication_date=None)
        self.assertEqual(ctx.exception.status, 502)
        self.assertEqual(await self.db.knowledgesource.count(), 0)
        self.assertEqual(self._manifest()['sources'], [])

    async def test_tipo_de_fuente_invalido_rechazado(self):
        with self.assertRaises(KnowledgeAdminError) as ctx:
            await knowledge_admin.add_source(
                self.db, file_bytes=VALID_PDF, upload_filename='documento.pdf', content_type='application/pdf',
                name='Documento', institution=None, version=None, source_type='NO_EXISTE', publication_date=None)
        self.assertEqual(ctx.exception.status, 422)

    async def test_nombre_vacio_rechazado(self):
        with self.assertRaises(KnowledgeAdminError) as ctx:
            await knowledge_admin.add_source(
                self.db, file_bytes=VALID_PDF, upload_filename='documento.pdf', content_type='application/pdf',
                name='   ', institution=None, version=None, source_type='GUIDELINE', publication_date=None)
        self.assertEqual(ctx.exception.status, 422)

    async def test_duplicado_por_checksum_devuelve_409(self):
        with patch.object(rag_engine, 'index_source', return_value={'status': 'indexed', 'chunkCount': 1, 'message': None}):
            await knowledge_admin.add_source(
                self.db, file_bytes=VALID_PDF, upload_filename='original.pdf', content_type='application/pdf',
                name='Original', institution=None, version=None, source_type='GUIDELINE', publication_date=None)
            with self.assertRaises(KnowledgeAdminError) as ctx:
                await knowledge_admin.add_source(
                    self.db, file_bytes=VALID_PDF, upload_filename='copia-con-otro-nombre.pdf', content_type='application/pdf',
                    name='Copia', institution=None, version=None, source_type='GUIDELINE', publication_date=None)
        self.assertEqual(ctx.exception.status, 409)
        self.assertIn('ya se encuentra registrado', ctx.exception.message)
        self.assertEqual(await self.db.knowledgesource.count(), 1)

    async def test_error_de_indexacion_revierte_archivo_manifest_y_fila(self):
        """Sección 11: si falla la indexación, se revierte todo -no queda
        nada fingiendo que la fuente está disponible-."""
        with patch.object(rag_engine, 'index_source', return_value={'status': 'error', 'chunkCount': 0, 'message': 'Qdrant no disponible'}):
            with self.assertRaises(KnowledgeAdminError) as ctx:
                await knowledge_admin.add_source(
                    self.db, file_bytes=VALID_PDF, upload_filename='falla.pdf', content_type='application/pdf',
                    name='Falla de indexación', institution=None, version=None, source_type='GUIDELINE', publication_date=None)
        self.assertEqual(ctx.exception.status, 502)
        self.assertEqual(await self.db.knowledgesource.count(), 0)
        self.assertEqual(self._manifest()['sources'], [])
        self.assertEqual(list(self.pdfs_dir.iterdir()), [])

    async def test_rollback_fallido_deja_fuente_en_estado_error(self):
        """Sección 11: si el rollback mismo falla, la fuente queda registrada
        en ERROR (nunca se pierde el rastro) para poder reintentar/eliminar."""
        with patch.object(rag_engine, 'index_source', return_value={'status': 'error', 'chunkCount': 0, 'message': 'falla de indexación'}), \
                patch.object(knowledge_admin, '_rollback', return_value=False):
            with self.assertRaises(KnowledgeAdminError) as ctx:
                await knowledge_admin.add_source(
                    self.db, file_bytes=VALID_PDF, upload_filename='falla2.pdf', content_type='application/pdf',
                    name='Falla con rollback fallido', institution=None, version=None, source_type='GUIDELINE',
                    publication_date=None)
        self.assertEqual(ctx.exception.status, 502)
        rows = await self.db.knowledgesource.find_many()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].indexStatus, 'ERROR')
        self.assertIn('falla de indexación', rows[0].indexError)

    async def test_manifest_sigue_siendo_json_valido_tras_alta(self):
        with patch.object(rag_engine, 'index_source', return_value={'status': 'indexed', 'chunkCount': 1, 'message': None}):
            await knowledge_admin.add_source(
                self.db, file_bytes=VALID_PDF, upload_filename='doc.pdf', content_type='application/pdf',
                name='Documento', institution=None, version=None, source_type='GUIDELINE', publication_date=None)
        # Si el JSON quedara truncado, json.loads lanzaría aquí.
        manifest = self._manifest()
        self.assertIn('version', manifest)
        self.assertIsInstance(manifest['sources'], list)


class ReindexSourceTests(KnowledgeAdminTestBase):
    async def test_reintento_exitoso_marca_indexed(self):
        with patch.object(rag_engine, 'index_source', return_value={'status': 'error', 'chunkCount': 0, 'message': 'temporal'}), \
                patch.object(knowledge_admin, '_rollback', return_value=False):
            with self.assertRaises(KnowledgeAdminError):
                await knowledge_admin.add_source(
                    self.db, file_bytes=VALID_PDF, upload_filename='doc.pdf', content_type='application/pdf',
                    name='Documento con error', institution=None, version=None, source_type='GUIDELINE', publication_date=None)
        row = (await self.db.knowledgesource.find_many())[0]
        self.assertEqual(row.indexStatus, 'ERROR')

        with patch.object(rag_engine, 'index_source', return_value={'status': 'indexed', 'chunkCount': 5, 'message': None}):
            result = await knowledge_admin.reindex_source(self.db, row.id)
        self.assertEqual(result.indexStatus, 'INDEXED')
        self.assertIsNone(result.indexError)

    async def test_reintento_de_fuente_inexistente_404(self):
        with self.assertRaises(KnowledgeAdminError) as ctx:
            await knowledge_admin.reindex_source(self.db, str(uuid4()))
        self.assertEqual(ctx.exception.status, 404)


class DeleteSourceTests(KnowledgeAdminTestBase):
    async def _add(self, filename='doc.pdf', name='Documento'):
        with patch.object(rag_engine, 'index_source', return_value={'status': 'indexed', 'chunkCount': 2, 'message': None}):
            return await knowledge_admin.add_source(
                self.db, file_bytes=VALID_PDF, upload_filename=filename, content_type='application/pdf',
                name=name, institution=None, version=None, source_type='GUIDELINE', publication_date=None)

    async def test_eliminar_fuente_sin_historial_la_borra_por_completo(self):
        source = await self._add()
        row = await knowledge_repo.get_source_row(self.db, source.id)
        stored_path = knowledge_storage.resolve_stored_path(row.storedFilename)
        self.assertTrue(stored_path.exists())

        with patch.object(rag_engine, 'delete_source_chunks', return_value=2) as mock_delete:
            await knowledge_admin.delete_source(self.db, source.id)
        mock_delete.assert_called_once_with(row.manifestSourceId)

        self.assertEqual(await self.db.knowledgesource.count(), 0)
        self.assertFalse(stored_path.exists())
        self.assertEqual(self._manifest()['sources'], [])

    async def test_eliminar_fuente_con_historial_la_desactiva_sin_borrar_la_fila(self):
        """Secciones 18/19: nunca se destruye la trazabilidad histórica."""
        source = await self._add()
        patient = await self.db.patient.create(data={'name': 'Paciente de prueba', 'sex': 'female', 'age': 30})
        consultation = await self.db.nutritionconsultation.create(data={'patientId': patient.id})
        generation = await self.db.aigeneration.create(data={
            'consultationId': consultation.id, 'modelProvider': 'fake', 'modelName': 'fake-model',
            'status': 'SUCCESS'})
        await self.db.retrievedsource.create(data={
            'generationId': generation.id, 'knowledgeSourceId': source.id, 'content': 'contenido citado'})

        row = await knowledge_repo.get_source_row(self.db, source.id)
        stored_path = knowledge_storage.resolve_stored_path(row.storedFilename)

        with patch.object(rag_engine, 'delete_source_chunks', return_value=2):
            await knowledge_admin.delete_source(self.db, source.id)

        # La fila NUNCA se borra: la FK con RetrievedSource lo exige, y además queremos preservar la trazabilidad.
        remaining = await knowledge_repo.get_source_row(self.db, source.id)
        self.assertFalse(remaining.isActive)
        self.assertFalse(stored_path.exists())
        manifest_entry = self._manifest()['sources'][0]
        self.assertFalse(manifest_entry['active'])
        self.assertEqual(manifest_entry['id'], row.manifestSourceId)

        # El RetrievedSource histórico sigue intacto.
        retrieved = await self.db.retrievedsource.find_many(where={'knowledgeSourceId': source.id})
        self.assertEqual(len(retrieved), 1)

    async def test_eliminar_siempre_limpia_qdrant_aunque_no_haya_historial(self):
        source = await self._add()
        row = await knowledge_repo.get_source_row(self.db, source.id)
        with patch.object(rag_engine, 'delete_source_chunks', return_value=3) as mock_delete:
            await knowledge_admin.delete_source(self.db, source.id)
        mock_delete.assert_called_once_with(row.manifestSourceId)

    async def test_fallo_al_limpiar_qdrant_propaga_error_502(self):
        source = await self._add()
        with patch.object(rag_engine, 'delete_source_chunks', side_effect=RuntimeError('Qdrant caído')):
            with self.assertRaises(KnowledgeAdminError) as ctx:
                await knowledge_admin.delete_source(self.db, source.id)
        self.assertEqual(ctx.exception.status, 502)
        # No se debe haber desactivado/borrado nada si Qdrant no confirmó la limpieza.
        remaining = await knowledge_repo.get_source_row(self.db, source.id)
        self.assertTrue(remaining.isActive)

    async def test_eliminar_fuente_inexistente_404(self):
        with self.assertRaises(KnowledgeAdminError) as ctx:
            await knowledge_admin.delete_source(self.db, str(uuid4()))
        self.assertEqual(ctx.exception.status, 404)


if __name__ == '__main__':
    unittest.main()
