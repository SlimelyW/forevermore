"""Güncellendi rozeti (ayar rev), oyun favorisi ve başlatma hedefi. Sahte sistem; gerçek bilgisayara dokunmaz."""

import copy
import tempfile
import unittest
from pathlib import Path

from app.core import settings
from app.engine.backup import BackupStore
from app.games import profiles
from tests.test_motor import EngineTestBase, make_tweak, reg_step


class TestRev(EngineTestBase):
    def test_no_rev_no_badge(self):
        tweak = make_tweak([reg_step()])
        self.assertTrue(self.engine.set_enabled(tweak, True).ok)
        self.assertNotIn("rev", self.engine.store.get("TEST-001"))
        self.assertFalse(self.engine.needs_update(tweak))

    def test_old_record_without_rev_no_false_alarm(self):
        tweak = make_tweak([reg_step()])
        self.assertTrue(self.engine.set_enabled(tweak, True).ok)  # kayıt rev'siz
        tweak["rev"] = 2                                          # katalog sonradan rev aldı
        self.assertFalse(self.engine.needs_update(tweak))

    def test_stamped_then_catalog_newer_then_reapply(self):
        tweak = make_tweak([reg_step()], rev=1)
        self.assertTrue(self.engine.set_enabled(tweak, True).ok)
        self.assertEqual(self.engine.store.get("TEST-001")["rev"], 1)
        self.assertFalse(self.engine.needs_update(tweak))
        newer = copy.deepcopy(tweak)
        newer["rev"] = 2
        newer["islem"]["adimlar"].append(reg_step("Yeni", path=r"Software\Test2"))
        self.assertTrue(self.engine.needs_update(newer))
        self.assertIsNone(self.sys.read_reg("HKCU", r"Software\Test2", "Yeni"))  # kendiliğinden uygulanmadı
        self.assertTrue(self.engine.set_enabled(newer, True).ok)                 # kullanıcı yeniden uygular
        self.assertFalse(self.engine.needs_update(newer))
        self.assertEqual(self.sys.read_reg("HKCU", r"Software\Test2", "Yeni"), (1, "REG_DWORD"))
        self.assertTrue(self.engine.revert("TEST-001").ok)                        # yeni adım da geri alınır
        self.assertIsNone(self.sys.read_reg("HKCU", r"Software\Test2", "Yeni"))
        self.assertIsNone(self.sys.read_reg("HKCU", r"Software\Test", "Deger"))

    def test_rev_survives_reload(self):
        tweak = make_tweak([reg_step()], rev=3)
        self.engine.set_enabled(tweak, True)
        self.assertEqual(BackupStore(Path(self.tmp.name)).get("TEST-001")["rev"], 3)


class TestGameLaunchAndFavorites(unittest.TestCase):
    def test_launch_target(self):
        self.assertEqual(profiles.launch_target({"baslat": "steam://rungameid/730", "exe": None}), "steam://rungameid/730")
        epic = "com.epicgames.launcher://apps/Foo?action=launch&silent=true"
        self.assertEqual(profiles.launch_target({"baslat": epic}), epic)
        # elle bozulmuş dosya: başka kalıp kabul edilmez, exe yoksa hedef yok
        self.assertIsNone(profiles.launch_target({"baslat": "calc.exe", "exe": r"C:\yok\x.exe"}))
        self.assertIsNone(profiles.launch_target({"baslat": "steam://rungameid/1 & calc"}))
        with tempfile.NamedTemporaryFile(suffix=".exe") as f:
            self.assertEqual(profiles.launch_target({"baslat": "ms-settings:", "exe": f.name}), f.name)

    def test_launch_rediscovers_missing_shortcut(self):
        """A7: kısayolu kaydedilmemiş eski oyun, Steam/Epic dosyalarından yeniden bulunur; benzer adlı klasör eşleşmez."""
        from unittest import mock
        from app.games import discovery
        steam = [{"klasor": r"C:\Steam\steamapps\common\Oyun", "baslat": "steam://rungameid/42"}]
        with tempfile.NamedTemporaryFile(suffix=".exe") as f, \
                mock.patch.object(discovery, "_steam", return_value=steam), \
                mock.patch.object(discovery, "_epic", return_value=[]):
            inside = {"exe": r"C:\Steam\steamapps\common\Oyun\bin\oyun.exe"}
            self.assertEqual(profiles.launch_target(inside, rediscover=True), "steam://rungameid/42")
            self.assertIsNone(profiles.launch_target(inside))  # sayfa kurulurken disk taranmaz
            self.assertEqual(profiles.launch_target({"exe": f.name}, rediscover=True), f.name)  # bulunamadı: exe
            other = {"klasor": r"C:\Steam\steamapps\common\Oyun2", "exe": None}
            self.assertIsNone(profiles.launch_target(other, rediscover=True))

    def test_store_keeps_launcher_shortcut(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = profiles.GameStore(Path(tmp) / "oyunlar.json")
            game = store.add("Oyun", tmp, "Steam", None, "steam://rungameid/10")
            self.assertEqual(profiles.GameStore(Path(tmp) / "oyunlar.json").get(game["id"])["baslat"],
                             "steam://rungameid/10")

    def test_favorites_setting_default_empty(self):
        self.assertEqual(settings.DEFAULTS["favori_oyunlar"], [])


if __name__ == "__main__":
    unittest.main()
