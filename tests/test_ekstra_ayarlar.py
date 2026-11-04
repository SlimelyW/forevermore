"""Ekstra ayarlar testleri: içe/dışa aktarma, Windows'la başlatma komutu, Bilgi verisi.

Hiçbir test gerçek Görev Zamanlayıcı'ya yazmaz (PowerShell çağrıları yakalanır).

Çalıştırma (proje klasöründe):
    py -3.12 -m unittest tests.test_ekstra_ayarlar -v
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LOCALAPPDATA"] = os.environ.get("PCOPT_TEST_LOCALAPPDATA") or tempfile.mkdtemp(prefix="pcopt_test_")

from app.core import autostart, i18n, paths, settings  # noqa: E402
from app.games.profiles import GameStore  # noqa: E402


class TestAbout(unittest.TestCase):
    def test_name_then_discord_and_single_donation_setting(self):
        data = json.loads((paths.data_dir() / "hakkinda.json").read_text(encoding="utf-8"))
        self.assertEqual(data["yapimci"], "Kubilay Paşa")
        self.assertEqual([s["deger"] for s in data["satirlar"]], [])
        self.assertEqual([b["url"] for b in data["baglantilar"]],
                         ["https://forevermore.pages.dev/"])
        self.assertEqual(data["bagis_url"], "https://buymeacoffee.com/forevermore")  # tek, küçük bağlantı (Bilgi sayfası)
        self.assertEqual([b["url"] for b in data["faydali"]],       # faydalı bağlantılar Oyunlar sayfasına taşındı
                         ["https://howmanyfps.com/games", "https://beforeiplay.com/wiki/Main_Page"])
        self.assertEqual(data["katkida_bulunanlar"], [])

    def test_old_format_still_read(self):
        from unittest import mock as _mock
        from app.ui import page_settings
        old = {"baslik": "Ad", "iletisim": [{"etiket": "Discord", "deger": "x"}], "baglantilar": []}
        with _mock.patch.object(page_settings.json, "loads", return_value=old):
            data = page_settings.about_data()
        self.assertEqual(data["satirlar"], old["iletisim"])
        self.assertEqual(data["yapimci"], "Ad")


class TestAutostart(unittest.TestCase):
    def test_enable_creates_highest_privilege_logon_task(self):
        with mock.patch.object(autostart.powershell, "run") as run, \
                mock.patch.object(autostart.paths, "in_user_profile", return_value=False):
            autostart.enable()
        command = run.call_args[0][0]
        self.assertIn("-RunLevel Highest", command)
        self.assertIn("-AtLogOn", command)
        self.assertIn("--tepside", command)
        self.assertIn(autostart.TASK_NAME, command)

    def test_enable_refused_when_program_is_in_user_profile(self):
        """Denetim 4: İndirilenler/Masaüstü'ndeki exe'yi herkes değiştirebilir; görev onu UAC sorusuz yönetici yapardı."""
        import os
        from app.core import paths
        self.assertTrue(paths.in_user_profile(os.path.join(os.path.expanduser("~"), "Downloads", "Forevermore")))
        self.assertFalse(paths.in_user_profile(r"C:\Program Files\Forevermore"))
        with mock.patch.object(autostart.powershell, "run") as run, \
                mock.patch.object(autostart.paths, "app_dir",
                                  return_value=Path(os.path.expanduser("~"), "Downloads", "Forevermore")):
            with self.assertRaises(autostart.ProfileFolderError):
                autostart.enable()
        run.assert_not_called()

    def test_disable_unregisters(self):
        with mock.patch.object(autostart.powershell, "run") as run:
            autostart.disable()
        self.assertIn("Unregister-ScheduledTask", run.call_args[0][0])


class TestUninstall(unittest.TestCase):
    def setUp(self):
        from app.engine.backup import BackupStore
        from app.engine.engine import Engine
        from tests.fake_system import FakeResolver, FakeSystem
        from tests.test_motor import DESKTOP
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name) / "veri"
        self.data.mkdir()
        self.sys = FakeSystem()
        self.engine = Engine(system=self.sys, store=BackupStore(self.data / "backups"), profile=DESKTOP,
                             resolver=FakeResolver(), is_admin=lambda: True)
        self.engine.prepare()

    def tearDown(self):
        self.tmp.cleanup()

    def _cleanup(self, **kwargs):
        from app.core import uninstall

        class Session:
            def recover(self):
                return True
        with (mock.patch.object(uninstall.autostart, "is_enabled", return_value=True),
              mock.patch.object(uninstall.autostart, "disable") as disable,
              mock.patch.object(uninstall.paths, "user_data_dir", return_value=self.data),
              mock.patch.object(uninstall.paths, "protected_root", return_value=self.data / "korumali"),
              mock.patch.object(uninstall.logging, "shutdown")):
            report = uninstall.cleanup(self.engine, session=Session(), **kwargs)
        disable.assert_called_once()
        return report

    def _change(self):
        step = {"tur": "yerlesik", "eylem": "baslangic_onayi", "parametreler": {"kok": "HKCU", "yol": "A", "ad": "X"}}
        self.assertTrue(self.engine.apply_custom("BAS-1", "Başlangıç", [step], [False]).ok)

    def test_data_kept_while_changes_remain(self):
        self._change()
        report = self._cleanup(delete_data=True)
        self.assertTrue(report["gorev"] and report["oyun_oturumu"])
        self.assertFalse(report["veri_silindi"])
        self.assertTrue(self.data.exists())
        self.assertIn(("HKCU", "A", "X"), self.sys.approved)  # geri alınmadı

    def test_revert_everything_and_delete_data(self):
        self._change()
        report = self._cleanup(revert_changes=True, delete_data=True)
        self.assertEqual(report["geri_alinan"], 1)
        self.assertEqual(self.sys.approved, {})
        self.assertTrue(report["veri_silindi"])
        self.assertFalse(self.data.exists())


class TestImportExport(unittest.TestCase):
    def setUp(self):
        i18n.load("tr")
        settings.reset_cache()
        self.tmp = tempfile.TemporaryDirectory()
        self.store = GameStore(Path(self.tmp.name) / "oyunlar.json")

    def tearDown(self):
        for key, value in settings.DEFAULTS.items():
            settings.set(key, value)
        self.tmp.cleanup()

    def test_import_skips_unknown_keys_and_anti_cheat(self):
        from app.ui.page_settings import import_settings
        data = {"uygulama": "Forevermore", "uygulama_ayarlari": {"ekstra_bilgi": True, "bilinmeyen": 1},
                "oyunlar": [
                    {"ad": "Oyun", "klasor": r"C:\Oyun", "kaynak": "Steam", "exe": r"C:\Oyun\oyun.exe",
                     "profil": {"oncelik": "High", "guc_plani": True, "kotu_anahtar": 5}},
                    {"ad": "Vanguard", "klasor": r"C:\Riot", "exe": r"C:\Riot\vgc.exe"}]}
        self.assertEqual(import_settings(data, self.store), 1)
        self.assertTrue(settings.get("ekstra_bilgi"))
        self.assertNotIn("bilinmeyen", settings.load())
        profile = self.store.games[0]["profil"]
        self.assertEqual(profile["oncelik"], "High")
        self.assertNotIn("kotu_anahtar", profile)

    def test_import_rejects_other_files(self):
        from app.ui.page_settings import import_settings
        with self.assertRaises(ValueError):
            import_settings({"baska": 1}, self.store)


class TestDefenderAndUac(unittest.TestCase):
    """Defender gerçek zamanlı koruma adımı ve UAC seviyeleri (sahte sistemde)."""

    def setUp(self):
        from app.engine.backup import BackupStore
        from app.engine.engine import Engine
        from tests.fake_system import FakeResolver, FakeSystem
        from tests.test_motor import DESKTOP
        self.tmp = tempfile.TemporaryDirectory()
        self.sys = FakeSystem()
        self.engine = Engine(system=self.sys, store=BackupStore(Path(self.tmp.name) / "backups"), profile=DESKTOP,
                             resolver=FakeResolver(), is_admin=lambda: True)
        self.engine.prepare()

    def tearDown(self):
        self.tmp.cleanup()

    def test_defender_off_and_revert(self):
        from app.engine import defender
        before = self.sys.state_copy()
        result = self.engine.apply_custom(defender.CHANGE_ID, "Defender", [defender.step()], [False], confirmed=True)
        self.assertTrue(result.ok)
        self.assertFalse(self.sys.defender["gercek_zamanli"])
        self.assertTrue(self.engine.revert(defender.CHANGE_ID, confirmed=True).ok)
        self.assertEqual(self.sys.state_copy(), before)

    def test_defender_tamper_protection_is_reported_and_nothing_kept(self):
        from app.engine import defender
        self.sys.defender["kurcalama"] = True
        result = self.engine.apply_custom(defender.CHANGE_ID, "Defender", [defender.step()], [False], confirmed=True)
        self.assertFalse(result.ok)
        self.assertEqual(result.key, "hata.defender_kurcalama")
        self.assertTrue(self.sys.defender["gercek_zamanli"])
        self.assertFalse(self.engine.store.has(defender.CHANGE_ID))

    def test_uac_detect(self):
        from app.engine import uac
        self.assertEqual(uac.detect(self.sys), "varsayilan")
        for level in uac.LEVELS:
            for name, value in zip(uac.NAMES, uac.values(level)):
                self.sys.write_reg("HKLM", uac.PATH, name, value, "REG_DWORD")
            self.assertEqual(uac.detect(self.sys), level)
        self.sys.write_reg("HKLM", uac.PATH, "ConsentPromptBehaviorAdmin", 1, "REG_DWORD")
        self.assertEqual(uac.detect(self.sys), "ozel")
        self.sys.write_reg("HKLM", uac.PATH, "EnableLUA", 0, "REG_DWORD")
        self.assertEqual(uac.detect(self.sys), "kapali")


if __name__ == "__main__":
    unittest.main()
