"""Veri dosyası kontrolleri. Sistemde hiçbir ayarı DEĞİŞTİRMEZ.

Çalıştırma (proje klasöründe):
    py -3.12 -m unittest tests.test_veri -v
"""

import json
import unittest
from pathlib import Path

from app.engine.resolvers import find_placeholders, substitute
from app.engine.schema import validate_tweak

ROOT = Path(__file__).resolve().parent.parent
APP_DATA = json.loads((ROOT / "data" / "tweaks_app.json").read_text(encoding="utf-8"))
SOURCE = json.loads((ROOT / "tweaks.json").read_text(encoding="utf-8"))
TWEAKS = APP_DATA["ayarlar"]
BY_ID = {t["id"]: t for t in TWEAKS}


class TestAppData(unittest.TestCase):
    def test_all_source_tweaks_present(self):
        self.assertEqual({t["id"] for t in TWEAKS}, {t["id"] for t in SOURCE["ayarlar"]})

    def test_ids_unique(self):
        ids = [t["id"] for t in TWEAKS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_schema_valid(self):
        errors = [e for t in TWEAKS for e in validate_tweak(t)]
        self.assertEqual(errors, [])

    def test_every_fix_points_to_a_usable_switch(self):
        from app.engine import fixes
        for code, spec in fixes.FIXES.items():
            finding = {"kod": code, "ilgili": [spec[1]], "params": {}, "seviye": "uyari"}
            self.assertIsNotNone(fixes.fix_for(finding, BY_ID), code)

    def test_fix_close_requires_every_step_off(self):
        from app.engine import fixes
        from app.engine.engine import TweakState
        fix = {"tur": "kapat", "id": "PLC-006"}
        self.assertFalse(fixes.is_resolved(fix, TweakState("kapali", ["diger"])))
        self.assertTrue(fixes.is_resolved(fix, TweakState("kapali", ["kapali"])))

    def test_forbidden_five_are_never_switches(self):
        for tid in ("PLC-008", "PLC-018", "PLC-020", "PLC-021", "PLC-022"):
            self.assertEqual(BY_ID[tid]["sinif"], "BILGI", tid)
            self.assertNotIn("islem", BY_ID[tid])

    def test_confirmation_levels_follow_risk(self):
        for t in TWEAKS:
            expected = {"dikkatli": 1, "riskli": 2}.get(t["risk"], 0)
            self.assertEqual(t["onay_seviyesi"], expected, t["id"])
            self.assertEqual(t["onay_gerekli"], expected > 0, t["id"])

    def test_info_cards_explain_why(self):
        """Uygulamanın yapamadığı her bilgi kartı nedenini söylemeli."""
        for t in TWEAKS:
            if t["sinif"] == "BILGI":
                self.assertTrue(t["bilgi"]["yapilamaz_nedeni"], t["id"])

    def test_off_only_switches_cannot_turn_on(self):
        for t in TWEAKS:
            if t.get("islem", {}).get("yalnizca_kapat"):
                self.assertIn(t["gerceklik"]["durum"], ("zararlı", "placebo"), t["id"])

    def test_placeholders_substitute_fully(self):
        for t in TWEAKS:
            islem = t.get("islem")
            if not islem:
                continue
            names = find_placeholders(islem)
            fake = {name: "TEST" for name in names}
            self.assertEqual(find_placeholders(substitute(islem, fake)), set(), t["id"])

    def test_every_category_present(self):
        cats = {c["ad"] for c in APP_DATA["kategoriler"]}
        self.assertEqual(cats, {t["kategori"] for t in TWEAKS})

    def test_anti_cheat_warning_carried(self):
        self.assertIn("anti-cheat", APP_DATA["meta"]["anti_cheat_uyarisi"].lower())


if __name__ == "__main__":
    unittest.main()
