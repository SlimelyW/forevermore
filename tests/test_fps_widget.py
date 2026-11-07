"""Oyun üstü FPS kutusu: sahte user32 ve sahte canlı FPS ile (gerçek kısayol, gerçek oyun, gerçek pencere yok).

Çalıştırma: set QT_QPA_PLATFORM=offscreen ve py -3.12 -m unittest tests.test_fps_widget -v
"""

import ctypes
import os
import types
import unittest
from ctypes import wintypes
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # test gerçek ekranda pencere açmasın

import shiboken6
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.core import i18n
from app.ui import fps_widget, theme
from app.ui.fps_widget import FpsWidget, text_for

OLCULUYOR = {"durum": "olculuyor", "fps": 144}


class TestText(unittest.TestCase):
    def setUp(self):
        i18n.load("tr")

    def test_measuring(self):
        self.assertEqual(text_for(OLCULUYOR), "144 FPS")
        self.assertEqual(text_for(OLCULUYOR, 73), "144 FPS · VRAM %73")

    def test_no_frames_is_not_zero_fps(self):
        self.assertEqual(text_for({"durum": "kare_yok", "fps": None}), "— FPS")

    def test_hidden_when_not_measuring(self):
        for state in ("basliyor", "duraklatildi", "baslamadi", "presentmon_yok", "hata"):
            self.assertIsNone(text_for({"durum": state, "fps": None}), state)

    def test_english_percent(self):
        i18n.load("en")
        self.addCleanup(i18n.load, "tr")
        self.assertEqual(text_for(OLCULUYOR, 73), "144 FPS · VRAM 73%")


class TestAllowed(unittest.TestCase):
    """Varsayılan kapalı; anti-cheat'li oyunda kutu HİÇBİR durumda açılmaz."""

    PLAIN, GUARDED = {"id": "a"}, {"id": "b", "anti_cheat": ["Riot Vanguard"]}

    def check(self, game, **values):
        from app.ui.app import MainWindow as App
        fake = types.SimpleNamespace(live_fps_allowed=lambda g: App.live_fps_allowed(None, g))
        with mock.patch("app.core.settings.get",
                        side_effect=lambda k: values.get(k, False if k in ("canli_fps", "fps_widget") else [])):
            return App.fps_widget_allowed(fake, game)

    def test_rules(self):
        self.assertFalse(self.check(self.PLAIN))                                      # varsayılan
        self.assertFalse(self.check(self.PLAIN, fps_widget=True))                     # canlı FPS kapalı
        self.assertFalse(self.check(self.PLAIN, canli_fps=True))                      # kutu kapalı
        self.assertTrue(self.check(self.PLAIN, fps_widget=True, canli_fps=True))

    def test_anti_cheat_never(self):
        on = {"fps_widget": True, "canli_fps": True}
        self.assertFalse(self.check(self.GUARDED, **on))
        self.assertFalse(self.check(self.GUARDED, **on, canli_fps_izinli=["b"], fps_widget_izinli=["b"]))  # eski izinler

    def test_defaults_are_off(self):
        from app.core.settings import DEFAULTS
        self.assertIs(DEFAULTS["fps_widget"], False)
        self.assertNotIn("fps_widget_izinli", DEFAULTS)
        self.assertNotIn("canli_fps_izinli", DEFAULTS)


class TestVramPercent(unittest.TestCase):
    def test_percent_below_warning_level_is_still_shown(self):
        from app.ui.app import _vram_percent
        gb = 2 ** 30
        self.assertEqual(_vram_percent(types.SimpleNamespace(read=lambda: (4 * gb, 8 * gb))), 50)

    def test_unreadable_or_integrated_gives_none(self):
        from app.ui.app import _vram_percent
        self.assertIsNone(_vram_percent(None))
        self.assertIsNone(_vram_percent(types.SimpleNamespace(read=lambda: None)))
        self.assertIsNone(_vram_percent(types.SimpleNamespace(read=lambda: (1, 512 * 2 ** 20))))


class TestWidget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        i18n.load("tr")
        cls.qt = QApplication.instance() or QApplication([])

    def make(self, source=lambda: "144 FPS", registered=True):
        user32 = mock.Mock()
        user32.RegisterHotKey.return_value = 1 if registered else 0
        widget = FpsWidget(source, user32=user32)
        self.addCleanup(widget.stop)
        return widget, user32

    def test_window_cannot_be_clicked_or_take_focus(self):
        widget, _ = self.make()
        for flag in (Qt.WindowType.WindowTransparentForInput, Qt.WindowType.WindowDoesNotAcceptFocus,
                     Qt.WindowType.WindowStaysOnTopHint, Qt.WindowType.FramelessWindowHint, Qt.WindowType.Tool):
            self.assertTrue(widget.windowFlags() & flag, flag)
        self.assertTrue(widget.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating))

    def test_background_is_painted_and_window_has_opacity(self):
        """Saydam pencere bayrağı QLabel arka planını siler; yazı oyunun üstünde okunmaz olur."""
        self.qt.setStyleSheet(theme.stylesheet())
        self.addCleanup(self.qt.setStyleSheet, "")
        widget, _ = self.make()
        image = widget.grab().toImage()
        self.assertEqual(image.pixelColor(4, image.height() // 2).alpha(), 255)
        self.assertLess(widget.windowOpacity(), 1.0)

    def test_shows_source_text_in_corner(self):
        widget, _ = self.make()
        self.assertTrue(widget.isVisible())
        self.assertEqual(widget.text(), "144 FPS")
        area = self.qt.primaryScreen().geometry()
        self.assertEqual((widget.x(), widget.y()), (area.left() + fps_widget.MARGIN, area.top() + fps_widget.MARGIN))

    def test_hides_when_source_gives_nothing(self):
        values = ["144 FPS"]
        widget, _ = self.make(lambda: values[0])
        values[0] = None
        widget.refresh()
        self.assertFalse(widget.isVisible())
        values[0] = "60 FPS"
        widget.refresh()
        self.assertTrue(widget.isVisible())
        self.assertEqual(widget.text(), "60 FPS")

    def test_hotkey_is_alt_h_without_repeat(self):
        widget, user32 = self.make()
        _hwnd, key_id, mods, vk = user32.RegisterHotKey.call_args.args
        self.assertEqual((key_id, mods, vk), (fps_widget.HOTKEY_ID, 0x4001, 0x48))
        self.assertTrue(widget.hotkey)

    def test_hotkey_conflict_is_silent_and_box_still_works(self):
        widget, user32 = self.make(registered=False)
        self.assertFalse(widget.hotkey)
        self.assertTrue(widget.isVisible())
        widget.stop()
        user32.UnregisterHotKey.assert_not_called()

    def test_toggle_hides_and_does_not_read_source_while_hidden(self):
        source = mock.Mock(return_value="144 FPS")
        widget, _ = self.make(source)
        widget.toggle()
        self.assertFalse(widget.isVisible())
        source.reset_mock()
        widget.refresh()
        source.assert_not_called()
        self.assertFalse(widget.isVisible())
        widget.toggle()
        self.assertTrue(widget.isVisible())

    def send(self, widget, message, wparam):
        msg = wintypes.MSG(None, message, wparam, 0, 0, wintypes.POINT(0, 0))
        return widget.nativeEvent(b"windows_generic_MSG", shiboken6.VoidPtr(ctypes.addressof(msg)))

    def test_wm_hotkey_toggles_only_for_our_id(self):
        widget, _ = self.make()
        self.send(widget, fps_widget.WM_HOTKEY, fps_widget.HOTKEY_ID + 1)
        self.assertTrue(widget.isVisible())
        handled, _result = self.send(widget, fps_widget.WM_HOTKEY, fps_widget.HOTKEY_ID)
        self.assertTrue(handled)
        self.assertFalse(widget.isVisible())

    def test_stop_releases_hotkey_and_timer(self):
        widget, user32 = self.make()
        widget.stop()
        self.assertEqual(user32.UnregisterHotKey.call_args.args[1], fps_widget.HOTKEY_ID)
        self.assertFalse(widget.timer.isActive())
        self.assertFalse(widget.isVisible())


class TestLifecycle(unittest.TestCase):
    """Kutu (ve Alt+H) yalnızca canlı FPS sürerken ve izinliyken yaşar."""

    def app(self, live=True, allowed=True):
        from app.ui.app import MainWindow as App
        return App, types.SimpleNamespace(fps_widget=None, live_fps=object() if live else None, live_fps_game={"id": "a"},
                                          fps_widget_allowed=lambda _g: allowed, _fps_widget_text=lambda: None)

    def test_opens_once_and_closes_when_live_fps_stops(self):
        App, fake = self.app()
        with mock.patch.object(fps_widget, "FpsWidget") as cls:
            App.update_fps_widget(fake)
            App.update_fps_widget(fake)
            cls.assert_called_once()
            box = fake.fps_widget
            fake.live_fps = None
            App.update_fps_widget(fake)
        box.stop.assert_called_once()
        self.assertIsNone(fake.fps_widget)

    def test_closes_when_setting_turned_off_mid_game(self):
        App, fake = self.app()
        with mock.patch.object(fps_widget, "FpsWidget"):
            App.update_fps_widget(fake)
            box = fake.fps_widget
            fake.fps_widget_allowed = lambda _g: False
            App.update_fps_widget(fake)
        box.stop.assert_called_once()

    def test_not_created_when_not_allowed_or_no_live_fps(self):
        for live, allowed in ((True, False), (False, True)):
            App, fake = self.app(live, allowed)
            with mock.patch.object(fps_widget, "FpsWidget") as cls:
                App.update_fps_widget(fake)
            cls.assert_not_called()


if __name__ == "__main__":
    unittest.main()
