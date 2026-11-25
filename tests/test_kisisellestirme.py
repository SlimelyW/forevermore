"""Özelleştirmeler: taşınan ayarların kategorisi ve QOL-011..016 yeni kişiselleştirme ayarları.
Gerçek bilgisayara DOKUNMAZ (tests/fake_system.py); ayarların gerçek Windows'ta etkisi DENENMEDİ."""

import json
import unittest

from app.engine import catalog
from tests.test_motor import BY_ID, EngineTestBase

ADV = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
PERS = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"

MOVED = {"QOL-001": "EXP", "QOL-002": "EXP", "QOL-003": "EXP", "QOL-007": "EXP", "QOL-008": "EXP",
         "AUD-001": "SND", "AUD-004": "SND", "AUD-007": "SND", "AUD-009": "SND", "QOL-006": "SND",
         "SYS-011": "QOL", "DISP-006": "QOL"}
STAYED = {"AUD-002": "AUD", "AUD-003": "AUD", "AUD-006": "AUD", "AUD-008": "AUD", "DISP-008": "DISP", "INP-007": "INP"}
# ayar kimliği -> (değerler: (yol, ad, açıkken, kapalıyken), varsayılan yokluğunda kapalı sayılır mı)
NEW = {
    "QOL-011": [(PERS, "AppsUseLightTheme", 0, 1), (PERS, "SystemUsesLightTheme", 0, 1)],
    "QOL-012": [(ADV, "Hidden", 1, 2)],
    "QOL-013": [(ADV, "TaskbarAl", 0, 1)],
    "QOL-014": [(ADV, "LaunchTo", 1, None)],
    "QOL-015": [(ADV, "DisallowShaking", 1, 0)],
    "QOL-016": [(ADV, "AutoCheckSelect", 1, 0)],
}


class TestKatalog(unittest.TestCase):
    def test_moved_settings_in_new_categories(self):
        for tid, cid in {**MOVED, **STAYED}.items():
            self.assertEqual(BY_ID[tid]["kategori_id"], cid, tid)

    def test_new_categories_exist_once(self):
        with open("data/tweaks_app.json", encoding="utf-8") as f:
            ids = [c["id"] for c in json.load(f)["kategoriler"]]
        self.assertEqual(len(ids), len(set(ids)))
        for cid in ("QOL", "EXP", "SND"):
            self.assertIn(cid, ids)
            self.assertTrue(any(t["kategori_id"] == cid for t in BY_ID.values()), cid)

    def test_new_settings_label_their_evidence_and_sources(self):
        for tid in NEW:
            tweak = BY_ID[tid]
            self.assertEqual(tweak["sinif"], "SWITCH", tid)
            self.assertEqual(tweak["risk"], "güvenli", tid)
            self.assertTrue(tweak["gerceklik"]["aciklama"].startswith("Kanıt düzeyi: ikincil kaynak"), tid)
            self.assertTrue(tweak["kaynaklar"] and all(u.startswith("https://") for u in tweak["kaynaklar"]), tid)
            self.assertFalse(tweak["yonetici"], tid)  # yalnızca HKCU: yönetici gerekmez

    def test_new_settings_only_touch_current_user(self):
        for tid in NEW:
            for step in BY_ID[tid]["islem"]["adimlar"]:
                self.assertEqual(step["kok"], "HKCU", tid)

    def test_windows_11_only_taskbar_alignment(self):
        self.assertEqual(BY_ID["QOL-013"]["uyumluluk"]["windows"]["surumler"], ["11"])

    def test_english_layer_complete(self):
        with open("data/tweaks_app.json", encoding="utf-8") as f:
            data = json.load(f)
        with open("data/ceviriler/en.json", encoding="utf-8") as f:
            layer = json.load(f)
        self.assertEqual(catalog.apply_translation(data, layer), 0)  # uygulanamayan girdi yok
        by_id = {t["id"]: t for t in data["ayarlar"]}
        for tid in NEW:
            self.assertNotRegex(by_id[tid]["ad"], r"[ğüşıöçĞÜŞİÖÇ]", tid)
            self.assertTrue(by_id[tid]["gerceklik"]["aciklama"].startswith("Evidence level"), tid)
        cats = {c["id"]: c["aciklama"] for c in data["kategoriler"]}
        self.assertTrue(cats["EXP"].startswith("File Explorer"))
        self.assertTrue(cats["SND"].startswith("Sound"))
        self.assertTrue(cats["PLC"].startswith("Common"))  # kategori sırası değişince Placebo açıklaması kaymadı


class TestYazOkuGeriAl(EngineTestBase):
    def read(self, path, name):
        return self.sys.read_reg("HKCU", path, name)

    def test_apply_then_revert_on_empty_registry(self):
        for tid, values in NEW.items():
            with self.subTest(tid):
                tweak = BY_ID[tid]
                before = self.sys.state_copy()
                self.assertEqual(self.engine.read_state(tweak).status, "kapali")  # değer yokken kapalı
                self.assertTrue(self.engine.set_enabled(tweak, True).ok)
                for path, name, on, _off in values:
                    self.assertEqual(self.read(path, name), (on, "REG_DWORD"))
                self.assertEqual(self.engine.read_state(tweak).status, "acik")
                self.assertTrue(self.engine.set_enabled(tweak, False).ok)
                self.assertEqual(self.sys.reg, before[0])  # yazılan değerler tamamen geri alındı
                self.assertEqual(self.sys.keys, before[1])
                self.assertFalse(self.engine.store.has(tid))

    def test_revert_restores_previous_value(self):
        """Kullanıcının mevcut değeri (ör. TaskbarAl=1 açıkça yazılı) yedekten aynen geri gelir."""
        for tid, values in NEW.items():
            for path, name, _on, off in values:
                self.sys.write_reg("HKCU", path, name, 7 if off is None else off, "REG_DWORD")
        for tid, values in NEW.items():
            with self.subTest(tid):
                tweak = BY_ID[tid]
                self.assertTrue(self.engine.set_enabled(tweak, True).ok)
                for path, name, on, _off in values:
                    self.assertEqual(self.read(path, name)[0], on)
                self.assertTrue(self.engine.set_enabled(tweak, False).ok)
                for path, name, _on, off in values:
                    self.assertEqual(self.read(path, name)[0], 7 if off is None else off)

    def test_state_reads_existing_values(self):
        self.sys.write_reg("HKCU", ADV, "Hidden", 1, "REG_DWORD")
        self.assertEqual(self.engine.read_state(BY_ID["QOL-012"]).status, "acik")
        self.sys.write_reg("HKCU", ADV, "Hidden", 2, "REG_DWORD")
        self.assertEqual(self.engine.read_state(BY_ID["QOL-012"]).status, "kapali")
        self.sys.write_reg("HKCU", ADV, "LaunchTo", 2, "REG_DWORD")  # Hızlı erişim: 'Bu bilgisayar' değil
        self.assertEqual(self.engine.read_state(BY_ID["QOL-014"]).status, "kapali")
        self.sys.write_reg("HKCU", PERS, "AppsUseLightTheme", 0, "REG_DWORD")  # yalnızca uygulamalar koyu
        self.assertEqual(self.engine.read_state(BY_ID["QOL-011"]).status, "kismen")
        self.sys.write_reg("HKCU", PERS, "SystemUsesLightTheme", 0, "REG_DWORD")
        self.assertEqual(self.engine.read_state(BY_ID["QOL-011"]).status, "acik")

    def test_changes_are_recorded(self):
        self.assertTrue(self.engine.set_enabled(BY_ID["QOL-016"], True).ok)
        self.assertTrue(self.engine.store.has("QOL-016"))  # Değişiklikler sayfasında görünür, geri alınabilir

    def test_windows_10_blocks_only_taskbar_alignment(self):
        from app.engine import compat
        win10 = compat.SystemProfile("10", 19045, "masaustu", ["NVIDIA", "AMD", "Intel"], True)
        engine = self.new_engine(profile=win10)
        engine.prepare()
        self.assertFalse(engine.set_enabled(BY_ID["QOL-013"], True).ok)
        self.assertIsNone(self.sys.read_reg("HKCU", ADV, "TaskbarAl"))
        self.assertTrue(engine.set_enabled(BY_ID["QOL-012"], True).ok)


if __name__ == "__main__":
    unittest.main()
