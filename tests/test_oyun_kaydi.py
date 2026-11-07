"""Oyun oturumu kaydı testleri (sahte sampler; gerçek sayaç ya da dosya klasörü kullanılmaz).

Çalıştırma: py -3.12 -m unittest tests.test_oyun_kaydi -v
"""

import json
import tempfile
import threading
import unittest
from pathlib import Path

from app.games import recorder

GIB = 2 ** 30


def sample(cpu, ram_used_gib, gpu=40.0, top=()):
    return {"cpu": cpu, "gpu": gpu, "disk": 5.0, "ram_toplam": 16 * GIB, "ram_kullanilan": ram_used_gib * GIB,
            "en_cok": [{"ad": n, "cpu": c, "bellek_mb": 100} for n, c in top]}


class TestStats(unittest.TestCase):
    def test_summary_numbers_and_thresholds(self):
        stats = recorder.SessionStats("Oyun.exe", interval=5.0)
        for cpu, ram in ((10, 8), (50, 12), (95, 15), (100, 15.5)):
            stats.add(sample(cpu, ram, top=[("oyun", 60), ("chrome", 20), ("forevermore", 30), ("discord", 0.2)]))
        summary = stats.summary(20.4)
        self.assertEqual(summary["cpu"], {"min": 10.0, "ort": 63.8, "maks": 100.0})
        self.assertEqual(summary["ram"]["maks"], 96.9)
        self.assertEqual((summary["sure"], summary["ornek"]), (20, 4))
        self.assertEqual((summary["cpu_yuksek_sn"], summary["ram_yuksek_sn"]), (10, 10))  # 2 örnek x 5 sn
        self.assertEqual(summary["arka_plan"], [{"ad": "chrome", "cpu": 20.0}])  # oyunun kendisi, uygulamamız ve <%1 hariç
        self.assertNotIn("fps", " ".join(summary).lower())

    def test_missing_values_are_skipped_not_zeroed(self):
        stats = recorder.SessionStats()
        stats.add({"cpu": None, "gpu": None, "ram_toplam": None, "ram_kullanilan": None})
        summary = stats.summary(5)
        self.assertEqual((summary["cpu"], summary["gpu"], summary["ram"]), (None, None, None))
        self.assertEqual(summary["arka_plan"], [])

    def test_memory_use_does_not_grow_with_samples(self):
        stats = recorder.SessionStats()
        for i in range(5000):
            stats.add(sample(i % 100, 8, top=[("chrome", 5)]))
        self.assertEqual(len(stats.process_cpu), 1)
        self.assertEqual(stats.samples, 5000)


class FakeSampler:
    def __init__(self):
        self.calls, self.closed = 0, threading.Event()

    def sample(self):
        self.calls += 1
        return sample(50, 8)

    def close(self):
        self.closed.set()


class TestRecorder(unittest.TestCase):
    def test_thread_collects_then_stops_and_closes_sampler(self):
        fake = FakeSampler()
        rec = recorder.SessionRecorder("oyun.exe", factory=lambda: fake, interval=0.01)
        rec.start()
        threading.Event().wait(0.2)
        summary = rec.stop()
        self.assertGreaterEqual(summary["ornek"], 2)
        self.assertTrue(fake.closed.wait(2))
        self.assertFalse(rec._thread.is_alive())  # noqa: SLF001
        calls = fake.calls
        threading.Event().wait(0.05)
        self.assertEqual(fake.calls, calls)  # durduktan sonra örnek alınmaz

    def test_failing_sampler_does_not_raise(self):
        class Broken(FakeSampler):
            def sample(self):
                raise OSError("sayaç yok")

        rec = recorder.SessionRecorder(factory=Broken, interval=0.01)
        rec.start()
        self.assertEqual(rec.stop()["ornek"], 0)

        def no_factory():
            raise OSError("başlatılamadı")

        rec = recorder.SessionRecorder(factory=no_factory, interval=0.01)
        rec.start()
        self.assertEqual(rec.stop()["ornek"], 0)


class TestHistory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "g.json"
        self.game = {"id": "G1", "ad": "Oyun"}

    def tearDown(self):
        self.tmp.cleanup()

    def test_keeps_last_ten_and_finds_latest_for_game(self):
        for i in range(13):
            recorder.add_history(self.game, {"sure": i, "ornek": 3}, f"2026-11-05T10:00:{i:02d}", self.path)
        recorder.add_history({"id": "G2", "ad": "Başka"}, {"sure": 99, "ornek": 3}, "2026-11-05T11:00:00", self.path)
        entries = recorder.load_history(self.path)
        self.assertEqual(len(entries), 10)
        self.assertEqual(recorder.latest_for("G1", self.path)["sure"], 12)
        self.assertIsNone(recorder.latest_for("YOK", self.path))

    def test_corrupt_or_wrong_type_file_gives_empty_history_and_recovers(self):
        self.path.write_bytes(bytes(100))
        self.assertEqual(recorder.load_history(self.path), [])
        self.path.write_text(json.dumps({"x": 1}), encoding="utf-8")
        self.assertEqual(recorder.load_history(self.path), [])
        recorder.add_history(self.game, {"sure": 1, "ornek": 2}, "t", self.path)
        self.assertEqual(len(recorder.load_history(self.path)), 1)

    def test_history_holds_only_numbers_names_and_dates(self):
        stats = recorder.SessionStats("oyun")
        stats.add(sample(50, 8, top=[("chrome", 10)]))
        recorder.add_history(self.game, stats.summary(5), "2026-11-05T10:00:00", self.path)
        entry = recorder.load_history(self.path)[0]
        self.assertEqual(set(entry), {"sure", "ornek", "cpu_yuksek_sn", "ram_yuksek_sn", "arka_plan", "cpu", "gpu", "ram",
                                      "disk", "oyun", "oyun_id", "tarih"})


if __name__ == "__main__":
    unittest.main()
