"""Tarayıcı eklentisi okuma: sahte profil klasörleriyle (gerçek tarayıcıya dokunulmaz)."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.scan import browser_ext


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


class TestBrowserExtensions(unittest.TestCase):
    def test_chromium_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp, "Default")
            ext = profile / "Extensions"
            _write(ext / "aaa" / "1.0_0" / "manifest.json",
                   {"name": "__MSG_appName__", "default_locale": "en", "version": "1.0", "manifest_version": 3,
                    "host_permissions": ["<all_urls>"], "background": {"service_worker": "b.js"}})
            _write(ext / "aaa" / "1.0_0" / "_locales" / "en" / "messages.json", {"appName": {"message": "Reklam Engel"}})
            _write(ext / "bbb" / "2.0_0" / "manifest.json", {"name": "Kapalı", "version": "2.0", "manifest_version": 3})
            _write(ext / "ccc" / "1.0_0" / "manifest.json", {"name": "Tema", "theme": {}, "version": "1"})
            _write(ext / "ddd" / "1.0_0" / "manifest.json", {"name": "PDF", "version": "1", "manifest_version": 3})
            _write(profile / "Secure Preferences", {"extensions": {"settings": {
                "bbb": {"location": 1, "disable_reasons": 1}, "ddd": {"location": 5}}}})
            result = browser_ext._chromium_profile(profile)
        by_id = {e["id"]: e for e in result}
        self.assertEqual(sorted(by_id), ["aaa", "bbb"])  # tema ve Chrome bileşeni atlandı
        self.assertEqual(by_id["aaa"]["ad"], "Reklam Engel")
        self.assertTrue(by_id["aaa"]["etkin"] and by_id["aaa"]["tum_siteler"] and by_id["aaa"]["arka_plan"])
        self.assertFalse(by_id["bbb"]["etkin"])
        self.assertFalse(by_id["bbb"]["tum_siteler"])

    def test_firefox_only_user_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(Path(tmp, "Mozilla", "Firefox", "Profiles", "abc.default-release", "extensions.json"), {"addons": [
                {"id": "u@x", "type": "extension", "location": "app-profile", "active": True,
                 "defaultLocale": {"name": "uBlock"}, "userPermissions": {"origins": ["<all_urls>"]}},
                {"id": "sys@x", "type": "extension", "location": "app-builtin", "active": True},
                {"id": "t@x", "type": "theme", "location": "app-profile", "active": True}]})
            with mock.patch.dict("os.environ", {"APPDATA": tmp}):
                result = browser_ext._firefox()
        self.assertEqual(len(result), 1)
        self.assertEqual([e["ad"] for e in result[0]["eklentiler"]], ["uBlock"])
        self.assertTrue(result[0]["eklentiler"][0]["tum_siteler"])

    def test_missing_browsers_give_empty_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict("os.environ", {"LOCALAPPDATA": tmp, "APPDATA": tmp}):
                self.assertEqual(browser_ext.collect(), [])


class TestPlainLabel(unittest.TestCase):
    def test_third_party_text_is_not_rendered_as_html(self):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
        from app.ui import widgets as w
        app = QApplication.instance() or QApplication([])  # noqa: F841
        self.assertEqual(w.label("<b>Reklam</b>", plain=True).textFormat(), Qt.TextFormat.PlainText)
        self.assertNotEqual(w.label("<b>Reklam</b>").textFormat(), Qt.TextFormat.PlainText)


if __name__ == "__main__":
    unittest.main()
