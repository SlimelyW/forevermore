"""Ekran yerleşim şemasında sürükle-bırak: konum Windows'taki gibi kenara oturur, birincil ekran taşınmaz."""
import unittest

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.ui.managers_ui import LayoutMap, snap_layout

HD = (1920, 1080)


class TestSnap(unittest.TestCase):
    def test_edge_snap_and_alignment(self):
        self.assertEqual(snap_layout(HD, [(0, 0, 1920, 1080)], 1930, 20, 190), (1920, 0))        # sağa bitişir, üst kenar hizalanır
        self.assertEqual(snap_layout(HD, [(0, 0, 1920, 1080)], -1900, 400, 190), (-1920, 400))   # sola bitişir, dikey serbest

    def test_no_overlap_and_no_gap(self):
        x, y = snap_layout(HD, [(0, 0, 1920, 1080)], 500, 100, 190)   # birincilin üstüne bırakıldı
        self.assertTrue(x + 1920 <= 0 or x >= 1920 or y + 1080 <= 0 or y >= 1080)
        self.assertTrue(x in (1920, -1920) or y in (1080, -1080))      # bitişik

    def test_far_drop_still_touches(self):
        x, y = snap_layout(HD, [(0, 0, 1920, 1080)], 9000, 9000, 190)
        self.assertTrue(x == 1920 or y == 1080)   # en yakın bitişik konum

    def test_single_screen_unchanged(self):
        self.assertEqual(snap_layout(HD, [], 40, 50, 190), (40, 50))


class TestLayoutMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make(self, movable=True):
        items = [{"aygit": "A", "x": 0, "y": 0, "genislik": 1920, "yukseklik": 1080, "birincil": True},
                 {"aygit": "B", "x": 1920, "y": 0, "genislik": 1920, "yukseklik": 1080, "birincil": False}]
        self.moved, self.selected = [], []
        widget = LayoutMap(items, "A", self.selected.append, (lambda d, x, y: self.moved.append((d, x, y))) if movable else None)
        widget.resize(600, 190)
        return widget

    def center(self, widget, device):
        rect = next(r for d, r, _n in widget._rects() if d == device)
        return QPoint(int(rect.center().x()), int(rect.center().y()))

    def drag(self, widget, device, dx, dy):
        start = self.center(widget, device)
        QTest.mousePress(widget, Qt.LeftButton, Qt.NoModifier, start)
        QTest.mouseMove(widget, start + QPoint(dx, dy))
        QTest.mouseRelease(widget, Qt.LeftButton, Qt.NoModifier, start + QPoint(dx, dy))

    def test_click_selects_without_moving(self):
        widget = self.make()
        QTest.mouseClick(widget, Qt.LeftButton, Qt.NoModifier, self.center(widget, "B"))
        self.assertEqual((self.selected, self.moved), (["B"], []))

    def test_drag_secondary_screen_below_primary(self):
        widget = self.make()
        rect = next(r for d, r, _n in widget._rects() if d == "A")
        self.drag(widget, "B", -int(rect.width() * 0.5), int(rect.height() * 1.1))
        (device, x, y), = self.moved
        self.assertEqual(device, "B")
        self.assertTrue(y == 1080 or x in (1920, -1920))           # birincilin altına ya da yanına oturdu
        self.assertFalse(x < 1920 and y < 1080 and x > -1920 and y > -1080)  # üst üste binmedi

    def test_primary_is_not_movable(self):
        widget = self.make()
        self.drag(widget, "A", 60, 40)
        self.assertEqual(self.moved, [])

    def test_read_only_when_changes_are_not_allowed(self):
        widget = self.make(movable=False)
        self.drag(widget, "B", 60, 40)
        self.assertEqual(self.moved, [])


if __name__ == "__main__":
    unittest.main()
