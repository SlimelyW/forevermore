import json
import unittest

from app.core import paths
from app.engine import skor


class SkorTesti(unittest.TestCase):
    def test_oran_ve_asagi_yuvarlama(self):
        self.assertEqual(skor.skor(28, 80), (35, 28, 80))
        self.assertEqual(skor.skor(2, 3), (66, 2, 3))      # 66,6 → 66: abartılmaz
        self.assertEqual(skor.skor(79, 80)[0], 98)         # 98,75 → 98; 100 yalnızca hepsi açıkken
        self.assertEqual(skor.skor(80, 80)[0], 100)
        self.assertEqual(skor.skor(0, 5)[0], 0)

    def test_payda_sifirsa_halka_yok(self):
        self.assertIsNone(skor.skor(0, 0))

    def test_oyun_kimlikleri_temel_profili_katar_isaretsizi_almaz(self):
        profil_listesi = json.loads((paths.data_dir() / "profiller.json").read_text(encoding="utf-8"))["profiller"]
        ids = skor.oyun_kimlikleri(profil_listesi)
        self.assertIn("PERF-001", ids)       # "guvenli" temel profilinden
        self.assertIn("INP-002", ids)        # "oyun" profilinin kendisi
        self.assertNotIn("DISP-002", ids)    # secili: false
        self.assertNotIn("SYS-002", ids)     # "dikkatli" profili oyun profiline dahil değil


if __name__ == "__main__":
    unittest.main()
