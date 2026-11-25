"""Haftalık temizlik ölçümü testleri: gerçek Görev Zamanlayıcı ve gerçek klasörler kullanılmaz.

Çalıştırma: py -3.12 -m unittest tests.test_temizlik_olcum -v
"""

import datetime
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.core import temizlik_olcum


class TestOlcum(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "olcum.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_measure_writes_only_totals(self):
        def scan():
            return [{"id": "gizli_kimlik", "boyut": 100, "adet": 2, "calisiyor": False},
                    {"id": "b", "boyut": 0, "adet": 0, "calisiyor": False}]
        done = temizlik_olcum.measure_and_save(self.path, scan, datetime.datetime(2026, 11, 8, 20, 0))
        self.assertEqual(done, {"tarih": "2026-11-08T20:00", "boyut": 100, "adet": 2})
        self.assertEqual(temizlik_olcum.last(self.path), done)
        self.assertNotIn("gizli_kimlik", self.path.read_text(encoding="utf-8"))  # yol/kimlik yazılmaz

    def test_last_is_none_when_missing_or_corrupt(self):
        self.assertIsNone(temizlik_olcum.last(self.path))
        for bad in ("{", "[]", '{"tarih": "x", "boyut": 1, "adet": 1}',
                    '{"tarih": "2026-11-08T20:00", "boyut": "a", "adet": 1}'):
            self.path.write_text(bad, encoding="utf-8")
            self.assertIsNone(temizlik_olcum.last(self.path), bad)

    def test_task_is_weekly_limited_and_never_elevated(self):
        with mock.patch.object(temizlik_olcum.powershell, "run") as run:
            temizlik_olcum.enable()
        command = run.call_args.args[0]
        self.assertIn("-Weekly", command)
        self.assertIn("-RunLevel Limited", command)
        self.assertNotIn("Highest", command)
        self.assertIn("--temizlik-olc", command)


if __name__ == "__main__":
    unittest.main()
