"""Ekran kartı belleği (SALT OKUMA): sahte sayaç ve sahte DXGI; gerçek sistem sorgulanmaz.

Çalıştırma: py -3.12 -m unittest tests.test_vram -v
"""

import types
import unittest
from unittest import mock

from app.scan import hardware, live

GB = 2 ** 30


class TestVramUsed(unittest.TestCase):
    ITEMS = [("luid_0x00000000_0x0001E894_phys_0", 1.0 * GB), ("luid_0x00000000_0x0001B630_phys_0", 5.0 * GB)]

    def test_matches_adapter_by_luid(self):
        self.assertEqual(live.vram_used(self.ITEMS, "000000000001B630"), 5.0 * GB)
        self.assertEqual(live.vram_used(self.ITEMS, "000000000001E894"), 1.0 * GB)

    def test_no_match_is_none_not_zero(self):
        self.assertIsNone(live.vram_used(self.ITEMS, "00000000000FFFFF"))
        self.assertIsNone(live.vram_used([], "000000000001B630"))

    def test_main_adapter_prefers_high_performance(self):
        adapters = [{"luid": "A", "vram_mb": 512, "yuksek_performans": False},
                    {"luid": "B", "vram_mb": 8192, "yuksek_performans": True}]
        with mock.patch("app.scan.gpus.dxgi_adapters", return_value=adapters):
            self.assertEqual(live.main_adapter(), ("B", 8192 * 2 ** 20))
        with mock.patch("app.scan.gpus.dxgi_adapters", return_value=[]):
            self.assertEqual(live.main_adapter(), (None, None))


class TestVramReader(unittest.TestCase):
    def reader(self, items, luid="000000000000000B", total=8 * GB):
        query = mock.Mock()
        query.add.return_value = True
        query.collect.return_value = True
        query.array.return_value = items
        with mock.patch.object(live, "PdhQuery", return_value=query), \
                mock.patch.object(live, "main_adapter", return_value=(luid, total)):
            return live.VramReader()

    def test_read_returns_used_and_total(self):
        r = self.reader([("luid_0x0_0xB_phys_0", 3.0 * GB)])
        self.assertEqual(r.read(), (3.0 * GB, 8 * GB))

    def test_unreadable_adapter_gives_none(self):
        self.assertIsNone(self.reader([], luid=None).read())
        self.assertIsNone(self.reader([("luid_0x0_0xC_phys_0", 1.0)]).read())


class TestVramWarning(unittest.TestCase):
    def check(self, used, total):
        from app.ui.app import MainWindow
        reader = types.SimpleNamespace(read=lambda: (used, total))
        return MainWindow.vram_dolu(types.SimpleNamespace(vram_reader=reader))

    def test_threshold_is_above_ninety_percent(self):
        gb = 2 ** 30
        self.assertIsNone(self.check(7.2 * gb, 8 * gb))  # %90 tam
        self.assertEqual(self.check(7.3 * gb, 8 * gb), 91)
        self.assertEqual(self.check(8 * gb, 8 * gb), 100)

    def test_unreadable_or_off_gives_none(self):
        from app.ui.app import MainWindow
        self.assertIsNone(MainWindow.vram_dolu(types.SimpleNamespace(vram_reader=None)))
        self.assertIsNone(self.check(5, 0))
        self.assertIsNone(self.check(511 * 2 ** 20, 512 * 2 ** 20))  # tümleşik kart (512 MB ayrılmış): uyarı yok
        broken = types.SimpleNamespace(read=mock.Mock(side_effect=OSError))
        self.assertIsNone(MainWindow.vram_dolu(types.SimpleNamespace(vram_reader=broken)))

    def test_default_off(self):
        from app.core import settings
        self.assertIs(settings.DEFAULTS["vram_uyari"], False)


class TestNvidiaSmi(unittest.TestCase):
    def test_row_has_no_power_limit(self):
        """Güç sınırı aynı kartta 83/79/77 W gibi değişti, gerçek sınır olmayabilir: hiç okunmaz."""
        out = b"NVIDIA GeForce RTX 5070 Laptop GPU, 621.01, 8151, 43, P2\n"
        proc = types.SimpleNamespace(returncode=0, stdout=out)
        with mock.patch.object(hardware.subprocess, "run", return_value=proc) as run, \
                mock.patch.object(hardware, "_nvidia_bar1", return_value=[8192]):
            rows = hardware._nvidia_smi()
        self.assertNotIn("power", " ".join(run.call_args.args[0]))
        self.assertEqual(rows[0]["guc_durumu"], "P2")
        self.assertNotIn("guc_siniri_w", rows[0])
        self.assertEqual(rows[0]["bar1_mb"], 8192)


if __name__ == "__main__":
    unittest.main()
