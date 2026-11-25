"""A1: fare tekerleği değer değiştirmez, sayfa kayar. A2: bölüm yerinde açılır, kaydırma korunur."""

import unittest

try:
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtWidgets import QApplication, QComboBox, QScrollArea, QSlider, QSpinBox, QVBoxLayout, QWidget
except ImportError:  # pragma: no cover
    QApplication = None


def _wheel(widget, down=True):
    delta = -120 if down else 120
    event = QWheelEvent(QPointF(5, 5), QPointF(widget.mapToGlobal(QPoint(5, 5))), QPoint(0, 0), QPoint(0, delta),
                        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(widget, event)


@unittest.skipIf(QApplication is None, "PySide6 kurulu değil")
class TestWheelGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.ui import widgets
        cls.qt = QApplication.instance() or QApplication([])
        widgets.install_wheel_guard(cls.qt)

    def test_values_do_not_change_and_page_scrolls(self):
        area = QScrollArea()
        area.setWidgetResizable(True)
        body = QWidget()
        lay = QVBoxLayout(body)
        combo, spin, slider = QComboBox(), QSpinBox(), QSlider(Qt.Orientation.Horizontal)
        combo.addItems(["a", "b", "c"])
        spin.setRange(0, 10)
        spin.setValue(5)
        slider.setRange(0, 10)
        slider.setValue(5)
        for widget in (combo, spin, slider):
            lay.addWidget(widget)
        lay.addSpacing(3000)
        area.setWidget(body)
        area.resize(300, 200)
        area.show()
        self.qt.processEvents()
        bar = area.verticalScrollBar()
        for widget in (combo, spin, spin.findChild(QWidget), slider):
            _wheel(widget)
        self.assertEqual((combo.currentIndex(), spin.value(), slider.value()), (0, 5, 5))
        self.assertGreater(bar.value(), 0, "tekerlek sayfayı kaydırmalı")
        area.close()

    def test_expand_keeps_scroll(self):
        from app.ui import motion
        box = QWidget()
        QVBoxLayout(box).addSpacing(80)
        box.setVisible(False)
        holder = QWidget()
        QVBoxLayout(holder).addWidget(box)
        holder.show()
        motion.expand(box, True)  # testlerde hareket azaltılmış: anında
        self.assertTrue(box.isVisible())
        motion.expand(box, False)
        self.assertFalse(box.isVisible())
        holder.close()


class TestMotionPause(unittest.TestCase):
    def test_pause_reasons_are_independent(self):
        """Ölçüm ve arka plan duraklatması birbirini bozmaz (odak geri gelince ölçüm sürerken animasyon başlamaz)."""
        from unittest import mock
        from app.ui import motion
        with mock.patch.dict("os.environ", {"PCOPT_HAREKET": ""}), \
                mock.patch.object(motion, "windows_animations_off", lambda: False), \
                mock.patch.object(motion.settings, "get", lambda _k: False), \
                mock.patch.object(motion, "_paused", set()):  # önceki testlerin pencereleri etkilemesin
            self.assertEqual(motion.ms(200), 200)
            motion.set_paused(True, "olcum")
            motion.set_paused(True, "arka_plan")
            motion.set_paused(False, "arka_plan")
            self.assertEqual(motion.ms(200), 0)
            motion.set_paused(False, "olcum")
            self.assertEqual(motion.ms(200), 200)


if __name__ == "__main__":
    unittest.main()
