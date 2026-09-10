"""Pruebas del manifiesto de fuentes autorizadas (Fase 3.5). Sin base de datos ni red."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services import knowledge_manifest


class ManifestLoadingTests(unittest.TestCase):
    def test_manifest_inexistente_no_lanza_y_no_autoriza_nada(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / 'manifest.json'
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(missing)}):
                manifest = knowledge_manifest.load_manifest()
                self.assertEqual(manifest, {'version': None, 'sources': []})

    def test_manifest_invalido_json_roto_no_lanza(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'manifest.json'
            path.write_text('{ esto no es json valido ][', encoding='utf-8')
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(path)}):
                manifest = knowledge_manifest.load_manifest()
                self.assertEqual(manifest, {'version': None, 'sources': []})

    def test_manifest_invalido_forma_incorrecta_no_lanza(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'manifest.json'
            path.write_text(json.dumps(['no', 'es', 'un', 'objeto']), encoding='utf-8')
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(path)}):
                manifest = knowledge_manifest.load_manifest()
                self.assertEqual(manifest, {'version': None, 'sources': []})

    def test_manifest_valido_vacio(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'manifest.json'
            path.write_text(json.dumps({'version': '1.0', 'sources': []}), encoding='utf-8')
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(path)}):
                manifest = knowledge_manifest.load_manifest()
                self.assertEqual(manifest, {'version': '1.0', 'sources': []})

    def test_fuente_registrada_valida(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'manifest.json'
            path.write_text(json.dumps({'version': '1.0', 'sources': [
                {'id': 'insp-tablas-2015', 'name': 'Tablas de composición de alimentos',
                 'institution': 'INSP', 'version': '2015', 'file': 'insp-2015.pdf', 'type': 'REFERENCE_TABLE'},
            ]}), encoding='utf-8')
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(path)}):
                manifest = knowledge_manifest.load_manifest()
                self.assertEqual(len(manifest['sources']), 1)
                source = manifest['sources'][0]
                self.assertEqual(source['id'], 'insp-tablas-2015')
                self.assertEqual(source['institution'], 'INSP')
                self.assertEqual(source['type'], 'REFERENCE_TABLE')

    def test_entrada_sin_campos_requeridos_se_omite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'manifest.json'
            path.write_text(json.dumps({'version': '1.0', 'sources': [
                {'id': 'sin-archivo', 'name': 'Falta el campo file'},
                {'name': 'Falta el id', 'file': 'x.pdf'},
            ]}), encoding='utf-8')
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(path)}):
                manifest = knowledge_manifest.load_manifest()
                self.assertEqual(manifest['sources'], [])

    def test_tipo_desconocido_cae_a_other(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'manifest.json'
            path.write_text(json.dumps({'version': '1.0', 'sources': [
                {'id': 'x', 'name': 'X', 'file': 'x.pdf', 'type': 'ALGO_INVENTADO'},
            ]}), encoding='utf-8')
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(path)}):
                manifest = knowledge_manifest.load_manifest()
                self.assertEqual(manifest['sources'][0]['type'], 'OTHER')


class AuthorizedDocumentsTests(unittest.TestCase):
    def test_documento_no_autorizado_es_ignorado(self):
        """Un archivo presente en la carpeta pero ausente del manifiesto nunca se procesa."""
        with tempfile.TemporaryDirectory() as tmp:
            knowledge_dir = Path(tmp) / 'pdfs'
            knowledge_dir.mkdir()
            (knowledge_dir / 'no_declarado.txt').write_text('contenido')
            manifest_path = Path(tmp) / 'manifest.json'
            manifest_path.write_text(json.dumps({'version': '1.0', 'sources': []}), encoding='utf-8')
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(manifest_path)}):
                authorized = knowledge_manifest.authorized_documents(knowledge_dir)
                self.assertEqual(authorized, [])

    def test_fuente_declarada_sin_archivo_en_disco_es_ignorada(self):
        """Una fuente en el manifiesto cuyo archivo no existe todavía no se procesa ni lanza excepción."""
        with tempfile.TemporaryDirectory() as tmp:
            knowledge_dir = Path(tmp) / 'pdfs'
            knowledge_dir.mkdir()
            manifest_path = Path(tmp) / 'manifest.json'
            manifest_path.write_text(json.dumps({'version': '1.0', 'sources': [
                {'id': 'insp-2015', 'name': 'Tablas INSP', 'file': 'insp-2015.pdf'},
            ]}), encoding='utf-8')
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(manifest_path)}):
                authorized = knowledge_manifest.authorized_documents(knowledge_dir)
                self.assertEqual(authorized, [])

    def test_documento_autorizado_procesado_y_metadata_conservada(self):
        """Un archivo declarado en el manifiesto Y presente en disco se autoriza con su metadata intacta."""
        with tempfile.TemporaryDirectory() as tmp:
            knowledge_dir = Path(tmp) / 'pdfs'
            knowledge_dir.mkdir()
            (knowledge_dir / 'insp-2015.pdf').write_text('contenido de prueba')
            (knowledge_dir / 'no_declarado.txt').write_text('esto no debe autorizarse')
            manifest_path = Path(tmp) / 'manifest.json'
            manifest_path.write_text(json.dumps({'version': '1.0', 'sources': [
                {'id': 'insp-tablas-2015', 'name': 'Tablas de composición de alimentos',
                 'institution': 'INSP', 'version': '2015', 'file': 'insp-2015.pdf', 'type': 'REFERENCE_TABLE'},
            ]}), encoding='utf-8')
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(manifest_path)}):
                authorized = knowledge_manifest.authorized_documents(knowledge_dir)
                self.assertEqual(len(authorized), 1)
                entry = authorized[0]
                self.assertEqual(entry['id'], 'insp-tablas-2015')
                self.assertEqual(entry['name'], 'Tablas de composición de alimentos')
                self.assertEqual(entry['institution'], 'INSP')
                self.assertEqual(entry['version'], '2015')
                self.assertEqual(entry['path'], knowledge_dir / 'insp-2015.pdf')

    def test_fuente_activa_por_defecto_si_no_se_declara(self):
        """Manifiestos existentes (Fase 3.5/4/5) sin 'active' siguen autorizando su fuente."""
        with tempfile.TemporaryDirectory() as tmp:
            knowledge_dir = Path(tmp) / 'pdfs'
            knowledge_dir.mkdir()
            (knowledge_dir / 'legado.pdf').write_text('contenido')
            manifest_path = Path(tmp) / 'manifest.json'
            manifest_path.write_text(json.dumps({'version': '1.0', 'sources': [
                {'id': 'legado', 'name': 'Fuente legada', 'file': 'legado.pdf'},
            ]}), encoding='utf-8')
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(manifest_path)}):
                manifest = knowledge_manifest.load_manifest()
                self.assertTrue(manifest['sources'][0]['active'])
                authorized = knowledge_manifest.authorized_documents(knowledge_dir)
                self.assertEqual(len(authorized), 1)

    def test_fuente_inactiva_no_se_ingiere(self):
        """Una fuente 'active: false' (referencia histórica) se conserva en el manifiesto
        pero nunca se autoriza para ingesta."""
        with tempfile.TemporaryDirectory() as tmp:
            knowledge_dir = Path(tmp) / 'pdfs'
            knowledge_dir.mkdir()
            (knowledge_dir / 'historica.pdf').write_text('contenido')
            manifest_path = Path(tmp) / 'manifest.json'
            manifest_path.write_text(json.dumps({'version': '1.0', 'sources': [
                {'id': 'historica', 'name': 'Fuente histórica', 'file': 'historica.pdf', 'active': False},
            ]}), encoding='utf-8')
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(manifest_path)}):
                manifest = knowledge_manifest.load_manifest()
                self.assertFalse(manifest['sources'][0]['active'])
                authorized = knowledge_manifest.authorized_documents(knowledge_dir)
                self.assertEqual(authorized, [])

    def test_scope_y_publication_year_se_conservan(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'manifest.json'
            path.write_text(json.dumps({'version': '1.0', 'sources': [
                {'id': 'x', 'name': 'X', 'file': 'x.pdf', 'publicationYear': 2012,
                 'scope': ['adult_general']},
            ]}), encoding='utf-8')
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(path)}):
                source = knowledge_manifest.load_manifest()['sources'][0]
                self.assertEqual(source['publicationYear'], 2012)
                self.assertEqual(source['scope'], ['adult_general'])

    def test_scope_ausente_se_normaliza_a_lista_vacia(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'manifest.json'
            path.write_text(json.dumps({'version': '1.0', 'sources': [
                {'id': 'x', 'name': 'X', 'file': 'x.pdf'},
            ]}), encoding='utf-8')
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(path)}):
                source = knowledge_manifest.load_manifest()['sources'][0]
                self.assertEqual(source['scope'], [])
                self.assertIsNone(source['publicationYear'])

    def test_knowledge_base_version_y_authorized_source_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / 'manifest.json'
            manifest_path.write_text(json.dumps({'version': '2.3', 'sources': [
                {'id': 'a', 'name': 'A', 'file': 'a.pdf'}, {'id': 'b', 'name': 'B', 'file': 'b.pdf'},
            ]}), encoding='utf-8')
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(manifest_path)}):
                self.assertEqual(knowledge_manifest.knowledge_base_version(), '2.3')
                self.assertEqual(knowledge_manifest.authorized_source_count(), 2)


if __name__ == '__main__':
    unittest.main()
