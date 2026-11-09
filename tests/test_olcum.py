"""Önce / Sonra ölçüm testleri (sahte sistem; PresentMon çalıştırılmaz).

Çalıştırma (proje klasöründe):
    py -3.12 -m unittest tests.test_olcum -v
"""

import os
import tempfile
import unittest
from pathlib import Path

from app.core import i18n
from app.measure import MeasurementStore, compare, presentmon, system_measure
from tests.fake_system import FakeSystem


class FakeSampler:
    def __init__(self):
        self.values = iter([10.0, 20.0, 30.0])

    def sample(self):
        return {"cpu": next(self.values), "ram_kullanilan": 8 * 2 ** 30, "surec_sayisi": 200.0}

    def close(self):
        pass


class TestFrameStats(unittest.TestCase):
    def test_lows_use_slowest_frames(self):
        frames = [10.0] * 990 + [50.0] * 10
        stats, details = presentmon.frame_stats(frames)
        self.assertEqual(stats["fps_ort"], round(1000 / 10.4, 1))
        self.assertEqual(stats["fps_1"], 20.0)       # en yavaş %1 = 10 kare, 50 ms
        self.assertEqual(stats["fps_01"], 20.0)
        self.assertEqual(stats["kare_suresi_p99_ms"], 50.0)
        self.assertEqual(details["kare_sayisi"], 1000)

    def test_too_few_frames(self):
        with self.assertRaises(ValueError):
            presentmon.frame_stats([16.6] * 100)

    def test_csv_only_target_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "o.csv")
            with open(path, "w", encoding="utf-8") as f:
                f.write("Application,ProcessID,MsBetweenPresents\n")
                f.write("oyun.exe,1,16.6\nDwm.exe,2,8.3\nOYUN.EXE,1,17.0\nbozuk.exe,3,x\n")
            self.assertEqual(presentmon.read_csv(path, "oyun.exe"), [16.6, 17.0])

    def test_csv_real_presentmon_headers(self):
        """PresentMon 2.6.0'ın gerçek başlıkları (exe içindeki metinden): v1 'msBetweenPresents' küçük m ile."""
        v1 = ("\ufeffApplication,ProcessID,SwapChainAddress,Runtime,SyncInterval,PresentFlags,Dropped,"
              "TimeInSeconds,msInPresentAPI,msBetweenPresents\n")
        v2 = "Application,ProcessID,SwapChainAddress,PresentRuntime,CPUStartDateTime,FrameTime,MsBetweenPresents\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "o.csv")
            with open(path, "w", encoding="utf-8") as f:
                f.write(v1 + "cs2.exe,5,0x1,DXGI,0,0,0,1.5,0.1,6.9\n")
            self.assertEqual(presentmon.read_csv(path, "cs2.exe"), [6.9])
            with open(path, "w", encoding="utf-8") as f:
                f.write(v2 + "cs2.exe,5,0x1,DXGI,2026-10-29 22:04:05.123456789,7.0,6.9\n")
            rows = presentmon.read_rows(path)
            self.assertEqual(rows[0][3], 6.9)
            self.assertEqual(rows[0][2][1].microsecond, 123456)


class TestTimeMapping(unittest.TestCase):
    def test_presentmon_clock_offset_is_ignored(self):
        """Gerçek deneme (30 Eki 2026): PresentMon '4:04:10.46' yazdı, yerel saat 01:04:10 idi (3 saat fark,
        tek haneli saat). Kareler yine ölçüm aralığına doğru düşmeli."""
        import datetime
        header = ("Application,ProcessID,SwapChainAddress,PresentRuntime,SyncInterval,PresentFlags,AllowsTearing,"
                  "PresentMode,TimeInDateTime,MsBetweenSimulationStart,MsBetweenPresents,MsBetweenDisplayChange,"
                  "MsInPresentAPI,MsRenderPresentLatency,MsUntilDisplayed,CPUStartDateTime,MsBetweenAppStart\n")
        rows = ("python.exe,17584,0x1,DXGI,1,0,0,Composed: Flip,2026-10-30 4:04:10.460615300,NA,1.9599,13.9,0.2,5.4,"
                "25.9,2026-10-30 4:04:10.458944200,1.8718\n"
                "python.exe,17584,0x1,DXGI,1,0,0,Composed: Flip,2026-10-30 4:04:20.526368700,NA,6.9529,6.9,0.3,7.4,"
                "20.6,2026-10-30 4:04:20.519779300,6.96\n")
        started = datetime.datetime(2026, 10, 30, 1, 4, 10, 200000).timestamp()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "o.csv")
            with open(path, "w", encoding="utf-8") as f:
                f.write(header + rows)
            parsed = presentmon.read_rows(path)
        first, last = presentmon.to_epoch(parsed, started, started + 10.5)
        self.assertAlmostEqual(first - started, 0.259, delta=0.01)
        self.assertAlmostEqual(last - started, 10.32, delta=0.01)
        self.assertEqual(parsed[0][3], 1.9599)


class FakeDesktop:
    """Oyun (PID 10) yalnızca belirli saniyelerde ön planda."""

    def __init__(self, clock, foreground_at):
        self.clock, self.foreground_at = clock, foreground_at

    def processes(self):
        return [(10, "oyun.exe"), (2, "dwm.exe")]

    def foreground(self):
        return 10 if self.foreground_at(self.clock.now - self.clock.start) else 99


class FakeClock:
    def __init__(self):
        self.start = self.now = 1_800_000_000.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class FakeProc:
    def poll(self):
        return None

    def wait(self, timeout=None):
        return 0


class TestCapture(unittest.TestCase):
    def run_capture(self, rows, foreground_at=lambda s: True, seconds=5,
                    header="Application,ProcessID,CPUStartTime,MsBetweenPresents"):
        clock = FakeClock()
        launched = []

        def launch(args):
            launched.append(args)
            with open(args[args.index("--output_file") + 1], "w", encoding="utf-8") as f:
                f.write(header + "\n" + "".join(rows))
            clock.start = clock.now  # ölçüm başı: zaman sütunu buna göre
            return FakeProc()

        result = presentmon.capture("Oyun.exe", seconds, exe="yok/PresentMon.exe", countdown=2,
                                    desktop=FakeDesktop(clock, foreground_at), launch=launch,
                                    sleep=clock.sleep, clock=clock)
        self.assertIn("--process_name", launched[0])
        self.assertNotIn("--v1_metrics", launched[0])
        return result

    def test_only_foreground_frames_count(self):
        frames = [f"oyun.exe,10,{i / 100:.2f},10\n" for i in range(1000)]          # 0-10 sn, 100 FPS
        frames += [f"oyun.exe,10,{2 + i / 1000:.3f},1\n" for i in range(500)]       # arka planda gelen kareler
        stats, details = self.run_capture(frames, lambda s: 0 <= s < 1.5 or 2.5 <= s < 6)
        self.assertEqual(stats["fps_ort"], 100.0)  # 2-2,5 sn arasındaki 1 ms'lik kareler sayılmadı
        self.assertAlmostEqual(details["sure_sn"], 5.0, delta=0.3)

    def test_reasons(self):
        cases = {"yakalama": [], "surec": [f"dwm.exe,2,{i / 60:.3f},16.6\n" for i in range(400)],
                 "on_plan": [f"oyun.exe,10,{i / 100:.2f},10\n" for i in range(600)]}
        for reason, rows in cases.items():
            with self.subTest(reason=reason):
                fg = (lambda s: s < 0.5 or s > 20) if reason == "on_plan" else (lambda s: True)
                with self.assertRaises(presentmon.MeasureError) as caught:
                    self.run_capture(rows, fg)
                self.assertEqual(str(caught.exception), "az_kare")
                self.assertEqual(caught.exception.diag["neden"], reason)
                self.assertIn("kare_hedef", presentmon.diagnosis_text(caught.exception.diag))

    def test_parse_problem_is_not_called_capture_problem(self):
        """2.6: CSV'de kare satırı var ama sütunlar tanınmıyorsa 'ayristirma' (eski sürümdeki msBetweenPresents hatası)."""
        rows = [f"oyun.exe,10,{i / 100:.2f},10\n" for i in range(600)]
        with self.assertRaises(presentmon.MeasureError) as caught:
            self.run_capture(rows, header="Application,ProcessID,CPUStartTime,BilinmeyenSutun")
        self.assertEqual(caught.exception.diag["neden"], "ayristirma")
        self.assertEqual(caught.exception.diag["kare_csv_satir"], 600)

    def test_diag_counts_filtered_frames_and_exclusive_fullscreen(self):
        rows = [f"oyun.exe,10,{i / 100:.2f},10,Hardware: Legacy Flip\n" for i in range(600)]
        with self.assertRaises(presentmon.MeasureError) as caught:
            self.run_capture(rows, lambda s: s < 0.5 or s > 20,
                             header="Application,ProcessID,CPUStartTime,MsBetweenPresents,PresentMode")
        diag = caught.exception.diag
        self.assertEqual(diag["kare_hedef"], 600)
        self.assertEqual(diag["kare_elenen_on_plan"], 600 - diag["kare_on_planda"])
        self.assertEqual(diag["kare_pid"], {"10": 600})
        self.assertTrue(diag["ozel_tam_ekran"])
        self.assertIn("Hardware: Legacy Flip (600)", presentmon.diagnosis_text(diag))
        self.assertTrue(any("ön planda değil" in line and "PID 99" in line for line in diag["log"]))

    def test_short_foreground_time_is_not_saved(self):
        """Gerçek deneme: bekleme süresi dolunca 10 sn yerine 3 sn ön plan vardı ve sonuç yine kaydediliyordu."""
        frames = [f"oyun.exe,10,{i / 100:.2f},10\n" for i in range(30000)]  # 300 sn boyunca 100 FPS
        with self.assertRaises(presentmon.MeasureError) as caught:
            self.run_capture(frames, lambda s: 1 <= s < 4)  # yalnızca 3 sn ön planda
        self.assertEqual(caught.exception.diag["neden"], "on_plan")

    def test_candidates_put_foreground_and_games_first(self):
        class Desk:
            def processes(self):
                return [(1, "notepad.exe"), (2, "cs2.exe"), (3, "explorer.exe"), (os.getpid(), "forevermore.exe")]

            def windows(self):
                return {1: "Not Defteri", 2: "Counter-Strike 2", 3: "", os.getpid(): "Forevermore"}

            def foreground(self):
                return 1

        games = [{"ad": "Counter-Strike 2", "exe": r"C:\\cs2\\cs2.exe"}, {"ad": "DMC5", "exe": r"D:\\DevilMayCry5.exe"}]
        found = presentmon.candidates(games, Desk())
        self.assertEqual([i["exe"] for i in found], ["notepad.exe", "cs2.exe", "devilmaycry5.exe"])
        self.assertTrue(found[0]["on_planda"])
        self.assertEqual(found[1]["oyun"], "Counter-Strike 2")
        self.assertFalse(found[2]["calisiyor"])


class TestCompare(unittest.TestCase):
    def test_direction(self):
        before = {"degerler": {"fps_ort": 100.0, "bosta_cpu": 5.0}}
        after = {"degerler": {"fps_ort": 110.0, "bosta_cpu": 6.0, "fps_1": 50.0}}
        rows = {r[0]: r for r in compare(before, after)}
        self.assertTrue(rows["fps_ort"][5])          # FPS arttı: daha iyi
        self.assertFalse(rows["bosta_cpu"][5])       # CPU arttı: daha kötü
        self.assertAlmostEqual(rows["fps_ort"][4], 10.0)
        self.assertNotIn("fps_1", rows)              # yalnızca ikisinde de olanlar


class TestSystemMeasure(unittest.TestCase):
    def test_measure_with_fake_system(self):
        system = FakeSystem()
        system.services["Foo"] = {"baslangic": "Automatic", "calisiyor": True}
        system.services["Bar"] = {"baslangic": "Disabled", "calisiyor": False}
        seen = []
        values, details = system_measure.measure(system, FakeSampler, seconds=3,
                                                 progress=lambda d, n: seen.append(d), sleep=lambda _s: None)
        self.assertEqual(values["acilis_sn"], 24.5)
        self.assertEqual(values["baslangic_uygulama"], 1)
        self.assertEqual(values["otomatik_servis"], 1)
        self.assertEqual(values["calisan_servis"], 1)
        self.assertEqual(values["bosta_cpu"], 20.0)
        self.assertEqual(details["bosta_cpu_en_yuksek"], 30.0)
        self.assertEqual(seen, [1, 2, 3])


class TestStoreAndReport(unittest.TestCase):
    def test_store_and_report(self):
        i18n.load("tr")
        with tempfile.TemporaryDirectory() as tmp:
            store = MeasurementStore(Path(tmp) / "olcumler.json")
            a = store.add("oyun", "once", {"fps_ort": 100.0, "fps_1": 60.0})
            b = store.add("oyun", "sonra", {"fps_ort": 104.0, "fps_1": 70.0})
            again = MeasurementStore(store.path)
            self.assertEqual(len(again.items), 2)
            from app.ui.page_measure import report_text
            text = report_text(a, b)
            self.assertIn("Ortalama FPS", text)
            self.assertIn("+4.0%", text)
            self.assertIn("Tek ölçüm kesin kanıt değildir", text)
            store.remove(a["id"])
            self.assertEqual([m["id"] for m in MeasurementStore(store.path).items], [b["id"]])

    def test_garbage_file_gives_empty_list(self):
        """Denetim B B3: null / [] / "x" / öğesi sözlük olmayan dosya Ölçüm sayfasını çökertmez."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "olcumler.json"
            for text in ("null", "[]", "\"x\"", "{bozuk", '{"olcumler": null}'):
                path.write_text(text, encoding="utf-8")
                self.assertEqual(MeasurementStore(path).items, [], text)
            path.write_text('{"olcumler": [1, {"id": "a"}]}', encoding="utf-8")
            self.assertEqual([m["id"] for m in MeasurementStore(path).items], ["a"])

    def test_measure_refuses_registered_anti_cheat_game(self):
        """Denetim B B2: kayıtlı anti-cheat'li oyunda PresentMon başlatılmaz (canlı FPS ile aynı ETW yöntemi)."""
        from app.ui.page_measure import anti_cheat_game
        games = [{"exe": r"C:\Oyun\TFD.exe", "ad": "TFD", "anti_cheat": ["Nexon BlackCipher"]},
                 {"exe": r"C:\Oyun	emiz.exe", "ad": "Temiz", "anti_cheat": []}]
        self.assertTrue(anti_cheat_game(games, "tfd.exe"))
        self.assertFalse(anti_cheat_game(games, "temiz.exe"))
        self.assertFalse(anti_cheat_game(games, "bilinmeyen.exe"))


if __name__ == "__main__":
    unittest.main()
