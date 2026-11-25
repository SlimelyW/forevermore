"""Canlı süreç listesi (C8) testleri: sahte sayaç ve sahte pencere listesi. Gerçek PDH/oyun/ağ/sistem ayarı yok.

Çalıştırma: py -3.12 -m unittest tests.test_canli_surec -v
"""

import threading
import unittest

from app.core import i18n
from app.games import canli_surec
from app.games.canli_surec import LiveProcesses, build


class FakeSource:
    def __init__(self, rows, windowed):
        self._rows, self._windowed, self.closed = rows, windowed, False

    def rows(self):
        return self._rows

    def windowed(self):
        return self._windowed

    def close(self):
        self.closed = True


class TestBuild(unittest.TestCase):
    def setUp(self):
        i18n.load("tr")

    def test_cpu_is_divided_by_core_count_and_same_names_are_summed(self):
        out = build([("svchost", 40.0), ("svchost#1", 40.0), ("svchost#2", 80.0)], set(), 8)
        self.assertEqual(out["arka_plan"]["toplam"], 20.0)  # 160 / 8
        self.assertEqual(out["arka_plan"]["liste"], [{"ad": "Windows hizmetleri", "cpu": 20.0}])  # tek satır, sade ad

    def test_groups_by_window(self):
        rows = [("chrome", 80.0), ("discord", 40.0), ("msmpeng", 120.0)]
        out = build(rows, {"chrome", "discord"}, 4)
        self.assertEqual([p["ad"] for p in out["uygulamalar"]["liste"]], ["Google Chrome", "Discord"])
        self.assertEqual(out["uygulamalar"]["toplam"], 30.0)
        self.assertEqual(out["arka_plan"]["liste"], [{"ad": "Windows Defender taraması", "cpu": 30.0}])

    def test_game_forevermore_and_totals_are_left_out(self):
        rows = [("Oyun", 300.0), ("_Total", 400.0), ("Idle", 900.0), ("forevermore", 50.0), ("python", 50.0), ("steam", 40.0)]
        out = build(rows, set(), 4, game="Oyun.exe")
        self.assertEqual([p["ad"] for p in out["arka_plan"]["liste"]], ["Steam"])
        self.assertEqual(out["arka_plan"]["toplam"], 10.0)
        self.assertEqual(out["uygulamalar"], {"toplam": 0.0, "liste": []})

    def test_only_top_five_and_tiny_values_dropped(self):
        rows = [(f"p{i}", 10.0 * (i + 1)) for i in range(8)] + [("sessiz", 0.2)]
        out = build(rows, set(), 1)
        names = [p["ad"] for p in out["arka_plan"]["liste"]]
        self.assertEqual(names, ["p7", "p6", "p5", "p4", "p3"])
        self.assertNotIn("sessiz", names)

    def test_unknown_name_stays_raw_and_total_is_capped(self):
        out = build([("benimprogram", 900.0)], set(), 1)
        self.assertEqual(out["arka_plan"]["liste"], [{"ad": "benimprogram", "cpu": 100.0}])
        self.assertEqual(out["arka_plan"]["toplam"], 100.0)

    def test_friendly_names_follow_language_and_dictionary_has_30(self):
        i18n.load("en")
        try:
            self.assertEqual(canli_surec.friendly("svchost#3"), "Windows services")
            self.assertEqual(canli_surec.friendly("Chrome"), "Google Chrome")
        finally:
            i18n.load("tr")
        self.assertGreaterEqual(len(canli_surec._names), 30)


class TestThread(unittest.TestCase):
    def test_runs_only_between_start_and_stop_and_closes_source(self):
        sources = []

        def factory():
            sources.append(FakeSource([("chrome", 50.0)], {"chrome"}))
            return sources[-1]

        live = LiveProcesses("oyun.exe", source=factory, interval=0.01, cpu_count=2)
        self.assertIsNone(live.snapshot())
        live.start()
        deadline = threading.Event()
        for _ in range(200):
            if live.snapshot() is not None:
                break
            deadline.wait(0.01)
        self.assertEqual(live.snapshot()["uygulamalar"]["toplam"], 25.0)
        live.stop()
        self.assertFalse(live.running)
        self.assertTrue(sources[0].closed)
        self.assertIsNone(live.snapshot())  # eski veri kalmaz

    def test_source_failure_stops_thread_quietly(self):
        def broken():
            raise OSError("sayaç yok")

        live = LiveProcesses(source=broken, interval=0.01)
        with self.assertLogs("pcopt.canli_surec", "ERROR"):
            live.start()
            live._thread.join(timeout=3)
        self.assertFalse(live.running)
        self.assertIsNone(live.snapshot())
        live.stop()


if __name__ == "__main__":
    unittest.main()
