"""Kart ızgarası (arayüz Tur 3B): sütun sayısı genişliğe göre, satırdaki kartlar eşit boyda, uzun metin kırpılır."""

import unittest

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication, QFrame, QSizePolicy

from app.ui import widgets as w

_app = QApplication.instance() or QApplication([])


def _card(height):
    frame = QFrame()
    frame.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)  # alt sınır: büyüyebilir (gerçek kart gibi)
    frame.setMinimumHeight(height)
    return frame


class IzgaraTesti(unittest.TestCase):
    GRID = (320, 3)

    def test_sutun_sayisi_genislige_gore(self):
        box = w.flow(spacing=12, grid=self.GRID)
        lay = box.layout()
        for width, cols in ((250, 1), (320, 1), (651, 1), (652, 2), (983, 2), (984, 3), (2000, 3)):
            self.assertEqual(lay.columns(width), cols, width)

    def _place(self, heights, width):
        cards = [_card(h) for h in heights]
        box = w.flow(*cards, spacing=12, grid=self.GRID)
        box.setGeometry(QRect(0, 0, width, 10))
        box.layout().setGeometry(QRect(0, 0, width, 10))
        return box, cards

    def test_satirdaki_kartlar_esit_boyda_ve_esit_genislikte(self):
        _box, cards = self._place([100, 140, 120, 90], 1000)  # 3 sütun
        first = cards[:3]
        self.assertEqual({c.height() for c in first}, {140})
        self.assertEqual(len({c.width() for c in first}), 1)
        self.assertEqual([c.y() for c in first], [0, 0, 0])
        self.assertGreater(cards[3].y(), 0)  # dördüncü kart alt satıra
        self.assertEqual(cards[3].x(), 0)
        self.assertEqual(cards[3].height(), 90)

    def test_dar_pencerede_tek_sutun_ve_yukseklik_toplami(self):
        box, cards = self._place([50, 60], 400)
        self.assertEqual([c.x() for c in cards], [0, 0])
        self.assertEqual(box.layout().heightForWidth(400), 50 + 12 + 60)

    def test_ortada_iki_sutun(self):
        _box, cards = self._place([80, 80, 80], 700)
        self.assertEqual([c.y() == 0 for c in cards], [True, True, False])

    def test_akis_kipi_degismedi(self):
        a, b = QFrame(), QFrame()
        a.setFixedSize(100, 20)
        b.setFixedSize(100, 20)
        box = w.flow(a, b, spacing=6)
        self.assertIsNone(box.layout()._grid)
        self.assertEqual(box.layout().heightForWidth(300), 20)   # yan yana
        self.assertEqual(box.layout().heightForWidth(150), 46)   # alt alta


class ClampLabelTesti(unittest.TestCase):
    def _label(self, text, lines, width=200):
        label = w.ClampLabel(text, lines)
        label.resize(width, 60)
        label._fit()
        return label

    def test_kisa_metin_kirpilmaz(self):
        label = self._label("Kısa açıklama", 2)
        self.assertEqual(label.text(), "Kısa açıklama")
        self.assertEqual(label.toolTip(), "")

    def test_uzun_metin_en_cok_iki_satir_ve_uc_nokta(self):
        full = "Bu açıklama çok uzun ve kartın iki satırına sığmaz, o yüzden sonu kesilir " * 3
        label = self._label(full, 2)
        self.assertLessEqual(len(label.text().split("\n")), 2)
        self.assertTrue(label.text().endswith("…"))
        self.assertEqual(label.toolTip(), full)
        self.assertEqual(label.accessibleName(), full)  # ekran okuyucuya tam metin

    def test_yukseklik_hep_ayni(self):
        self.assertEqual(self._label("a", 2).height(), self._label("b " * 200, 2).height())

    def test_tek_uzun_sozcuk_taşmaz(self):
        label = self._label("x" * 300, 2)
        self.assertTrue(label.text().endswith("…"))


if __name__ == "__main__":
    unittest.main()
