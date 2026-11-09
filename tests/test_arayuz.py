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
    from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QPlainTextEdit, QPushButton, QScrollArea, QWidget
except ImportError:  # pragma: no cover
    QApplication = QLabel = QPlainTextEdit = QPushButton = QScrollArea = QWidget = None

from app.core import i18n
from app.core.i18n import fmt_percent, t
from app.engine.backup import BackupStore
from app.games import profiles
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
        from app.core import temizlik_olcum
        cls._saved_olcum = temizlik_olcum.is_enabled
        temizlik_olcum.is_enabled = lambda: False
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
        from app.core import temizlik_olcum
        temizlik_olcum.is_enabled = cls._saved_olcum
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
        keys = ["ozet", "pc_detay", "profiller", "degisiklikler", "rapor", "ayarlar", "bilgi", "elle", "temizlik",
                "oyunlar", "boost", "kaldirici", "baslangic", "olcum", "rehber"] + [c["id"] for c in self.window.c.categories]
        with self.assertNoLogs(level="ERROR"):  # Denetim B O8: kurulum sırasında yutulan hata olmasın
            for key in keys:
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

    def test_nav_bar_fits_narrow_window(self):
        """400-700 px: çubuk düğmeleri adsız kalır (ad ipucunda), üst şerit yalnızca logo + arama; çubuk pencereye sığar.
        (Pencereyi gerçekten daraltmak sayfaların en küçük genişliğine takılır; bu yüzden genişlik mantığı doğrudan çağrılır.)"""
        self.window = window = self.make_window()
        for width in (500, 600, 700):  # uygulamanın en küçük penceresi 900; 9 öğeli çubuk adsız kipte ≥ ~440 px'e sığar
            window._apply_width(width)
            for item in (*window.nav_groups.values(), window.nav["ozet"], window.nav["GPU"]):
                self.assertTrue(item.text.isHidden(), width)
                self.assertTrue(item.toolTip())
            self.assertTrue(window.brand_name.isHidden())
            self.assertEqual(window.search_box.width(), 180)
            self.assertLessEqual(window.nav_bar.minimumSizeHint().width(), width - 16, width)
            self.assertLessEqual(window.nav_strips["optimizasyonlar"].minimumSizeHint().width(), width - 16, width)  # şerit de (en geniş grup)
        window._apply_width(900)  # en küçük pencerede adlı çubuk ve şerit sığar
        self.assertFalse(window.nav["ozet"].text.isHidden())
        self.assertLessEqual(window.nav_bar.minimumSizeHint().width(), 900 - 32)
        window.navigate("GPU")
        self.assertLessEqual(window.nav_strips["optimizasyonlar"].minimumSizeHint().width(), 900 - 32)
        window._apply_width(1000)
        self.assertFalse(window.nav["ozet"].text.isHidden())  # geniş pencerede adlar geri gelir
        self.assertFalse(window.brand_name.isHidden())
        self.assertEqual(window.search_box.width(), 300)

    def test_nav_bar_fits_900_english_readable_font(self):
        """EN dili + okunabilir yazı (Verdana; yoksa yüklü en geniş yazı tipi): çubuk ve şerit 900 px pencereye sığar."""
        from unittest import mock
        from PySide6.QtGui import QFont, QFontDatabase, QFontMetrics
        from app.core import i18n
        from app.ui import theme
        if "Verdana" not in QFontDatabase.families():  # ekran dışı kipte sistem yazı tipleri yüklü gelmez
            import glob
            for f in glob.glob(os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "verdana*.ttf")):
                QFontDatabase.addApplicationFont(f)
        families = QFontDatabase.families()
        wide ="Verdana" if "Verdana" in families else max(
            families, key=lambda f: QFontMetrics(QFont(f, 12)).horizontalAdvance("Optimizations Customizations"))
        real_ui_font = theme.ui_font

        def wide_font(size=theme.BODY_SIZE, bold=False):
            font = real_ui_font(size + 1, bold)
            font.setFamily(wide)
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.3)
            return font

        i18n.load("en")
        try:
            with mock.patch.object(theme.settings, "get", lambda key: True if key == "okunabilir_yazi" else
                                   theme.settings.DEFAULTS.get(key)), mock.patch.object(theme, "ui_font", wide_font):
                self.window = window = self.make_window()
                window._apply_width(900)
                window.navigate("GPU")
                self.assertEqual(window.nav["GPU"].text.font().family(), wide)  # yazı tipi gerçekten uygulandı
                self.assertLessEqual(window.nav_bar.minimumSizeHint().width(), 900 - 32, wide)
                self.assertLessEqual(window.nav_strips["optimizasyonlar"].minimumSizeHint().width(), 900 - 32, wide)
        finally:
            i18n.load("tr")

    def test_group_button_closes_open_tools_panel(self):
        """Zaten grubun içindeyken Araçlar paneli açıksa grup düğmesine basmak paneli kapatır; sayfa ve geçmiş değişmez."""
        self.window = window = self.make_window()
        window.navigate("GPU")
        window._open_panel("araclar")
        self.assertEqual(window._panel_open, "araclar")
        current, history = window.current, list(window._history)
        window._open_group("optimizasyonlar")
        self.assertIsNone(window._panel_open)
        self.assertEqual(window.current, current)
        self.assertEqual(window._history, history)

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

    def test_search_keyboard_moves_through_results_and_enter_opens_current(self):
        """Denetim B B5: Aşağı/Yukarı sonuçlarda gezer, Tab bağış düğmesine atlamaz, Enter seçili sonucu açar."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        self.window = window = self.make_window()
        box = window.search_box
        calls = []
        box._on_tweak = calls.append
        box.edit.setText("ekran")
        self.assertGreater(box.results.count(), 2)
        QTest.keyClick(box.edit, Qt.Key.Key_Down)
        QTest.keyClick(box.edit, Qt.Key.Key_Down)
        self.assertEqual(box.results.currentRow(), 1)
        QTest.keyClick(box.edit, Qt.Key.Key_Up)
        self.assertEqual(box.results.currentRow(), 0)
        QTest.keyClick(box.edit, Qt.Key.Key_Tab)   # Tab sonuç listesinde ilerler, odak kutuda kalır
        self.assertEqual(box.results.currentRow(), 1)
        self.assertEqual(box.results.focusPolicy(), Qt.FocusPolicy.NoFocus)
        self.assertTrue(box.edit.accessibleName())
        want = box.results.item(1).data(Qt.ItemDataRole.UserRole)
        window.search_box._on_page = lambda key: calls.append(key)
        QTest.keyClick(box.edit, Qt.Key.Key_Return)
        self.assertEqual(calls, [want[1]])

    def test_search_hit_for_tweak_not_fitting_this_pc_opens_hidden_list(self):
        """Denetim B B6: masaüstünde yalnızca dizüstüne uyan ayar aranırsa sayfada gizli liste açılır, satır görünür."""
        self.window = window = self.make_window()
        self.assertFalse(window.c.availability["PWR-008"].visible)
        window.go_to_tweak("PWR-008")
        page = window.pages[window.current]
        self.assertTrue(page.show_hidden)
        self.assertIn("PWR-008", page.hidden_cards)  # soluk kart, nedeni yazılı ("bu bilgisayarda yok")

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
                "NET", "INP", "AUD", "QOL", "EXP", "SND", "PLC", "elle", "degisiklikler", "olcum", "boost", "ayarlar", "bilgi"]
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

    def driver_page_card(self, *vendors, tur="masaustu"):
        from app.ui import managers_ui
        self.window = self.make_window()
        hw = {"gpu": [{"uretici": v} for v in vendors], "bilgisayar": {"tur": tur}}
        self.window.c.scan = dict(self.window.c.scan, bolumler={"donanim": hw})
        return managers_ui.DriverToolsCard(self.window, self.window.c.by_id["GPU-019"])

    def page_buttons(self, card):
        return [b for b in card.rows.findChildren(QPushButton) if b.text() == t("ui.surucu_sayfa.ac")]

    def test_driver_page_button_opens_official_page_in_browser_only(self):
        card = self.driver_page_card("AMD", "NVIDIA", "AMD", tur="laptop")
        buttons = self.page_buttons(card)
        self.assertEqual(len(buttons), 2)  # hibrit dizüstü: kart başına değil, üretici başına bir düğme
        for button in buttons:
            button.click()
        self.assertEqual(self.sys.opened, ["https://www.nvidia.com/en-us/drivers/",
                                           "https://www.amd.com/en/support/download/drivers.html"])
        self.assertIn(t("ui.surucu_sayfa.dizustu"), [x.text() for x in card.rows.findChildren(QLabel)])

    def test_driver_page_laptop_note_and_unknown_vendor(self):
        desktop = self.driver_page_card("NVIDIA")
        self.assertEqual(len(self.page_buttons(desktop)), 1)
        self.assertNotIn(t("ui.surucu_sayfa.dizustu"), [x.text() for x in desktop.rows.findChildren(QLabel)])
        intel = self.driver_page_card("Intel", tur="laptop")  # yalnızca NVIDIA/AMD araştırıldı: uyarı da düğme de yok
        self.assertEqual(self.page_buttons(intel), [])
        self.assertNotIn(t("ui.surucu_sayfa.dizustu"), [x.text() for x in intel.rows.findChildren(QLabel)])

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

    def test_input_device_vendor_software_button(self):
        from unittest import mock
        from PySide6.QtWidgets import QPushButton
        from app.ui.page_category import InputDevicesCard
        self.window = self.make_window()
        base = {"tur": "fare", "turler": ["fare"], "baglanti": "usb", "gercek_ad": True, "adet": 1}
        known = dict(base, ad="G502", vid_pid="046D:C08B", uretici="Logitech")
        unknown = dict(base, ad="X", vid_pid="1234:0001", uretici=None)
        steel = dict(base, ad="Rival", vid_pid="1038:1234", uretici="SteelSeries")  # adres doğrulanamadı: düğme yok
        card = InputDevicesCard(self.window, [known, unknown, steel])
        buttons = [b for b in card.findChildren(QPushButton) if b.text() == t("ui.giris.yazilim_ac")]
        self.assertEqual(len(buttons), 1)
        with mock.patch.object(self.window.c.engine.system, "open_path") as op:
            buttons[0].click()
        self.assertTrue(op.call_args[0][0].startswith("https://www.logitechg.com/"))
        self.assertIn(t("ui.giris.dpi_not"), " ".join(lbl.text() for lbl in card.findChildren(QLabel)))

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
        self.row("EXP", "QOL-001").switch.click()
        self.wait_idle()
        self.assertEqual(self.sys.read_reg("HKCU", path, "HideFileExt"), (0, "REG_DWORD"))
        self.assertTrue(self.window.c.engine.store.has("QOL-001"))
        self.assertTrue(self.row("EXP", "QOL-001").switch.isChecked())
        self.row("EXP", "QOL-001").switch.click()
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
        row = self.row("EXP", "QOL-001")
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

    def test_summary_rings_open_lists(self):
        """Özet: iki halka (Optimizasyon, Oyun) listesini açar ve kapatır; sayılar halkadakiyle aynı; Başlangıç/bulgu halkası YOK."""
        from PySide6.QtCore import QEvent
        from PySide6.QtWidgets import QPushButton
        self.window = self.make_window()
        self.window.toggle(self.window.c.by_id["PLC-010"], True, lambda: None)
        self.wait_idle()
        page = self.window.pages["ozet"]
        page.data_reloaded()
        self.assertIn("uygun", page.stat_tiles)
        self.assertLessEqual(set(page.stat_tiles), {"uygun", "oyun"})
        scores = page._scores()
        for kind, tile in page.stat_tiles.items():
            on = sum(1 for tw in scores[kind] if page._is_on(tw))
            self.assertEqual(tile.sentence.text(), t(f"ui.skor.{kind}", acik=on, uygun=len(scores[kind])))
            self.assertEqual(tile.ring.percent, on * 100 // len(scores[kind]))
            tile.clicked.emit()
            self.qt.processEvents()
            self.qt.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)  # önceki liste silinsin
            box = page.detail_lay.parentWidget()
            self.assertIn(t(f"ui.stat_liste.{kind}", adet=len(scores[kind])), [lbl.text() for lbl in box.findChildren(QLabel)])
            go = [b for b in box.findChildren(QPushButton) if b.text() == t("ui.ayara_git")]
            self.assertEqual(len(go), len(scores[kind]))
        self.assertTrue(page.change_button.text().endswith("1") or "1" in page.change_button.text())
        page.change_button.click()  # uygulamanın yaptığı değişiklikler listesi
        self.qt.processEvents()
        self.assertEqual(page.detail_kind, "degisen")
        page.change_button.click()  # aynı düğme: kapanır
        self.qt.processEvents()
        self.assertIsNone(page.detail_kind)
        self.assertEqual(page.detail_lay.count(), 0)

    def test_summary_live_cards_on_top_and_hub_order(self):
        """Özet: en üstte gerçek 'Canlı sistem durumu' kartları (tek ölçüm kaynağı; aynı bilgi sayfada ikinci kez yok), altında
        kahraman kart + halkalar, sonra Oyunlar/Boost/Temizlik kısayolları, bulgu listesi bunların altında."""
        from PySide6.QtCore import QEvent
        from app.ui import page_summary
        from app.ui.page_summary import ShortcutTile
        self.assertFalse(hasattr(page_summary, "PcStrip"))  # Tur 3C'nin ayrı CPU/GPU/RAM/Disk şeridi kalktı
        self.window = window = self.make_window()
        page = window.pages["ozet"]
        page.data_reloaded()
        self.qt.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)  # önceki kurulumların kutuları silinsin
        tiles = page.findChildren(ShortcutTile)
        self.assertEqual(len(tiles), 3)
        tiles[1].clicked.emit()  # Boost kısayolu sayfayı açar
        self.assertEqual(window.current, "boost")
        window.navigate("ozet")
        live = page.tiles["cpu"].parentWidget()  # canlı kartların ızgarası

        def slot(target):  # sayfa gövdesindeki sıra: doğrudan öğe ya da bir yerleşimin ilk öğesi
            for i in range(page.body.count()):
                item = page.body.itemAt(i)
                first = item.layout().itemAt(0).widget() if item.layout() and item.layout().count() else None
                if item.widget() is target or first is target:
                    return i
            self.fail("sayfada yok")

        order = [slot(x) for x in (live, page.recommendations, tiles[0], page.findings_title)]
        self.assertEqual(order, sorted(set(order)))  # canlı kartlar < kahraman < kısayollar < bulgular
        self.assertEqual(len(page.tiles), 6)  # alttaki ikinci bir canlı bölüm yok

    def test_summary_findings_are_cards_without_summary_line(self):
        """Bulgular: özet yazısı ('1 uyarı var') yok; her bulgu simge + başlık + tek satır + eylem taşıyan kart."""
        from PySide6.QtWidgets import QLabel
        from app.ui import widgets as w
        finding = {"kod": "ram_tek_kanal", "seviye": "uyari", "ilgili": [], "params": {}}
        self.window = self.make_window(findings=[finding])
        page = self.window.pages["ozet"]
        page.data_reloaded()
        self.assertFalse(hasattr(page, "_findings_line"))
        self.assertNotIn("bulgu", page.stat_tiles)
        self.assertNotIn("baslangic", page.stat_tiles)
        self.assertEqual(len(page.finding_cards), 1)
        card = page.finding_cards[0]
        self.assertTrue(card.property("tile"))  # düz yüzey + ince çerçeve
        self.assertEqual(card.findChildren(w.IconTile)[0].accessibleName(), t("seviye.uyari"))
        self.assertEqual(len(card.findChildren(w.ClampLabel)), 1)  # tek satır açıklama
        self.assertFalse(any("uyarı var" in lbl.text() for lbl in page.findChildren(QLabel)))

    def test_nav_bar_and_panels_keep_every_page(self):
        """Alt-orta çubuk: 5 sayfa + Optimizasyonlar/Özelleştirmeler (şerit) + Araçlar (panel) + Ayarlar; her sayfa kimliği yerinde;
        her kategori tam bir şerit grubunda; Araçlar paneli açılınca/kapanınca doğru düğme seçili; sayfa açılınca panel kapanır."""
        self.window = window = self.make_window()
        categories = {c["id"] for c in window.c.categories}
        pages = {"ozet", "pc_detay", "oyunlar", "boost", "temizlik", "kaldirici", "profiller", "olcum", "degisiklikler",
                 "rapor", "baslangic", "elle", "rehber", "ayarlar", "bilgi"}
        self.assertEqual(set(window.nav), categories | pages)
        self.assertEqual({k for k, _ in window.search_box._pages}, categories | pages)  # Ctrl+K her sayfayı bulur
        self.assertEqual(set(window.nav_groups), {"optimizasyonlar", "ozellestirmeler", "araclar"})
        self.assertEqual(set(window.nav_panels), {"araclar"})  # kategoriler artık panelde değil, şeritte
        self.assertEqual(set(window.nav_panels["araclar"].keys), set(window.NAV_TOOLS))
        self.assertEqual(set(window.NAV_BAR) | set(window.NAV_TOOLS) | {"ayarlar"}, pages)
        self.assertEqual(window.NAV_BAR[0], "profiller")  # Hazır profiller çubuğun en başında
        self.assertIn("pc_detay", window.NAV_TOOLS)  # çubuğa sığmak için Araçlar'da
        self.assertNotIn("ayarlar", window.NAV_TOOLS)  # uygulamanın kendi ayarları çubukta ayrı öğe, panelde değil
        strips = window.strip_keys
        self.assertEqual(set(strips["optimizasyonlar"]) | set(strips["ozellestirmeler"]), categories)
        self.assertFalse(set(strips["optimizasyonlar"]) & set(strips["ozellestirmeler"]))  # her kategori tek grupta
        self.assertEqual(strips["ozellestirmeler"], ["QOL", "EXP", "SND"])
        self.assertIn("PLC", strips["optimizasyonlar"])  # Placebo Optimizasyonlar şeridinde (Kubilay kararı)
        for category in categories:  # Ctrl+K sonucu / navigate: şerit doğru grupla açılır
            self.assertEqual(window._group_of(category),
                             "ozellestirmeler" if category in ("QOL", "EXP", "SND") else "optimizasyonlar")
        for tid, cid in (("QOL-012", "EXP"), ("AUD-001", "SND"), ("SYS-011", "QOL"), ("AUD-003", "AUD")):
            self.assertEqual(window.c.by_id[tid]["kategori_id"], cid, tid)  # taşınan ayar doğru kategoride
        window.go_to_tweak("AUD-001")  # Ctrl+K sonucu: taşınan ayarın grubu ve sayfası
        self.assertEqual((window.current, window._group_of(window.current)), ("SND", "ozellestirmeler"))
        window.go_to_tweak("AUD-003")  # taşınmayan ses ayarı Optimizasyonlar'da kalır
        self.assertEqual((window.current, window._group_of(window.current)), ("AUD", "optimizasyonlar"))
        window.navigate("ozet")
        self.assertEqual(t("ui.menu.grup.optimizasyonlar"), "Optimizasyonlar")
        self.assertEqual(t("ui.menu.grup.ozellestirmeler"), "Özelleştirmeler")
        self.assertEqual(t("ui.menu.ayarlar"), "Ayarlar")
        self.assertTrue(window.nav_panels["araclar"].isHidden())
        self.assertTrue(window.strip_holder.isHidden())  # sayfa grup dışındayken şerit yok
        window.navigate("ozet")
        self.assertIsNone(window._panel_open)
        self.assertFalse(any(window.nav_groups[g].property("selected") for g in window.nav_groups))
        window._toggle_panel("araclar")
        self.assertFalse(window.nav_panels["araclar"].isHidden())
        self.assertTrue(window.nav_groups["araclar"].property("selected"))  # açık panelin düğmesi seçili
        window._escape()  # Esc önce paneli kapatır, sayfa değişmez
        self.assertIsNone(window._panel_open)
        self.assertEqual(window.current, "ozet")
        window._toggle_panel("araclar")
        window.nav["bilgi"]._on_click("bilgi")  # paneldeki düğmeye tıklama
        self.assertEqual(window.current, "bilgi")
        self.assertIsNone(window._panel_open)  # sayfa açılınca panel kapanır
        self.assertTrue(window.nav_panels["araclar"].isHidden())
        self.assertTrue(window.nav_groups["araclar"].property("selected"))
        self.assertTrue(window.strip_holder.isHidden())
        window.navigate("pc_detay")  # Araçlar'a taşınan sayfa: Araçlar seçili, şerit yok
        self.assertTrue(window.nav_groups["araclar"].property("selected"))
        window.navigate("ozet")
        self.assertFalse(any(window.nav_groups[g].property("selected") for g in window.nav_groups))

    def test_category_strip_follows_open_page(self):
        """Şerit yalnızca grup sayfası açıkken görünür ve yalnızca o grubun düğmelerini taşır; grup düğmesi son açılan
        kategoriye (yoksa ilkine) götürür; zaten içerideyken hiçbir şey yapmaz; seçili kategori şeritte işaretli."""
        self.window = window = self.make_window()
        strips = window.strip_keys
        window.navigate("ozet")
        self.assertTrue(window.strip_holder.isHidden())
        window.nav_groups["optimizasyonlar"]._on_click("optimizasyonlar")  # grup düğmesi: ilk kategori
        self.assertEqual(window.current, strips["optimizasyonlar"][0])
        self.assertFalse(window.strip_holder.isHidden())
        self.assertTrue(window.nav_groups["optimizasyonlar"].property("selected"))
        self.assertFalse(window.nav_groups["ozellestirmeler"].property("selected"))
        self.assertFalse(window.nav_strips["optimizasyonlar"].isHidden())  # şeritte yalnızca bu grubun düğmeleri
        self.assertTrue(window.nav_strips["ozellestirmeler"].isHidden())
        window.navigate("GPU")
        window.navigate("ozet")
        self.assertTrue(window.strip_holder.isHidden())
        window.nav_groups["optimizasyonlar"]._on_click("optimizasyonlar")  # en son açılan kategoriye döner
        self.assertEqual(window.current, "GPU")
        self.assertTrue(window.nav["GPU"].property("selected"))
        history = list(window._history)
        window.nav_groups["optimizasyonlar"]._on_click("optimizasyonlar")  # zaten grubun içinde: değişmez
        self.assertEqual(window.current, "GPU")
        self.assertEqual(window._history, history)
        window.nav_groups["ozellestirmeler"]._on_click("ozellestirmeler")
        self.assertEqual(window.current, "QOL")
        self.assertFalse(window.strip_holder.isHidden())
        self.assertFalse(window.nav_strips["ozellestirmeler"].isHidden())
        self.assertTrue(window.nav_strips["optimizasyonlar"].isHidden())
        self.assertTrue(window.nav_groups["ozellestirmeler"].property("selected"))
        self.assertFalse(window.nav_groups["optimizasyonlar"].property("selected"))
        window.go_to_tweak("PERF-003")  # Ctrl+K sonucu: doğru grubun şeridi açılır
        self.assertEqual(window.current, "PERF")
        self.assertTrue(window.nav["PERF"].property("selected"))
        self.assertTrue(window.nav_strips["ozellestirmeler"].isHidden())

    def test_nav_group_open_by_keyboard_and_count_badge(self):
        """Grup düğmesi klavyeyle (Enter) çalışır, Tab ile gezilir; kategori düğmesindeki "önerilen" sayısı ve grup
        düğmesindeki toplam korunur."""
        from PySide6.QtCore import QEvent, Qt
        from PySide6.QtGui import QKeyEvent
        self.window = window = self.make_window()
        head = window.nav_groups["optimizasyonlar"]
        self.assertEqual(head.focusPolicy(), Qt.FocusPolicy.TabFocus)
        self.assertEqual(window.nav["GPU"].focusPolicy(), Qt.FocusPolicy.TabFocus)  # şerit düğmeleri de klavyeyle gezilir
        window.navigate("ozet")
        head.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier))
        self.assertEqual(window.current, window.strip_keys["optimizasyonlar"][0])
        self.assertFalse(window.strip_holder.isHidden())
        window.nav_groups["araclar"].keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier))
        self.assertEqual(window._panel_open, "araclar")  # Araçlar hâlâ yukarı açılan panel
        window._close_panel(refocus=False)
        window._update_counts()
        tags = {c["id"]: window.nav[c["id"]].count.text() for c in window.c.categories
                if window.nav[c["id"]].count.text()}
        for group, keys in window.strip_keys.items():
            total = sum(int(v) for k, v in tags.items() if k != "PLC" and k in keys)
            self.assertEqual(window.nav_groups[group].count.text(), str(total) if total else "", group)
            self.assertEqual(window.nav_groups[group].count.isHidden(), not total, group)

    def test_page_titles_are_two_tone(self):
        """Başlıkta son kelime yeşil vurgu; sondaki "(not)" vurgulanmaz; ekran okuyucuya tam metin."""
        from app.ui import theme, widgets as w
        self.assertEqual(w.title_parts("Sistem özeti"), ("Sistem ", "özeti", ""))
        self.assertEqual(w.title_parts("Boost (bellek)"), ("", "Boost", " (bellek)"))
        self.assertEqual(w.title_parts("Temizlik"), ("", "Temizlik", ""))
        label = w.title("Uygulama <kaldırıcı>")
        self.assertIn(theme.palette()["accent"], label.text())
        self.assertIn("&lt;kaldırıcı&gt;", label.text())  # metin HTML olarak yorumlanmaz
        self.assertEqual(label.accessibleName(), "Uygulama <kaldırıcı>")

    def test_summary_greeting_is_plain_without_user_name(self):
        """Özet'te küçük sade "Merhaba"; kullanıcı adı işletim sisteminden okunmaz (gizlilik)."""
        import inspect
        from app.ui import page_summary
        self.window = window = self.make_window()
        page = window.pages["ozet"]
        page.ensure_built()
        texts = [lbl.text() for lbl in page.findChildren(QLabel)]
        self.assertIn(t("ui.merhaba"), texts)
        self.assertIn(t("ui.ozet_aciklama"), texts)
        source = inspect.getsource(page_summary)
        for forbidden in ("getpass", "getlogin", "USERNAME", "expanduser"):
            self.assertNotIn(forbidden, source)

    def test_games_cards_use_local_cover_or_letter(self):
        """Oyun kartı: Steam yerel önbelleğinde kapak varsa o, yoksa (Epic dahil) adın harfi; sonda tek '+ Oyun ekle'."""
        from pathlib import Path
        from unittest import mock
        from PySide6.QtGui import QImage
        from PySide6.QtWidgets import QPushButton
        from app.games import discovery
        from app.ui.page_games import Cover
        self.window = self.make_window()
        store = self.window.game_store
        for game in list(store.games):
            store.remove(game["id"])
        with tempfile.TemporaryDirectory() as steam:
            image = Path(steam, "appcache", "librarycache", "42", "abc", "library_600x900.jpg")
            image.parent.mkdir(parents=True)
            self.assertTrue(QImage(600, 900, QImage.Format.Format_RGB32).save(str(image)))
            page = self.window._page("oyunlar")
            page.found = [{"ad": "Kapaklı", "klasor": r"C:\Kapakli", "kaynak": "Steam", "exe": None,
                           "baslat": "steam://rungameid/42"},
                          {"ad": "Epicli", "klasor": r"C:\Epicli", "kaynak": "Epic", "exe": None, "baslat": None}]
            with mock.patch.object(discovery, "steam_root", return_value=steam):
                page.ensure_built()
                covers = page.findChildren(Cover)
                shown = [c.pixmap is not None for c in covers]  # resim ilk erişimde (çizimde) çözülür: geçici klasör silinmeden
        self.assertEqual(shown, [True, False])
        self.assertEqual(covers[1].letter, "E")
        # Sıra: yerel kapak -> exe simgesi -> harf. Exe'si olmayan ya da simgesi okunamayan oyun harfe düşer.
        self.assertIsNone(Cover.exe_icon(None))
        self.assertIsNone(Cover.exe_icon(r"C:\yok\yok.exe"))
        add = [b for b in page.findChildren(QPushButton) if b.objectName() == "AddCard"]
        self.assertEqual(len(add), 1)

    def test_games_pick_and_remove_own_picture(self):
        """'…' menüsü: Resim seç -> yerel kopya + ölçek, kart o resmi gösterir; Resmi kaldır -> eski sıraya döner; geçersiz dosya
        durum çubuğunda uyarı verir ve hiçbir şey yazmaz."""
        from pathlib import Path
        from unittest import mock
        from PySide6.QtGui import QImage
        from app.games import discovery
        from app.ui import page_games
        from app.ui.page_games import Cover
        self.window = self.make_window()
        page = self.window._page("oyunlar")
        game = {"id": "OYUN-0123456789", "ad": "Benim Oyunum"}
        with tempfile.TemporaryDirectory() as data, tempfile.TemporaryDirectory() as src:
            image = str(Path(src, "kapak.png"))
            self.assertTrue(QImage(800, 500, QImage.Format.Format_RGB32).save(image))
            junk = Path(src, "bozuk.png")
            junk.write_bytes(b"resim degil")
            statuses = []
            with mock.patch.object(discovery.paths, "user_data_path", return_value=Path(data)), \
                    mock.patch.object(self.window, "set_status", lambda text, tone="": statuses.append((text, tone))):
                with mock.patch.object(page_games.QFileDialog, "getOpenFileName", return_value=(str(junk), "")):
                    page._pick_image(game)
                self.assertEqual(statuses[-1], (t("ui.oyun_resim_hata"), "uyari"))
                self.assertIsNone(discovery.user_cover(game["id"]))
                with mock.patch.object(page_games.QFileDialog, "getOpenFileName", return_value=(image, "")):
                    page._pick_image(game)
                self.assertEqual(statuses[-1][1], "iyi")
                self.assertIsNotNone(discovery.user_cover(game["id"]))
                self.assertIsNotNone(Cover(game, discovery.cover_path(game)).pixmap)
                page._remove_image(game)
                self.assertIsNone(discovery.user_cover(game["id"]))
                with mock.patch.object(page_games.QFileDialog, "getOpenFileName", return_value=("", "")):
                    page._pick_image(game)  # iptal: hiçbir şey olmaz
                self.assertIsNone(discovery.user_cover(game["id"]))

    def test_game_cover_falls_back_cover_then_exe_icon_then_letter(self):
        """Kapak sırası: yerel Steam kapağı -> exe simgesi (koyu zeminde ortada) -> ad harfi. Üçü de gerçekten çizilir."""
        from unittest import mock
        from PySide6.QtGui import QColor, QImage, QPixmap
        from app.ui import theme
        from app.ui.page_games import Cover
        self.window = self.make_window()
        game = {"ad": "Örnek", "exe": r"C:\Oyun\oyun.exe"}
        red = QPixmap(128, 128)
        red.fill(QColor("#ff0000"))

        def corner_and_centre(cover):
            image = cover.grab().toImage()
            return image.pixelColor(6, 6), image.pixelColor(image.width() // 2, image.height() // 2)

        with mock.patch.object(Cover, "exe_icon", return_value=red) as icon:
            corner, centre = corner_and_centre(Cover(game, None))
            self.assertEqual(corner.name(), theme.ICON_GROUND)  # koyu zemin
            self.assertEqual(centre.name(), "#ff0000")          # simge ortada
            icon.assert_called_with(game["exe"])
            Cover(game, None)  # kapak varsa exe simgesi hiç istenmez
            icon.reset_mock()
            image = Path(self.tmp.name, "kapak.png")
            self.assertTrue(QImage(60, 90, QImage.Format.Format_RGB32).save(str(image)))
            Cover(game, str(image)).grab()
            icon.assert_not_called()
        with mock.patch.object(Cover, "exe_icon", return_value=None):
            corner, _ = corner_and_centre(Cover(game, None))
            self.assertEqual(corner.name(), theme.letter_style("Örnek")[1])  # harf kartı zemini

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

    # ------------------------------------------------------------------ Ayarlar: 3 sekme
    def _settings_page(self):
        self.window = self.make_window()
        self.window.navigate("ayarlar")
        self.qt.processEvents()
        return self.window.pages["ayarlar"]

    def _visible(self, page, cls):
        """Sayfada şu an görünen widget'lar (yeniden kurulunca eskiler gizlenir, silinmeyi bekler)."""
        return [x for x in page.findChildren(cls) if x.isVisibleTo(page)]

    def _button(self, page, text):
        return next(b for b in self._visible(page, QPushButton) if b.text() == text)

    def test_settings_tabs_hold_the_same_rows(self):
        """Yalnızca yerleşim: üç sekme, her satır tek yerde; ayar anahtarları aynı."""
        from app.core import settings
        page = self._settings_page()
        self.assertEqual([b.text() for b in self._visible(page, QPushButton) if b.property("segment")],
                         [t("ui.ayarlar.sekme.genel"), t("ui.ayarlar.sekme.sistem"), t("ui.ayarlar.sekme.bakim")])
        titles = {}
        for tab in ("genel", "sistem", "bakim"):
            page._select_tab(tab)
            self.qt.processEvents()
            titles[tab] = {lab.text() for lab in self._visible(page, QLabel) if lab.objectName() == "CardTitle"}
        self.assertLessEqual({t("ui.ayar.dil"), t("ui.ayar.tepsi"), t("ui.ayar.windows_ile_baslat"),
                              t("ui.erisim.hareket"), t("ui.erisim.okunabilir"), t("ui.erisim.karsitlik")}, titles["genel"])
        self.assertLessEqual({t("ui.guncelleme.otomatik"), t("ui.guncelleme.simdi"), t("ui.surum.baslik"),
                              t("ui.hakkinda.baslik")}, titles["sistem"])
        self.assertLessEqual({t("ui.bakim.disa_aktar"), t("ui.bakim.ice_aktar"), t("ui.bakim.sifirla"),
                              t("ui.bakim.tanilama"), t("ui.bakim.log"), t("ui.bakim.geri_yukleme"), t("ui.rpl.ac")},
                             titles["bakim"])
        self.assertFalse(titles["genel"] & titles["sistem"] | titles["genel"] & titles["bakim"] | titles["sistem"] & titles["bakim"])
        for key in ("ekstra_bilgi", "rp_sorma", "tepsiye_kucult", "okunabilir_yazi", "hareket_azalt", "yuksek_karsitlik",
                    "guncelleme_denetle", "dil"):
            self.assertIn(key, settings.DEFAULTS)

    def test_failed_update_swap_shown_once_at_startup(self):
        """Denetim A S3: değişim geri döndüyse açılışta tek durum satırı; ağa bağlanılmaz."""
        from unittest import mock
        from app.core import guncelleme
        with mock.patch.object(guncelleme, "onceki_degisim_hatasi", return_value=True), \
                mock.patch.object(guncelleme, "kontrol", side_effect=AssertionError("ağ")):
            self.window = self.make_window()
            self.window._auto_update_check()
        self.assertEqual(self.window.status.text(), t("ui.guncelleme.hata.degisim"))

    def test_settings_restore_points_listed_read_only(self):
        """Bakım sekmesi açılınca salt okunur liste okunur; en yeni önde; liste okunamazsa dürüst ileti."""
        page = self._settings_page()
        self.sys.restore_points = [{"Description": "Eski", "Zaman": "2026-10-01T10:00:00"},
                                   {"Description": "Yeni", "Zaman": "2026-11-02T10:00:00"}]
        page._select_tab("bakim")
        end = time.time() + 5
        while page.points is None and time.time() < end:
            self.qt.processEvents()
            time.sleep(0.01)
        self.qt.processEvents()
        self.assertEqual([p["Description"] for p in page.points], ["Eski", "Yeni"])
        shown = [lab.text() for lab in self._visible(page, QLabel)]
        self.assertTrue(any("Yeni" in s for s in shown) and any("Eski" in s for s in shown))
        self.assertLess(next(i for i, s in enumerate(shown) if "Yeni" in s), next(i for i, s in enumerate(shown) if "Eski" in s))
        self.assertIn(t("ui.rpl.not"), shown)  # 24 saat sınırı yazılı
        page.points = False
        page.data_reloaded()
        self.assertIn(t("ui.rpl.okunamadi"), [lab.text() for lab in self._visible(page, QLabel)])

    def test_settings_restore_point_helpers(self):
        from app.ui.page_settings import restore_point_lines
        pts = [{"Description": f"n{i}", "Zaman": f"2026-11-0{i}T10:00:00"} for i in range(1, 9)] + [{"Zaman": ""}, "bozuk", None]
        lines, more = restore_point_lines(pts, limit=3)
        self.assertEqual((len(lines), more), (3, 5))
        self.assertTrue(lines[0].endswith("n8"))
        self.assertEqual(restore_point_lines(None), ([], 0))

    def test_settings_create_now_uses_existing_code_and_never_restores(self):
        """"Şimdi oluştur" mevcut restore_point koduyla (burada sahte: gerçek nokta OLUŞMAZ); geri yükleme yalnızca rstrui'ye yönlendirir."""
        from unittest import mock
        from app.engine import restore_point
        from app.ui import page_settings as ps
        page = self._settings_page()
        page._select_tab("bakim")
        page.points = []
        created = restore_point.RestorePointResult(restore_point.RestorePointResult.CREATED, "2026-11-05T09:00")
        with mock.patch.object(restore_point, "ensure", return_value=created) as ensure:
            self._button(page, t("ui.bakim.geri_yukleme")).click()
            end = time.time() + 5
            while not ensure.called and time.time() < end:
                self.qt.processEvents()
                time.sleep(0.01)
            ensure.assert_called_once_with(self.window.c.engine.system)
        self.assertEqual(self.sys.restore_points, [])  # sahte sistemde de gerçek oluşturma çağrılmadı
        with mock.patch.object(ps.os, "startfile") as start:
            self._button(page, t("ui.rpl.ac")).click()
            start.assert_called_once_with("rstrui.exe")
            start.reset_mock()
            self._button(page, t("ui.bakim.log")).click()
            start.assert_called_once()

    def test_info_window_shows_sources_even_when_extra_info_is_off(self):
        from app.core import settings
        self.window = self.make_window()
        settings.set("ekstra_bilgi", False)
        tweak = next(tw for tw in self.window.c.by_id.values() if tw.get("kaynaklar"))
        dialog = self.dialogs.InfoDialog(self.window, tweak)
        links = [lab.text() for lab in dialog.findChildren(QLabel) if lab.text().startswith("<a href=")]
        self.assertEqual(len(links), len(tweak["kaynaklar"]))
        dialog.deleteLater()

    def test_release_notes_are_embedded_and_offline(self):
        from app.ui import page_settings as ps
        from app.ui.page_settings import release_notes_text
        tr, en = release_notes_text(lang="tr"), release_notes_text(lang="en")
        self.assertIn("Yeni neler var", tr)
        self.assertIn("What's new", en)
        self.assertNotIn("Yeni neler var", en)
        self.assertNotIn("904A89FB", tr)  # sürümün sağlama (hash) bloğu pencereye girmez
        self.assertNotIn("## 2.2.0", tr)  # yalnızca son 3 sürüm: eski Pro/lisans dönemi notları gösterilmez (ücretsiz ürün)
        self.assertEqual(tr.count("\n## "), 2)
        from pathlib import Path
        self.assertEqual(release_notes_text(path=Path(self.__class__.__module__ + ".yok")), "")
        page = self._settings_page()
        page._select_tab("sistem")
        dialog = ps.ReleaseNotesDialog(self.window)
        self.assertIn("2.3.2", dialog.viewer.toPlainText())
        dialog.deleteLater()

    def test_card_shows_recommended_label_only_for_recommended_and_no_impact_badge(self):
        from app.ui import page_category
        self.window = self.make_window()
        recommended = {p["id"] for p in self.window.c.recommendations(99)}
        seen = set()
        pages = [self.window._page(c["id"]) for c in self.window.c.categories]
        for page in pages:
            page.ensure_built()
        for tid, row in ((tid, row) for page in pages for tid, row in page.rows.items()):
            if not isinstance(row, page_category.TweakRow):
                continue
            texts = {lb.text() for lb in row.meta.findChildren(QLabel)}
            level = row.tweak["performans_etkisi"]["seviye"]
            self.assertNotIn(t("ui.etki", seviye=i18n.value_label("deger.etki", level)), texts, tid)  # etki (i) penceresinde
            shown = t("ui.onerilen_etiket") in texts
            self.assertEqual(shown, tid in recommended, tid)
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

    def test_detected_csrss_priority_restored_to_windows_default(self):
        """Başka programın yaptığı csrss.exe önceliği: Özet'te "Windows varsayılanına döndür", önizleme onayı,
        apply_custom (yedek + Değişiklikler), yeniden okuma bulguyu kaldırır; Vazgeç hiçbir şey yazmaz."""
        from unittest import mock
        from app.engine import varsayilan
        from app.scan import checks
        from app.ui import dialogs
        self.window = self.make_window()
        self.sys.write_reg("HKLM", varsayilan.CSRSS_PERF, "CpuPriorityClass", 4, "REG_DWORD")
        finding = {"kod": "tespit", "seviye": "sorun", "ilgili": ["PLC-018"], "params": {"ad": "x", "mesaj": "y"}}
        self.window.c.scan["bulgular"] = [finding]
        self.window.c.scan["tespitler"] = [{"id": "PLC-018", "ad": "x", "mesaj": "y", "durum": "zararlı"}]
        page = self.window.pages["ozet"]
        page.data_reloaded()
        card = page.finding_cards[0]
        self.assertEqual(card.fix, {"tur": "varsayilan", "id": "PLC-018"})
        self.assertIn(t("ui.varsayilan.dugme"), [b.text() for b in card.findChildren(QPushButton)])
        with mock.patch.object(checks.registry, "key_exists", self.sys.get_key_exists):
            with mock.patch.object(dialogs, "ask_yes_no", return_value=False):
                card._solve()
                self.wait_idle()
                self.wait_for(lambda: not page.busy_fixes)
            self.assertTrue(self.sys.get_key_exists("HKLM", varsayilan.CSRSS_PERF))  # Vazgeç: dokunulmadı
            with mock.patch.object(dialogs, "ask_yes_no", return_value=True):
                page.finding_cards[0]._solve()
                self.wait_idle()
                self.wait_for(lambda: not page.busy_fixes)
        self.assertFalse(self.sys.get_key_exists("HKLM", varsayilan.CSRSS_PERF))
        self.assertTrue(self.window.c.engine.store.has("VARSAYILAN-PLC-018"))
        self.assertEqual(self.window.c.scan["bulgular"], [])
        with mock.patch.object(checks.registry, "key_exists", self.sys.get_key_exists):
            self.window.revert("VARSAYILAN-PLC-018", lambda: None)
            self.wait_idle()
        self.assertEqual(self.sys.read_reg("HKLM", varsayilan.CSRSS_PERF, "CpuPriorityClass"), (4, "REG_DWORD"))
        # Geri alma: bulgu "Yeniden tara" beklemeden Özet'e döner, yeşil tek satır çıkar
        self.assertEqual([f["ilgili"] for f in self.window.c.scan["bulgular"]], [["PLC-018"]])
        self.assertEqual(len(page.finding_cards), 1)
        self.assertEqual(self.window.status.text(), t("ui.geri_alindi_kisa", ad=t("ui.varsayilan.degisiklik", ad=self.window.c.by_id["PLC-018"]["ad"])))
        self.assertIn(self.window.status.text(), self.window.toast.text())

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
        self.wait_for(lambda: self.sys.npi_imports)
        self.wait_idle()
        self.assertEqual(self.sys.npi_imports, [[(0x0064B541, 1)]])
        self.assertEqual(self.sys.npi_hashes, ["ab" * 32])  # onaylanan dosyanın özeti çalıştırmadan önce yeniden denetlenir

    def test_npi_and_tool_signature_checks_run_off_the_ui_thread(self):
        """Denetim B B4: imza denetimi (PowerShell) arayüz iş parçacığında çalışmaz."""
        import threading
        from unittest import mock
        from app.engine import driver_tools
        from app.ui import managers_ui
        self.window = self.make_window()
        self.sys.nvidia_ok = False
        page = self.window._page("GPU")
        self.window.navigate("GPU")
        card = page.rows["GPU-009"]
        self.wait_for(lambda: card.value != "okunuyor")
        threads = []
        original_check = self.sys.npi_check
        self.sys.npi_check = lambda: threads.append(threading.current_thread()) or original_check()
        asked = []
        original = self.dialogs.ask_yes_no
        self.dialogs.ask_yes_no = lambda *a, **k: asked.append(a[2]) or False
        try:
            card._npi()
            self.wait_for(lambda: asked)
            tools = managers_ui.DriverToolsCard(self.window, self.window.c.by_id["GPU-019"])
            fake = {"imza_gecerli": False, "sha256": "cd" * 32, "imzalayan": ""}
            with mock.patch.object(driver_tools, "verify",
                                   lambda p: threads.append(threading.current_thread()) or dict(fake)):
                tools._open_tool(r"C:	ools\ddu.exe")
                self.wait_for(lambda: len(asked) == 2)
        finally:
            self.dialogs.ask_yes_no = original
        self.assertEqual(len(threads), 2)
        self.assertNotIn(threading.main_thread(), threads)

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
            self.wait_for(lambda: asked)  # imza denetimi işçi iş parçacığında: soru geri çağrıda sorulur
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
        for game in list(self.window.game_store.games):  # liste doluyken tarama durumu oyunun alt sayfasındadır
            self.window.game_store.remove(game["id"])

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
        page.found, page.editing, page.opened = [], game["id"], True
        page.data_reloaded()
        for _ in range(20):
            self.qt.processEvents()
            time.sleep(0.02)
        button = next(b for b in page.findChildren(QPushButton) if b.text() == t("ui.oyun_gelismis_goster") and b.isVisible())
        button.click()  # Gelişmiş kapalı gelir; açılınca sayfa uzar
        for _ in range(20):
            self.qt.processEvents()
            time.sleep(0.02)
        self.assertTrue(page.advanced_open)
        bar = page.scroll.verticalScrollBar()
        bar.setValue(bar.maximum() // 2)
        position = bar.value()
        self.assertGreater(position, 0)
        page.data_reloaded()
        for _ in range(3):
            self.qt.processEvents()
        self.assertEqual(bar.value(), position)
        store.remove(game["id"])

    def test_cleanup_scan_failure_says_unreadable_not_nothing_to_clean(self):
        """Denetim B B8: tarama istisna verirse "temizlenecek bir şey yok" değil "liste okunamadı" yazar."""
        from unittest import mock
        from PySide6.QtWidgets import QLabel
        from app.engine import cleaners
        self.window = self.make_window()
        with mock.patch.object(cleaners, "scan", side_effect=OSError("sahte")):
            self.window.navigate("temizlik")
            page = self.window._page("temizlik")
            self.wait_for(lambda: page.found is not None)
        self.qt.processEvents()
        texts = [x.text() for x in page.findChildren(QLabel)]
        self.assertIn(t("ui.liste_okunamadi"), texts)
        self.assertNotIn(t("ui.temizlik.bos"), texts)

    def test_revert_confirmation_names_the_change_and_start_failure_is_visible(self):
        """Denetim B B7: katalogda karşılığı olmayan seviye-2 değişikliği geri alırken "{ad}" çiğ görünmez.
        B9: "Oyunu başlat" başarısız olursa durum çubuğunda görünür hata çıkar."""
        from unittest import mock
        from PySide6.QtWidgets import QPushButton
        self.window = win = self.make_window()
        engine = win.c.engine
        asked = []
        with mock.patch.object(engine, "stored_confirm_level", return_value=2),                 mock.patch.object(engine, "stored_related", return_value=None),                 mock.patch.object(engine.store, "get", return_value={"ad": "Eski Ayar"}),                 mock.patch.object(self.dialogs, "ask_yes_no", lambda *a, **k: asked.append(a[2]) or False):
            win.revert("ESKI-999", lambda: None)
        self.assertIn("Eski Ayar", asked[0])
        self.assertNotIn("{ad}", asked[0])
        # B9
        store = win.game_store
        for game in list(store.games):
            store.remove(game["id"])
        game = store.add("Denemelik", "C:/Denemelik", "Steam", "C:/Denemelik/d.exe", baslat="steam://rungameid/42")
        page = win._page("oyunlar")
        page.ensure_built()
        page.editing, page.opened = game["id"], True  # oyunun alt sayfası: ana düğmeler burada
        page.data_reloaded()
        buttons = [b for b in page.findChildren(QPushButton) if b.text() == t("ui.oyun_baslat")]
        self.assertTrue(buttons)
        with mock.patch("app.ui.page_games.os.startfile", side_effect=OSError("yok")):
            buttons[0].click()
            self.wait_idle()
        self.assertEqual(win.status.text(), t("ui.oyun_baslatilamadi"))
        store.remove(store.games[0]["id"])

    def test_toast_with_undo_stays_while_mouse_or_focus_is_on_it(self):
        """Denetim B O3: "Geri al" bildirimi fare ya da odak üstündeyken kapanmaz."""
        from unittest import mock
        self.window = win = self.make_window()
        toast = win.toast
        toast.show_text("Tamam", ms=60000, action=lambda: None, action_label="Geri al")
        with mock.patch.object(toast, "underMouse", return_value=True):
            toast._expire()
        self.assertFalse(toast.isHidden())
        self.assertTrue(toast._timer.isActive())
        toast._expire()  # fare gitti
        self.assertTrue(toast.isHidden())

    def test_prepare_button_reference_is_dropped_when_game_is_prepared(self):
        """Denetim B O2: hazır oyunda "Hazırla" düğmesi yoktur; eski (silinmiş) düğmeye başvuru kalmaz."""
        self.window = win = self.make_window()
        store = win.game_store
        game = store.add("Hazir", "C:/Hazir", "Steam", "C:/Hazir/h.exe")
        page = win._page("oyunlar")
        page._prepare_button = object()
        win.prepared_game = game
        try:
            page._main_row(game)
        finally:
            win.prepared_game = None
            store.remove(game["id"])
        self.assertIsNone(page._prepare_button)

    def test_source_links_open_with_keyboard_too(self):
        """Denetim B B10: (i) penceresindeki kaynak bağlantıları Tab + Enter ile de açılır."""
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
        from app.ui import dialogs
        box = QWidget()
        lay = QVBoxLayout(box)
        dialogs._sources(lay, {"kaynaklar": ["https://example.com/kanit"]})
        link = box.findChildren(QLabel)[-1]
        self.assertTrue(link.textInteractionFlags() & Qt.TextInteractionFlag.LinksAccessibleByKeyboard)

    def test_cleanup_page_sends_only_ids_and_blocks_running_programs(self):
        from unittest import mock
        from app.engine import cleaners
        found = [{"id": "discord", "boyut": 5 * 1048576, "adet": 3, "calisiyor": False},
                 {"id": "steam", "boyut": 1048576, "adet": 1, "calisiyor": True},
                 {"id": "eski_log", "boyut": 0, "adet": 0, "calisiyor": False}]
        self.window = self.make_window()
        with mock.patch.object(cleaners, "scan", return_value=found):
            self.window.navigate("temizlik")
            page = self.window._page("temizlik")
            end = time.time() + 5
            while page.found is None and time.time() < end:
                self.qt.processEvents()
                time.sleep(0.01)
        self.qt.processEvents()
        self.assertEqual(set(page.checks), {"discord", "steam", "eski_log"})
        self.assertFalse(page.checks["eski_log"].isChecked() or page.checks["eski_log"].isEnabled())  # boş: seçilemez
        self.assertTrue(page.checks["discord"].isChecked() and page.checks["discord"].isEnabled())
        self.assertFalse(page.checks["steam"].isChecked() or page.checks["steam"].isEnabled())  # program açık: temizlenemez
        done = {"oturum": "x", "kaldirilan": 3, "basarisiz": [], "atlanan": [], "boyut": 5 * 1048576}
        with mock.patch.object(cleaners, "clean", return_value=done) as clean, mock.patch.object(cleaners, "scan", return_value=[]):
            next(b for b in page.findChildren(QPushButton) if b.text() == t("ui.temizlik.dugme") and b.isVisibleTo(page)).click()
            end = time.time() + 5
            while not clean.called and time.time() < end:
                self.qt.processEvents()
                time.sleep(0.01)
            self.qt.processEvents()
        clean.assert_called_once()
        self.assertEqual(clean.call_args.args[0], ["discord"])  # yalnızca kimlik gider, yol değil
        self.assertIn(t("ui.temizlik.sonuc", adet=3, mb="5,0"), self.window.status.text())
        with mock.patch.object(cleaners, "clean", return_value=done) as clean, mock.patch.object(cleaners, "scan", return_value=found):
            page.refresh()
            end = time.time() + 5
            while page.found is None and time.time() < end:
                self.qt.processEvents()
                time.sleep(0.01)
            self.qt.processEvents()
            next(b for b in page.findChildren(QPushButton) if b.text() == t("ui.temizlik.hepsi") and b.isVisibleTo(page)).click()
            end = time.time() + 5
            while not clean.called and time.time() < end:
                self.qt.processEvents()
                time.sleep(0.01)
        self.assertEqual(clean.call_args.args[0], ["discord"])  # "Hepsini temizle": açık program ve boş olan dışarıda

    def test_cleanup_page_shows_moved_line_recent_moves_and_brings_back(self):
        """A8-A9: taşımadan hemen sonra sayfada "N dosya taşındı" + [Geri getir], altta "Son taşımalar"; yol gösterilmez;
        Geri getir sorusuz tek tıkla uninstaller.restore'u çağırır; Kaldırıcı > Yedekler her gösterilişte listeyi yeniler."""
        from unittest import mock
        from app.engine import cleaners, uninstaller
        found = [{"id": "discord", "boyut": 5 * 1048576, "adet": 3, "calisiyor": False}]
        move = {"oturum": "20261107-120000", "program": "Temizlik", "tarih": "2026-11-07T12:00:00", "adet": 3,
                "tur": "temizlik", "boyut": 5 * 1048576}
        done = {"oturum": move["oturum"], "kaldirilan": 3, "basarisiz": [], "atlanan": [], "boyut": 5 * 1048576}
        sessions = []
        self.window = self.make_window()
        with mock.patch.object(cleaners, "scan", return_value=found), mock.patch.object(cleaners, "clean", return_value=done),                 mock.patch.object(uninstaller, "list_sessions", side_effect=lambda: list(sessions)),                 mock.patch.object(uninstaller, "restore", return_value={"geri_yuklenen": 3, "basarisiz": []}) as restore:
            self.window.navigate("temizlik")
            page = self.window._page("temizlik")
            self.assertTrue(self._wait(lambda: page.found is not None))
            self.assertIsNone(page.last_move)
            sessions.append(move)
            with mock.patch("app.ui.dialogs.ask_yes_no", return_value=True):
                self._visible_buttons(page)[t("ui.temizlik.dugme")].click()
            self.assertTrue(self._wait(lambda: page.last_move and page.found is not None and page.moves))
            texts = [lbl.text() for lbl in page.findChildren(QLabel) if lbl.isVisibleTo(page)]
            self.assertTrue(any(t("ui.temizlik.sonuc", adet=3, mb="5,0") in x for x in texts))     # taşımadan hemen sonra tek satır
            self.assertTrue(any(t("ui.temizlik.son_tasimalar") == x for x in texts))               # alttaki kısa liste
            self.assertFalse(any("ProgramData" in x or "AppData" in x or "\\" in x for x in texts))  # yol gösterilmez
            buttons = [b for b in page.findChildren(QPushButton) if b.text() == t("ui.temizlik.geri_getir") and b.isVisibleTo(page)]
            self.assertEqual(len(buttons), 2)   # tek satırda ve listede
            sessions.clear()
            buttons[0].click()
            self.assertTrue(self._wait(lambda: restore.called and page.last_move is None))
            restore.assert_called_once_with(move["oturum"])
            self.assertIn(t("ui.temizlik.geri_getirildi", adet=3), self.window.status.text())
            self.assertTrue(self._wait(lambda: page.found is not None and not page.moves))
            # Kaldırıcı > Yedekler: sayfa daha önce kurulmuş olsa da yeni yedek görünür ve "Geri getir" düğmesi vardır
            self.window.navigate("kaldirici")
            un_page = self.window._page("kaldirici")
            self.assertTrue(self._wait(lambda: un_page.programs is not None))
            sessions.append(move)
            self.window.navigate("temizlik")
            self.window.navigate("kaldirici")
            self.assertTrue(self._wait(lambda: any(b.text() == t("ui.kaldirici.geri_yukle") and b.isVisibleTo(un_page)
                                                   for b in un_page.findChildren(QPushButton))))

    def _wait(self, condition, seconds=8):
        end = time.time() + seconds
        while not condition() and time.time() < end:
            self.qt.processEvents()
            time.sleep(0.01)
        self.qt.processEvents()
        return condition()

    def test_maintenance_cards_use_mocked_tools_and_show_plain_result(self):
        from unittest import mock
        from app.engine import bakim, cleaners
        drives = [{"harf": "C", "tur": "SSD"}, {"harf": "E", "tur": "bilinmiyor"}]
        self.window = self.make_window()
        with mock.patch.object(cleaners, "scan", return_value=[]), mock.patch.object(bakim, "suruculer", return_value=drives):
            self.window.navigate("temizlik")
            page = self.window._page("temizlik")
            self.assertTrue(self._wait(lambda: page.found is not None and page.bakim.suruculer is not None))
        buttons = self._visible_buttons(page)
        self.assertTrue(buttons[t("ui.bakim.onar_dugme")].isEnabled())
        repair = {"sonuc": "temiz", "cikti": "ham sfc cikti"}
        with mock.patch.object(bakim, "sistem_onar", return_value=repair) as run, mock.patch.object(bakim, "calistir") as real:
            buttons[t("ui.bakim.onar_dugme")].click()
            self.assertTrue(self._wait(lambda: run.called and page.bakim.onar.sonuc is not None))
        real.assert_not_called()
        self.assertEqual(page.bakim.onar.sonuc, (t("ui.bakim.onar_temiz"), "iyi"))
        self.assertIn(t("ui.bakim.onar_temiz"), self.window.status.text())
        self.assertEqual(self.window.c.engine.store.read_history("bakim", 1)[0]["id"], "sistem_onar")
        self._visible_buttons(page)[t("ui.bakim.detay")].click()
        self.qt.processEvents()
        self.assertTrue(any("ham sfc cikti" in e.toPlainText() for e in page.findChildren(QPlainTextEdit)))
        # Sürücü: yalnızca türü bilinen sürücü seçilir; arayüz yalnızca harf gönderir.
        done = {"sonuc": "tamam", "suruculer": [{"harf": "C", "tur": "SSD", "islem": "trim", "tamam": True}], "cikti": "x"}
        with mock.patch.object(bakim, "optimize", return_value=done) as opt:
            self._visible_buttons(page)[t("ui.bakim.surucu_dugme")].click()
            self.assertTrue(self._wait(lambda: opt.called and page.bakim.surucu.sonuc is not None))
        self.assertEqual(opt.call_args.args[0], ["C"])
        self.assertIn(t("ui.bakim.islem_tamam", harf="C", islem="TRIM"), page.bakim.surucu.sonuc[0])

    def test_maintenance_buttons_disabled_without_admin(self):
        from unittest import mock
        from app.engine import bakim, cleaners
        self.window = self.make_window("salt_okunur")
        with mock.patch.object(cleaners, "scan", return_value=[]),                 mock.patch.object(bakim, "suruculer", return_value=[{"harf": "C", "tur": "SSD"}]):
            self.window.navigate("temizlik")
            page = self.window._page("temizlik")
            self.assertTrue(self._wait(lambda: page.found is not None and page.bakim.suruculer is not None))
        buttons = self._visible_buttons(page)
        self.assertFalse(buttons[t("ui.bakim.onar_dugme")].isEnabled())
        self.assertFalse(buttons[t("ui.bakim.surucu_dugme")].isEnabled())

    # ------------------------------------------------------------------ kullanıcı presetleri
    def _preset_page(self):
        from app.engine.user_presets import PresetStore
        self.window = self.make_window()
        self.window.preset_store = PresetStore(Path(self.tmp.name) / "presetler.json")  # testler arası sızıntı olmasın
        self.window.navigate("profiller")
        self.qt.processEvents()
        return self.window._page("profiller")

    def _visible_buttons(self, page):
        return {b.text(): b for b in page.findChildren(QPushButton) if b.isVisibleTo(page)}

    def test_user_preset_save_select_and_apply_through_normal_path(self):
        from unittest import mock
        from app.engine import user_presets
        from app.ui import page_other
        page = self._preset_page()
        careful = next(tw["id"] for tw in self.window.c.by_id.values()
                       if tw["onay_gerekli"] and user_presets.usable(tw) and self.window.c.availability[tw["id"]].visible)
        with mock.patch.object(page_other.QInputDialog, "getText", return_value=("Benim <b>seti</b>", True)):
            self._visible_buttons(page)[t("ui.preset.kaydet_secili")].click()
        self.qt.processEvents()
        preset = self.window.preset_store.presets[0]
        self.assertEqual(preset["ad"], "Benim bseti/b")
        self.assertEqual(page.selected, preset["id"])
        self.assertIn("Benim bseti/b", self._visible_buttons(page))
        self.assertIn(t("ui.preset.disa_aktar"), self._visible_buttons(page))
        self.window.preset_store.add("Dikkatli", [careful], self.window.c.by_id)
        page.selected = self.window.preset_store.presets[1]["id"]
        page._rebuild()
        self.assertFalse(page.checks[careful].isChecked())  # dikkatli ayar preset'te bile işaretli gelmez
        page.checks[careful].setChecked(True)
        with mock.patch.object(self.window, "apply_profile") as apply:
            self._visible_buttons(page)[t("ui.secilenleri_uygula")].click()
        apply.assert_called_once()  # preset kendi yolunu açmaz: her zamanki apply_profile (onay, yedek, geri alma)
        self.assertEqual([r["id"] for r in apply.call_args.args[0]], [careful])

    def test_user_preset_import_export_delete(self):
        from unittest import mock
        import json as _json
        from app.ui import page_other
        page = self._preset_page()
        folder = Path(self.tmp.name)
        good_ids = [i for i in self.window.c.by_id if i in ("PERF-001", "PERF-002", "INP-007")]
        bad = folder / "kotu.json"
        bad.write_text("{not json", encoding="utf-8")
        good = folder / "iyi.json"
        good.write_text(_json.dumps({"uygulama": "Forevermore preset", "surum": 1, "ad": "Dışarıdan",
                                     "ayarlar": good_ids + ["YOK-999", "../etc"]}), encoding="utf-8")
        with mock.patch.object(page_other.QFileDialog, "getOpenFileName", return_value=(str(bad), "")):
            self._visible_buttons(page)[t("ui.preset.ice_aktar")].click()
        self.assertEqual(self.window.preset_store.presets, [])
        self.assertIn(t("ui.preset.hata.gecersiz"), self.messages)
        with mock.patch.object(page_other.QFileDialog, "getOpenFileName", return_value=(str(good), "")), \
                mock.patch.object(self.window, "apply_profile") as apply:
            self._visible_buttons(page)[t("ui.preset.ice_aktar")].click()
        apply.assert_not_called()  # içe aktarılan preset kendiliğinden uygulanmaz
        preset = self.window.preset_store.presets[0]
        self.assertEqual((preset["ad"], preset["ayarlar"]), ("Dışarıdan", good_ids))
        self.assertTrue(any(t("ui.preset.atilan", ad="Dışarıdan", adet=2) == m for m in self.messages))
        out = folder / "cikti.json"
        with mock.patch.object(page_other.QFileDialog, "getSaveFileName", return_value=(str(out), "")):
            self._visible_buttons(page)[t("ui.preset.disa_aktar")].click()
        self.assertEqual(_json.loads(out.read_text(encoding="utf-8"))["ayarlar"], good_ids)
        self._visible_buttons(page)[t("ui.preset.sil")].click()
        self.assertEqual(self.window.preset_store.presets, [])
        self.assertEqual(page.selected, "guvenli")

    def test_games_page_has_no_watcher_switch_banner_or_snooze(self):
        """Oyun izleyici kaldırıldı (7 Kas 2026): anahtar, şerit, duraklat düğmeleri ve oyun sırasında ayarları yok;
        son oturum kartı yalnızca kaynak/FPS özetini gösterir; "Önerilen N/M" yalnızca kalıcı ayarları sayar."""
        from app.core import settings
        from app.games import presets
        self.assertNotIn("oyun_izleyici", settings.DEFAULTS)
        for name in ("game_watcher", "snooze_games", "resume_games", "game_snoozed", "update_game_watcher"):
            self.assertFalse(hasattr(self.app_module.MainWindow, name), name)
        self.window = self.make_window()
        store = self.window.game_store
        for game in list(store.games):
            store.remove(game["id"])
        game = store.add("Oyun", r"C:\Oyun", "Elle", r"C:\Oyun\oyun.exe")
        self.window.last_sessions[game["id"]] = {"ad": "Oyun", "kaynak": {"ornek": 0}}
        self.window.navigate("oyunlar")
        page = self.window._page("oyunlar")
        page.found, page.editing, page.opened, page.advanced_open = [], game["id"], True, True
        page.data_reloaded()
        self.qt.processEvents()
        visible = lambda cls: [x for x in page.findChildren(cls) if x.isVisibleTo(page)]  # noqa: E731
        texts = [lab.text() for lab in visible(QLabel)]
        self.assertIn(t("ui.oyun_oturum.baslik", ad="Oyun"), texts)
        self.assertIn(t("ui.oyun_kayit.yetersiz"), texts)
        self.assertFalse(any(s.startswith("• ") for s in texts), texts)  # uygulanan/atlanan ayar satırı yok
        done, total = presets.recommended_count(game["profil"], page._two_gpus())
        self.assertIn(t("ui.oyun_onerilen", n=done, m=total), [b.text() for b in visible(QPushButton)])
        self.assertEqual(done, 0)
        self.assertIn(total, (1, 2))  # yalnızca öncelik (+ iki kart varsa GPU)
        store.remove(game["id"])

    def test_game_recording_runs_only_when_enabled_and_only_during_a_game(self):
        from unittest import mock
        from app.core import settings
        from app.games import recorder
        usage = {"sure": 600, "ornek": 120, "cpu": {"min": 5.0, "ort": 40.0, "maks": 99.0}, "gpu": None,
                 "ram": {"min": 40.0, "ort": 55.0, "maks": 70.0}, "disk": None, "cpu_yuksek_sn": 30, "ram_yuksek_sn": 0,
                 "arka_plan": [{"ad": "chrome", "cpu": 7.5}]}

        class FakeRecorder:
            made = []

            def __init__(self, exe=""):
                self.exe, self.started, self.stopped = exe, False, False
                FakeRecorder.made.append(self)

            def start(self):
                self.started = True

            def stop(self):
                self.stopped = True
                return usage

        self.window = self.make_window()
        game = {"id": "G1", "ad": "Oyun", "exe": r"C:\Oyun\oyun.exe", "profil": {}}
        settings.set("oyun_kaydi", False)
        with mock.patch.object(recorder, "SessionRecorder", FakeRecorder), \
                mock.patch.object(recorder, "add_history") as history:
            self.window._game_event("basladi", game)
            self.assertIsNone(self.window.recorder)  # ayar kapalı: hiçbir kayıt başlamaz
            self.window._game_event("bitti", game)
            self.assertNotIn("G1", self.window.last_sessions)
            history.assert_not_called()
            settings.set("oyun_kaydi", True)
            self.window._game_event("basladi", game)
            self.assertTrue(FakeRecorder.made[0].started)
            self.assertEqual(FakeRecorder.made[0].exe, "oyun.exe")
            self.window._game_event("bitti", game)
            self.assertTrue(FakeRecorder.made[0].stopped)
            self.assertIsNone(self.window.recorder)
            self.assertEqual(self.window.last_sessions["G1"]["kaynak"], usage)
            history.assert_called_once()
            self.window._game_event("bitti", game)  # kayıt yokken bitiş: hata vermez
        settings.set("oyun_kaydi", False)

    def test_games_page_shows_resource_usage_lines(self):
        self.window = self.make_window()
        store = self.window.game_store
        for game in list(store.games):
            store.remove(game["id"])
        game = store.add("Oyun", r"C:\Oyun", "Elle", r"C:\Oyun\oyun.exe")
        self.window.last_sessions[game["id"]] = {
            "ad": "Oyun",
            "kaynak": {"sure": 600, "ornek": 120, "cpu": {"min": 5.0, "ort": 40.0, "maks": 99.0}, "gpu": None,
                       "ram": {"min": 40.0, "ort": 55.0, "maks": 70.0}, "disk": None, "cpu_yuksek_sn": 30,
                       "ram_yuksek_sn": 0, "arka_plan": [{"ad": "<b>chrome</b>", "cpu": 7.5}]}}
        self.window.navigate("oyunlar")
        page = self.window._page("oyunlar")
        page.found, page.editing, page.opened, page.advanced_open = [], game["id"], True, True  # kaynak özeti Gelişmiş'te
        page.data_reloaded()
        self.qt.processEvents()
        texts = [lab.text() for lab in page.findChildren(QLabel) if lab.isVisibleTo(page)]
        self.assertTrue(any(t("ui.oyun_kayit.baslik", sure=t("ui.oyun_kayit.dk", n=10)) == s for s in texts), texts)
        self.assertTrue(any(s.startswith("• " + t("ui.oyun_kayit.cpu")) and "%40" in s for s in texts), texts)
        self.assertTrue(any(t("ui.oyun_kayit.esik_cpu", sure=t("ui.oyun_kayit.sn", n=30)) == s for s in texts))
        self.assertFalse(any("%90" in s and "Bellek" in s for s in texts))  # RAM eşiği aşılmadı: satır yok
        self.assertTrue(any("<b>chrome</b>" in s for s in texts))  # düz metin: HTML olarak yorumlanmaz
        store.remove(game["id"])

    def test_anti_cheat_game_page_has_note_and_no_permission_switch(self):
        """Anti-cheat'li oyunda canlı FPS/kutu hiç açılmaz: ayar açıksa tek satır neden, izin anahtarı YOK."""
        from PySide6.QtCore import QEvent
        from PySide6.QtWidgets import QApplication, QLabel
        from app.core import settings
        self.window = self.make_window()
        store = self.window.game_store
        for game in list(store.games):
            store.remove(game["id"])
        plain = store.add("Düz", r"C:\Duz", "Elle", r"C:\Duz\duz.exe")
        guarded = store.add("Korumalı", r"C:\Kor", "Elle", r"C:\Kor\kor.exe")
        guarded["anti_cheat"] = ["Riot Vanguard"]
        page = self.window._page("oyunlar")
        closed = t("ui.canli_fps.oyunda_kapali")

        def show(game):
            self.window.navigate("oyunlar")
            page.found, page.editing, page.opened, page.draft = [], game["id"], True, None
            page.data_reloaded()
            QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)  # önceki kurulumun satırları silinsin
            return [lab for lab in page.findChildren(QLabel) if lab.text() == closed]

        self.addCleanup(settings.set, "fps_widget", False)
        self.addCleanup(settings.set, "canli_fps", False)
        settings.set("fps_widget", False)
        settings.set("canli_fps", False)
        self.assertEqual(show(guarded), [])            # ayarlar kapalı: hiç konuşmaz
        for key in ("canli_fps", "fps_widget"):
            settings.set("canli_fps", key == "canli_fps")
            settings.set("fps_widget", key == "fps_widget")
            self.assertEqual(show(plain), [])          # korumasız oyunda bilgi yok
            line = show(guarded)[0]
            self.assertFalse(line.isHidden())
        texts = {lab.text() for lab in page.findChildren(QLabel)}
        self.assertNotIn("Bu oyunda canlı FPS'e izin ver", texts)
        self.assertNotIn("Bu oyunda FPS kutusunu aç", texts)

    def test_fps_box_setting_applies_at_once(self):
        from unittest import mock
        from app.core import settings
        self.window = self.make_window()
        self.addCleanup(settings.set, "fps_widget", False)
        page = self.window._page("ayarlar")
        with mock.patch.object(self.window, "update_fps_widget") as update:
            page._set_fps_widget(True)
            update.assert_called_once()
        self.assertTrue(settings.get("fps_widget"))

    def test_games_page_live_process_list_follows_setting_game_and_visibility(self):
        import types
        from unittest import mock
        from app.core import settings
        from app.games import canli_surec

        class FakeLive:
            made = []

            def __init__(self, exe=""):
                self.exe, self.running = exe, False
                FakeLive.made.append(self)

            def start(self):
                self.running = True

            def stop(self):
                self.running = False

            def snapshot(self):
                return {"uygulamalar": {"toplam": 12.5, "liste": [{"ad": "<b>Chrome</b>", "cpu": 12.5}]},
                        "arka_plan": {"toplam": 0.0, "liste": []}}

        self.window = self.make_window()
        store = self.window.game_store
        for game in list(store.games):
            store.remove(game["id"])
        game = store.add("Oyun", r"C:\Oyun", "Elle", r"C:\Oyun\oyun.exe")
        page = self.window._page("oyunlar")
        self.window.navigate("oyunlar")  # menüden gelince liste açılır: alt sayfa navigate'ten SONRA açılır
        page.found, page.editing, page.opened = [], game["id"], True

        def texts():
            return [lab.text() for lab in page.findChildren(QLabel)]

        title = t("ui.canli_surec.baslik")
        with mock.patch.object(canli_surec, "LiveProcesses", FakeLive):
            settings.set("oyun_kaydi", True)
            self.window.game_detector = None  # oyun sürmüyor: kart da ölçüm de yok
            page.data_reloaded()
            self.assertNotIn(title, texts())
            self.assertFalse(page._proc_timer.isActive())
            self.window.game_detector = types.SimpleNamespace(active=(game, 1), stop=lambda: None)
            settings.set("oyun_kaydi", False)  # oyun sürüyor ama kayıt ayarı kapalı: yine yok
            page.data_reloaded()
            self.assertNotIn(title, texts())
            settings.set("oyun_kaydi", True)
            page.data_reloaded()
            self.assertIn(title, texts())
            self.assertTrue(page._proc_timer.isActive())
            page._procs_tick()
            self.assertEqual(FakeLive.made, [])  # pencere ekranda değil (ekran dışı çizim): ölçüm başlamaz
            shown = mock.patch.object(type(page), "isVisible", lambda self: True)
            shown.start()
            page._procs_tick()
            self.assertEqual(FakeLive.made[-1].exe, "oyun.exe")
            self.assertTrue(FakeLive.made[-1].running)
            body = texts()
            self.assertIn(t("ui.canli_surec.grup", ad=t("ui.canli_surec.uygulamalar"), yuzde="%12,5"), body)
            self.assertIn("<b>Chrome</b>  %12,5", body)  # düz metin
            self.assertIn(t("ui.canli_surec.bos"), body)
            shown.stop()  # sayfa görünmüyor: ölçüm durur
            page._procs_tick()
            self.assertFalse(FakeLive.made[-1].running)
            self.assertIsNone(page._procs)
            shown.start()
            page._procs_tick()  # tekrar görününce yeniden başlar
            self.assertTrue(FakeLive.made[-1].running)
            self.window.game_detector = None  # oyun bitti: iş parçacığı ve sayaç kapanır
            page._procs_tick()
            self.assertFalse(FakeLive.made[-1].running)
            self.assertFalse(page._proc_timer.isActive())
            shown.stop()
        settings.set("oyun_kaydi", False)
        store.remove(game["id"])

    def test_game_detector_runs_only_with_live_fps_or_recording(self):
        """"Oyun açık mı" algılayıcısı yalnızca canlı FPS veya oyun kaydı açıkken ve exe'si bilinen oyun varken çalışır."""
        from app.core import settings
        self.addCleanup(settings.set, "oyun_kaydi", False)
        self.addCleanup(settings.set, "canli_fps", False)
        settings.set("oyun_kaydi", False)
        settings.set("canli_fps", False)
        self.window = self.make_window()
        store = self.window.game_store
        for game in list(store.games):
            store.remove(game["id"])
        game = store.add("Oyun", r"C:\Oyun", "Elle", r"C:\Oyun\oyun.exe")
        self.window.update_game_detector()
        self.assertIsNone(self.window.game_detector)  # ikisi de kapalı: hiç çalışmaz
        page = self.window._page("ayarlar")
        page.ensure_built()
        page._set_game_setting("oyun_kaydi", True)
        self.assertIsNotNone(self.window.game_detector)
        page._set_game_setting("oyun_kaydi", False)
        self.assertIsNone(self.window.game_detector)
        store.remove(game["id"])
        settings.set("canli_fps", True)
        self.window.update_game_detector()
        self.assertIsNone(self.window.game_detector)  # oyun listesi boş: çalışmaz

    def test_games_page_saves_persistent_settings(self):
        self.window = self.make_window()
        from app.games import profiles
        store = self.window.game_store
        for game in list(store.games):
            store.remove(game["id"])
        game = store.add("Oyun", r"C:\Oyun", "Elle", r"C:\Oyun\oyun.exe")
        page = self.window._page("oyunlar")
        page.found = []
        page.editing, page.opened = game["id"], True
        page.ensure_built()
        page.draft.update(oncelik="AboveNormal", fso_kapali=True)
        page._save(game)
        self.wait_idle()
        self.wait_for(lambda: not self.window.busy and self.window.c.engine.store.has(game["id"] + "-fso"))
        ifeo = profiles.IFEO + r"\oyun.exe\PerfOptions"
        self.assertEqual(self.sys.read_reg("HKLM", ifeo, "CpuPriorityClass")[0], 6)
        self.assertIn(profiles.FSO_FLAG, self.sys.read_reg("HKCU", profiles.LAYERS_KEY, r"C:\Oyun\oyun.exe")[0])
        self.assertTrue(self.window.c.engine.store.has(game["id"] + "-oncelik"))
        self.assertIsNone(self.window.game_detector)  # canlı FPS / kayıt kapalı: arka planda hiçbir şey çalışmaz
        self.window.revert(game["id"] + "-oncelik", lambda: None)
        self.wait_idle()
        self.assertIsNone(self.sys.read_reg("HKLM", ifeo, "CpuPriorityClass"))
        store.remove(game["id"])

    def test_games_page_preset_fills_draft_without_applying(self):
        self.window = self.make_window()
        store = self.window.game_store
        for game in list(store.games):
            store.remove(game["id"])
        game = store.add("Oyun", r"C:\Oyun", "Elle", r"C:\Oyun\oyun.exe")
        page = self.window._page("oyunlar")
        page.found = []
        page.editing, page.opened = game["id"], True
        page.ensure_built()
        page._apply_preset("performans")
        self.wait_idle()
        self.assertEqual(page.draft["oncelik"], "High")
        self.assertEqual(self.window.c.engine.changed_ids(), [])  # Kaydet'e basılana kadar hiçbir şey uygulanmaz
        self.assertEqual(store.get(game["id"])["profil"]["oncelik"], "Normal")
        store.remove(game["id"])

    def test_games_first_look_is_list_plus_two_buttons_and_advanced_holds_the_rest(self):
        """Oyunlar: ilk bakışta yalnızca liste + 'Oyunu başlat' + 'Önerilen ayarları uygula (N/M)'; gerisi Gelişmiş'te."""
        from PySide6.QtWidgets import QLabel, QPushButton
        folder = Path(tempfile.mkdtemp())
        exe = folder / "oyun.exe"
        exe.write_bytes(b"")
        self.window = self.make_window()
        self.window.resize(1100, 640)
        self.window.show()
        store = self.window.game_store
        for game in list(store.games):
            store.remove(game["id"])
        game = store.add("Oyun", str(folder), "Elle", str(exe))
        self.window.navigate("oyunlar")
        page = self.window._page("oyunlar")
        page.found, page.editing, page.opened, page.advanced_open = [], game["id"], True, False
        page.data_reloaded()
        for _ in range(10):
            self.qt.processEvents()
        visible = lambda cls: [x for x in page.findChildren(cls) if x.isVisibleTo(page)]  # noqa: E731
        buttons = [b.text() for b in visible(QPushButton)]
        self.assertIn(t("ui.oyun_baslat"), buttons)
        self.assertTrue(any(b.startswith(t("ui.oyun_onerilen", n=0, m=0).split("(")[0]) for b in buttons), buttons)
        for hidden in (t("ui.oyun_kaydet"), t("ui.oyun_kaldir"), t("ui.oyun_hazir.dengeli"), t("ui.oyun_hazir.performans")):
            self.assertNotIn(hidden, buttons)
        self.assertLessEqual(len(buttons), 7, buttons)  # tara, elle ekle, satır '…', favori, başlat, önerilen, Gelişmiş
        texts = [lab.text() for lab in visible(QLabel)]
        self.assertFalse(any(t("ui.oyun_ici.baslik") == s for s in texts))  # 'Oyun içi ayarlar' kartı ilk bakışta yok
        self.assertFalse(any(t("ui.anti_cheat_genel") == s for s in texts))
        page.advanced_open = True
        page.data_reloaded()
        for _ in range(10):
            self.qt.processEvents()
        buttons = [b.text() for b in visible(QPushButton)]
        for shown in (t("ui.oyun_kaydet"), t("ui.oyun_kaldir"), t("ui.oyun_hazir.dengeli")):
            self.assertIn(shown, buttons)
        store.remove(game["id"])

    def test_games_settings_file_buttons_only_for_catalog_game_and_disabled_while_open(self):
        """Oyun içi ayarlar kartı: katalogdaki oyunda sakla/geri yükle/sıfırla/geri al; oyun açıkken düğmeler kapalı."""
        import time
        from unittest import mock
        from PySide6.QtWidgets import QLabel, QPushButton
        from app.games import oyun_ayar
        self.window = self.make_window()
        self.window.resize(1100, 640)
        self.window.show()
        store = self.window.game_store
        for game in list(store.games):
            store.remove(game["id"])
        self.window.navigate("oyunlar")
        page = self.window._page("oyunlar")
        info = {"var": True, "calisiyor": False, "sifirla": True, "kopyalar": [{"ad": "20261107-120000", "tarih": "2026-11-07T12:00:00"}],
                "geri_al": "20261107-120100"}
        names = [t(f"ui.oyun_ayar.{k}") for k in ("sakla", "geri_yukle", "sifirla", "geri_al")]

        def show(name, state):
            game = store.add(name, r"C:\Oyun", "Elle", r"C:\Oyun\oyun.exe")
            page.found, page.editing, page.opened, page.advanced_open = [], game["id"], True, True
            with mock.patch.object(oyun_ayar, "status", return_value=state):
                page.data_reloaded()
                for _ in range(50):
                    self.qt.processEvents()
                    time.sleep(0.01)
            store.remove(game["id"])
            return {b.text(): b for b in page.findChildren(QPushButton) if b.isVisibleTo(page) and b.text() in names}

        self.assertEqual(show("Oyun", info), {})
        self.assertFalse(any(lab.text() == t("ui.oyun_ayar.baslik") for lab in page.findChildren(QLabel)))
        buttons = show("VALORANT", info)
        self.assertEqual(sorted(buttons), sorted(names))
        self.assertTrue(all(b.isEnabled() for b in buttons.values()))
        with mock.patch.object(oyun_ayar, "reset") as reset, mock.patch("app.ui.dialogs.ask_yes_no", return_value=True):
            buttons[t("ui.oyun_ayar.sifirla")].click()
            for _ in range(50):
                self.qt.processEvents()
                time.sleep(0.01)
        reset.assert_called_once_with("valorant")
        buttons = show("VALORANT", dict(info, calisiyor=True))
        self.assertTrue(buttons and not any(b.isEnabled() for b in buttons.values()))
        self.assertTrue(any(lab.text() == t("ui.oyun_ayar.acik") for lab in page.findChildren(QLabel) if lab.isVisibleTo(page)))

    def test_games_recommended_button_fills_balanced_preset_and_saves(self):
        from unittest import mock
        from app.games import presets
        self.window = self.make_window()
        store = self.window.game_store
        for game in list(store.games):
            store.remove(game["id"])
        game = store.add("Oyun", r"C:\Oyun", "Elle", r"C:\Oyun\oyun.exe")
        page = self.window._page("oyunlar")
        page.found, page.editing, page.opened = [], game["id"], True
        page.ensure_built()
        with mock.patch.object(page, "_save") as save:
            page._apply_recommended(game)
        expected = presets.build("dengeli", page._two_gpus())
        self.assertTrue(all(page.draft.get(k) == v for k, v in expected.items()))
        save.assert_called_once_with(game)
        done, total = presets.recommended_count(dict(game["profil"], **expected), page._two_gpus())
        self.assertEqual(done, total)  # hepsi uygulanınca düğme yerine 'uygulandı' rozeti gelir
        store.remove(game["id"])

    def test_boost_hero_has_one_big_button_preview_line_and_measured_result(self):
        from PySide6.QtWidgets import QLabel, QPushButton
        self.window = self.make_window()
        self.window.resize(1100, 640)
        self.window.show()
        page = self.window._page("boost")
        page.loading, page.last, page.advanced_open = False, None, False
        page.data = {"en_cok_bellek": [], "bilinen_arka_plan": [],
                     "hedefler": [{"ad": "Discord", "adet": 3, "bellek_mb": 400}, {"ad": "OneDrive", "adet": 1, "bellek_mb": 120}]}
        page.ensure_built()
        page.data_reloaded()
        for _ in range(5):
            self.qt.processEvents()
        visible = lambda cls: [x for x in page.findChildren(cls) if x.isVisibleTo(page)]  # noqa: E731
        texts = [lab.text() for lab in visible(QLabel)]
        self.assertIn(t("ui.boost.onizleme", liste="Discord, OneDrive"), texts)  # tek satır önizleme
        buttons = [b.text() for b in visible(QPushButton)]
        self.assertEqual(buttons.count(t("ui.boost.boost_et")), 1)
        self.assertNotIn(t("ui.boost.kapat"), buttons)                          # program seçme listesi Gelişmiş'te, kapalı
        # sonuç: yalnızca ölçülen sayılar; ölçüm yoksa bellek cümlesi hiç yazılmaz
        done = {"kapanan": ["a", "b", "c"], "acik": ["d"], "surec": 7, "bosalan_mb": 2150}
        self.assertEqual(page.result_text(done, 0), "3 uygulama kapatıldı, 2,1 GB boşaldı. 1 uygulama açık kaldı.")
        self.assertEqual(page.result_text(dict(done, bosalan_mb=640, acik=[]), 2),
                         "3 uygulama kapatıldı, 640 MB boşaldı. 2 ayar açıldı.")
        self.assertEqual(page.result_text(dict(done, bosalan_mb=None, acik=[]), 0),
                         "3 uygulama kapatıldı; bellekte ölçülebilir fark yok.")
        self.assertEqual(page.result_text(None, 1), "1 ayar açıldı.")

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
                     "bilinen_arka_plan": [], "hedefler": []}
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

            class FakeRun:
                def __init__(self, names):
                    calls["kapat"].append(list(names))

                def close(self):
                    return ["discord"]  # discord kapanmadı

                def force(self, names):
                    calls["zorla"].append(list(names))
                    return 1

                def result(self):
                    return {"kapanan": ["chrome", "discord"], "acik": [], "surec": 5, "bosalan_mb": 2150}

            page.data["hedefler"] = [{"ad": "chrome", "adet": 2, "bellek_mb": 900}, {"ad": "discord", "adet": 3, "bellek_mb": 400}]
            with mock.patch("app.ui.page_boost.closer.running", side_effect=lambda names: list(names)), \
                    mock.patch("app.ui.page_boost.boost.Run", FakeRun):
                page._boost()
                self.wait_for(lambda: calls["zorla"])  # çalışma, onay ve zorla sonlandırma art arda arka planda
                self.wait_for(lambda: page.last)
            self.assertEqual(calls["kapat"], [["chrome", "discord"]])
            self.assertEqual(calls["zorla"], [["discord"]])  # yalnızca kapanmayan, ikinci onayla (testte onaylı)
            self.assertTrue(page.last["metin"].startswith("2 uygulama kapatıldı, 2,1 GB boşaldı."))  # ölçülen sayılar
            self.assertEqual(self.window.toast.text(), "✓  " + page.last["metin"])
            self.assertFalse(page.busy)
        finally:
            settings.set("boost_listesi", [])

    def test_one_click_boost_turns_on_safe_settings_and_can_undo(self):
        """Tek tuş Boost: Oyun Modu + Game DVR kapalı (motor yolundan, geri alınabilir); bellek boşaltma vb. yok."""
        from unittest import mock
        from app.core import settings
        self.window = self.make_window()
        page = self.window._page("boost")
        page.loading = False
        page.data = {"en_cok_bellek": [], "bilinen_arka_plan": [], "hedefler": []}
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

    def test_games_card_opens_subpage_hides_list_and_back_or_esc_returns(self):
        """Karta basınca oyunun alt sayfası hemen açılır ("Aşağıda açık" yok): liste ve 'Bulunan' bölümü gizli, üstte '← Oyunlar';
        düğme ve Esc listeye döner (önceki sayfaya değil); menüden yeniden gelince liste görünür; oyun içi ayar kılavuzu yok."""
        from PySide6.QtCore import QEvent
        from PySide6.QtWidgets import QLabel, QPushButton
        from app.ui.page_games import GameCard
        self.window = self.make_window()
        self.window.resize(1100, 640)
        self.window.show()
        store = self.window.game_store
        for game in list(store.games):
            store.remove(game["id"])
        game = store.add("Oyun", r"C:\Oyun", "Elle", r"C:\Oyun\oyun.exe")
        self.window.navigate("oyunlar")
        page = self.window._page("oyunlar")
        self.wait_for(lambda: not page.scanning)  # açılışta başlayan tarama bitmeden bulunan liste elle verilirse ezilir
        page.found = [{"ad": "Bulunan", "klasor": r"C:\Bulunan", "kaynak": "Steam", "exe": None}]
        page.data_reloaded()
        self.qt.processEvents()
        def flush():  # önceki kurulumun silinen kartları gerçekten gitsin
            for _ in range(5):
                self.qt.processEvents()
                time.sleep(0.03)
            self.qt.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)

        texts = lambda: [lab.text() for lab in page.findChildren(QLabel)]  # noqa: E731
        self.assertFalse(page.opened)
        self.assertIn(t("ui.oyun_liste_bulunan"), texts())
        flush()
        cards = page.findChildren(GameCard)
        self.assertEqual(len(cards), 2)
        cards[0].opened.emit()  # kartın herhangi bir yerine basmak
        flush()
        self.assertTrue(page.opened)
        self.assertEqual(page.editing, game["id"])
        self.assertEqual(page.findChildren(GameCard), [])  # liste ve Bulunan gizli (yeniden kurulmadı: hiç yok)
        self.assertNotIn(t("ui.oyun_liste_bulunan"), texts())
        self.assertNotIn("Aşağıda açık", texts())
        back = [b for b in page.findChildren(QPushButton) if b.text() == t("ui.oyun_geri")]
        self.assertEqual(len(back), 1)
        page.advanced_open = True
        page.data_reloaded()
        self.qt.processEvents()
        for gone in (t("ui.oyun_ici.baslik"), t("ui.oyun_rehber"), t("ui.oyun_faydali.baslik")):  # kılavuz Rehber sayfasına taşındı
            self.assertNotIn(gone, texts())
        self.window.search_box.edit.clearFocus()  # odak aramada değil sayfada (aramadayken Esc önce aramayı temizler)
        self.window._escape()  # Esc: alt sayfadan listeye, önceki sayfaya değil
        flush()
        self.assertEqual(self.window.current, "oyunlar")
        self.assertFalse(page.opened)
        self.assertEqual(len(page.findChildren(GameCard)), 2)
        page._open(game["id"])
        flush()
        self.assertTrue(page.opened)
        back = [b for b in page.findChildren(QPushButton) if b.text() == t("ui.oyun_geri")][0]
        back.click()
        self.assertFalse(page.opened)
        page._open(game["id"])
        self.qt.processEvents()
        self.window.navigate("ozet")
        self.window.navigate("oyunlar")  # menüden (yeniden) gelince alt sayfa açık kalmaz
        self.assertFalse(page.opened)
        store.remove(game["id"])

    def test_guide_page_links_per_game_and_no_pro_player_content(self):
        """Rehber sayfası: oyuna göre bağlantılar (sistem gereksinimi / FPS), genel oyun içi maddeler; profesyonel oyuncu içeriği
        hiçbir oyunda yok; oyunun kendi sayfasında oyun içi ayar kılavuzu ve rehber bağlantıları artık görünmez."""
        from PySide6.QtWidgets import QLabel, QPushButton
        self.window = self.make_window()
        self.window.navigate("rehber")
        page = self.window.pages["rehber"]
        links = lambda: [b for b in page.content.findChildren(QPushButton) if b.text() != "i"]  # "i": bilgi düğmesi
        texts = lambda: [lab.text() for lab in page.content.findChildren(QLabel)]
        self.assertIn(t("ui.oyun_ici.baslik"), texts())  # genel: oyun içi ayar maddeleri
        general = len(links())                              # genelde yalnızca "Faydalı bağlantılar" kartının düğmeleri
        page._choose("Valorant")
        self.assertGreater(len(links()), general)
        for button in links():
            self.assertNotIn("prosettings", (button.text() + button.toolTip()).lower())
        page._choose("Yok Oyun")
        self.assertIn(t("ui.oyun_rehber.yok"), texts())
        self.assertFalse(any("rofesyonel" in s for s in texts()))
        names = page.names()
        self.assertIn("Valorant", names)
        self.assertEqual(len(names), len({n.lower() for n in names}))  # aynı oyun iki kez yok
        games = self.window._page("oyunlar")
        for bad in ("_guide_row", "_ingame_card", "_useful_card"):
            self.assertFalse(hasattr(games, bad), bad)

    def test_games_page_picker_and_auto_apply_off(self):
        """Açılır listeden bulunan oyun eklenir; 'otomatik uygula' kapalıyken kalıcı ayar yazılmaz."""
        self.window = self.make_window()
        from app.games import profiles
        store = self.window.game_store
        for game in list(store.games):
            store.remove(game["id"])
        page = self.window._page("oyunlar")
        page.found = [{"ad": "Bulunan", "klasor": r"C:\Bulunan", "kaynak": "Steam", "exe": r"C:\Bulunan\b.exe"}]
        page.ensure_built()
        from PySide6.QtWidgets import QPushButton
        setup = [b for b in page.findChildren(QPushButton) if b.text() == t("ui.oyun_hazirla")]
        self.assertEqual(len(setup), 1)  # bulunan oyun satırında tek 'Hazırla'
        setup[0].click()
        self.assertEqual(store.games[0]["ad"], "Bulunan")
        game = store.games[0]
        self.assertEqual(page.editing, game["id"])
        page.data_reloaded()
        self.qt.processEvents()
        page.draft.update(otomatik=False, oncelik="AboveNormal")
        page._save(game)
        self.wait_idle()
        ifeo = profiles.IFEO + r"\b.exe\PerfOptions"
        self.assertIsNone(self.sys.read_reg("HKLM", ifeo, "CpuPriorityClass"))
        self.assertEqual(store.get(game["id"])["profil"]["oncelik"], "AboveNormal")  # seçim saklandı
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
        self.assertNotIn("smileyw", labels(page))  # bilgi bölümü Ayarlar'dan kaldırıldı
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

    def test_cache_garbage_does_not_crash(self):
        """Denetim B B3: içeriği null / [] / bozuk JSON olan önbellek açılışı çökertmez, yok sayılır."""
        self.window = self.make_window()
        from app.ui.controller import Controller
        other = Controller("onizleme", engine=self.window.c.engine, cache_file=self.window.c.cache_file)
        for text in ("null", "[]", "[1]", "\"x\"", "{bozuk"):
            other.cache_file.write_text(text, encoding="utf-8")
            self.assertFalse(other.load_cache(), text)

    # ------------------------------------------------------------------ oyun sırasında seçenekleri (Hazırla / Geri al)
    def _prep_setup(self):
        """İki oyun, sahte süreç işlemleri ve sahte algılayıcı (gerçek süreç listesine bakılmaz)."""
        from app.games import discovery, runtime

        class FakeOps:
            def __init__(self):
                self.prio = {}

            def list_processes(self):
                return []

            def get_priority(self, pid):
                return 0x20

            def set_priority(self, pid, value):
                self.prio[pid] = value

        class FakeDetector:
            made = []

            def __init__(self, games, ops=None, on_event=None, interval=2.0):
                self.on_event, self.started, self.stopped = on_event, False, False
                FakeDetector.made.append(self)

            def start(self):
                self.started = True

            def stop(self):
                self.stopped = True

        saved = (self.app_module.ProcessOps, self.app_module.GameDetector, discovery.steam_downloading)
        self.app_module.ProcessOps, self.app_module.GameDetector = FakeOps, FakeDetector
        discovery.steam_downloading = lambda *a, **k: False

        def restore():
            self.app_module.ProcessOps, self.app_module.GameDetector, discovery.steam_downloading = saved
        self.addCleanup(restore)
        self.window = self.make_window()
        store = self.window.game_store
        for game in list(store.games):
            store.remove(game["id"])
        self.game_a = store.add("Oyun A", r"C:\A", "Elle", r"C:\A\a.exe")
        self.game_b = store.add("Oyun B", r"C:\B", "Elle", r"C:\B\b.exe")
        FakeDetector.made.clear()
        return FakeDetector, runtime

    def _open_game(self, game):
        self.window.navigate("oyunlar")
        page = self.window._page("oyunlar")
        page.found, page.editing, page.opened, page.draft = [], game["id"], True, None
        page.data_reloaded()
        from PySide6.QtCore import QEvent
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)  # önceki kurulumun düğmeleri silinsin
        self.qt.processEvents()
        return page

    def _switches(self, page):
        from app.ui import widgets as w
        return {s.accessibleName(): s for s in page.findChildren(w.ToggleSwitch) if s.accessibleName()}

    def _prepare_button(self, page):
        return next((b for b in page.findChildren(QPushButton) if b.text() == t("ui.hazirla.dugme")), None)

    def test_game_page_options_off_by_default_saved_per_game(self):
        self._prep_setup()
        page = self._open_game(self.game_a)
        switches = self._switches(page)
        name = t("ui.hazirla.ad.hazirla_rahatsiz_etme")
        self.assertEqual(set(switches), {t(f"ui.hazirla.ad.{k}") for k in profiles.RUNTIME_KEYS})  # düz anahtar, oyunda 6 seçenek
        self.assertFalse(any(s.isChecked() for s in switches.values()))
        self.assertFalse(self._prepare_button(page).isVisibleTo(page))  # hiçbir seçenek açık değil: Hazırla yok
        switches[name].setChecked(True)
        self.qt.processEvents()
        self.assertTrue(self._prepare_button(page).isVisibleTo(page))
        self.assertTrue(self.window.game_store.get(self.game_a["id"])["profil"]["hazirla_rahatsiz_etme"])
        self.assertFalse(self.window.game_store.get(self.game_b["id"])["profil"]["hazirla_rahatsiz_etme"])
        self.assertEqual(self.sys.read_reg("HKCU", "Software\\Microsoft\\Windows\\CurrentVersion\\Notifications\\Settings",
                                           "NOC_GLOBAL_SETTING_TOASTS_ENABLED"), None)  # seçmek sisteme hiçbir şey yazmaz
        page_b = self._open_game(self.game_b)
        self.assertFalse(any(s.isChecked() for s in self._switches(page_b).values()))

    def test_anti_cheat_game_hides_process_and_service_options(self):
        self._prep_setup()
        self.game_b["anti_cheat"] = ["EasyAntiCheat"]
        page = self._open_game(self.game_b)
        names = set(self._switches(page))
        self.assertEqual(names, {t(f"ui.hazirla.ad.{k}") for k in ("hazirla_rahatsiz_etme", "hazirla_steam_uyari", "hazirla_guc_plani")})
        self.assertTrue(any(lab.text() == t("ui.hazirla.anticheat") for lab in page.findChildren(QLabel)))

    def test_prepare_applies_through_engine_and_game_exit_reverts(self):
        detector, runtime = self._prep_setup()
        profile = self.window.game_store.get(self.game_a["id"])["profil"]
        profile["hazirla_rahatsiz_etme"], profile["hazirla_guc_plani"] = True, True
        before = self.sys.state_copy()
        launched = []
        self.assertIsNone(self.window.prep_detector)  # hazırlanmadan hiçbir izleme yok
        self.window.prepare_game(self.game_a, launch=lambda: launched.append(1))
        self.wait_idle()
        self.assertEqual(launched, [1])
        self.assertEqual(self.sys.active_scheme, runtime.HIGH_PERFORMANCE_PLAN,
                         (self.window.status.text(), self.messages[-3:], self.window.busy, self.window._blocked()))
        self.assertEqual(self.sys.read_reg("HKCU", runtime.DND_KEY, runtime.DND_VALUE)[0], 0)
        self.assertTrue(self.window.c.engine.store.has("oyunsirasi-guc"))  # Değişiklikler'de görünür
        self.assertTrue(self.window.game_session.active)
        self.assertEqual(len(detector.made), 1)
        self.assertTrue(detector.made[0].started)
        page = self._open_game(self.game_a)  # alt sayfada "Geri al" var, "Hazırla" yok
        self.assertIsNone(self._prepare_button(page))
        self.assertTrue(any(b.text() == t("ui.hazirla.geri_al") for b in page.findChildren(QPushButton)))
        detector.made[0].on_event("basladi", self.game_a)  # oyun açıldı
        self.wait_idle()
        self.window._prep_timeout()
        self.assertIsNotNone(self.window.game_session)  # oyun açıkken süre dolması geri almaz
        detector.made[0].on_event("bitti", self.game_a)  # oyun kapandı
        deadline = time.time() + 5
        while self.window.game_session is not None and time.time() < deadline:
            self.qt.processEvents()
            time.sleep(0.01)
        self.wait_idle()
        self.assertIsNone(self.window.game_session)
        self.assertEqual(self.sys.state_copy(), before)
        self.assertTrue(detector.made[0].stopped)
        self.assertEqual(self.window.c.engine.store.ids_newest_first(), [])

    def test_startup_recovery_does_not_revert_session_prepared_after_launch(self):
        detector, runtime = self._prep_setup()
        self.window.game_store.get(self.game_a["id"])["profil"]["hazirla_guc_plani"] = True
        self.window.prepare_game(self.game_a)
        self.wait_idle()
        self.window._start_games()  # 500 ms'lik başlangıç taraması tam şimdi çalışsın (zamana bağlı değil)
        self.wait_idle()
        self.assertTrue(self.window.game_session.active)
        self.assertEqual(self.sys.active_scheme, runtime.HIGH_PERFORMANCE_PLAN)
        self.window.unprepare_game()
        self.wait_idle()

    def test_undo_button_and_never_started_timeout_revert(self):
        detector, runtime = self._prep_setup()
        self.window.game_store.get(self.game_a["id"])["profil"]["hazirla_guc_plani"] = True
        before = self.sys.state_copy()
        for how in ("geri_al", "zaman_asimi"):
            self.window.prepare_game(self.game_a)
            self.wait_idle()
            self.assertEqual(self.sys.active_scheme, runtime.HIGH_PERFORMANCE_PLAN)
            if how == "geri_al":
                self.window.unprepare_game()
            else:
                self.window._prep_timeout()  # oyun hiç açılmadı
            self.wait_idle()
            self.assertIsNone(self.window.game_session)
            self.assertEqual(self.sys.state_copy(), before)

    def test_close_while_busy_leaves_session_to_recover(self):
        """Denetim A O1: işlem sürerken 'yine de kapat' denirse aynı oturum ikinci kez (arayüz iş parçacığında) geri
        alınmaz; günlük kalır, sonraki açılışta recover yapar."""
        from PySide6.QtGui import QCloseEvent
        self._prep_setup()
        self.window.game_store.get(self.game_a["id"])["profil"]["hazirla_guc_plani"] = True
        self.window.prepare_game(self.game_a)
        self.wait_idle()
        session, stopped = self.window.game_session, []
        session.stop = lambda: stopped.append(1)
        self.window.busy = True
        self.window.closeEvent(QCloseEvent())
        self.window.busy = False
        self.assertEqual(stopped, [])
        self.assertTrue(session.journal_path.exists())
        type(session).stop(session)  # temizlik: sonraki testlere günlük kalmasın

    def test_prepare_with_nothing_selected_just_launches(self):
        self._prep_setup()
        launched = []
        self.window.prepare_game(self.game_a, launch=lambda: launched.append(1))
        self.assertEqual(launched, [1])
        self.assertIsNone(self.window.game_session)
        self.assertEqual(self.sys.calls, [x for x in self.sys.calls if x not in ("set_active_scheme", "set_service")])

    def test_cover_is_decoded_only_when_first_shown_and_index_is_cached(self):
        """Oyunlar sayfası kapak sayısıyla yavaşlamasın: resim kart ilk çizilirken çözülür (ekrana gelmeyenler hiç), gömülü
        kapak dizini dosya değişmedikçe bir kez ayrıştırılır."""
        from app.games import discovery
        from app.ui.page_games import Cover
        calls = []
        original = Cover.__dict__["_load"]
        Cover._load = classmethod(lambda cls, path: calls.append(path))
        try:
            cover = Cover({"ad": "Oyun"}, "kapak.jpg")
            self.assertEqual(calls, [])          # kurulurken çözülmez
            self.assertIsNone(cover.pixmap)      # ilk erişimde (çizimde) çözülür
            cover.pixmap
            self.assertEqual(calls, ["kapak.jpg"])  # bir kez
        finally:
            Cover._load = original
        path = Path(discovery.paths.data_dir()) / "oyun_kapaklari.json"
        self.assertIs(discovery._cover_entries(path), discovery._cover_entries(path))


if __name__ == "__main__":
    unittest.main()
