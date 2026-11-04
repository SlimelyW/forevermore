"""Arayüz testleri (Qt "offscreen": ekranda HİÇBİR pencere açılmaz).

Gerçek arayüz, bellekteki sahte Windows'a (tests/fake_system.py) bağlanır;
düğmeler programla tıklanır. Gerçek bilgisayarda hiçbir ayar değişmez.
PySide6 kurulu değilse testler atlanır.

Çalıştırma (proje klasöründe):
    py -3.12 -m unittest tests.test_arayuz -v
"""

import os
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LOCALAPPDATA"] = os.environ.get("PCOPT_TEST_LOCALAPPDATA") or tempfile.mkdtemp(prefix="pcopt_test_")

try:
    from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QPushButton, QScrollArea, QWidget
except ImportError:  # pragma: no cover
    QApplication = QLabel = QPushButton = QScrollArea = QWidget = None

from app.core import i18n
from app.core.i18n import t
from app.engine.backup import BackupStore
from app.engine.engine import Engine
from tests.fake_system import FakeResolver, FakeSystem
from tests.test_motor import DESKTOP

class FakeSampler:
    """Gerçek performans sayaçları yerine sabit değerler."""

    def sample(self):
        return {"cpu": 12.0, "cpu_ghz": 3.6, "ram_toplam": 32 * 2 ** 30, "ram_kullanilan": 8 * 2 ** 30,
                "gpu": 40.0, "gpu_bellek": 2 * 2 ** 30, "disk": 5.0, "disk_okuma": 2 ** 20, "disk_yazma": 0.0,
                "ag_alinan": 125000.0, "ag_gonderilen": 1000.0, "surec_sayisi": 200.0,
                "en_cok": [{"ad": "oyun", "cpu": 25.0, "bellek_mb": 4000}], "olcum_ms": 1.0}

    def close(self):
        pass


MINIMAL_SCAN = {"zaman": "2026-01-01T00:00:00", "bolumler": {}, "bulgular": [], "hatalar": {}, "tespitler": [],
                "toplam_sure": 0}


@unittest.skipIf(QApplication is None, "PySide6 kurulu değil")
class TestUserInterface(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        i18n.load("tr")
        from app.ui import app as app_module, dialogs
        cls.app_module, cls.dialogs = app_module, dialogs
        cls.qt = app_module.create_app()
        cls.messages = []
        cls.risky_calls = []
        cls.risky_answer = True
        cls._saved = (dialogs.confirm_careful, dialogs.ask_yes_no, dialogs.show_message,
                      app_module.MainWindow._start_background, dialogs.confirm_risky)
        dialogs.confirm_careful = lambda *a, **k: True
        cls._saved_rp = dialogs.ask_restore_point
        dialogs.ask_restore_point = lambda *a, **k: ("olustur", False)

        def risky(_parent, tweak, _avail=None, enabling=True, _anti_cheat=""):
            cls.risky_calls.append((tweak["id"], enabling))
            return cls.risky_answer

        dialogs.confirm_risky = risky
        dialogs.ask_yes_no = lambda *a, **k: True
        dialogs.show_message = lambda _parent, _title, text, kind="bilgi": cls.messages.append(text)
        app_module.MainWindow._start_background = lambda self: None  # gerçek tarama yapılmasın
        cls._saved_scan = app_module.MainWindow.start_scan
        app_module.MainWindow.start_scan = lambda self: None
        app_module.MainWindow.live_sampler_factory = FakeSampler
        from app.core import autostart
        cls._saved_autostart = autostart.is_enabled
        autostart.is_enabled = lambda: False  # gerçek Görev Zamanlayıcı okunmasın
        from app.games import discovery
        cls._saved_discover = discovery.discover
        discovery.discover = lambda errors=None: []  # gerçek oyun klasörleri taranmasın

    @classmethod
    def tearDownClass(cls):
        (cls.dialogs.confirm_careful, cls.dialogs.ask_yes_no, cls.dialogs.show_message,
         cls.app_module.MainWindow._start_background, cls.dialogs.confirm_risky) = cls._saved
        cls.app_module.MainWindow.live_sampler_factory = None
        cls.dialogs.ask_restore_point = cls._saved_rp
        cls.app_module.MainWindow.start_scan = cls._saved_scan
        from app.core import autostart
        autostart.is_enabled = cls._saved_autostart
        from app.games import discovery
        discovery.discover = cls._saved_discover

    def make_window(self, mode="normal", findings=()):
        from app.ui.controller import Controller
        self.tmp = tempfile.TemporaryDirectory()
        self.sys = FakeSystem()
        engine = Engine(system=self.sys, store=BackupStore(Path(self.tmp.name)), profile=DESKTOP,
                        resolver=FakeResolver(), is_admin=lambda: mode == "normal")
        controller = Controller(mode, engine=engine, cache_file=Path(self.tmp.name) / "onbellek.json")
        controller.scan = dict(MINIMAL_SCAN, bulgular=list(findings))
        controller.refresh_all()
        self.messages.clear()
        self.risky_calls.clear()
        type(self).risky_answer = True
        window = self.app_module.MainWindow(controller)
        window.reload_pages()
        return window

    def tearDown(self):
        if getattr(self, "window", None):
            self.window.worker.shutdown()
            self.window.close()
            self.window.deleteLater()
            self.qt.processEvents()
        if getattr(self, "tmp", None):
            self.tmp.cleanup()

    def wait_idle(self, timeout=10):
        end = time.time() + timeout
        while time.time() < end:
            self.qt.processEvents()
            if not self.window.busy:
                time.sleep(0.05)
                self.qt.processEvents()
                if not self.window.busy:
                    return
            time.sleep(0.01)
        self.fail("arayüz işlemi zaman aşımına uğradı")

    def row(self, category, tweak_id):
        self.window.navigate(category)
        self.qt.processEvents()
        return self.window.pages[category].rows[tweak_id]

    # ------------------------------------------------------------------ testler
    def test_every_page_builds(self):
        self.window = self.make_window()
        for key in ["ozet", "pc_detay", "profiller", "degisiklikler", "rapor", "ayarlar", "bilgi", "elle"] + \
                [c["id"] for c in self.window.c.categories]:
            self.window.navigate(key)
            self.qt.processEvents()
            self.assertTrue(self.window.pages[key].built, key)

    def test_post_scan_refresh_does_not_reread_states(self):
        """2.9: tarama sonrası tazeleme okunmuş durumları yeniden okumaz (açılışta ikinci tur PowerShell yok)."""
        self.window = self.make_window()
        c, reads = self.window.c, []
        real = c.engine.read_state
        c.engine.read_state = lambda tw: reads.append(tw["id"]) or real(tw)
        c.refresh_all(reread=False)
        self.assertEqual(reads, [])
        c.refresh_all()
        self.assertTrue(reads)

    def test_sidebar_scrolls_when_short(self):
        self.window = window = self.make_window()
        window._show_rare(True)
        bar = window.findChild(QWidget, "Sidebar")
        scroll = bar.findChild(QScrollArea)
        self.assertLess(bar.minimumSizeHint().height(), scroll.widget().sizeHint().height())

    def test_search_finds_tweaks_and_pages(self):
        from app.ui.search import search
        self.window = window = self.make_window()
        tweaks, pages = window.c.tweaks, window.search_box._pages
        for query in ("PERF-003", "hvci", "bellek butunlugu"):
            self.assertEqual(search(tweaks, pages, query)[0][:2], ("tweak", "PERF-003"), query)
        self.assertEqual(search(tweaks, pages, "oyunlar")[0][:2], ("page", "oyunlar"))
        self.assertEqual(search(tweaks, pages, "zzzzqqq"), [])
        calls = []
        window.search_box._on_tweak = calls.append
        window.search_box.edit.setText("PERF-003")
        window.search_box.edit.returnPressed.emit()
        self.assertEqual(calls, ["PERF-003"])
        self.assertEqual(window.search_box.edit.text(), "")

    def test_motion_respects_reduced_setting(self):
        from unittest import mock
        from app.ui import motion
        self.window = self.make_window()
        page = self.window._page("PERF")
        self.assertTrue(motion.reduced())  # testlerde varsayılan: hareket yok
        motion.fade_in(page)
        self.assertIsNone(page.graphicsEffect())
        with mock.patch.dict(os.environ, {"PCOPT_HAREKET": "ac"}):
            motion.fade_in(page)
            self.assertIsNotNone(page.graphicsEffect())  # animasyon bitince kaldırılır
            page.ensure_built()
            row = next(iter(page.rows.values()))
            row.hover = True
            row._hover_to(1.0)
            self.assertEqual(row._hover_anim.duration(), motion.HOVER_MS)
        row._hover_to(0.0)
        self.assertEqual(row._hover_anim.duration(), 0)  # azaltılmışken anında

    def test_bulk_recommended_preview_then_apply(self):
        from unittest import mock
        self.window = self.make_window(findings=[])
        tweaks = [self.window.c.by_id[p["id"]] for p in self.window.c.recommendations()]
        ids = [tw["id"] for tw in tweaks]
        self.assertGreaterEqual(len(ids), 1)
        store = self.window.c.engine.store
        dialog = self.dialogs.BulkPreviewDialog(self.window, tweaks)
        self.assertEqual(dialog.chosen(), ids)  # hepsi varsayılan işaretli
        dialog.checks[0][1].setChecked(False)
        self.assertEqual(dialog.chosen(), ids[1:])
        with mock.patch.object(self.dialogs, "choose_bulk", lambda parent, tw: []):  # vazgeç
            self.window.apply_recommended(tweaks)
        self.assertFalse(any(store.has(i) for i in ids))
        with mock.patch.object(self.dialogs, "choose_bulk", lambda parent, tw: ids[:1]):  # yalnızca ilki onaylı
            self.window.apply_recommended(tweaks)
            self.wait_idle()
        self.assertTrue(store.has(ids[0]))
        self.assertFalse(any(store.has(i) for i in ids[1:]))
        self.assertTrue(self.window.toast.text().startswith("✓"))  # modal pencere yerine yeşil onay

    def test_back_navigation_history(self):
        self.window = self.make_window()
        win = self.window
        self.assertFalse(win.go_back())            # geçmiş boş
        win.navigate("SYS")
        win.navigate("GPU")
        win.navigate("GPU")                         # aynı sayfaya tekrar gitmek geçmişe eklenmez
        self.assertEqual(win._history, ["ozet", "SYS"])
        bar = win.pages["SYS"].scroll.verticalScrollBar()
        bar.setValue(bar.maximum() // 2)
        position = bar.value()
        self.assertTrue(win.go_back())
        self.assertEqual(win.current, "SYS")
        self.assertEqual(bar.value(), position)     # kaydırma korunur
        self.assertTrue(win.go_back())
        self.assertEqual(win.current, "ozet")
        self.assertFalse(win.go_back())

    def test_mouse_back_and_escape_go_back(self):
        from PySide6.QtCore import QEvent, QPointF, Qt
        from PySide6.QtGui import QMouseEvent, QPointingDevice
        self.window = self.make_window()
        win = self.window
        win.navigate("SYS")
        win.navigate("GPU")
        press = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(5, 5), QPointF(5, 5), Qt.MouseButton.BackButton,
                            Qt.MouseButton.BackButton, Qt.KeyboardModifier.NoModifier,
                            QPointingDevice.primaryPointingDevice())
        win.mousePressEvent(press)
        self.assertEqual(win.current, "SYS")
        self.assertTrue(press.isAccepted())
        win._escape()
        self.assertEqual(win.current, "ozet")
        win._escape()                                # geçmiş bitti: yerinde kalır
        self.assertEqual(win.current, "ozet")

    def test_escape_in_search_box_clears_then_leaves_field(self):
        win = self.make_window()
        self.window = win
        win.navigate("SYS")
        edit = win.search_box.edit
        edit.setFocus()
        edit.setText("ağ")
        win.isActiveWindow()  # odak ekran dışında etkin olmayabilir: _escape doğrudan çağrılır
        from unittest import mock
        with mock.patch("app.ui.app.QApplication.focusWidget", return_value=edit):
            win._escape()
        self.assertEqual(edit.text(), "")
        self.assertEqual(win.current, "SYS")           # ilk Esc yalnızca kutuyu temizledi

    def test_undo_toast_after_apply(self):
        self.window = self.make_window()
        win = self.window
        tweak = win.c.by_id["QOL-001"]
        win.toggle(tweak, True, lambda: None)
        self.wait_idle()
        self.assertTrue(win.c.engine.store.has("QOL-001"))
        self.assertTrue(win.toast.button.isVisibleTo(win.toast))   # "Geri al" düğmesi
        self.assertEqual(win.toast.button.text(), t("ui.geri_al"))
        win.toast.button.click()
        self.wait_idle()
        self.assertFalse(win.c.engine.store.has("QOL-001"))        # düğme gerçekten geri aldı
        win.toggle(tweak, True, lambda: None)
        self.wait_idle()
        win.toggle(tweak, False, lambda: None)                     # kapatmak zaten geri almadır: düğme yok
        self.wait_idle()
        self.assertTrue(win.toast.isHidden())

    def test_live_monitor_pauses_when_window_inactive(self):
        from app.ui.live_monitor import LiveMonitor
        monitor = LiveMonitor(lambda: FakeSampler())
        monitor.set_active(True, owner=self)
        self.assertTrue(monitor._active.is_set())
        monitor.set_window_active(False)
        self.assertFalse(monitor._active.is_set())   # odak kaybı: örnekleme durur
        monitor.set_window_active(True)
        self.assertTrue(monitor._active.is_set())
        monitor.set_active(False, owner=self)
        monitor.stop()

    def test_hover_prebuilds_stale_page_only_when_idle(self):
        self.window = self.make_window()
        win = self.window
        win.navigate("SYS")
        win.navigate("ozet")
        page = win.pages["SYS"]
        page.stale = True
        win._hover_key = "SYS"
        win.busy = True
        win._prebuild_hovered("SYS")
        self.assertTrue(page.stale)                 # işlem sürerken hiçbir şey yapılmaz
        win.busy = False
        win._hover_key = "PERF"
        win._prebuild_hovered("SYS")
        self.assertTrue(page.stale)                 # imleç başka öğeye geçti
        win._hover_key = "SYS"
        win._prebuild_hovered("SYS")
        self.assertFalse(page.stale)                # tıklamadan önce hazır

    def test_nav_items_reachable_by_keyboard(self):
        from PySide6.QtCore import QEvent, Qt
        from PySide6.QtGui import QKeyEvent
        self.window = self.make_window()
        item = self.window.nav["SYS"]
        self.assertEqual(item.focusPolicy(), Qt.FocusPolicy.TabFocus)
        item.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier))
        self.assertEqual(self.window.current, "SYS")

    def test_accessibility_modes(self):
        from unittest import mock
        from app.ui import theme
        flags = {"yuksek_karsitlik": True, "okunabilir_yazi": True}
        with mock.patch.object(theme.settings, "get", lambda key: flags.get(key)):
            self.assertIn(theme.palette()["text"], (theme.HIGH_DARK["text"], theme.HIGH_LIGHT["text"]))
            font = theme.ui_font(13)
            self.assertEqual(font.pixelSize(), 14)
            self.assertAlmostEqual(font.letterSpacing(), 0.3, places=1)
        self.assertEqual(theme.ui_font(13).pixelSize(), 13)  # varsayılan değişmez
        self.window = self.make_window()
        page = self.window._page("ayarlar")
        page.ensure_built()
        texts = {lb.text() for lb in page.findChildren(QLabel)}
        for key in ("ui.erisim.okunabilir", "ui.erisim.hareket", "ui.erisim.karsitlik"):
            self.assertIn(t(key), texts)

    def test_category_status_line_matches_menu_count(self):
        self.window = self.make_window()
        page = self.window._page("PERF")
        page.ensure_built()
        on, total = self.window.c.category_counts(page.category["ad"])
        self.assertEqual(page.status_big.text(), f"{on} / {total}")
        self.assertEqual((page.status_bar.value(), page.status_bar.maximum()), (on, total))

    def test_guides_only_on_manual_page(self):
        """Uygulamanın yapamadığı ayarlar kategori sayfalarında yok; Elle yapılacaklar'da nedene göre."""
        from app.ui.controller import MANUAL_REASONS, is_manual
        self.window = self.make_window()
        manual = [tw["id"] for tw in self.window.c.tweaks if is_manual(tw)]
        self.assertTrue(manual)
        for category in self.window.c.categories:
            if category["id"] == "PLC":
                continue
            self.window.navigate(category["id"])
            self.qt.processEvents()
            self.assertFalse(set(manual) & set(self.window.pages[category["id"]].rows), category["id"])
        self.window.navigate("elle")
        self.qt.processEvents()
        visible = {tid for tid in manual if self.window.c.availability[tid].visible}  # masaüstü: laptop rehberleri yok
        self.assertEqual(set(self.window.pages["elle"].rows), visible)
        for tweak in self.window.c.tweaks:
            if is_manual(tweak):
                self.assertIn(tweak.get("elle_nedeni"), MANUAL_REASONS, tweak["id"])
        self.window.go_to_tweak("CPU-008")
        self.assertEqual(self.window.current, "elle")

    def test_timer_resolution_card(self):
        from unittest import mock
        from app.core import settings
        from app.ui import page_category
        self.window = self.make_window()
        card = page_category.TimerResolutionCard(self.window)
        try:
            with mock.patch.object(page_category.timer_resolution, "hold", return_value=0.5) as hold:
                card._apply(5000)
                hold.assert_called_with(5000)
                self.assertEqual(settings.get("zamanlayici_cozunurlugu"), 5000)
                card._apply(0)
                hold.assert_called_with(0)
            self.assertEqual(settings.get("zamanlayici_cozunurlugu"), 0)
        finally:
            settings.set("zamanlayici_cozunurlugu", 0)

    def test_amd_card_toggle_and_revert(self):
        """AMD (ADLX) ayarı açılınca yedeklenir; anahtarı geri çevirmek uygulamanın değişikliğini geri alır."""
        from app.ui.managers_ui import AmdSettingCard
        self.window = self.make_window()
        card = AmdSettingCard(self.window, self.window.c.by_id["GPU-013"])
        card.set_values(self.sys.get_amd_settings())
        switch = self.app_module.w.ToggleSwitch()
        switch.setChecked(True)  # kullanıcı Anti-Lag'i açtı
        card._toggle("Test Radeon", "anti_lag", switch)
        self.wait_idle()
        self.assertTrue(self.sys.amd["Test Radeon"]["anti_lag"]["acik"])
        change_id = AmdSettingCard.change_id("Test Radeon", "anti_lag")
        self.assertTrue(self.window.c.engine.store.has(change_id))
        switch.setChecked(False)
        card._toggle("Test Radeon", "anti_lag", switch)
        self.wait_idle()
        self.assertFalse(self.sys.amd["Test Radeon"]["anti_lag"]["acik"])
        self.assertFalse(self.window.c.engine.store.has(change_id))

    def test_report_shows_overlay_processes_not_just_applied(self):
        """2.5: bindirme yasağı uygulandı görünürken NVIDIA Overlay süreçleri çalışıyordu; rapor gerçek durumu yazar."""
        from app.ui import managers_ui, report_extra
        self.window = self.make_window()
        self.window.c.engine.store.save_first("GPU-022", "Turn off the NVIDIA app overlay", [{"meta": {}}])
        original = managers_ui.running_count
        try:
            for count, key in ((5, "ui.nvidia_bindirme_suruyor"), (0, "ui.nvidia_bindirme_kapali")):
                managers_ui.running_count = lambda _exe, n=count: n
                text = "\n".join(line for _title, lines in report_extra.sections(self.window.c) for line in lines)
                self.assertIn(t(key, adet=count), text)
                self.assertNotIn("Turn off the NVIDIA app overlay", text)  # eski kayıt adı değil güncel ad
        finally:
            managers_ui.running_count = original

    def test_wheel_changes_no_value_on_any_page(self):
        """2.2: hiçbir ekranda tekerlek liste/sayı/kaydırıcı/aç-kapa değerini değiştirmez."""
        from PySide6.QtWidgets import QAbstractButton, QAbstractSlider, QAbstractSpinBox, QComboBox, QScrollBar
        from app.ui import widgets
        from shiboken6 import isValid
        from tests.test_tekerlek import _wheel
        widgets.install_wheel_guard(self.qt)
        self.window = self.make_window()
        self.window.show()
        checked = 0
        keys = ["ozet", "pc_detay", "profiller", "oyunlar", "DISP", "SYS", "baslangic", "PERF", "GPU", "CPU", "PWR",
                "NET", "INP", "AUD", "QOL", "PLC", "elle", "degisiklikler", "olcum", "boost", "ayarlar", "bilgi"]
        for key in keys:
            self.window.navigate(key)
            self.qt.processEvents()
            page = self.window._page(key)  # noqa: SLF001
            items = [x for x in page.findChildren(QWidget) if x.isVisible() and (
                isinstance(x, (QComboBox, QAbstractSpinBox, QAbstractSlider)) or isinstance(x, widgets.ToggleSwitch))
                and not isinstance(x, QScrollBar)]
            read = lambda x: (x.currentIndex() if isinstance(x, QComboBox) else x.value()  # noqa: E731
                              if isinstance(x, (QAbstractSpinBox, QAbstractSlider)) and hasattr(x, "value")
                              else x.isChecked() if isinstance(x, QAbstractButton) else None)
            for item in items:
                if not isValid(item):
                    continue  # arka plan okuması kartı yeniden çizdi
                before = read(item)
                for down in (True, False):
                    if isValid(item):
                        _wheel(item, down)
                after = read(item) if isValid(item) else before  # olay sırasında yeniden çizildiyse
                self.assertEqual(after, before, f"{key}: {type(item).__name__}")
                checked += 1
        self.assertGreater(checked, 10)

    def test_stall_watch_logs_where_the_ui_thread_hangs(self):
        from app.ui import worker
        original = worker.StallWatch.LIMIT
        worker.StallWatch.LIMIT = 0.4
        try:
            watch = worker.StallWatch()

            def busy_ui_call():
                time.sleep(1.2)   # ana iş parçacığını bloke eden çağrı
            with self.assertLogs(worker._log, "WARNING") as logs:  # noqa: SLF001
                self.qt.processEvents()
                busy_ui_call()
                self.qt.processEvents()
            self.assertIn("busy_ui_call", "\n".join(logs.output))
            self.assertEqual(len(logs.output), 1)   # aynı takılma bir kez
            from shiboken6 import delete
            delete(watch)   # destroyed -> izleme iş parçacığı durur
        finally:
            worker.StallWatch.LIMIT = original

    def test_monitor_driver_reads_never_block_the_ui_thread(self):
        """Arkadaşlarda 'yanıt vermiyor': sürücü (NVAPI/ADLX) okuması her ayar güncellemesinde ana iş parçacığındaydı."""
        import threading
        from app.ui.managers_ui import MonitorsCard
        self.window = self.make_window()
        threads, real = [], self.sys.list_monitors
        self.sys.list_monitors = lambda: threads.append(threading.current_thread()) or real()
        card = MonitorsCard(self.window, self.window.c.by_id["DISP-001"])
        for _ in range(5):
            card.refresh()   # tweak_updated her ayar değişiminde bunu çağırır
        self.settle(card)
        self.assertTrue(threads)
        self.assertNotIn(threading.main_thread(), threads)
        self.assertLessEqual(len(threads), 3)   # üst üste istekler birleşir
        self.assertTrue(card.monitors)

    def test_monitor_scaling_via_driver(self):
        """Ölçekleme modu (GPU / monitör) sürücüyle yazılır, geri sayımlı onay sorulur, geri alınabilir."""
        from app.ui.managers_ui import MonitorsCard
        self.window = self.make_window()
        card = MonitorsCard(self.window, self.window.c.by_id["DISP-001"])
        original = self.dialogs.ask_keep_display
        self.dialogs.ask_keep_display = lambda *_a, **_k: True
        try:
            card._change(card._read_monitors()[0], "olcekleme", "nvidia:2")
            self.settle(card)
        finally:
            self.dialogs.ask_keep_display = original
        self.assertEqual(self.sys.monitors["TEST"]["surucu_olcekleme"]["deger"], "nvidia:2")
        card._revert(card._read_monitors()[0], ["olcekleme"])
        self.settle(card)
        self.assertEqual(self.sys.monitors["TEST"]["surucu_olcekleme"]["deger"], "nvidia:6")

    def test_safe_mode_needs_two_confirmations_and_can_be_undone(self):
        from app.engine import driver_tools
        from app.ui import managers_ui
        self.window = self.make_window()
        card = managers_ui.DriverToolsCard(self.window, self.window.c.by_id["GPU-019"])
        answers, asked = [True, False], []
        original = self.dialogs.ask_yes_no
        self.dialogs.ask_yes_no = lambda *a, **k: asked.append(a[2]) or answers.pop(0)
        try:
            card._safe_mode()  # ikinci uyarıda vazgeçildi: hiçbir şey yapılmaz
            self.wait_idle()
            self.assertEqual(len(asked), 2)
            self.assertNotIn("safeboot", self.sys.bcd)
            self.assertEqual(self.sys.restarts, [])
            answers[:] = [True, True]
            card._safe_mode()
            self.wait_idle()
        finally:
            self.dialogs.ask_yes_no = original
        self.assertEqual(self.sys.bcd.get("safeboot"), "minimal")
        self.assertEqual(self.sys.restarts, [driver_tools.RESTART_SECONDS])
        self.assertTrue(self.window.c.engine.store.has(driver_tools.SAFE_MODE_ID))
        card._normal_boot()
        self.wait_idle()
        self.assertNotIn("safeboot", self.sys.bcd)
        self.assertFalse(self.window.c.engine.store.has(driver_tools.SAFE_MODE_ID))

    def test_driver_tool_verify_hash_and_signature(self):
        from unittest import mock
        from app.engine import driver_tools
        with tempfile.TemporaryDirectory() as tmp:
            exe = os.path.join(tmp, "arac.exe")
            with open(exe, "wb") as f:
                f.write(b"abc")
            with mock.patch.object(driver_tools.powershell, "run_object",
                                   return_value={"durum": "Valid", "imzalayan": "CN=Test"}):
                ok = driver_tools.verify(exe)
            with mock.patch.object(driver_tools.powershell, "run_object", return_value={"durum": "NotSigned"}):
                bad = driver_tools.verify(exe)
        self.assertEqual(ok["sha256"], "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
        self.assertTrue(ok["imza_gecerli"])
        self.assertFalse(bad["imza_gecerli"])

    def test_driver_tools_found_in_tools_folder_or_download_page(self):
        from unittest import mock
        from app.engine import driver_tools
        from app.ui import managers_ui
        self.window = self.make_window()
        tools = Path(self.tmp.name) / "tools"
        (tools / "ddu").mkdir(parents=True)
        (tools / "ddu" / "Display Driver Uninstaller.exe").write_bytes(b"")
        with mock.patch.object(driver_tools.paths, "tools_dir", return_value=tools):
            self.assertEqual(driver_tools.find("ddu").name, "Display Driver Uninstaller.exe")
            self.assertIsNone(driver_tools.find("nvcleanstall"))
            card = managers_ui.DriverToolsCard(self.window, self.window.c.by_id["GPU-019"])
            card._open(driver_tools.download_page("nvcleanstall"))
        self.assertEqual(self.sys.opened, ["https://www.techpowerup.com/download/techpowerup-nvcleanstall/"])

    def test_audio_device_disable_and_exclusive_mode(self):
        from app.ui.managers_ui import AudioDevicesCard, DeviceListCard, exclusive_steps
        self.window = self.make_window()
        card = DeviceListCard(self.window, self.window.c.by_id["AUD-009"])
        device = next(d for d in self.sys.audio_pnp if d["sinif"] == "Bluetooth")
        switch = self.app_module.w.ToggleSwitch()
        switch.setChecked(False)  # kullanıcı "Kullanılsın"ı kapattı
        card._toggle(dict(device), switch)
        self.wait_idle()
        self.assertFalse(device["etkin"])
        switch.setChecked(True)  # yeniden açmak = geri almak
        card._toggle(dict(device, etkin=False), switch)
        self.wait_idle()
        self.assertTrue(device["etkin"])
        self.assertFalse(self.window.c.engine.store.has(device["id"]))
        audio = AudioDevicesCard(self.window, self.window.c.by_id["AUD-003"])
        row = {"cihaz": "{TEST}", "ad": "Speaker", "adimlar": exclusive_steps("{TEST}"), "izinli": True}
        switch.setChecked(False)
        audio._toggle_exclusive(row, switch)
        self.wait_idle()
        step = row["adimlar"][0]
        self.assertEqual(self.sys.read_reg("HKLM", step["yol"], step["ad"])[0], 0)
        switch.setChecked(True)
        audio._toggle_exclusive(row, switch)
        self.wait_idle()
        self.assertIsNone(self.sys.read_reg("HKLM", step["yol"], step["ad"]))  # önceki hâl: değer yoktu

    def test_windows_update_modes_switch_and_restore(self):
        """Güvenlik modu WinUtil değerlerini yazar; 2100 modu iki aşamalı onay ister ve öncekini geri alır;
        Varsayılan her şeyi önceki hâline döndürür."""
        from app.engine import windows_update as wu
        from app.ui.managers_ui import WindowsUpdateCard
        self.window = self.make_window()
        card = WindowsUpdateCard(self.window, self.window.c.by_id["SYS-014"])
        policy = wu.POLICY + r"\WindowsUpdate"
        self.assertEqual(wu.detect(self.sys), "varsayilan")
        card._set("guvenlik")
        self.wait_idle()
        self.assertEqual(wu.detect(self.sys), "guvenlik")
        self.assertEqual(self.sys.read_reg("HKLM", policy, "DeferFeatureUpdatesPeriodInDays")[0], 365)
        type(self).risky_answer = False  # iki aşamalı onayda vazgeçildi: hiçbir şey değişmez
        card._set("duraklat")
        self.wait_idle()
        self.assertEqual(wu.detect(self.sys), "guvenlik")
        type(self).risky_answer = True
        card._set("duraklat")
        self.wait_idle()
        self.wait_idle()
        self.assertEqual(wu.detect(self.sys), "duraklat")
        self.assertIsNone(self.sys.read_reg("HKLM", policy, "DeferFeatureUpdatesPeriodInDays"))  # güvenlik geri alındı
        self.assertEqual(self.sys.read_reg("HKLM", wu.UX, "PauseUpdatesExpiryTime")[0], wu.PAUSE_END)
        self.assertIn((wu.CHANGE_ID, True), self.risky_calls)
        card._set("varsayilan")
        self.wait_idle()
        self.assertEqual(wu.detect(self.sys), "varsayilan")
        self.assertIsNone(self.sys.read_reg("HKLM", wu.UX, "PauseUpdatesExpiryTime"))
        self.assertFalse(self.window.c.engine.store.has(wu.CHANGE_ID))

    def test_uac_levels_switch_and_restore(self):
        """Seviyeler iki değeri birlikte yazar; "Hiçbir zaman" iki aşamalı onay ister; varsayılana dönünce
        uygulamanın değişikliği geri alınır ve Değişiklikler'de kayıt kalmaz."""
        from app.engine import uac
        from app.ui.managers_ui import UacCard
        self.window = self.make_window()
        card = UacCard(self.window, self.window.c.by_id["SYS-016"])
        self.assertEqual(uac.detect(self.sys), "varsayilan")
        card._set("her_zaman")
        self.wait_idle()
        self.assertEqual(uac.detect(self.sys), "her_zaman")
        self.assertEqual(self.sys.read_reg("HKLM", uac.PATH, "ConsentPromptBehaviorAdmin")[0], 2)
        type(self).risky_answer = False
        card._set("hic")
        self.wait_idle()
        self.assertEqual(uac.detect(self.sys), "her_zaman")
        type(self).risky_answer = True
        card._set("hic")
        self.wait_idle()
        self.wait_idle()
        self.assertEqual(uac.detect(self.sys), "hic")
        self.assertEqual(self.sys.read_reg("HKLM", uac.PATH, "PromptOnSecureDesktop")[0], 0)
        card._set("varsayilan")
        self.wait_idle()
        self.assertEqual(uac.detect(self.sys), "varsayilan")
        self.assertIsNone(self.sys.read_reg("HKLM", uac.PATH, "ConsentPromptBehaviorAdmin"))  # önceki hâl: değer yoktu
        self.assertFalse(self.window.c.engine.store.has(uac.CHANGE_ID))

    def test_defender_card_warns_and_restores_with_one_click(self):
        """Varsayılan açık; kapatmak iki aşamalı onay ister; "Korumayı geri aç" onay sormadan geri açar.
        Kurcalama koruması açıksa kapatma düğmesi yok, yönlendirme metni var."""
        from PySide6.QtCore import QEvent
        from PySide6.QtWidgets import QPushButton
        from app.engine import defender
        from app.ui.managers_ui import DefenderCard
        self.window = self.make_window()

        def buttons(card):
            end = time.time() + 5
            while time.time() < end:  # durum arka planda okunur
                self.qt.processEvents()
                self.qt.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)  # eski düğmeler silinsin
                texts = [b.text() for b in card.findChildren(QPushButton)]
                if t("ui.defender.yeniden_oku") in texts:
                    return {b.text(): b for b in card.findChildren(QPushButton)}
                time.sleep(0.02)
            self.fail("Defender durumu okunmadı")

        card = DefenderCard(self.window, self.window.c.by_id["SYS-017"])
        self.assertIn(t("ui.defender.kapat"), buttons(card))
        type(self).risky_answer = False
        card._turn_off()
        self.wait_idle()
        self.assertTrue(self.sys.defender["gercek_zamanli"])
        type(self).risky_answer = True
        card._turn_off()
        self.wait_idle()
        self.assertFalse(self.sys.defender["gercek_zamanli"])
        self.assertIn((defender.CHANGE_ID, True), self.risky_calls)
        found = buttons(card)
        self.assertIn(t("ui.defender.geri_ac"), found)
        calls = len(self.risky_calls)
        found[t("ui.defender.geri_ac")].click()
        self.wait_idle()
        self.assertTrue(self.sys.defender["gercek_zamanli"])
        self.assertEqual(len(self.risky_calls), calls)  # geri açarken yeniden onay sorulmaz
        self.assertFalse(self.window.c.engine.store.has(defender.CHANGE_ID))

        self.sys.defender["kurcalama"] = True
        card.refresh()
        found = buttons(card)
        self.assertNotIn(t("ui.defender.kapat"), found)
        self.assertIn(t("ui.defender.kurcalama_acik"), " ".join(lbl.text() for lbl in card.findChildren(QLabel)))

    def test_input_device_custom_name_is_local(self):
        from app.core import settings
        from app.ui.page_category import InputDevicesCard
        self.window = self.make_window()
        device = {"anahtar": "19F5:6120", "ad": "NuPhy Air75 HE", "vid_pid": "19F5:6120", "turler": ["fare", "klavye"],
                  "tur": "fare+klavye", "baglanti": "usb", "gercek_ad": True, "uretici": None, "adet": 3}
        old = {"tur": "klavye", "ad": "HID Keyboard Device", "baglanti": "usb", "uretici": None, "adet": 1}  # eski önbellek
        card = InputDevicesCard(self.window, [device, old])
        try:
            card.set_name(device, "Masa klavyem")
            self.assertEqual(settings.get("cihaz_adlari"), {"19F5:6120": "Masa klavyem"})
            texts = " ".join(lbl.text() for lbl in card.findChildren(QLabel))
            self.assertIn("Masa klavyem", texts)
            self.assertIn("NuPhy Air75 HE", texts)  # cihazın kendi adı da görünür
            self.assertIn("VID:PID 19F5:6120", texts)
            card.set_name(device, "")
            self.assertEqual(settings.get("cihaz_adlari"), {})
        finally:
            settings.set("cihaz_adlari", {})

    def test_moved_items_not_left_in_old_place(self):
        """Oyunlar / Başlangıç menüsüne taşınan ayarlar kategori sayfasında görünmez ("taşındı" kartı yok)."""
        self.window = self.make_window()
        moved = [tw for tw in self.window.c.tweaks if tw.get("liste_yoneticisi") in ("oyunlar", "baslangic")]
        self.assertTrue(moved)
        for tweak in moved:
            category = next(c for c in self.window.c.categories if c["ad"] == tweak["kategori"])
            self.window.navigate(category["id"])
            self.qt.processEvents()
            self.assertNotIn(tweak["id"], self.window.pages[category["id"]].rows)
        self.window.go_to_tweak(next(tw["id"] for tw in moved if tw["liste_yoneticisi"] == "oyunlar"))
        self.assertEqual(self.window.current, "oyunlar")

    def test_pc_details_shows_both_gpus_and_roles(self):
        from PySide6.QtWidgets import QLabel
        self.window = self.make_window()
        displays = [{"aygit": r"\\.\DISPLAY1", "monitor": "Generic PnP Monitor", "ekran_karti": "AMD Radeon 880M",
                     "birincil": False, "cozunurluk": "1920x1080", "yenileme_hz": 144,
                     "bu_cozunurlukte_en_yuksek_hz": 144, "en_yuksek_cozunurluk": "1920x1080",
                     "gpu_rol": "guc_tasarrufu"},
                    {"aygit": r"\\.\DISPLAY6", "monitor": "VG27WQ1B", "ekran_karti": "NVIDIA RTX 5070 Laptop GPU",
                     "birincil": True, "cozunurluk": "2560x1440", "yenileme_hz": 144,
                     "bu_cozunurlukte_en_yuksek_hz": 165, "en_yuksek_cozunurluk": "3840x2160",
                     "gpu_rol": "yuksek_performans"}]
        gpus = [{"ad": "AMD Radeon 880M", "uretici": "AMD", "surucu_surumu": "1", "surucu_tarihi": "2025-01-01",
                 "rol": "guc_tasarrufu", "vram_mb": 512, "ekran_suruyor": [r"\\.\DISPLAY1"], "birincil_ekran": False},
                {"ad": "NVIDIA RTX 5070 Laptop GPU", "uretici": "NVIDIA", "surucu_surumu": "2",
                 "surucu_tarihi": "2026-01-01", "rol": "yuksek_performans", "vram_mb": 8192,
                 "ekran_suruyor": [r"\\.\DISPLAY6"], "birincil_ekran": True}]
        hw = {"bilgisayar": {"uretici": "HP", "model": "OMEN", "tur": "laptop"},
              "cpu": {"ad": "AMD Ryzen AI 9 365", "cekirdek": 10, "is_parcacigi": 20, "hibrit": True,
                      "x3d_cift_ccd": False},
              "gpu": gpus, "ram": {"moduller": []}, "anakart": {}, "ekranlar": displays}
        self.window.c.scan = dict(self.window.c.scan, bolumler={"donanim": hw})
        self.window.navigate("pc_detay")
        page = self.window.pages["pc_detay"]
        page.data_reloaded()
        self.qt.processEvents()
        text = [lbl.text() for lbl in page.findChildren(QLabel)]
        joined = "\n".join(text)
        self.assertIn("AMD Radeon 880M", joined)
        self.assertIn("NVIDIA RTX 5070 Laptop GPU", joined)
        nvidia = joined.index("NVIDIA RTX 5070 Laptop GPU")
        self.assertLess(nvidia, joined.index("AMD Radeon 880M"))  # oyunlarda kullanılan kart önce
        self.assertIn("VG27WQ1B", joined)
        self.assertIn(t("ui.ekran_adi", no=1), joined)  # genel ad yerine tahmin değil "Ekran 1"

    def test_toggle_on_off_and_revert_button(self):
        self.window = self.make_window()
        path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
        self.row("QOL", "QOL-001").switch.click()
        self.wait_idle()
        self.assertEqual(self.sys.read_reg("HKCU", path, "HideFileExt"), (0, "REG_DWORD"))
        self.assertTrue(self.window.c.engine.store.has("QOL-001"))
        self.assertTrue(self.row("QOL", "QOL-001").switch.isChecked())
        self.row("QOL", "QOL-001").switch.click()
        self.wait_idle()
        self.assertIsNone(self.sys.read_reg("HKCU", path, "HideFileExt"))
        self.assertFalse(self.window.c.engine.store.has("QOL-001"))

    def test_toggle_is_optimistic_and_reverts_when_cancelled(self):
        """C1: tıklanan durum anında görünür (sonuç beklenmez); risk onayı reddedilirse gerçek duruma döner."""
        self.window = self.make_window()
        row = self.row("SYS", "SYS-001")
        type(self).risky_answer = False
        saved = self.dialogs.confirm_careful
        self.dialogs.confirm_careful = lambda *a, **k: False  # kullanıcı vazgeçti
        try:
            seen = []
            original = self.window.toggle

            def spy(tweak, desired, done):
                seen.append((row.switch.isChecked(), row.switch.waiting))  # işlem başlarken görünüm
                original(tweak, desired, done)
            self.window.toggle = spy
            row.switch.click()
            self.wait_idle()
        finally:
            self.dialogs.confirm_careful = saved
            del self.window.toggle
        self.assertEqual(seen, [(True, True)])  # anında açık ve "bekliyor"
        self.assertFalse(row.switch.isChecked())  # vazgeçilince gerçek durum (kapalı)
        self.assertFalse(row.switch.waiting)
        self.assertFalse(self.window.c.engine.store.has("SYS-001"))  # hiçbir şey yazılmadı

    def test_long_uninstaller_list_is_drawn_in_chunks(self):
        from app.ui import page_kaldirici, widgets
        self.window = self.make_window()
        page = self.window._page("kaldirici")
        page.ensure_built()
        programs = [{"ad": f"Program {i}", "yayinci": "X", "surum": "1", "boyut_kb": 0, "korumali": False}
                    for i in range(150)]
        page._loaded((programs, []))
        drawn = lambda: sum(1 for c in page._list.findChildren(widgets.Card) if c.property("inlist"))  # noqa: E731
        self.assertEqual(drawn(), page_kaldirici.CHUNK)
        page._near_end(page.scroll.verticalScrollBar().maximum())
        self.assertEqual(drawn(), 2 * page_kaldirici.CHUNK)

    def test_careful_tweak_and_revert(self):
        self.window = self.make_window()
        self.row("SYS", "SYS-001").switch.click()
        self.wait_idle()
        self.assertEqual(self.sys.services["Spooler"]["baslangic"], "Disabled")
        self.row("SYS", "SYS-001")._revert()
        self.wait_idle()
        self.assertEqual(self.sys.services["Spooler"]["baslangic"], "Automatic")

    def test_selection(self):
        self.window = self.make_window()
        row = self.row("INP", "INP-006")
        kind, combo = row.controls["gecikme"]
        combo.setCurrentIndex(combo.findData("0"))
        row._apply()
        self.wait_idle()
        self.assertEqual(self.sys.read_reg("HKCU", r"Control Panel\Keyboard", "KeyboardDelay"), ("0", "REG_SZ"))

    def test_profile_and_revert_all(self):
        self.window = self.make_window()
        self.window.navigate("profiller")
        self.qt.processEvents()
        page = self.window.pages["profiller"]
        page._apply()
        self.wait_idle()
        self.assertTrue(self.window.c.engine.changed_ids())
        self.window.revert_all(lambda: None)
        self.wait_idle()
        self.assertEqual(self.window.c.engine.changed_ids(), [])

    def test_preview_mode_blocks_changes(self):
        self.window = self.make_window(mode="onizleme")
        row = self.row("QOL", "QOL-001")
        self.assertFalse(row.switch.isEnabled())
        self.window.toggle(self.window.c.by_id["QOL-001"], True, lambda: None)
        self.assertTrue(self.messages)  # "bu modda değiştirilemez" mesajı
        self.assertEqual(self.sys.reg, {})

    def test_risky_needs_confirmation_both_ways(self):
        self.window = self.make_window()
        tweak = self.window.c.by_id["PERF-003"]
        type(self).risky_answer = False
        self.window.toggle(tweak, True, lambda: None)
        self.wait_idle()
        self.assertEqual(self.risky_calls, [("PERF-003", True)])
        self.assertFalse(self.window.c.engine.store.has("PERF-003"))  # reddedildi: hiçbir şey yazılmadı
        type(self).risky_answer = True
        self.window.toggle(tweak, True, lambda: None)
        self.wait_idle()
        self.assertTrue(self.window.c.engine.store.has("PERF-003"))
        self.window.revert("PERF-003", lambda: None)
        self.wait_idle()
        self.assertEqual(self.risky_calls[-1], ("PERF-003", False))  # eski haline getirirken de iki ekran
        self.assertFalse(self.window.c.engine.store.has("PERF-003"))

    def test_placebo_page_lists_applied_items_first(self):
        self.window = self.make_window()
        self.window.navigate("PLC")
        self.qt.processEvents()
        page = self.window.pages["PLC"]
        self.assertNotIn("PLC-010", page._applied_ids)
        self.window.toggle(self.window.c.by_id["PLC-010"], True, lambda: None)
        self.wait_idle()
        self.qt.processEvents()
        self.assertIn("PLC-010", page._applied_ids)

    def test_off_only_switch_cannot_be_turned_on(self):
        self.window = self.make_window()
        row = self.row("PLC", "PLC-017")
        if self.window.c.states["PLC-017"].status not in ("acik", "kismen"):
            self.assertFalse(row.switch.isEnabled())

    def test_one_shot_action(self):
        self.window = self.make_window()
        tweak = self.window.c.by_id["PLC-023"]
        self.window.run_action(tweak, tweak["islem"]["eylemler"][0])
        self.wait_idle()
        records = self.window.c.engine.store.read_history("eylem")
        self.assertTrue(records and records[0]["id"] == "PLC-023")
        self.assertFalse(self.window.c.engine.store.has("PLC-023"))  # değişiklik listesine girmez

    def test_extra_info_setting(self):
        from app.core import settings
        settings.reset_cache()
        self.window = self.make_window()
        self.window.navigate("ayarlar")
        self.qt.processEvents()
        self.assertFalse(settings.get("ekstra_bilgi"))
        from app.ui.widgets import ToggleSwitch
        self.window.pages["ayarlar"].findChildren(ToggleSwitch)[0].click()
        self.assertTrue(settings.get("ekstra_bilgi"))
        settings.reset_cache()
        self.assertTrue(settings.get("ekstra_bilgi"))  # dosyaya yazıldı
        settings.set("ekstra_bilgi", False)

    def test_live_monitor_fills_tiles(self):
        self.window = self.make_window()
        page = self.window.pages["ozet"]
        self.window.show()  # offscreen: ekranda görünmez; sayfa "görünür" olunca izleme başlar
        end = time.time() + 5
        while page.last_sample is None and time.time() < end:
            self.qt.processEvents()
            time.sleep(0.02)
        self.assertIsNotNone(page.last_sample, "canlı örnek gelmedi")
        self.assertEqual(page.tiles["cpu"].value.text(), "%12")
        self.assertEqual(page.tiles["ram"].value.text(), "%25")
        self.assertTrue(page.tiles["ag"].value.text().startswith("↓ 1,0 Mbps"))
        self.window.navigate("QOL")  # sayfa gizlenince izleme durur
        self.qt.processEvents()
        self.assertFalse(self.window.live_monitor._active.is_set())

    def test_summary_tiles_open_lists(self):
        """Özet kutuları: uygun / açık / değiştirilen listesini açar ve kapatır; sayılar kutudakiyle aynı."""
        from PySide6.QtCore import QEvent
        from PySide6.QtWidgets import QPushButton
        self.window = self.make_window()
        self.window.toggle(self.window.c.by_id["PLC-010"], True, lambda: None)
        self.wait_idle()
        page = self.window.pages["ozet"]
        page.data_reloaded()
        counts = dict(zip(page.STATS, page._stat_values()))
        self.assertEqual(counts["degisen"], 1)
        for kind in ("uygun", "acik", "degisen"):
            page.stat_tiles[kind].clicked.emit()
            self.qt.processEvents()
            self.qt.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)  # önceki liste silinsin
            texts = [lbl.text() for lbl in page.detail_lay.parentWidget().findChildren(QLabel)]
            self.assertIn(t(f"ui.stat_liste.{kind}", adet=counts[kind]), texts)
            go = [b for b in page.detail_lay.parentWidget().findChildren(QPushButton) if b.text() == t("ui.ayara_git")]
            self.assertEqual(len(go), counts[kind])
        page.stat_tiles["degisen"].clicked.emit()  # aynı kutu: kapanır
        self.qt.processEvents()
        self.assertIsNone(page.detail_kind)
        self.assertEqual(page.detail_lay.count(), 0)

    def test_summary_findings_open_grouped_and_collapsible(self):
        """2.10: bulgular açık gelir, önem sırasıyla gruplu; "iyi" daralı; daraltma tercihi kalıcı; Çöz görünür."""
        from app.core import settings
        findings = [{"kod": "arka_plan_kaydi", "seviye": "uyari", "ilgili": ["PERF-002"], "params": {}},
                    {"kod": "arka_plan_kaydi", "seviye": "iyi", "ilgili": [], "params": {}},
                    {"kod": "arka_plan_kaydi", "seviye": "sorun", "ilgili": [], "params": {}}]
        saved = settings.get("bulgu_daralt")
        self.addCleanup(settings.set, "bulgu_daralt", saved)
        settings.set("bulgu_daralt", ["iyi"])
        self.window = self.make_window(findings=findings)
        page = self.window.pages["ozet"]
        page.ensure_built()
        self.assertEqual(list(page.finding_groups), ["sorun", "uyari", "iyi"])
        groups = page.finding_groups
        self.assertFalse(groups["sorun"][0].isHidden())
        self.assertFalse(groups["uyari"][0].isHidden())
        self.assertTrue(groups["iyi"][0].isHidden())
        solve = [b for b in groups["uyari"][0].findChildren(QPushButton) if b.text() == t("ui.coz")]
        self.assertEqual(len(solve), 1)
        groups["uyari"][1].click()
        self.assertEqual(settings.get("bulgu_daralt"), ["iyi", "uyari"])
        page.data_reloaded()  # yeniden kurulunca tercih korunur
        self.assertTrue(page.finding_groups["uyari"][0].isHidden())

    def test_about_has_quiet_donation_link_that_opens_in_browser(self):
        """3: Bilgi'de tek küçük bağış bağlantısı; yalnızca https + Buy Me a Coffee açılır; başka yerde bağış yok."""
        from unittest import mock
        from app.ui import page_settings as ps
        self.assertTrue(ps.donate_url_ok("https://buymeacoffee.com/forevermore"))
        for bad in ("http://buymeacoffee.com/x", "https://evil.example/buymeacoffee.com", "https://buymeacoffee.com.evil.example/x",
                    "", "javascript:alert(1)", "file:///C:/Windows"):
            self.assertFalse(ps.donate_url_ok(bad), bad)
        self.window = self.make_window()
        self.window.navigate("bilgi")
        links = [lbl for lbl in self.window.pages["bilgi"].findChildren(QLabel) if lbl.text().startswith("<a href=")]
        self.assertEqual(len(links), 1)
        self.assertIn(t("ui.bilgi.bagis"), links[0].text())
        with mock.patch.object(ps.os, "startfile") as start:
            links[0].linkActivated.emit("https://evil.example/")
            start.assert_not_called()
            links[0].linkActivated.emit("https://buymeacoffee.com/forevermore")
            start.assert_called_once_with("https://buymeacoffee.com/forevermore")
        self.assertEqual(len([lbl for lbl in self.window.findChildren(QLabel) if "buymeacoffee" in lbl.text()
                              and lbl.isVisibleTo(self.window) and lbl is not links[0]]), 0)

    def test_row_shows_impact_badge_only_when_loud(self):
        from app.ui import page_category
        self.window = self.make_window()
        seen = set()
        pages = [self.window._page(c["id"]) for c in self.window.c.categories]
        for page in pages:
            page.ensure_built()
        for tid, row in ((tid, row) for page in pages for tid, row in page.rows.items()):
            if not isinstance(row, page_category.TweakRow):
                continue
            level = row.tweak["performans_etkisi"]["seviye"]
            text = t("ui.etki", seviye=i18n.value_label("deger.etki", level))
            shown = any(lb.text() == text for lb in row.meta.findChildren(QLabel))
            self.assertEqual(shown, level in page_category.LOUD_IMPACT, tid)
            seen.add(shown)
        self.assertEqual(seen, {True, False})  # iki durum da sınandı

    def test_fix_button_applies_and_undoes(self):
        finding = {"kod": "arka_plan_kaydi", "seviye": "uyari", "ilgili": ["PERF-002"], "params": {}}
        self.window = self.make_window(findings=[finding])
        page = self.window.pages["ozet"]
        card = page.finding_cards[0]
        self.assertEqual(card.fix, {"tur": "ac", "id": "PERF-002"})
        card._solve()
        self.wait_idle()
        self.assertEqual(self.window.c.states["PERF-002"].status, "acik")
        self.assertTrue(self.window.c.engine.store.has("PERF-002"))  # yedek alındı, Değişiklikler'de görünür
        self.assertIs(page.finding_cards[0], card)  # sayfa yeniden kurulmadı, yalnızca kart güncellendi
        card._undo()
        self.wait_idle()
        self.assertFalse(self.window.c.engine.store.has("PERF-002"))

    def test_restore_point_question_choices(self):
        from app.core import settings
        for answer, expect_proceed, expect_pref in (
                (("atla", False), True, ""), (("atla", True), True, "atla"), ((None, False), False, "")):
            self.window = self.make_window()
            engine = self.window.c.engine
            engine.restore_point = None  # make_window hazırlık yapmış olabilir
            engine.accepted_without_restore_point = False
            settings.set("rp_sorma", "")
            self.dialogs.ask_restore_point = lambda *a, _r=answer, **k: _r
            outcome = []
            try:
                self.window.ensure_prepared(lambda: outcome.append("devam"), lambda: outcome.append("iptal"))
                self.assertEqual(outcome, ["devam"] if expect_proceed else ["iptal"])
                self.assertEqual(settings.get("rp_sorma"), expect_pref)
                self.assertEqual(engine.accepted_without_restore_point, expect_proceed)
            finally:
                settings.set("rp_sorma", "")
                self.dialogs.ask_restore_point = lambda *a, **k: ("olustur", False)

    def test_restore_point_failure_offers_system_protection(self):
        """3.1: nokta oluşmadı + koruma kapalı -> onayla açılır, ilk nokta oluşursa değişiklik sorusuz devam eder;
        grup ilkesiyle kapalıysa açılmaz, sebep yazılır ve eski 'yine de devam' sorusuna düşülür."""
        from app.engine import restore_point, system_protection as sp
        from tests.test_sistem_koruma import data
        self.window = self.make_window()
        saved = (self.app_module.admin.is_admin, sp.status, sp.enable)
        created = restore_point.RestorePointResult(restore_point.RestorePointResult.CREATED, "2026-10-31T12:00")
        failed = restore_point.RestorePointResult(restore_point.RestorePointResult.FAILED)
        self.app_module.admin.is_admin = lambda: True
        try:
            for state, expect in ((data(), "acildi"), (data(ilke_kapali=True), "ilke")):
                sp.status = lambda run=None, _s=state: _s
                sp.enable = lambda _system, _d, **_k: {"basarili": True, "adimlar": [("ac", True, "C:"),
                                                       ("sinir", True, "15.0 GB")], "nokta": created, "sinir_gb": 15,
                                                       "neden": None}
                self.messages.clear()
                outcome = []
                self.window._restore_point_result(failed, lambda: outcome.append("devam"),  # noqa: SLF001
                                                  lambda: outcome.append("iptal"))
                self.wait_for(lambda: outcome)
                self.assertEqual(outcome, ["devam"])
                if expect == "acildi":
                    self.assertIs(self.window.c.engine.restore_point, created)
                    self.assertIn(t("koruma.sonuc.acildi", surucu="C:"), self.messages[-1])
                else:
                    self.assertEqual(self.messages[-1], t("koruma.engel.ilke", surucu="C:"))
                    self.assertTrue(self.window.c.engine.accepted_without_restore_point)  # ask_yes_no sahtesi: evet
        finally:
            self.app_module.admin.is_admin, sp.status, sp.enable = saved

    def test_hero_next_advances_and_apply_is_primary(self):
        self.window = self.make_window(findings=[])
        card = self.window.pages["ozet"].recommendations
        texts = [b.text() for b in card.findChildren(QPushButton)]
        self.assertEqual(texts[0], t("ui.uygula"))
        if t("ui.oneri.sonra") in texts:
            first = card.pos
            card._next()
            self.assertNotEqual(card.pos, first)

    def test_recommendations_card_shows_apply_button(self):
        from PySide6.QtWidgets import QPushButton
        self.window = self.make_window(findings=[])
        card = self.window.pages["ozet"].recommendations
        self.assertGreaterEqual(len(card.findChildren(QPushButton)), 1)  # "Uygula" düğmeleri

    def test_fix_rechecks_only_that_item(self):
        """2.1: "Çöz" sonrası tam tarama (15-25 sn, tüm sayfalar yeniden kurulur) değil, yalnız bu madde okunur."""
        finding = {"kod": "arka_plan_kaydi", "seviye": "uyari", "ilgili": ["PERF-002"], "params": {}}
        self.window = self.make_window(findings=[finding])
        scans, rechecks, real = [], [], self.window.c.recheck
        self.window.start_scan = lambda: scans.append(1)
        self.window.c.recheck = lambda tid: rechecks.append(tid) or real(tid)
        self.window.pages["ozet"].finding_cards[0]._solve()
        self.wait_idle()
        self.wait_for(lambda: not self.window.pages["ozet"].busy_fixes)
        self.assertEqual(scans, [])
        self.assertEqual(rechecks, ["PERF-002"])

    def test_msconfig_limits_fixed_with_bcd_backup_and_recheck(self):
        """2.1: numproc/truncatememory bulgusu "Çöz" ile kaldırılır: önce BCD dışa aktarılır, sonra değer silinir,
        gerçek durum yeniden okunur ve bulgu listeden kalkar (tam tarama yok)."""
        self.window = self.make_window()
        self.sys.bcd.update({"numproc": "2", "truncatememory": "0x100000000"})
        self.window.c.refresh_one("PLC-005")
        finding = {"kod": "tespit", "seviye": "sorun", "ilgili": ["PLC-005"], "params": {"ad": "x", "mesaj": "y"}}
        self.window.c.scan["bulgular"] = [finding]
        from app.scan import checks
        original = checks._bcd_elements  # noqa: SLF001
        checks._bcd_elements = lambda: dict(self.sys.bcd)  # tespit sahte BCD'den okunur
        checks._bcd_elements.cache_clear = lambda: None
        scans = []
        self.window.start_scan = lambda: scans.append(1)
        try:
            self.window.pages["ozet"].data_reloaded()
            card = self.window.pages["ozet"].finding_cards[0]
            self.assertEqual(card.fix, {"tur": "kapat", "id": "PLC-005"})
            card._solve()
            self.wait_idle()
            self.wait_for(lambda: not self.window.pages["ozet"].busy_fixes)
        finally:
            checks._bcd_elements = original
        self.assertNotIn("numproc", self.sys.bcd)
        self.assertNotIn("truncatememory", self.sys.bcd)
        self.assertEqual(len(self.sys.bcd_exports), 1)       # BCD değişiklikten önce yedeklendi
        self.assertEqual(self.window.c.states["PLC-005"].status, "kapali")   # geri okundu
        self.assertEqual(self.window.c.scan["bulgular"], [])
        self.assertEqual(scans, [])

    def test_fix_turns_off_detected_placebo(self):
        self.window = self.make_window()
        tweak = self.window.c.by_id["PLC-010"]
        self.window.toggle(tweak, True, lambda: None)
        self.wait_idle()
        finding = {"kod": "tespit", "seviye": "uyari", "ilgili": ["PLC-010"], "params": {"ad": "x", "mesaj": "y"}}
        self.window.c.scan["bulgular"] = [finding]
        self.window.pages["ozet"].data_reloaded()
        card = self.window.pages["ozet"].finding_cards[0]
        self.assertEqual(card.fix["tur"], "kapat")
        card._solve()
        self.wait_idle()
        self.assertEqual(self.window.c.states["PLC-010"].status, "kapali")

    def test_startup_page_toggle_and_revert(self):
        self.window = self.make_window()
        self.window.navigate("baslangic")
        page = self.window.pages["baslangic"]
        end = time.time() + 5
        while page.data.get("uygulamalar") is None and time.time() < end:
            self.qt.processEvents()
            time.sleep(0.02)
        page._apps(page.data["uygulamalar"])  # liste yüklendi
        from app.ui.widgets import ToggleSwitch
        page.findChildren(ToggleSwitch)[0].click()
        self.wait_idle()
        self.assertTrue(self.window.c.engine.store.has("BAS-test"))
        self.assertTrue(self.sys.approved[("HKCU", "Approved", "Uygulama")].startswith("03"))
        self.window.revert("BAS-test", lambda: None)
        self.wait_idle()
        self.assertEqual(self.sys.approved, {})

    def test_service_start_type_change(self):
        self.window = self.make_window()
        self.sys.services["Foo"] = {"baslangic": "Automatic", "calisiyor": True}
        page = self.window._page("baslangic")
        page.ensure_built()
        page._apply_service({"id": "SRV-Foo", "ad": "Foo", "servis": "Foo", "baslangic": "Automatic",
                             "windows": False, "kilit": None}, "Manual")
        self.wait_idle()
        self.assertEqual(self.sys.services["Foo"]["baslangic"], "Manual")
        self.assertTrue(self.window.c.engine.store.has("SRV-Foo"))

    def test_service_filters(self):
        """Başlangıç türü süzgeci ve FPS listesi (kullanıcıya özel ekli servis adı önekle eşleşir)."""
        from app.ui.page_startup import fps_entry, fps_services
        self.window = self.make_window()
        self.sys.services.clear()
        self.sys.services.update({"SysMain": {"baslangic": "Automatic", "calisiyor": True},
                                  "Foo": {"baslangic": "Manual", "calisiyor": False},
                                  "BcastDVRUserService_1a2b3": {"baslangic": "Manual", "calisiyor": False}})
        page = self.window._page("baslangic")
        page.ensure_built()
        page.tab = "servisler"
        page.data["servisler"] = self.sys.list_services()

        def names():
            page.data_reloaded()
            self.qt.processEvents()
            return {lbl.toolTip() for lbl in page.findChildren(QLabel) if lbl.toolTip() and lbl.isVisibleTo(page)}

        page.start_filter = "el_ile"
        self.assertEqual(names(), {"Foo", "BcastDVRUserService_1a2b3"})
        page.start_filter, page.fps_only = "tumu", True
        self.assertEqual(names(), {"SysMain", "BcastDVRUserService_1a2b3"})
        entries = fps_services()
        self.assertEqual(fps_entry("BcastDVRUserService_1a2b3", entries)["ilgili"], "PERF-002")
        self.assertIsNone(fps_entry("SysMain_1", entries))  # önek eşleşmesi yalnızca işaretli servislerde
        for item in entries.values():  # her satırın kaynağı veritabanındaki bir ayarda
            self.assertIn(item["ilgili"], self.window.c.by_id)

    def test_msi_list_needs_risky_confirmation(self):
        self.window = self.make_window()
        from app.ui.managers_ui import DeviceListCard
        card = DeviceListCard(self.window, self.window.c.by_id["GPU-018"])
        device = self.sys.list_pci_devices()[0]
        from app.ui.widgets import ToggleSwitch
        switch = ToggleSwitch()
        switch.setChecked(True)
        type(self).risky_answer = False
        card._toggle(device, switch)
        self.wait_idle()
        self.assertFalse(self.window.c.engine.store.has("MSI-test"))
        type(self).risky_answer = True
        switch.setChecked(True)
        card._toggle(device, switch)
        self.wait_idle()
        self.assertTrue(self.window.c.engine.store.has("MSI-test"))
        self.assertIn(("GPU-018", True), self.risky_calls)

    def test_monitor_card_mode_and_scale(self):
        """Çözünürlük+Hz, ölçek ve ölçekleme modu ayrı değişiklik olarak yedeklenir ve geri alınır."""
        self.window = self.make_window()
        from app.ui.managers_ui import MonitorsCard
        card = MonitorsCard(self.window, self.window.c.by_id["DISP-001"])
        monitor = card._read_monitors()[0]
        keep = {"cevap": True}
        original = self.dialogs.ask_keep_display
        self.dialogs.ask_keep_display = lambda *_a, **_k: keep["cevap"]
        try:
            card._change(monitor, "mod", "1920x1080@144")
            self.settle(card)
            self.assertEqual(self.sys.monitors["TEST"]["mod"]["hz"], 144)
            self.assertTrue(self.window.c.engine.store.has(MonitorsCard.change_id(monitor, "mod")))
            card._change(card._read_monitors()[0], "olcek", "125")
            self.settle(card)
            self.assertEqual(self.sys.monitors["TEST"]["olcek"]["yuzde"], 125)
            keep["cevap"] = False  # kullanıcı "Geri dön" dedi: yalnızca bu değişiklik geri alınır
            card._change(card._read_monitors()[0], "mod", "1280x720@60")
            self.settle(card)
            self.settle(card)
            self.assertEqual(self.sys.monitors["TEST"]["mod"]["cozunurluk"], "1920x1080")
            self.assertEqual(self.sys.monitors["TEST"]["mod"]["hz"], 144)
        finally:
            self.dialogs.ask_keep_display = original
        card._revert(card._read_monitors()[0], ["mod", "olcek"])
        self.settle(card)
        self.settle(card)
        self.assertEqual(self.sys.monitors["TEST"]["mod"], {"cozunurluk": "1920x1080", "hz": 60,
                                                             "modlar": {"1920x1080": [144, 120, 60], "1280x720": [60]}})
        self.assertEqual(self.sys.monitors["TEST"]["olcek"]["yuzde"], 100)

    def test_monitor_card_layout_orientation_and_position(self):
        """Yön ve konum ayrı değişiklik olarak yedeklenir/geri alınır; üst üste binen konum reddedilir."""
        import copy
        self.window = self.make_window()
        second = copy.deepcopy(self.sys.monitors["TEST"])
        second.update(monitor_yolu="MON-TEST2", birincil=False)
        second["yerlesim"].update(x=1920)
        self.sys.monitors["TEST2"] = second
        from app.ui.managers_ui import MonitorsCard
        card = MonitorsCard(self.window, self.window.c.by_id["DISP-001"])
        keep = {"cevap": True}
        original = self.dialogs.ask_keep_display
        self.dialogs.ask_keep_display = lambda *_a, **_k: keep["cevap"]
        try:
            monitor = next(m for m in card._read_monitors() if m["aygit"] == "TEST2")
            card._change(monitor, "yon", "dikey")
            self.settle(card)
            self.assertEqual(self.sys.monitors["TEST2"]["yerlesim"]["yon"], "dikey")
            self.assertEqual(self.sys.monitors["TEST2"]["yerlesim"]["genislik"], 1080)  # yön değişince boyut yer değiştirir
            monitor = next(m for m in card._read_monitors() if m["aygit"] == "TEST2")
            card._change(monitor, "konum", "500,0")  # birincil ekranla (0..1920) çakışır
            self.settle(card)
            self.assertEqual(self.sys.monitors["TEST2"]["yerlesim"]["x"], 1920)
            self.assertFalse(self.window.c.engine.store.has(MonitorsCard.change_id(monitor, "konum")))
            card._change(monitor, "konum", "1920,300")
            self.settle(card)
            self.assertEqual(self.sys.monitors["TEST2"]["yerlesim"]["y"], 300)
        finally:
            self.dialogs.ask_keep_display = original
        card._revert(next(m for m in card._read_monitors() if m["aygit"] == "TEST2"), ["yon", "konum"])
        self.settle(card)
        self.settle(card)
        self.assertEqual(self.sys.monitors["TEST2"]["yerlesim"],
                         {"x": 1920, "y": 0, "genislik": 1920, "yukseklik": 1080, "yon": "yatay"})

    def test_laptop_gets_battery_switches(self):
        from tests.test_motor import LAPTOP
        self.window = self.make_window()
        self.window.c.engine._profile = LAPTOP
        self.window.c.refresh_all()
        self.assertIn("PWR-003", self.window.c.dc_variants)
        self.assertIn("PWR-003@pil", self.window.c.states)
        self.window.reload_pages()
        row = self.row("PWR", "PWR-003")
        self.assertIsNotNone(row.dc_switch)

    def settle(self, card):
        """Değişiklik + monitör kartının arka plan okuması (ve onun tetiklediği geri dönüş) bitene kadar."""
        for _ in range(3):
            self.wait_idle()
            self.wait_for(lambda: not card._reading and not card._after_read)
        self.wait_idle()

    def wait_for(self, condition, timeout=5):
        end = time.time() + timeout
        while not condition() and time.time() < end:
            self.qt.processEvents()
            time.sleep(0.02)
        self.assertTrue(condition(), "beklenen durum oluşmadı")

    def test_nvidia_cards_read_and_apply(self):
        self.window = self.make_window()
        self.sys.nvidia[0x00A879CF] = 138504007  # V-Sync kapalı
        page = self.window._page("GPU")
        self.window.navigate("GPU")
        card = page.rows["GPU-006"]
        self.wait_for(lambda: card.value != "okunuyor")
        self.assertEqual(card.combo.currentData(), 138504007)
        card.combo.setCurrentIndex(card.combo.findData(1199655232))
        card._apply()
        self.wait_idle()
        self.assertEqual(self.sys.nvidia[0x00A879CF], 1199655232)
        self.assertTrue(self.window.c.engine.store.has("GPU-006"))

    def test_nvidia_unavailable_offers_profile_inspector(self):
        self.window = self.make_window()
        self.sys.nvidia_ok = False
        page = self.window._page("GPU")
        self.window.navigate("GPU")
        card = page.rows["GPU-009"]
        self.wait_for(lambda: card.value != "okunuyor")
        self.assertIsNone(card.value)
        card._npi()
        self.wait_idle()
        self.assertEqual(self.sys.npi_imports, [[(0x0064B541, 1)]])
        self.assertEqual(self.sys.npi_hashes, ["ab" * 32])  # onaylanan dosyanın özeti çalıştırmadan önce yeniden denetlenir

    def test_npi_dialog_shows_hash_and_unsigned_warning_and_no_answer_runs_nothing(self):
        self.window = self.make_window()
        self.sys.nvidia_ok = False
        self.sys.npi_signed = False
        page = self.window._page("GPU")
        self.window.navigate("GPU")
        card = page.rows["GPU-009"]
        self.wait_for(lambda: card.value != "okunuyor")
        asked = []
        original = self.dialogs.ask_yes_no
        self.dialogs.ask_yes_no = lambda *a, **k: asked.append(a[2]) or False
        try:
            card._npi()
            self.wait_idle()
        finally:
            self.dialogs.ask_yes_no = original
        self.assertIn("ab" * 32, asked[0])
        self.assertIn(self.window.c.engine.system.npi_check()["sha256"], asked[0])
        self.assertIn("imzası geçerli değil", asked[0])
        self.assertEqual(self.sys.npi_imports, [])

    def test_audio_format_card(self):
        self.window = self.make_window()
        from app.ui.managers_ui import AudioDevicesCard
        card = AudioDevicesCard(self.window, self.window.c.by_id["AUD-002"])
        self.wait_for(lambda: card.body_lay.count() and "Okunuyor" not in str(
            getattr(card.body_lay.itemAt(0).widget(), "text", lambda: "")()))
        card._set_format({"cihaz": "TEST", "ad": "Hoparlör", "deger": "48000/16"}, "48000/24")
        self.wait_idle()
        self.assertEqual(self.sys.audio_formats["TEST"], "48000/24")

    def test_games_scan_after_restart_uses_cache_and_shows_errors(self):
        """A3: yeniden başlatma sonrası son tarama hemen görünür; yeni tarama başarısızsa sebep ve düğme çıkar."""
        from unittest import mock
        from app.games import discovery
        discovery.save_cache([discovery._game("Önbellekteki Oyun", r"C:\Oyunlar\A", "Steam")], {})
        self.window = self.make_window()

        def broken(errors=None):
            raise OSError("disk okunamadı")
        with mock.patch.object(discovery, "discover", broken):
            self.window.navigate("oyunlar")
            page = self.window.pages["oyunlar"]
            self.assertEqual([g["ad"] for g in page.found], ["Önbellekteki Oyun"])
            self.wait_for(lambda: not page.scanning)
        self.qt.processEvents()
        labels = " ".join(lbl.text() for lbl in page.findChildren(QLabel))
        self.assertIn("disk okunamadı", labels)
        self.assertIn(t("ui.oyun_yeniden_tara"), [b.text() for b in page.findChildren(QPushButton)])
        self.assertEqual([g["ad"] for g in page.found], ["Önbellekteki Oyun"])  # liste kaybolmadı
        page._rescan()
        self.wait_for(lambda: not page.scanning)
        self.assertIsNone(page.scan_error)

    def test_gpu_page_groups_settings_per_card_on_hybrid(self):
        """B2: hibritte NVIDIA ve AMD ayarları kart adı ve rolüyle ayrı başlıklar altında; genel olanlar en sonda."""
        self.window = self.make_window()
        self.window.c.scan = dict(MINIMAL_SCAN, bolumler={"donanim": {"gpu": [
            {"ad": "AMD Radeon(TM) Graphics", "uretici": "AMD", "rol": "guc_tasarrufu", "ekran_suruyor": ["D1"]},
            {"ad": "NVIDIA GeForce RTX 4060 Laptop GPU", "uretici": "NVIDIA", "rol": "yuksek_performans",
             "ekran_suruyor": []}]}})
        page = self.window._page("GPU")
        tweaks = [tw for tw in self.window.c.tweaks if tw["kategori_id"] == "GPU"]
        groups = page._by_gpu(tweaks)
        headings = [h for h, _items, _note in groups]
        self.assertIn("NVIDIA GeForce RTX 4060 Laptop GPU", headings[0])
        self.assertIn(t("ui.gpu_grup.cizen"), headings[0])
        self.assertIn(t("ui.gpu_grup.ekran"), headings[1])
        self.assertTrue(all("NVIDIA" in tw["uyumluluk"]["gpu"] for tw in groups[0][1]))
        self.assertEqual(sum(len(items) for _h, items, _n in groups), len(tweaks))  # hiçbir ayar kaybolmadı
        # 3.4: oyunları NVIDIA çiziyor; AMD ayarlarının oyunu etkilemediği yazar, NVIDIA'nınki yazmaz
        self.assertEqual([n for _h, _i, n in groups][:2], [None, t("ui.gpu_grup.cizmiyor")])

    def test_manual_gpu_vendor_when_not_detected(self):
        from unittest import mock
        from app.core import settings
        from app.engine import compat, resolvers
        scan = {"bolumler": {"sistem": {"windows": {"surum": "10", "build": 19045}}, "donanim": {"gpu": []}}}
        with mock.patch.object(resolvers, "gpu_vendors", lambda: []):
            settings.set("gpu_markasi_elle", "")
            self.assertEqual(compat.SystemProfile.from_scan(scan).gpu_vendors, [])
            settings.set("gpu_markasi_elle", "AMD")
            self.assertEqual(compat.SystemProfile.from_scan(scan).gpu_vendors, ["AMD"])
            settings.set("gpu_markasi_elle", "")

    def test_store_restore_card_flow(self):
        """B1: durum okunur, eksik uygulamada Geri yükle; başarısızlıkta sebep ve alternatif yollar yazılır."""
        from unittest import mock
        from app.engine import store_restore
        missing = {"ad": "Microsoft.WindowsStore", "anahtar": "store", "kurulu": False, "manifest": None,
                   "saglanmis": False}
        data = {"derleme": 19045, "paketler": [missing], "servisler": [], "uyarilar": [("store_geri.uyari.wu_kapali", {})]}
        self.window = self.make_window()
        self.window.navigate("kaldirici")
        page = self.window.pages["kaldirici"]
        with mock.patch.object(store_restore, "status", lambda: data), \
                mock.patch.object(store_restore, "restore", lambda *a, **k: {"basarili": False, "yontemler": [],
                                                                            "neden": "dosya_yok", "hata": None}):
            page._check_apps()
            self.wait_for(lambda: isinstance(page.apps, dict))
            labels = " ".join(lbl.text() for lbl in page.findChildren(QLabel))
            self.assertIn(t("store_geri.uyari.wu_kapali"), labels)
            page._restore_app(missing)
            self.wait_for(lambda: page.app_result is not None)
        self.qt.processEvents()
        labels = " ".join(lbl.text() for lbl in page.findChildren(QLabel))
        self.assertIn(t("store_geri.alternatif"), labels)
        self.assertTrue(any(t("store_geri.neden.dosya_yok", ad=t("store_geri.paket.store")) in m for m in self.messages))

    def test_nvidia_overlay_card_reports_real_process_state(self):
        """A4: bindirme yasaklanınca 'uygulandı' yerine NVIDIA Overlay süreçlerinin gerçek durumu yazılır."""
        from unittest import mock
        from app.ui import managers_ui
        self.window = self.make_window()
        tweak = self.window.c.by_id["GPU-022"]
        with mock.patch.object(managers_ui, "running_count", lambda exe: 5 if exe == "nvidia overlay.exe" else 0):
            card = managers_ui.NvidiaSettingCard(self.window, tweak)
            card.set_value({"deger": 1, "ozel": True})
            self.assertTrue(card.process_state.isVisibleTo(card))
            self.assertEqual(card.process_state.text(), t("ui.nvidia_bindirme_suruyor", adet=5))
            card.set_value({"deger": 0, "ozel": False})
            self.assertFalse(card.process_state.isVisibleTo(card))
        with mock.patch.object(managers_ui, "running_count", lambda exe: 0):
            card.set_value({"deger": 1, "ozel": True})
            self.assertEqual(card.process_state.text(), t("ui.nvidia_bindirme_kapali"))

    def test_games_advanced_and_rebuild_keep_scroll(self):
        """2.3: "Gelişmiş ayarları göster" ve sayfanın yeniden kurulması (ör. oyun taraması bitince) en üste atmaz."""
        self.window = self.make_window()
        self.window.resize(1100, 640)
        self.window.show()
        store = self.window.game_store
        for game in list(store.games):
            store.remove(game["id"])
        game = store.add("Oyun", r"C:\Oyun", "Elle", r"C:\Oyun\oyun.exe")
        self.window.navigate("oyunlar")
        page = self.window._page("oyunlar")
        page.found, page.editing = [], game["id"]
        page.data_reloaded()
        for _ in range(20):
            self.qt.processEvents()
            time.sleep(0.02)
        bar = page.scroll.verticalScrollBar()
        bar.setValue(bar.maximum() // 2)
        position = bar.value()
        self.assertGreater(position, 0)
        button = next(b for b in page.findChildren(QPushButton) if b.text() == t("ui.oyun_gelismis_goster"))
        button.click()
        self.qt.processEvents()
        self.assertEqual(bar.value(), position)
        page.data_reloaded()
        for _ in range(3):
            self.qt.processEvents()
        self.assertEqual(bar.value(), position)
        store.remove(game["id"])

    def test_games_page_saves_persistent_settings(self):
        self.window = self.make_window()
        from app.games import profiles
        store = self.window.game_store
        for game in list(store.games):
            store.remove(game["id"])
        game = store.add("Oyun", r"C:\Oyun", "Elle", r"C:\Oyun\oyun.exe")
        page = self.window._page("oyunlar")
        page.found = []
        page.editing = game["id"]
        page.ensure_built()
        page.draft.update(oncelik="AboveNormal", fso_kapali=True, guc_plani=True)
        page._save(game)
        self.wait_idle()
        self.wait_for(lambda: not self.window.busy and self.window.c.engine.store.has(game["id"] + "-fso"))
        ifeo = profiles.IFEO + r"\oyun.exe\PerfOptions"
        self.assertEqual(self.sys.read_reg("HKLM", ifeo, "CpuPriorityClass")[0], 6)
        self.assertIn(profiles.FSO_FLAG, self.sys.read_reg("HKCU", profiles.LAYERS_KEY, r"C:\Oyun\oyun.exe")[0])
        self.assertTrue(self.window.c.engine.store.has(game["id"] + "-oncelik"))
        self.assertIsNotNone(self.window.game_watcher)  # oyun sırasında ayarı var: izleyici çalışıyor
        self.window.revert(game["id"] + "-oncelik", lambda: None)
        self.wait_idle()
        self.assertIsNone(self.sys.read_reg("HKLM", ifeo, "CpuPriorityClass"))
        self.window.game_watcher.stop()
        store.remove(game["id"])

    def test_games_page_preset_fills_draft_without_applying(self):
        self.window = self.make_window()
        store = self.window.game_store
        for game in list(store.games):
            store.remove(game["id"])
        game = store.add("Oyun", r"C:\Oyun", "Elle", r"C:\Oyun\oyun.exe")
        page = self.window._page("oyunlar")
        page.found = []
        page.editing = game["id"]
        page.ensure_built()
        page._apply_preset("performans")
        self.wait_idle()
        self.assertEqual((page.draft["oncelik"], page.draft["guc_plani"], page.draft["servisleri_duraklat"]),
                         ("High", True, False))
        self.assertEqual(self.window.c.engine.changed_ids(), [])  # Kaydet'e basılana kadar hiçbir şey uygulanmaz
        self.assertEqual(store.get(game["id"])["profil"]["oncelik"], "Normal")
        store.remove(game["id"])

    def test_boost_page_lists_memory_holders_read_only(self):
        from PySide6.QtWidgets import QLabel, QPushButton
        self.window = self.make_window()
        self.assertIn("boost", self.window.nav)
        page = self.window._page("boost")
        page.loading = False
        page.data = {"en_cok_bellek": [{"ad": "chrome", "adet": 12, "cpu_yuzde": 1.0, "bellek_mb": 2048, "kategori": None}],
                     "bilinen_arka_plan": [{"ad": "Discord", "adet": 3, "cpu_yuzde": 0.1, "bellek_mb": 400,
                                            "kategori": "iletisim"}]}
        page.ensure_built()
        texts = " ".join(label.text() for label in page.findChildren(QLabel))
        self.assertIn("chrome ×12", texts)
        self.assertIn("Discord ×3", texts)
        buttons = [b.text() for b in page.findChildren(QPushButton)]
        self.assertEqual(buttons.count(t("ui.boost.kapat")), 2)  # chrome ve Discord; korumalı program yok
        from unittest import mock
        calls = []
        with mock.patch("app.ui.page_boost.closer.close_gently", side_effect=lambda n: calls.append(n) or "kapandi"):
            page._close({"ad": "chrome", "adet": 12})
            self.wait_idle()
        self.assertEqual(calls, ["chrome"])  # ask_yes_no testlerde onaylı
        row = page._row({"ad": "explorer", "adet": 1, "bellek_mb": 100, "kategori": None})  # korumalı: Kapat düğmesi yok
        self.assertEqual([b.text() for b in row.findChildren(QPushButton)], [])

    def test_uninstaller_page_flow_with_fake_data(self):
        """Liste -> Kaldır (kendi kaldırıcısı) -> kalıntı tara -> yedekleyip kaldır -> geri yükle; gerçek sisteme dokunulmaz."""
        from unittest import mock
        from PySide6.QtWidgets import QCheckBox, QPushButton
        self.window = self.make_window()
        self.assertIn("kaldirici", self.window.nav)
        page = self.window._page("kaldirici")
        foo = {"ad": "Foo Tool", "surum": "1.0", "yayinci": "Foo", "konum": "", "komut": "foo.exe /S", "boyut_kb": 2048,
               "kok": "HKLM", "anahtar": "K/Foo", "korumali": False}
        vcpp = dict(foo, ad="Microsoft Visual C++ 2015", anahtar="K/Vc", korumali=True)
        programs, started, removed = [foo, vcpp], [], []
        found = [{"tur": "klasor", "yol": "C:/x/Foo Tool", "boyut": 1048576}, {"tur": "kayit", "kok": "HKCU", "yol": "Software/Foo"}]
        un = "app.ui.page_kaldirici.uninstaller."
        with mock.patch(un + "list_programs", side_effect=lambda: list(programs)),                 mock.patch(un + "list_sessions", return_value=[]),                 mock.patch(un + "start_uninstall", side_effect=lambda p: started.append(p["ad"]) or True),                 mock.patch(un + "find_leftovers", return_value=found),                 mock.patch(un + "remove_leftovers", side_effect=lambda n, items: removed.append((n, len(items))) or
                           {"oturum": "20261029-120000", "kaldirilan": len(items), "basarisiz": []}):
            page.on_show()
            self.wait_idle()
            buttons = [b.text() for b in page.findChildren(QPushButton)]
            self.assertEqual(buttons.count(t("ui.kaldirici.kaldir")), 1)        # korumalı programın Kaldır düğmesi yok
            page._uninstall(foo)
            self.assertEqual(started, ["Foo Tool"])
            self.assertIsNotNone(page.pending)
            programs.remove(foo)                                                # kaldırıcı bitti
            page._scan()
            self.wait_idle()
            boxes = page.findChildren(QCheckBox)
            self.assertEqual(len(boxes), 2)
            boxes[1].setChecked(False)                                          # kayıt anahtarını işaretsiz bırak
            page._remove()
            self.wait_idle()
            self.assertEqual(removed, [("Foo Tool", 1)])
            self.assertIsNone(page.pending)

    def test_uninstaller_does_not_scan_while_program_is_still_installed(self):
        from unittest import mock
        self.window = self.make_window()
        page = self.window._page("kaldirici")
        foo = {"ad": "Foo", "surum": "", "yayinci": "", "konum": "", "komut": "f.exe", "boyut_kb": 0, "kok": "HKLM",
               "anahtar": "K/Foo", "korumali": False}
        un = "app.ui.page_kaldirici.uninstaller."
        with mock.patch(un + "list_programs", return_value=[foo]), mock.patch(un + "list_sessions", return_value=[]),                 mock.patch(un + "find_leftovers", return_value=[{"tur": "klasor", "yol": "C:/Foo"}]):
            page.on_show()
            self.wait_idle()
            page.pending = foo
            page._scan()
            self.wait_idle()
            self.assertIsNone(page.leftovers)                                   # hâlâ kurulu: kalıntı listesi açılmadı

    def test_boost_list_and_one_click_boost(self):
        from unittest import mock
        from app.core import settings
        self.window = self.make_window()
        page = self.window._page("boost")
        page.loading = False
        page.data = {"en_cok_bellek": [{"ad": "chrome", "adet": 2, "cpu_yuzde": 0, "bellek_mb": 900, "kategori": None}],
                     "bilinen_arka_plan": []}
        settings.set("boost_listesi", [])
        try:
            page.ensure_built()
            page._toggle_listed("chrome", True)
            page._toggle_listed("Chrome", True)  # aynı ad (büyük/küçük harf) iki kez eklenmez
            self.assertEqual(settings.get("boost_listesi"), ["Chrome"])
            page._toggle_listed("chrome", False)
            self.assertEqual(settings.get("boost_listesi"), [])
            settings.set("boost_listesi", ["chrome", "discord"])
            calls = {"kapat": [], "zorla": []}
            with mock.patch("app.ui.page_boost.closer.running", side_effect=lambda names: list(names)),                     mock.patch("app.ui.page_boost.closer.close_many",
                               side_effect=lambda names: calls["kapat"].append(list(names)) or
                               {"chrome": "kapandi", "discord": "calisiyor"}),                     mock.patch("app.ui.page_boost.closer.kill", side_effect=lambda n: calls["zorla"].append(n) or 1):
                page._boost()
                self.wait_for(lambda: calls["zorla"])  # çalışma, onay ve zorla sonlandırma art arda arka planda
            self.assertEqual(calls["kapat"], [["chrome", "discord"]])
            self.assertEqual(calls["zorla"], ["discord"])  # yalnızca kapanmayan, ikinci onayla (testte onaylı)
        finally:
            settings.set("boost_listesi", [])

    def test_one_click_boost_turns_on_safe_settings_and_can_undo(self):
        """Tek tuş Boost: Oyun Modu + Game DVR kapalı (motor yolundan, geri alınabilir); bellek boşaltma vb. yok."""
        from unittest import mock
        from app.core import settings
        self.window = self.make_window()
        page = self.window._page("boost")
        page.loading = False
        page.data = {"en_cok_bellek": [], "bilinen_arka_plan": []}
        settings.set("boost_listesi", [])
        settings.set("boost_ayarlari", [])
        try:
            page.ensure_built()
            pending = [tw["id"] for tw in page._pending_tweaks()]
            self.assertIn("PERF-002", pending)                                  # FakeSystem'de Oyun Modu zaten açık olabilir
            with mock.patch("app.ui.page_boost.closer.running", side_effect=lambda names: []):
                page._boost()
                self.wait_for(lambda: len(settings.get("boost_ayarlari")) == len(pending))
            self.wait_idle()
            self.assertEqual(sorted(settings.get("boost_ayarlari")), sorted(pending))
            self.assertTrue(all(self.window.c.engine.store.has(i) for i in pending))
            self.assertEqual(page._pending_tweaks(), [])                       # artık açık: tekrar basınca "zaten hazır"
            page._undo_boost()
            self.wait_for(lambda: not any(self.window.c.engine.store.has(i) for i in pending))
            self.assertEqual(settings.get("boost_ayarlari"), [])
        finally:
            settings.set("boost_listesi", [])
            settings.set("boost_ayarlari", [])

    def test_games_page_guide_links(self):
        from PySide6.QtWidgets import QPushButton
        self.window = self.make_window()
        page = self.window._page("oyunlar")
        box = page._guide_row({"ad": "Valorant"})  # kutu tutulmazsa düğmeleri de silinir
        links = lambda widget: [b for b in widget.findChildren(QPushButton) if b.text() != "i"]  # "i": bilgi düğmesi
        self.assertGreaterEqual(len(links(box)), 1)
        empty = page._guide_row({"ad": "Yok Oyun"})
        self.assertEqual(links(empty), [])

    def test_games_page_picker_and_auto_apply_off(self):
        """Açılır listeden bulunan oyun eklenir; 'otomatik uygula' kapalıyken kalıcı ayar yazılmaz, izleyici çalışmaz."""
        self.window = self.make_window()
        from app.games import profiles
        store = self.window.game_store
        for game in list(store.games):
            store.remove(game["id"])
        page = self.window._page("oyunlar")
        page.found = [{"ad": "Bulunan", "klasor": r"C:\Bulunan", "kaynak": "Steam", "exe": r"C:\Bulunan\b.exe"}]
        page.ensure_built()
        page._picked(("bulunan", page.found[0]))
        self.assertEqual(store.games[0]["ad"], "Bulunan")
        game = store.games[0]
        self.assertEqual(page.editing, game["id"])
        page.data_reloaded()
        self.qt.processEvents()
        page.draft.update(otomatik=False, oncelik="AboveNormal", guc_plani=True)
        page._save(game)
        self.wait_idle()
        ifeo = profiles.IFEO + r"\b.exe\PerfOptions"
        self.assertIsNone(self.sys.read_reg("HKLM", ifeo, "CpuPriorityClass"))
        self.assertEqual(store.get(game["id"])["profil"]["oncelik"], "AboveNormal")  # seçim saklandı
        self.assertFalse(store.runtime_games())
        store.remove(game["id"])

    def test_placebo_page_toggles_other_menus_and_services(self):
        self.window = self.make_window()
        self.sys.services.clear()
        self.sys.services.update({"Spooler": {"baslangic": "Disabled", "calisiyor": False}})
        self.window.navigate("PLC")
        page = self.window.pages["PLC"]
        others = [i["id"] for i in self.window.c.placebo_menu["diger_kategorilerde_placebo_veya_zararli"]
                  if self.window.c.by_id.get(i["id"], {}).get("sinif") == "SWITCH"
                  and self.window.c.availability[i["id"]].visible]
        self.assertTrue(others)
        for tweak_id in others:
            self.assertIn(tweak_id, page.rows)  # diğer menülerdeki placebo ayar burada da anahtar
        texts = lambda: " ".join(lbl.text() for lbl in page.findChildren(QLabel))  # noqa: E731
        self.wait_for(lambda: "Print Spooler" in texts() or "Spooler" in texts())
        self.assertIn("devre dışı", texts())

    def test_settings_page_and_tray_close(self):
        from app.core import settings
        self.window = self.make_window()
        self.window.navigate("ayarlar")
        page = self.window.pages["ayarlar"]
        self.wait_for(lambda: page.autostart is not None)
        labels = lambda p: " ".join(lbl.text() for lbl in p.findChildren(type(p.header.itemAt(0).widget()))  # noqa: E731
                                    if hasattr(lbl, "text"))
        self.assertNotIn("smileyw", labels(page))  # bilgi bölümü Ekstra ayarlar'dan kaldırıldı
        self.window.navigate("bilgi")
        about = self.window.pages["bilgi"]
        text = labels(about)
        self.assertIn("Kubilay Paşa", text)
        self.assertNotIn("smileyw", text)
        settings.set("tepsiye_kucult", True)
        self.window.update_tray()
        if self.window.tray is not None:  # bazı test ortamlarında sistem tepsisi yok
            self.window.show()
            self.window.close()
            self.assertFalse(self.window.isVisible())  # kapatınca tepsiye gizlendi
            self.assertFalse(self.window.worker.closed)  # uygulama çalışmaya devam ediyor
        settings.set("tepsiye_kucult", False)
        self.window.update_tray()
        self.assertIsNone(self.window.tray)

    def test_measure_page_system_measurement(self):
        from unittest import mock
        self.window = self.make_window()
        self.window.navigate("olcum")
        page = self.window.pages["olcum"]
        for item in list(page.store.items):
            page.store.remove(item["id"])
        with mock.patch("app.measure.system_measure.time.sleep", lambda _s: None):
            page._run_system("once", 3)
            self.wait_for(lambda: page.running is None)
            page._run_system("sonra", 3)
            self.wait_for(lambda: page.running is None)
        self.assertEqual(len(page.store.items), 2)
        self.assertEqual(len(page.selected), 2)  # "Sonra" otomatik olarak "Önce" ile karşılaştırıldı
        self.assertIsNotNone(page._pair())

    def test_measure_page_failure_screen_and_process_list(self):
        """A5: 'yeterli kare yok' genel kutu değil teşhis kartı; liste kayıtlı oyunları içerir."""
        from app.measure import presentmon
        self.window = self.make_window()
        self.window.game_store.add("Deneme Oyunu", r"C:\Oyun", "Elle", r"C:\Oyun\deneme.exe")
        self.window.navigate("olcum")
        page = self.window.pages["olcum"]
        page._refresh_choices(rebuild=False)
        self.assertIn("deneme.exe", [c["exe"] for c in page.choices])
        if presentmon.find_presentmon() is None:
            self.skipTest("PresentMon tools klasöründe yok")
        page.failure = {"surec": "deneme.exe", "neden": "surec", "pidler": [], "kare_hedef": 0, "kare_dwm": 900,
                        "kare_on_planda": 0, "on_plan_sn": 60, "yontem": "PresentMon", "log": ["satır"]}
        self.window.navigate("olcum")
        self.qt.processEvents()
        texts = [b.text() for b in page.findChildren(QPushButton)]
        self.assertIn(t("olcum.log_kopyala"), texts)
        self.assertIn(t("olcum.sureyi_uzat"), texts)
        labels = " ".join(lbl.text() for lbl in page.findChildren(QLabel))
        self.assertIn(t("olcum.neden.surec"), labels)
        self.assertEqual(self.messages, [])  # genel hata kutusu açılmadı

    def test_report_includes_app_activity_without_paths(self):
        self.window = self.make_window()
        store = self.window.game_store
        game = store.add("Deneme Oyunu", r"C:\GizliKlasor", "Elle", r"C:\GizliKlasor\deneme.exe")
        step = {"tur": "yerlesik", "eylem": "baslangic_onayi", "parametreler": {"kok": "HKCU", "yol": "A", "ad": "X"}}
        self.window.apply_custom("BAS-r", "Başlangıç: Deneme", [step], [False], lambda: None)
        self.wait_idle()
        self.window.c.engine.store.history("npi", "GPU-009", True, "test")
        self.window.navigate("rapor")
        self.qt.processEvents()
        from PySide6.QtWidgets import QPlainTextEdit
        text = self.window.pages["rapor"].findChildren(QPlainTextEdit)[0].toPlainText()
        self.assertIn("UYGULAMANIN YAPTIĞI DEĞİŞİKLİKLER", text)
        self.assertIn("Başlangıç: Deneme", text)
        self.assertIn("Deneme Oyunu (deneme.exe)", text)
        self.assertNotIn("GizliKlasor", text)  # oyun yolları rapora girmez
        self.assertIn(self.window.c.by_id["GPU-009"]["ad"], text)  # NPI: geri alınamaz işlemler
        store.remove(game["id"])

    def test_cache_round_trip(self):
        self.window = self.make_window()
        self.window.c.save_cache()
        from app.ui.controller import Controller
        other = Controller("onizleme", engine=self.window.c.engine, cache_file=self.window.c.cache_file)
        self.assertTrue(other.load_cache())
        self.assertEqual(set(other.states), set(self.window.c.states))
        self.assertFalse(other.fresh)  # önbellekteki durumlarla değişiklik yapılamaz


if __name__ == "__main__":
    unittest.main()
