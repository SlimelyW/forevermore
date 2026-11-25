"""Kullanıcı presetleri testleri (yalnızca ayar kimlikleri; içe aktarma güvenilmeyen girdi sayılır).

Çalıştırma: py -3.12 -m unittest tests.test_kullanici_presetleri -v
"""

import json
import tempfile
import unittest
from pathlib import Path

from app.engine import user_presets as up

ROOT = Path(__file__).resolve().parent.parent
TWEAKS = json.loads((ROOT / "data" / "tweaks_app.json").read_text(encoding="utf-8"))["ayarlar"]
BY_ID = {t["id"]: t for t in TWEAKS}
GOOD = [t["id"] for t in TWEAKS if up.usable(t)][:6]
PLACEBO = next(t["id"] for t in TWEAKS if t["gerceklik"]["durum"] == "placebo" and t["sinif"] == "SWITCH")
NOT_SWITCH = next(t["id"] for t in TWEAKS if t["sinif"] != "SWITCH")


def payload(**kw):
    data = {"uygulama": up.MARKER, "surum": up.VERSION, "ad": "Benim", "ayarlar": GOOD[:3]}
    data.update(kw)
    return json.dumps(data).encode("utf-8")


class TestUserPresets(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "p.json"
        self.store = up.PresetStore(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def code(self, func, *args):
        with self.assertRaises(up.PresetError) as ctx:
            func(*args)
        return ctx.exception.code

    def test_usable_rejects_placebo_harmful_forbidden_and_non_switch(self):
        self.assertTrue(len(GOOD) == 6)
        self.assertFalse(up.usable(BY_ID[PLACEBO]))
        self.assertFalse(up.usable(BY_ID[NOT_SWITCH]))
        for tid in up.FORBIDDEN_IDS & set(BY_ID):
            self.assertFalse(up.usable(BY_ID[tid]), tid)
        self.assertFalse(any(BY_ID[i]["gerceklik"]["durum"] in up.REJECTED_REALITY for i in GOOD))

    def test_name_is_cleaned(self):
        self.assertEqual(up.clean_name("  Oyun   <b>ses</b>\x00\u202e "), "Oyun bses/b")
        self.assertEqual(len(up.clean_name("x" * 200)), up.MAX_NAME)
        self.assertEqual(up.clean_name(None), "")
        self.assertEqual(up.clean_name("Oyun & Ses"), "Oyun & Ses")

    def test_add_keeps_only_known_usable_ids_and_reports_dropped(self):
        preset, dropped = self.store.add("Deneme", GOOD[:2] + [PLACEBO, NOT_SWITCH, "YOK-999", 5, None, "../x", GOOD[0]], BY_ID)
        self.assertEqual(preset["ayarlar"], GOOD[:2])
        self.assertEqual(dropped, 7)
        self.assertEqual(self.code(self.store.add, "Hiç", [PLACEBO, "YOK-999"], BY_ID), "bos")
        self.assertEqual(self.code(self.store.add, "   ", GOOD, BY_ID), "ad_bos")
        self.assertEqual(self.code(self.store.add, "Düz", "PERF-001", BY_ID), "gecersiz")

    def test_duplicate_names_get_a_number_and_limits_hold(self):
        names = [self.store.add("Aynı", GOOD[:1], BY_ID)[0]["ad"] for _ in range(3)]
        self.assertEqual(names, ["Aynı", "Aynı (2)", "Aynı (3)"])
        for i in range(up.MAX_PRESETS - 3):
            self.store.add(f"p{i}", GOOD[:1], BY_ID)
        self.assertEqual(self.code(self.store.add, "fazla", GOOD[:1], BY_ID), "cok_fazla")
        self.assertEqual(self.code(self.store.add, "x", [GOOD[0]] * 1, BY_ID), "cok_fazla")

    def test_persistence_rename_and_remove(self):
        preset, _ = self.store.add("Kalıcı", GOOD[:3], BY_ID)
        self.assertEqual(up.PresetStore(self.path).get(preset["id"])["ayarlar"], GOOD[:3])
        self.store.rename(preset["id"], "Yeni ad")
        self.assertEqual(up.PresetStore(self.path).get(preset["id"])["ad"], "Yeni ad")
        self.assertEqual(self.code(self.store.rename, preset["id"], "<>"), "ad_bos")
        self.store.remove(preset["id"])
        self.assertEqual(up.PresetStore(self.path).presets, [])

    def test_corrupt_file_gives_empty_list_and_reports(self):
        self.path.write_bytes(bytes(300))
        store = up.PresetStore(self.path)
        self.assertEqual((store.presets, store.load_error), ([], "bozuk"))
        self.path.write_text(json.dumps({"presetler": [{"id": "k", "ad": "<>", "ayarlar": ["A-1"]}, "x", None]}), encoding="utf-8")
        self.assertEqual(up.PresetStore(self.path).presets, [])  # adı boşalan ve bozuk kayıtlar atlanır

    def test_file_holds_only_ids_no_values_or_commands(self):
        self.store.add("Sade", GOOD, BY_ID)
        text = self.path.read_text(encoding="utf-8")
        for word in ("HKLM", "HKCU", "reg add", "powershell", "komut", "deger"):
            self.assertNotIn(word.lower(), text.lower())
        self.assertEqual(set(json.loads(text)["presetler"][0]), {"id", "ad", "ayarlar"})

    def test_export_import_roundtrip(self):
        preset, _ = self.store.add("Gidiş dönüş", GOOD[:4], BY_ID)
        exported = self.store.export_text(preset["id"]).encode("utf-8")
        other = up.PresetStore(Path(self.tmp.name) / "diger.json")
        imported, dropped = other.import_bytes(exported, BY_ID)
        self.assertEqual((imported["ad"], imported["ayarlar"], dropped), ("Gidiş dönüş", GOOD[:4], 0))
        self.assertNotEqual(imported["id"], preset["id"])  # kimlik dosyadan alınmaz

    def test_import_rejects_hostile_or_broken_files(self):
        imp = lambda raw: self.code(self.store.import_bytes, raw, BY_ID)  # noqa: E731
        self.assertEqual(imp(b"not json"), "gecersiz")
        self.assertEqual(imp(b"\xff\xfe\x00"), "gecersiz")
        self.assertEqual(imp(b"[]"), "gecersiz")
        self.assertEqual(imp(payload(uygulama="Baska")), "gecersiz")
        self.assertEqual(imp(payload(surum=2)), "gecersiz")
        self.assertEqual(imp(payload(ad=5)), "gecersiz")
        self.assertEqual(imp(payload(ayarlar="PERF-001")), "gecersiz")
        self.assertEqual(imp(payload(ayarlar={"PERF-001": 1})), "gecersiz")
        self.assertEqual(imp(payload(ayarlar=GOOD * 200)), "gecersiz")  # çok fazla kimlik
        self.assertEqual(imp(payload(ayarlar=["YOK-001"] * 5)), "bos")
        self.assertEqual(imp(b" " * (up.MAX_BYTES + 1)), "buyuk")
        self.assertEqual(imp(b"[" * 60000), "gecersiz")  # aşırı iç içe: çökmez
        self.assertEqual(self.store.presets, [])  # hiçbiri eklenmedi

    def test_import_drops_unsafe_ids_and_sanitizes_name(self):
        preset, dropped = self.store.import_bytes(payload(ad="<script>x</script>\u202e", ayarlar=[GOOD[0], PLACEBO, "x; rm", NOT_SWITCH]), BY_ID)
        self.assertEqual(preset["ayarlar"], [GOOD[0]])
        self.assertEqual(dropped, 3)
        self.assertNotIn("<", preset["ad"])
        self.assertNotIn("\u202e", preset["ad"])


if __name__ == "__main__":
    unittest.main()
