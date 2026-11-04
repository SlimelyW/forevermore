"""Depo denetimi (31 Ekim 2026) ve yayın öncesi güvenlik denetimi (4 Kasım 2026) düzeltmelerinin testleri."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.core import powershell
from app.engine import uninstaller
from app.engine.backup import BackupStore
from app.engine.engine import Engine
from tests.fake_system import FakeResolver, FakeSystem
from tests.test_motor import DESKTOP, make_tweak, reg_step


class TestTempCleanupJunction(unittest.TestCase):
    def test_junction_target_outside_folder_is_not_deleted(self):
        """os.walk bağlantı klasörüne (junction) girer; yönetici olarak TEMP temizlenirken dışarıdaki dosya silinmemeli."""
        from app.engine.system import WindowsSystem
        with tempfile.TemporaryDirectory() as tmp:
            temp, target = Path(tmp, "temp"), Path(tmp, "hedef")
            temp.mkdir()
            target.mkdir()
            (target / "onemli.txt").write_text("x")
            (temp / "gecici.txt").write_text("y")
            made = subprocess.run(["cmd", "/c", "mklink", "/J", str(temp / "baglanti"), str(target)],
                                  capture_output=True, creationflags=powershell.CREATE_NO_WINDOW)
            if made.returncode != 0:
                self.skipTest("junction oluşturulamadı")
            count, _size = WindowsSystem.__new__(WindowsSystem).delete_temp_files(str(temp))
            self.assertTrue((target / "onemli.txt").exists())
            self.assertFalse((temp / "gecici.txt").exists())
            self.assertEqual(count, 1)


class TestRollbackKeepsBackup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sys = FakeSystem()
        self.engine = Engine(system=self.sys, store=BackupStore(Path(self.tmp.name)), profile=DESKTOP,
                             resolver=FakeResolver(), is_admin=lambda: True)
        self.engine.prepare()

    def tearDown(self):
        self.tmp.cleanup()

    def test_failed_rollback_keeps_backup(self):
        """A yazıldı, B reddedildi, A'yı geri almak da başarısız: A sistemde kaldığı için yedek silinmemeli."""
        tweak = make_tweak([reg_step("A"), {"tur": "servis", "ad": "Svc",
                                            "acik": {"baslangic": "Disabled", "calisiyor": False},
                                            "kapali": {"baslangic": "Automatic", "calisiyor": True}}])
        self.sys.fail_on |= {"set_service", "delete_reg_value"}
        self.assertFalse(self.engine.set_enabled(tweak, True).ok)
        self.assertEqual(self.sys.read_reg("HKCU", r"Software\Test", "A")[0], 1)  # geri alınamadı
        self.assertTrue(self.engine.store.has("TEST-001"))
        self.sys.fail_on.clear()
        self.assertTrue(self.engine.revert("TEST-001").ok)  # kullanıcı yine geri alabilir
        self.assertIsNone(self.sys.read_reg("HKCU", r"Software\Test", "A"))

    def test_successful_rollback_still_drops_backup(self):
        tweak = make_tweak([reg_step("A"), {"tur": "servis", "ad": "Svc",
                                            "acik": {"baslangic": "Disabled", "calisiyor": False},
                                            "kapali": {"baslangic": "Automatic", "calisiyor": True}}])
        self.sys.fail_on.add("set_service")
        self.assertFalse(self.engine.set_enabled(tweak, True).ok)
        self.assertFalse(self.engine.store.has("TEST-001"))

    def test_half_applied_step_is_restored(self):
        """sc config tamam, Stop-Service hata: yarıda kalan adım da geri alınmalı."""
        tweak = make_tweak([{"tur": "servis", "ad": "Svc", "acik": {"baslangic": "Disabled", "calisiyor": False},
                             "kapali": {"baslangic": "Automatic", "calisiyor": True}}])
        original = self.sys.set_service

        def half(name, start_type, running):
            original(name, start_type, running)
            self.sys.set_service = original
            raise PermissionError("Stop-Service")

        self.sys.set_service = half
        self.assertFalse(self.engine.set_enabled(tweak, True).ok)
        self.assertEqual(self.sys.get_service("Svc")["baslangic"], "Automatic")
        self.assertFalse(self.engine.store.has("TEST-001"))


class TestFeatureQuery(unittest.TestCase):
    def test_each_feature_is_asked_alone(self):
        """-FeatureName tek metin alır; 'a','b' vermek her zaman hata (PERF-004 hiç görünmüyordu)."""
        from app.engine import resolvers
        from app.engine.system import WindowsSystem
        seen = []
        with mock.patch.object(powershell, "run_json", lambda cmd, **_k: seen.append(cmd) or []):
            resolvers._features_present.cache_clear()
            resolvers._features_present(("VirtualMachinePlatform", "Microsoft-Hyper-V-All"))
            WindowsSystem.__new__(WindowsSystem).get_features(["VirtualMachinePlatform", "Microsoft-Hyper-V-All"])
        resolvers._features_present.cache_clear()
        for cmd in seen:
            self.assertIn("-FeatureName $_", cmd)
            self.assertNotIn("-FeatureName '", cmd)


class TestGuvenlikDenetimi(unittest.TestCase):
    def test_quote_doubles_every_powershell_quote(self):
        self.assertEqual(powershell.quote("a\u2019b'c\u2018d"), "'a\u2019\u2019b''c\u2018\u2018d'")

    def test_child_gets_no_user_module_path(self):
        with mock.patch("subprocess.run") as run:
            run.return_value = mock.Mock(returncode=0, stdout=b"", stderr=b"")
            powershell.run("Get-Date")
        self.assertEqual(run.call_args[1]["env"]["PSModulePath"], powershell._MODULE_PATH)

    def test_restore_stays_inside_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            session = base / "20261101-120000"
            session.mkdir()
            outside = base / "disarida.txt"
            outside.write_text("x", encoding="utf-8")
            target = base / "hedef.txt"
            manifest = {"program": "P", "tarih": "2026-11-01T12:00:00",
                        "ogeler": [{"tur": "klasor", "yol": str(target), "yedek": "..\\disarida.txt"}]}
            (session / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            result = uninstaller.restore(session.name, base, mock.Mock())
            self.assertEqual(result["geri_yuklenen"], 0)
            self.assertTrue(outside.exists())
            self.assertFalse(target.exists())

    def test_restore_rejects_dotdot_backup_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            session = base / "20261101-120000"
            session.mkdir()
            target = base / "hedef"
            manifest = {"program": "P", "tarih": "2026-11-01T12:00:00",
                        "ogeler": [{"tur": "klasor", "yol": str(target), "yedek": ".."}]}
            (session / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            self.assertEqual(uninstaller.restore(session.name, base, mock.Mock())["geri_yuklenen"], 0)
            self.assertFalse(target.exists())

    def test_restore_rejects_bad_session_name(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            uninstaller.restore("..\\baska", tmp, mock.Mock())


if __name__ == "__main__":
    unittest.main()
