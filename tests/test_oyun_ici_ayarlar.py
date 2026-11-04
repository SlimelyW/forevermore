"""Oyun içi ayarlar maddeleri: veri biçimi, iki dil, kanıt durumu ve oyun desteği."""
import json
import unittest
from pathlib import Path

from app.games import guides

ROOT = Path(__file__).resolve().parent.parent
KANIT = {"belgeli", "olculmus", "tartismali", "genel"}


class TestIngameItems(unittest.TestCase):
    def test_items_have_both_languages_and_known_evidence(self):
        raw = json.loads((ROOT / "data" / "oyun_ici_ayarlar.json").read_text(encoding="utf-8"))["maddeler"]
        self.assertGreaterEqual(len(raw), 5)
        for item in raw:
            self.assertIn(item["kanit"], KANIT, item["id"])
            for field in ("baslik", "metin"):
                self.assertTrue(item[field]["tr"] and item[field]["en"], (item["id"], field))
            if item["kanit"] in ("belgeli", "olculmus"):
                self.assertTrue(item["kaynak"], f"{item['id']}: belgeli/ölçülmüş madde kaynaksız olamaz")

    def test_language_fallback_and_ids_unique(self):
        tr, en = guides.ingame_items("tr"), guides.ingame_items("en")
        self.assertEqual([i["id"] for i in tr], [i["id"] for i in en])
        self.assertEqual(len({i["id"] for i in tr}), len(tr))
        self.assertNotEqual(tr[0]["metin"], en[0]["metin"])
        self.assertEqual(guides.ingame_items("xx")[0]["metin"], tr[0]["metin"])   # bilinmeyen dil Türkçe'ye döner

    def test_support_is_only_true_or_false_when_verified(self):
        self.assertIn(guides.support("Valorant")["reflex"], (True, False, None))
        self.assertIsNone(guides.support("Böyle Bir Oyun Yok")["reflex"])


if __name__ == "__main__":
    unittest.main()
