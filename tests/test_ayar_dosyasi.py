"""Denetim A B6: bozuk uygulama_ayarlari.json açılışı çöktürmemeli, varsayılanlara dönülmeli."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.core import settings


class BozukAyarDosyasi(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.file = Path(tmp.name) / "uygulama_ayarlari.json"
        patch = mock.patch.object(settings, "_path", return_value=self.file)
        patch.start()
        self.addCleanup(patch.stop)
        settings.reset_cache()
        self.addCleanup(settings.reset_cache)

    def test_invalid_contents_fall_back_to_defaults(self):
        for content in ("null", "[]", "[1, 2]", '"metin"', "42", "{bozuk"):
            with self.subTest(content=content):
                self.file.write_text(content, encoding="utf-8")
                settings.reset_cache()
                self.assertEqual(settings.get("dil"), settings.DEFAULTS["dil"])

    def test_valid_file_still_read(self):
        self.file.write_text('{"fps_widget": true, "bilinmeyen": 1}', encoding="utf-8")
        self.assertIs(settings.get("fps_widget"), True)
        self.assertNotIn("bilinmeyen", settings.load())


if __name__ == "__main__":
    unittest.main()
