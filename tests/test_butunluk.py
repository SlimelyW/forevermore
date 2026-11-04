"""Paket imzası (Ed25519) ve bütünlük denetimi."""

import json
import tempfile
import unittest
from pathlib import Path

from app.core import ed25519, integrity


class TestEd25519(unittest.TestCase):
    def test_rfc8032_vector_1(self):
        secret = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
        public = ed25519.public_key(secret)
        self.assertEqual(public.hex(), "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
        signature = ed25519.sign(secret, b"")
        self.assertEqual(signature.hex(), "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33b"
                                          "acc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")
        self.assertTrue(ed25519.verify(public, b"", signature))
        self.assertFalse(ed25519.verify(public, b"x", signature))
        broken = bytes([signature[0] ^ 1]) + signature[1:]
        self.assertFalse(ed25519.verify(public, b"", broken))

    def test_embedded_public_key_is_valid(self):
        self.assertEqual(len(bytes.fromhex(integrity.PUBLIC_KEY_HEX)), 32)
        self.assertRegex(integrity.fingerprint(), r"^[0-9A-F]{4}(-[0-9A-F]{4}){3}$")


class TestIntegrity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "_internal" / "data").mkdir(parents=True)
        (self.root / "Forevermore.exe").write_bytes(b"exe")
        (self.root / "_internal" / "data" / "hakkinda.json").write_text('{"yapimci": "Kubilay"}', encoding="utf-8")
        self.secret = bytes(range(32))
        self.public = ed25519.public_key(self.secret).hex()
        self._sign()

    def tearDown(self):
        self.tmp.cleanup()

    def _sign(self, secret=None):
        manifest = integrity.build_manifest(self.root, "2.0.0")
        signature = ed25519.sign(secret or self.secret, integrity.canonical(manifest)).hex()
        (self.root / "_internal" / "imza.json").write_text(json.dumps({"manifest": manifest, "imza": signature}),
                                                          encoding="utf-8")

    def check(self):
        return integrity.check_folder(self.root, self.public)

    def test_original(self):
        result = self.check()
        self.assertEqual(result["durum"], "orijinal")
        self.assertEqual(result["surum"], "2.0.0")

    def test_changed_author_file_is_detected(self):
        (self.root / "_internal" / "data" / "hakkinda.json").write_text('{"yapimci": "Baskasi"}', encoding="utf-8")
        result = self.check()
        self.assertEqual(result["durum"], "bozuk")  # imza geçerli, dosya farklı: bozulma da değiştirme de olabilir
        self.assertEqual(result["degisen"], ["_internal/data/hakkinda.json"])

    def test_override_folder_beside_exe_is_detected(self):
        (self.root / "data").mkdir()
        (self.root / "data" / "hakkinda.json").write_text('{"yapimci": "Baskasi"}', encoding="utf-8")
        result = self.check()
        self.assertEqual(result["durum"], "degistirilmis")
        self.assertEqual(result["eklenen"], ["data/hakkinda.json"])

    def test_missing_file_is_detected(self):
        (self.root / "Forevermore.exe").unlink()
        self.assertEqual(self.check()["eksik"], ["Forevermore.exe"])
        self.assertEqual(self.check()["durum"], "bozuk")

    def test_explorer_files_are_ignored(self):
        (self.root / "desktop.ini").write_text("[.ShellClassInfo]", encoding="utf-8")
        (self.root / "_internal" / "Thumbs.db").write_bytes(b"x")
        self.assertEqual(self.check()["durum"], "orijinal")

    def test_added_executable_is_still_tampering(self):
        (self.root / "version.dll").write_bytes(b"MZ")
        self.assertEqual(self.check()["durum"], "degistirilmis")

    def test_user_tools_folder_is_ignored(self):
        (self.root / "tools" / "DDU").mkdir(parents=True)
        (self.root / "tools" / "DDU" / "ddu.exe").write_bytes(b"x")
        self.assertEqual(self.check()["durum"], "orijinal")

    def test_resigned_with_other_key_is_rejected(self):
        self._sign(secret=bytes(32))
        result = self.check()
        self.assertEqual(result["durum"], "degistirilmis")
        self.assertEqual(result["degisen"], [integrity.MANIFEST])

    def test_edited_manifest_is_rejected(self):
        path = self.root / "_internal" / "imza.json"
        signed = json.loads(path.read_text(encoding="utf-8"))
        signed["manifest"]["surum"] = "9.9.9"
        path.write_text(json.dumps(signed), encoding="utf-8")
        self.assertEqual(self.check()["durum"], "degistirilmis")

    def test_unsigned(self):
        (self.root / "_internal" / "imza.json").unlink()
        self.assertEqual(self.check()["durum"], "imzasiz")


if __name__ == "__main__":
    unittest.main()
