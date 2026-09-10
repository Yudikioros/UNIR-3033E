"""Pruebas de validación y almacenamiento físico de documentos RAG."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services import knowledge_storage
from app.services.knowledge_storage import FileValidationError

VALID_PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\ncontenido de prueba\n%%EOF"


class ValidatePdfTests(unittest.TestCase):
    def test_archivo_valido_no_lanza(self):
        knowledge_storage.validate_pdf(filename="doc.pdf", content_type="application/pdf", data=VALID_PDF)

    def test_extension_invalida(self):
        with self.assertRaises(FileValidationError):
            knowledge_storage.validate_pdf(filename="doc.txt", content_type="application/pdf", data=VALID_PDF)

    def test_sin_extension(self):
        with self.assertRaises(FileValidationError):
            knowledge_storage.validate_pdf(filename="doc", content_type="application/pdf", data=VALID_PDF)

    def test_mime_invalido(self):
        with self.assertRaises(FileValidationError):
            knowledge_storage.validate_pdf(filename="doc.pdf", content_type="text/plain", data=VALID_PDF)

    def test_archivo_vacio(self):
        with self.assertRaises(FileValidationError):
            knowledge_storage.validate_pdf(filename="doc.pdf", content_type="application/pdf", data=b"")

    def test_firma_pdf_ausente(self):
        with self.assertRaises(FileValidationError):
            knowledge_storage.validate_pdf(filename="doc.pdf", content_type="application/pdf", data=b"no es un pdf real")

    def test_excede_tamano_maximo(self):
        with patch.dict("os.environ", {"ALIMENTIA_MAX_KNOWLEDGE_FILE_MB": "1"}):
            data = knowledge_storage.PDF_SIGNATURE + b"0" * (2 * 1024 * 1024)
            with self.assertRaises(FileValidationError):
                knowledge_storage.validate_pdf(filename="doc.pdf", content_type="application/pdf", data=data)

    def test_content_type_ausente_no_bloquea(self):
        """Algunos clientes no envían Content-Type; solo se rechaza si viene
        y es explícitamente incorrecto -nunca se exige-."""
        knowledge_storage.validate_pdf(filename="doc.pdf", content_type=None, data=VALID_PDF)


class SlugifyTests(unittest.TestCase):
    def test_normaliza_acentos_y_espacios(self):
        self.assertEqual(knowledge_storage.slugify("Guía de Alimentos Ñoño"), "guia-de-alimentos-nono")

    def test_cadena_vacia_produce_slug_por_defecto(self):
        self.assertEqual(knowledge_storage.slugify(""), "fuente")

    def test_solo_caracteres_especiales_produce_slug_por_defecto(self):
        self.assertEqual(knowledge_storage.slugify("!!!///???"), "fuente")


class FilenameTests(unittest.TestCase):
    def test_generate_stored_filename_incluye_slug_y_es_unico(self):
        a = knowledge_storage.generate_stored_filename("mi-guia")
        b = knowledge_storage.generate_stored_filename("mi-guia")
        self.assertTrue(a.startswith("mi-guia__"))
        self.assertTrue(a.endswith(".pdf"))
        self.assertNotEqual(a, b)

    def test_sanitize_display_filename_quita_ruta_y_caracteres_de_control(self):
        self.assertEqual(knowledge_storage.sanitize_display_filename("../../etc/passwd.pdf"), "passwd.pdf")
        self.assertEqual(knowledge_storage.sanitize_display_filename('mal"formado.pdf'), "malformado.pdf")

    def test_sanitize_display_filename_vacio_usa_valor_por_defecto(self):
        self.assertEqual(knowledge_storage.sanitize_display_filename(""), "documento.pdf")


class ResolveStoredPathTests(unittest.TestCase):
    def test_path_traversal_es_rechazado(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict("os.environ", {"ALIMENTIA_KNOWLEDGE_PATH": tmp}):
                with self.assertRaises(FileValidationError):
                    knowledge_storage.resolve_stored_path("../fuera-del-directorio.pdf")
                with self.assertRaises(FileValidationError):
                    knowledge_storage.resolve_stored_path("../../etc/passwd")

    def test_ruta_dentro_del_directorio_autorizado_se_acepta(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict("os.environ", {"ALIMENTIA_KNOWLEDGE_PATH": tmp}):
                resolved = knowledge_storage.resolve_stored_path("documento.pdf")
        self.assertEqual(resolved, (Path(tmp) / "documento.pdf").resolve())

    def test_save_y_delete_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict("os.environ", {"ALIMENTIA_KNOWLEDGE_PATH": tmp}):
                path = knowledge_storage.save_file("archivo__abc123.pdf", VALID_PDF)
                self.assertTrue(path.exists())
                self.assertEqual(path.read_bytes(), VALID_PDF)
                knowledge_storage.delete_file("archivo__abc123.pdf")
                self.assertFalse(path.exists())

    def test_delete_file_inexistente_no_lanza(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict("os.environ", {"ALIMENTIA_KNOWLEDGE_PATH": tmp}):
                knowledge_storage.delete_file("no-existe.pdf")

    def test_delete_file_none_no_lanza(self):
        knowledge_storage.delete_file(None)


if __name__ == "__main__":
    unittest.main()
