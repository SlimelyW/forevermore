"""Canlı FPS testleri: sahte PresentMon, sahte masaüstü, sahte saat. Gerçek PresentMon çalışmaz, ağ ya da sistem ayarı yok.

Çalıştırma: py -3.12 -m unittest tests.test_canli_fps -v
"""

import unittest

from app.games import recorder
from app.measure import live_fps
from app.measure.live_fps import DropDetector, LiveFps, SecondBinner


def feed(detector, values):
    return [detector.add(v) for v in values]


class TestBinner(unittest.TestCase):
    def test_one_second_of_frames_gives_fps(self):
        binner = SecondBinner()
        out = [binner.add(10.0) for _ in range(100)]  # 100 kare x 10 ms = 1 sn
        self.assertEqual([x for x in out if x is not None], [100.0])

    def test_bursty_delivery_does_not_change_result(self):
        binner = SecondBinner()
        out = [binner.add(16.0) for _ in range(63)]  # 63 x 16 ms = 1008 ms
        fps = [x for x in out if x is not None]
        self.assertEqual(len(fps), 1)
        self.assertAlmostEqual(fps[0], 62.5, places=1)

    def test_bad_values_are_ignored(self):
        binner = SecondBinner()
        self.assertIsNone(binner.add(0))
        self.assertIsNone(binner.add(-3))
        self.assertIsNone(binner.add(None))
        self.assertEqual((binner.total, binner.count), (0.0, 0))


class TestDropDetector(unittest.TestCase):
    def test_no_alarm_during_first_30_seconds(self):
        det = DropDetector()
        feed(det, [100] * 10 + [10] * 15)  # ısınma bitmeden büyük düşüş
        self.assertIsNone(det.alarm)

    def test_four_seconds_low_is_not_a_drop_five_is(self):
        det = DropDetector()
        feed(det, [100] * 30)
        feed(det, [50] * 4)  # 50 < 60: ama 4 sn
        self.assertIsNone(det.alarm)
        det.add(100)
        feed(det, [50] * 5)
        self.assertIsNotNone(det.alarm)
        self.assertEqual(det.alarm["onceki_fps"], 100)

    def test_ratio_is_relative_to_baseline_not_refresh_rate(self):
        det = DropDetector()
        feed(det, [60] * 30)           # 144 Hz ekranda 60 FPS sınırı: normal, uyarı yok
        feed(det, [58] * 20)
        self.assertIsNone(det.alarm)
        feed(det, [33] * 5)            # 60 taban, %60 = 36: altı düşüş
        self.assertEqual(det.alarm["en_dusuk_fps"], 33)

    def test_exactly_at_threshold_is_not_a_drop(self):
        det = DropDetector()
        feed(det, [100] * 30)
        feed(det, [60] * 10)           # tam %60: "altına" inmedi
        self.assertIsNone(det.alarm)

    def test_recovery_closes_record_with_duration(self):
        det = DropDetector()
        feed(det, [100] * 30)
        feed(det, [40] * 7)
        record = det.add(95)
        self.assertEqual((record["sure_sn"], record["onceki_fps"], record["en_dusuk_fps"]), (7, 100, 40))
        self.assertIsNone(det.alarm)
        self.assertEqual(record["sn"], 31 + 0)  # düşüşün ilk saniyesi (odaktaki 31. sn)

    def test_drop_seconds_do_not_lower_baseline(self):
        det = DropDetector()
        feed(det, [100] * 30)
        feed(det, [40] * 8)
        det.add(100)
        feed(det, [40] * 5)            # ikinci düşüş de yakalanır (taban 100'de kaldı)
        self.assertIsNotNone(det.alarm)

    def test_long_drop_becomes_new_normal_without_repeat_alarm(self):
        det = DropDetector()
        feed(det, [100] * 30)
        records = [r for r in feed(det, [30] * 40) if r]
        self.assertEqual(len(records), 1)
        self.assertGreaterEqual(records[0]["sure_sn"], 30)
        self.assertIsNone(det.alarm)
        feed(det, [30] * 10)           # yeni taban 30
        self.assertIsNone(det.alarm)

    def test_pause_closes_open_drop_and_keeps_baseline(self):
        det = DropDetector()
        feed(det, [100] * 30)
        feed(det, [20] * 6)
        record = det.pause()
        self.assertEqual(record["sure_sn"], 6)
        self.assertIsNone(det.alarm)
        self.assertEqual(det.baseline(), 100)
        self.assertIsNone(det.pause())


class FakeProc:
    def __init__(self, lines=(), code=None):
        self.stdout = list(lines)
        self.code = code
        self.terminated = False

    def poll(self):
        return self.code

    def terminate(self):
        self.terminated = True
        self.code = 1

    def wait(self, timeout=None):
        return self.code

    def kill(self):
        self.terminated = True


class FakeDesktop:
    def __init__(self):
        self.pid, self.foreground_pid = 100, 100

    def processes(self):
        return [(self.pid, "oyun.exe"), (7, "other.exe")]

    def foreground(self):
        return self.foreground_pid


class Harness:
    """Saati ve döngüyü elle ilerletir: her wait() 1 sn geçirir ve verilen eylemi çalıştırır."""

    def __init__(self, actions):
        self.now, self.tick, self.actions = 0.0, 0, actions
        self.procs, self.fps, self.drops = [], [], []
        self.desktop = FakeDesktop()
        self.live = LiveFps("OYUN.exe", exe="presentmon.exe", on_second=self.fps.append, on_drop=self.drops.append,
                            desktop=self.desktop, launch=self.launch, clock=lambda: self.now, wait=self.wait)

    def launch(self, args):
        proc = FakeProc(code=self.next_code)
        proc.args = args
        self.procs.append(proc)
        return proc

    next_code = None

    def wait(self, _seconds):
        self.now += 1.0
        if self.tick < len(self.actions):
            self.actions[self.tick](self)
        self.tick += 1
        if self.tick > len(self.actions):
            self.live._stop.set()
        return self.live._stop.is_set()

    def run(self):
        self.live.exe = "presentmon.exe"
        self.live._loop()
        self.live._end()


class TestLiveFps(unittest.TestCase):
    def test_arguments_target_game_only_and_use_stdout(self):
        h = Harness([lambda s: None] * 2)
        h.run()
        args = h.procs[0].args
        self.assertEqual(args[0], "presentmon.exe")
        self.assertIn("--output_stdout", args)
        self.assertEqual(args[args.index("--process_name") + 1], "oyun.exe")
        self.assertEqual(args[args.index("--session_name") + 1], live_fps.SESSION)
        self.assertNotIn("--output_file", args)  # kare dosyası yazılmaz

    def test_pauses_when_game_loses_focus_and_resumes(self):
        def away(s):
            s.desktop.foreground_pid = 999

        def back(s):
            s.desktop.foreground_pid = 100

        h = Harness([lambda s: None] + [away] + [lambda s: None] * 4 + [back] + [lambda s: None] * 2)
        h.run()
        self.assertEqual(len(h.procs), 2)          # odak dönünce yeniden başladı
        self.assertTrue(h.procs[0].terminated)     # odak kaybında (kısa bekleme sonrası) durduruldu
        self.assertEqual(h.live.snapshot()["fps"], None)

    def test_short_alt_tab_does_not_restart_presentmon(self):
        def away(s):
            s.desktop.foreground_pid = 999

        def back(s):
            s.desktop.foreground_pid = 100

        h = Harness([lambda s: None, away, back, lambda s: None])  # 1 sn'lik alt-tab < bekleme süresi
        h.run()
        self.assertEqual(len(h.procs), 1)

    def test_quick_exit_means_not_started_and_is_not_retried(self):
        h = Harness([lambda s: None] * 6)
        h.next_code = 5                               # erişim reddedildi benzeri: hemen kapanır
        h.run()
        self.assertEqual(h.live.snapshot()["durum"], "baslamadi")
        self.assertEqual(len(h.procs), 1)

    def test_no_frames_reports_unavailable_not_zero(self):
        h = Harness([lambda s: None] * (live_fps.NO_FRAMES_SN + 3))
        h.run()
        snap = h.live.snapshot()
        self.assertEqual(snap["durum"], "kare_yok")
        self.assertIsNone(snap["fps"])
        self.assertEqual(h.fps, [])

    def test_frames_become_seconds_and_drop_is_recorded(self):
        h = Harness([lambda s: None] * 2)
        live = h.live
        live._focused = True
        header = ["Application,ProcessID,MsBetweenPresents".encode()]
        live._read(FakeProc(header + [b"oyun.exe,1,10.0"] * 100 * 31))  # 31 sn x 100 FPS
        self.assertEqual(len(h.fps), 31)
        self.assertEqual(round(h.fps[0]), 100)
        live._read(FakeProc(header + [b"oyun.exe,1,25.0"] * 40 * 6))      # 6 sn x 40 FPS
        self.assertIsNotNone(live.snapshot()["dusus"])
        live._read(FakeProc(header + [b"oyun.exe,1,10.0"] * 100))
        self.assertEqual(len(h.drops), 1)
        self.assertEqual(h.drops[0]["onceki_fps"], 100)
        self.assertIsNone(live.snapshot()["dusus"])

    def test_frames_ignored_when_not_focused(self):
        h = Harness([])
        h.live._focused = False
        h.live._read(FakeProc([b"Application,MsBetweenPresents", b"oyun.exe,10.0"] + [b"oyun.exe,10.0"] * 500))
        self.assertEqual(h.fps, [])

    def test_error_text_before_header_is_kept_as_note_and_utf16_is_handled(self):
        h = Harness([])
        h.live._focused = True
        text = "error: failed to start trace session (access denied)".encode("utf-16-le")
        h.live._read(FakeProc([text + b"\n", b"Application,MsBetweenPresents"]))
        self.assertIn("access denied", h.live.snapshot()["ayrinti"])

    def test_missing_presentmon_is_reported(self):
        live = LiveFps("oyun.exe", desktop=FakeDesktop())
        from unittest import mock
        with mock.patch("app.measure.presentmon.find_presentmon", return_value=None):
            live._run()
        self.assertEqual(live.snapshot()["durum"], "presentmon_yok")

    def test_callback_errors_do_not_break_measurement(self):
        def boom(_value):
            raise RuntimeError("x")

        live = LiveFps("oyun.exe", on_second=boom, on_drop=boom, desktop=FakeDesktop())
        live._focused = True
        live._read(FakeProc([b"Application,MsBetweenPresents"] + [b"oyun.exe,10.0"] * 250))
        self.assertEqual(live.snapshot()["fps"], 100)


class TestFailureNeverCrashes(unittest.TestCase):
    """TEST_FAZI C1/C4 (gerçek denemede çökme): her başarısızlık tek seferlik on_fail olur, döngü durur, istisna dışarı sızmaz."""

    def harness(self, actions):
        h = Harness(actions)
        h.fails = []
        h.live.on_fail = h.fails.append
        return h

    def test_quick_exit_reports_failure_once_and_stops(self):
        h = self.harness([lambda s: None] * 6)
        h.next_code = 6                                   # gerçek PresentMon 2.6: yönetici yokken "access denied", kod 6
        h.run()
        self.assertEqual((h.fails, len(h.procs)), (["baslamadi"], 1))
        self.assertTrue(h.live._stop.is_set())

    def test_game_process_missing_starts_nothing_and_does_not_fail(self):
        h = self.harness([lambda s: None] * 4)
        h.desktop.processes = lambda: [(7, "other.exe")]  # oyun süreci yok (kapandı / henüz açılmadı)
        h.run()
        self.assertEqual((h.procs, h.fails, h.live.snapshot()["durum"]), ([], [], "basliyor"))

    def test_alt_tab_back_with_failing_restart_turns_off_instead_of_crashing(self):
        def away(s):
            s.desktop.foreground_pid = 999

        def back(s):
            s.desktop.foreground_pid = 100

            def gone(_args):
                raise FileNotFoundError("PresentMon silinmiş")
            s.live.launch = gone

        h = self.harness([lambda s: None, away] + [lambda s: None] * 4 + [back, lambda s: None])
        h.live._run()                                     # gerçek giriş noktası: istisna burada yakalanmalı
        self.assertEqual(h.fails, ["baslamadi"])
        self.assertTrue(h.procs[0].terminated)
        self.assertEqual(h.live.snapshot()["durum"], "baslamadi")

    def test_alt_tab_back_with_quick_exit_fails_once(self):
        def away(s):
            s.desktop.foreground_pid = 999

        def back(s):
            s.desktop.foreground_pid = 100
            s.next_code = 6

        h = self.harness([lambda s: None, away] + [lambda s: None] * 4 + [back] + [lambda s: None] * 3)
        h.run()
        self.assertEqual((h.fails, len(h.procs)), (["baslamadi"], 2))

    def test_unexpected_output_error_is_logged_and_reported(self):
        h = self.harness([])
        h.live._focused = True

        class Broken:
            def __iter__(self):
                yield b"Application,ProcessID,FrameTime"
                raise RuntimeError("bozuk boru")

        proc = FakeProc()
        proc.stdout = Broken()
        with self.assertLogs("pcopt.canli_fps", "ERROR"):
            h.live._read(proc)
        self.assertEqual(h.fails, ["baslamadi"])

    def test_presentmon_26_output_with_na_cells_and_stray_lines(self):
        h = self.harness([])
        h.live._focused = True
        lines = [b"warning: PresentMon requires elevated privilege ...",
                 b"Application,ProcessID,SwapChainAddress,PresentRuntime,SyncInterval,PresentFlags,AllowsTearing,"
                 b"PresentMode,FrameType,CPUStartTime,FrameTime,CPUBusy,CPUWait,GPULatency,GPUTime",
                 b"oyun.exe,100,0x1,DXGI,0,0,1,Hardware: Independent Flip,Application,1.0,NA,1,1,1,1",
                 b"error: lost events"] + \
                [b"oyun.exe,100,0x1,DXGI,0,0,1,Hardware: Independent Flip,Application,1.0,8.0,1,1,1,1"] * 250
        h.live._read(FakeProc(lines))
        self.assertEqual((h.live.snapshot()["fps"], h.fails), (125, []))

    def test_missing_presentmon_reports_failure(self):
        from unittest import mock
        fails = []
        live = LiveFps("oyun.exe", desktop=FakeDesktop(), on_fail=fails.append)
        with mock.patch("app.measure.presentmon.find_presentmon", return_value=None):
            live._run()
        self.assertEqual(fails, ["presentmon_yok"])

    def test_normal_stop_is_not_a_failure(self):
        h = self.harness([lambda s: None] * 3)
        h.run()
        h.live._fail("baslamadi")                         # durdurulmuş ölçücüde geç gelen hata
        self.assertEqual(h.fails, [])


class TestAppTurnsFeatureOff(unittest.TestCase):
    """Arayüz: başarısızlıkta ayar kapanır, tek satır durum, Oyunlar yenilenir; başlatma istisnası dışarı sızmaz."""

    def fake_app(self):
        from unittest import mock
        app = mock.Mock()
        app.live_fps = None
        app.recorder = None
        return app

    def test_failure_turns_setting_off_and_tells_once(self):
        from unittest import mock
        from app.ui.app import MainWindow as App
        app = self.fake_app()
        with mock.patch("app.core.settings.set") as set_:
            App._live_fps_failed(app, "baslamadi")
        set_.assert_called_once_with("canli_fps", False)
        app.set_status.assert_called_once()
        app._reload_games_page.assert_called_once()

    def test_start_exception_does_not_escape(self):
        from unittest import mock
        from app.ui.app import MainWindow as App
        app = self.fake_app()
        app.live_fps_allowed.return_value = True
        with mock.patch("app.measure.live_fps.LiveFps", side_effect=RuntimeError("iş parçacığı yok")), \
                self.assertLogs("pcopt.ui", "ERROR"):
            App._start_live_fps(app, {"id": "a", "exe": r"C:\o\oyun.exe"})
        self.assertIsNone(app.live_fps)
        app._live_fps_failed.assert_called_once_with("baslamadi")


class TestFpsStats(unittest.TestCase):
    def test_summary_and_drop_limit(self):
        stats = recorder.FpsStats()
        self.assertEqual(stats.result(), {})
        for value in (60, 144, 90):
            stats.add(value)
        for i in range(recorder.DROP_LIMIT + 5):
            stats.drop({"sn": i, "sure_sn": 5, "onceki_fps": 100, "en_dusuk_fps": 30})
        result = stats.result()
        self.assertEqual(result["fps"], {"min": 60.0, "ort": 98.0, "maks": 144.0})
        self.assertEqual(len(result["fps_dususleri"]), recorder.DROP_LIMIT)

    def test_recorder_summary_includes_fps_only_when_measured(self):
        rec = recorder.SessionRecorder("oyun.exe", factory=lambda: None)
        self.assertNotIn("fps", rec.stop())
        rec2 = recorder.SessionRecorder("oyun.exe", factory=lambda: None)
        rec2.fps.add(75)
        self.assertEqual(rec2.stop()["fps"]["ort"], 75.0)


class TestAllowed(unittest.TestCase):
    """Canlı FPS: ayar kapalıysa hiç; anti-cheat'li oyunda HİÇBİR durumda (eski izin listesi dosyada kalmış olsa bile)."""

    def check(self, game, **values):
        from unittest import mock
        from app.ui.app import MainWindow as App
        with mock.patch("app.core.settings.get", side_effect=lambda k: values.get(k, False if k == "canli_fps" else [])):
            return App.live_fps_allowed(None, game)

    def test_rules(self):
        plain, guarded = {"id": "a"}, {"id": "b", "anti_cheat": ["Riot Vanguard"]}
        self.assertFalse(self.check(plain))                                   # ayar kapalı
        self.assertTrue(self.check(plain, canli_fps=True))
        self.assertFalse(self.check(guarded, canli_fps=True))                 # anti-cheat: asla
        self.assertFalse(self.check(guarded, canli_fps=True, canli_fps_izinli=["b"]))  # eski sürümün izni yok sayılır


if __name__ == "__main__":
    unittest.main()


class TestCrashTrace(unittest.TestCase):
    """Pencereli .exe'de stderr yok: yakalanmamış hata log'a, önceki yerel çökmenin izi (cokme.txt) temizlenip log'a."""

    def test_previous_crash_moves_to_log_and_hooks_log_errors(self):
        import faulthandler
        import logging
        import sys
        import tempfile
        import threading
        from pathlib import Path
        from unittest import mock

        from app.core import log
        folder = Path(tempfile.mkdtemp())
        (folder / "cokme.txt").write_text("Fatal Python error: Segmentation fault\nThread canli-fps", encoding="utf-8")
        old = sys.excepthook, threading.excepthook
        logger = logging.getLogger("pcopt.deneme_cokme")
        try:
            with mock.patch("app.core.paths.logs_dir", return_value=folder), self.assertLogs(logger, "ERROR") as seen:
                log._capture_crashes(logger)
                sys.excepthook(RuntimeError, RuntimeError("ana"), None)
                thread = threading.Thread(target=lambda: 1 / 0, name="canli-fps")
                thread.start()
                thread.join()
        finally:
            faulthandler.disable()
            sys.excepthook, threading.excepthook = old
        text = "\n".join(seen.output)
        self.assertIn("Segmentation fault", text)
        self.assertIn("canli-fps", text)
        self.assertIn("ZeroDivisionError", "\n".join(r.exc_text or "" for r in seen.records) + text)
        self.assertEqual(len(seen.records), 3)
        self.assertEqual((folder / "cokme.txt").read_text(encoding="utf-8"), "")
