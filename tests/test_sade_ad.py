"""sade_ad (kart başlığındaki sade ad) testleri: alan yoksa ham ad görünür; her sade adın İngilizcesi var;
katalogda olmayan kimlik dönüşümde hata verir.

Çalıştırma: py -3.12 -m unittest tests.test_sade_ad -v
"""

import json
import os
import unittest
from collections import defaultdict
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
SADE = json.loads((ROOT / "data" / "sade_adlar.json").read_text(encoding="utf-8"))["ayarlar"]
CATALOG = json.loads((ROOT / "data" / "tweaks_app.json").read_text(encoding="utf-8"))["ayarlar"]
EN = json.loads((ROOT / "data" / "ceviriler" / "en.json").read_text(encoding="utf-8"))["ayarlar"]


class TestSadeAd(unittest.TestCase):
    def test_name_falls_back_to_raw_name_when_no_sade_ad(self):
        from app.core import i18n
        from app.ui.dialogs import display_name
        i18n.load("tr")
        tweak = {"ad": "HAM AD", "gerceklik": {"durum": "gercek"}}
        self.assertEqual(display_name(tweak), "HAM AD")
        self.assertEqual(display_name(dict(tweak, sade_ad="")), "HAM AD")  # boş sade ad da ham adı gösterir
        self.assertEqual(display_name(dict(tweak, sade_ad="Sade ad")), "Sade ad")
        for tw in CATALOG:
            if "sade_ad" not in tw:
                self.assertTrue(display_name(tw).startswith(tw["ad"]), tw["id"])  # sonda "(placebo)" etiketi olabilir

    def test_catalog_has_exactly_the_listed_sade_adlar(self):
        got = {tw["id"]: tw["sade_ad"] for tw in CATALOG if "sade_ad" in tw}
        self.assertEqual(got, SADE)

    def test_every_sade_ad_has_english(self):
        for tid, tr_name in SADE.items():
            self.assertTrue(tr_name.strip(), tid)
            en_name = (EN.get(tid) or {}).get("sade_ad")
            self.assertTrue(isinstance(en_name, str) and en_name.strip(), f"{tid}: data/ceviriler/en.json'da sade_ad yok")

    def test_unknown_id_is_a_conversion_error(self):
        from tools.convert_tweaks import apply_sade_adlar
        report = defaultdict(list)
        tweaks = [{"id": "AAA-001", "ad": "x"}, {"id": "AAA-002", "ad": "y"}]
        apply_sade_adlar(tweaks, {"AAA-001": "Sade", "YOK-999": "Hayalet"}, report)
        self.assertEqual(tweaks[0]["sade_ad"], "Sade")
        self.assertNotIn("sade_ad", tweaks[1])
        self.assertEqual(len(report["hata"]), 1)
        self.assertIn("YOK-999", report["hata"][0])
        clean = defaultdict(list)
        apply_sade_adlar(tweaks, {"AAA-002": "Başka"}, clean)
        self.assertEqual(clean["hata"], [])


if __name__ == "__main__":
    unittest.main()
