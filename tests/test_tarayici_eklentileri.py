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


class TestManageLaunch(unittest.TestCase):
    """'Tarayıcıda kaldır': yalnızca yönetim sayfasını açan komut; hiçbir şey silinmez/yazılmaz."""
    ID = "a" * 32

    def test_chrome_and_edge_open_extension_page_in_its_profile(self):
        self.assertEqual(browser_ext.manage_launch("Chrome", "Profile 2", self.ID),
                         ("chrome.exe", f'--profile-directory="Profile 2" chrome://extensions/?id={self.ID}'))
        self.assertEqual(browser_ext.manage_launch("Edge", "Default", self.ID),
                         ("msedge.exe", f'--profile-directory="Default" edge://extensions/?id={self.ID}'))

    def test_launch_never_carries_a_web_address(self):
        """Düğme internete/mağazaya çıkmaz: yalnızca tarayıcının yerel (chrome:// edge:// about:) sayfaları."""
        for browser, profile, ext_id in (("Chrome", "Default", self.ID), ("Edge", "Profile 1", self.ID), ("Firefox", "x", "u@x")):
            program, arguments = browser_ext.manage_launch(browser, profile, ext_id)
            self.assertNotIn("http", arguments.lower())
            self.assertRegex(arguments, r"(chrome://|edge://|about:)")

    def test_firefox_opens_general_addons_page(self):
        self.assertEqual(browser_ext.manage_launch("Firefox", "default-release", "u@x"), ("firefox.exe", "about:addons"))

    def test_other_browsers_and_bad_ids_give_no_command(self):
        self.assertIsNone(browser_ext.manage_launch("Brave", "Default", self.ID))
        self.assertIsNone(browser_ext.manage_launch("Chrome", "Default", "abc"))
        self.assertIsNone(browser_ext.manage_launch("Chrome", "Default", self.ID[:-1] + '" --x'))
        self.assertEqual(browser_ext.manage_launch("Chrome", 'x" --y', self.ID)[1], f"chrome://extensions/?id={self.ID}")  # bozuk profil adı eklenmez

    def test_button_opens_page_only_and_failure_is_a_quiet_status_line(self):
        import os
        import types
        from PySide6.QtWidgets import QApplication, QPushButton
        from app.core import i18n
        from app.ui import page_details
        i18n.load("tr")
        app = QApplication.instance() or QApplication([])  # noqa: F841
        status = []
        page = types.SimpleNamespace(app=types.SimpleNamespace(set_status=lambda text, tone: status.append((text, tone))))
        group = {"tarayici": "Chrome", "profil": "Default"}
        ext = {"id": self.ID, "ad": "Reklam Engel", "etkin": True, "tum_siteler": True}
        row = page_details.PcDetailsPage._extension_row(page, group, ext)
        button = row.findChild(QPushButton)
        self.assertIsNotNone(button)
        page._open_manage = lambda *a: page_details.PcDetailsPage._open_manage(page, *a)
        with mock.patch.object(os, "startfile") as start:
            button.click()
        start.assert_called_once_with("chrome.exe", arguments=f'--profile-directory="Default" chrome://extensions/?id={self.ID}')
        self.assertEqual(status, [])
        with mock.patch.object(os, "startfile", side_effect=OSError):
            button.click()
        self.assertEqual(len(status), 1)  # tarayıcı açılamadı: pencere yok, tek satır
        brave = page_details.PcDetailsPage._extension_row(page, {"tarayici": "Brave", "profil": "Default"}, ext)
        self.assertEqual(brave.findChildren(QPushButton), [])  # Brave/Vivaldi/Opera: düğme yok


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
