"""Ortak görsel parçalar: aç/kapa düğmesi, rozetler, kartlar, sayfa tabanı."""

import os
import subprocess

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QPoint, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtCore import QAbstractAnimation, QVariantAnimation
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QAbstractButton, QAbstractScrollArea, QAbstractSlider, QAbstractSpinBox, QComboBox,
                               QFrame, QGridLayout, QHBoxLayout, QLabel, QLayout, QPushButton, QScrollArea,
                               QScrollBar, QSizePolicy, QStyle, QStyleOptionButton, QStylePainter,
                               QVBoxLayout, QWidget)

from app.core import log, paths, powershell
from app.core.i18n import t, value_label
from app.engine.schema import validate_opener
from app.ui import motion, theme

_log = log.get("ui")


class WheelGuard(QObject):
    """Fare tekerleği açılır liste, sayı kutusu ve kaydırıcının değerini değiştirmez; sayfa kaydırılır.
    Değer yalnızca tıklama, sürükleme veya klavyeyle değişir. Açık liste penceresinin içi etkilenmez."""

    VALUE_WIDGETS = (QComboBox, QAbstractSpinBox, QAbstractSlider)

    def eventFilter(self, obj, event):
        if event.type() != QEvent.Type.Wheel or not isinstance(obj, QWidget):
            return False
        widget = obj
        while not isinstance(widget, self.VALUE_WIDGETS):
            if widget is None or widget.isWindow():
                return False
            widget = widget.parentWidget()
        if isinstance(widget, QScrollBar):
            return False  # kaydırma çubuğunun kendisi
        area = widget.parentWidget()
        while area is not None and not isinstance(area, QAbstractScrollArea):
            area = area.parentWidget()
        if area is not None:
            QCoreApplication.sendEvent(area.verticalScrollBar(), event)
        return True


def install_wheel_guard(qt_app):
    if getattr(qt_app, "_wheel_guard", None) is None:
        qt_app._wheel_guard = WheelGuard(qt_app)
        qt_app.installEventFilter(qt_app._wheel_guard)


def repolish(widget):
    """setProperty sonrası stilin yeniden uygulanması için."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class ToggleSwitch(QAbstractButton):
    """Elle çizilen aç/kapa düğmesi. Tıklayınca durum ANINDA değişir; topuz 160 ms'de hafif yayla kayar
    (yalnızca çizim konumu, yerleşim değişmez). Programla değiştirilince (durum okununca) atlar.
    waiting: işlem sürerken tıklama kabul edilmez ama düğme soluklaşmaz (iyimser görünüm)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setFixedSize(48, 40)  # 40 px yüksek tıklama alanı; çizim 28 px, dikeyde ortalanır
        self._pos = 0.0          # 0 = kapalı, 1 = açık (çizim konumu)
        self._anim = None
        self.waiting = False

    def sizeHint(self):
        return QSize(48, 40)

    def set_waiting(self, on):
        self.waiting = on
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, on)

    def nextCheckState(self):  # kullanıcı tıkladı: anında durum, kısa animasyon
        start = self._pos
        super().nextCheckState()  # setChecked -> checkStateSet konumu sıçratır; animasyon eski konumdan başlar
        self._pos = start
        self._animate_to(1.0 if self.isChecked() else 0.0)

    def checkStateSet(self):  # programla (setChecked): atla
        super().checkStateSet()
        if self._anim is None or self._anim.state() != QAbstractAnimation.State.Running:
            self._pos = 1.0 if self.isChecked() else 0.0
            self.update()

    def _animate_to(self, target):
        duration = motion.ms(motion.TOGGLE_MS)
        if not duration:
            self._pos = target
            self.update()
            return
        if self._anim is None:
            self._anim = QVariantAnimation(self)
            self._anim.valueChanged.connect(self._step)
        self._anim.stop()
        self._anim.setDuration(duration)
        self._anim.setEasingCurve(motion.SPRING)
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(target)
        self._anim.start()

    def _step(self, value):
        self._pos = value
        self.update()

    def paintEvent(self, _event):
        p = theme.palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(0, (self.height() - 28) / 2)
        pos = max(0.0, min(1.0, self._pos))
        off, on = QColor(p["track_off"]), QColor(p["accent"])
        track = QColor(int(off.red() + (on.red() - off.red()) * pos), int(off.green() + (on.green() - off.green()) * pos),
                       int(off.blue() + (on.blue() - off.blue()) * pos))
        enabled = self.isEnabled() or self.waiting
        if not enabled:
            track.setAlpha(110)
        if self.hasFocus():  # klavye odağı: net mor halka (theme: mor yalnızca vurgu)
            painter.setPen(QPen(QColor(p["purple"]), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(1, 1, 46, 26), 13, 13)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track)
        painter.drawRoundedRect(QRectF(2, 4, 44, 20), 10, 10)
        knob = QColor(p["knob"])
        if not enabled:
            knob.setAlpha(170)
        painter.setBrush(knob)
        painter.drawEllipse(QRectF(5 + self._pos * 24, 7, 14, 14))  # yay taşması topuzu biraz öteye götürebilir


class IconTile(QWidget):
    """Renkli, yuvarlak köşeli simge kutusu (kategori rengi). Stil sayfası yerine elle çizilir."""

    def __init__(self, glyph, color, size=36, letter=False):
        super().__init__()
        self.glyph, self.color, self.size_, self.letter = glyph, color, size, letter
        self.setFixedSize(size, size)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(theme.soft(self.color, 46))
        painter.drawRoundedRect(QRectF(0, 0, self.size_, self.size_), self.size_ * 0.28, self.size_ * 0.28)
        painter.setPen(QColor(self.color))
        painter.setFont(theme.ui_font(int(self.size_ * 0.5), bold=True) if self.letter
                        else theme.icon_font(int(self.size_ * 0.47)))
        painter.drawText(self.rect(), int(Qt.AlignmentFlag.AlignCenter), self.glyph)


def logo_pixmap(height):
    """Yaprak motifli sonsuzluk logosu (data/logo.png); dosya yoksa None."""
    pixmap = QPixmap(str(paths.data_dir() / "logo.png"))
    if pixmap.isNull():
        return None
    return pixmap.scaledToHeight(height, Qt.TransformationMode.SmoothTransformation)


def logo(height):
    """Logo etiketi; yüksek DPI ekranda bulanık olmasın diye iki kat çözünürlükle çizilir."""
    pixmap = logo_pixmap(height * 2)
    if pixmap is None:
        return None
    pixmap.setDevicePixelRatio(2)
    widget = QLabel()
    widget.setPixmap(pixmap)
    widget.setFixedSize(pixmap.width() // 2, height)
    return widget


def summary_text(text, limit=150):
    """Kart altındaki tek satırlık özet: metnin ilk cümlesi (uzunsa kısaltılır)."""
    text = (text or "").strip()
    for mark in (". ", "! ", "? "):
        index = text.find(mark)
        if 0 < index < limit:
            return text[:index + 1]
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def summary_label(text):
    widget = QLabel(summary_text(text))
    widget.setObjectName("Summary")
    widget.setWordWrap(True)
    return widget


def label(text, muted=False, wrap=True, bold=False, size=None, selectable=False, plain=False):
    """plain=True: üçüncü taraftan gelen metin (eklenti adı vb.) HTML sayılmaz."""
    widget = QLabel(text)
    if plain:
        widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(wrap)
    if muted:
        widget.setProperty("muted", True)
    if bold or size:
        widget.setFont(theme.ui_font(size or 13, bold))
    if selectable:
        widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return widget


def title(text):
    widget = QLabel(text)
    widget.setObjectName("Title")
    return widget


def section_title(text):
    widget = QLabel(text)
    widget.setObjectName("Section")
    return widget


def badge(text, tone):
    widget = QLabel(text)
    widget.setProperty("tone", tone)
    widget.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    font = widget.font()
    font.setPixelSize(11)
    font.setWeight(font.Weight.DemiBold)
    widget.setFont(font)
    return widget


def impact_badge(level):
    return badge(t("ui.etki", seviye=value_label("deger.etki", level)), theme.IMPACT_TONE.get(level, "mor"))


def risk_badge(risk):
    return badge(t(f"ui.risk.{risk}"), theme.RISK_TONE.get(risk, "uyari"))


def reality_badge(reality):
    return badge(t("ui.gerceklik", durum=value_label("deger.gerceklik", reality)),
                 theme.REALITY_TONE.get(reality, "uyari"))


def colored(text, tone, wrap=True):
    widget = QLabel(text)
    widget.setProperty("fg", tone)
    widget.setWordWrap(wrap)
    return widget


class Toast(QFrame):
    """Pencerenin altında kısa süre görünen yeşil onay (modal değil). `action` verilirse yanında tek bir düğme çıkar
    (ör. "Geri al"); düğmesiz onay tıklamayı geçirir."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("Toast")
        self.label = QLabel()
        self.button = QPushButton()
        self.button.setObjectName("ToastAction")
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.clicked.connect(self._clicked)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 6, 8, 6)
        lay.setSpacing(12)
        lay.addWidget(self.label)
        lay.addWidget(self.button)
        self._action = None
        self.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def text(self):
        return self.label.text()

    def _clicked(self):
        action, self._action = self._action, None
        self.hide()
        if action:
            action()

    def show_text(self, text, ms=3200, action=None, action_label=""):
        self._action = action
        self.label.setText("✓  " + text)
        self.button.setVisible(action is not None)
        self.button.setText(action_label)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, action is None)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.adjustSize()
        parent = self.parentWidget()
        self.move(max(0, (parent.width() - self.width()) // 2), max(0, parent.height() - self.height() - 56))
        self.show()
        self.raise_()
        motion.fade_in(self)
        self._timer.start(ms)


class Card(motion.HoverFade, QFrame):
    def __init__(self, parent=None, layout="v", margins=(24, 20, 24, 20), spacing=6, hover=False):
        super().__init__(parent)
        self.hover = hover  # satır/tıklanır kartlarda üstüne gelince parlama
        self.setObjectName("Card")
        lay = QVBoxLayout(self) if layout == "v" else QHBoxLayout(self)
        lay.setContentsMargins(*margins)
        lay.setSpacing(spacing)
        self.lay = lay

    def set_highlight(self, on):
        self.setProperty("highlight", on)
        repolish(self)


def skeleton(height, width=None):
    """Yüklenirken yer tutucu: düz, sakin bir blok (parıltı döngüsü yok: boşta CPU 0)."""
    block = QFrame()
    block.setObjectName("Skeleton")
    block.setFixedHeight(height)
    if width:
        block.setMaximumWidth(width)
    return block


class RowList(QFrame):
    """Ayar satırlarını tek kartta toplar, aralarına ince çizgi koyar. Her satırın ayrı çerçeveli kart olması
    sayfayı aynı anda boş (kartların içi) ve kalabalık (üst üste çerçeveler) gösteriyordu (tasarım yönü A)."""

    def __init__(self):
        super().__init__()
        self.setObjectName("List")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(4, 4, 4, 4)
        self.lay.setSpacing(0)

    def add(self, row):
        if self.lay.count():
            line = QFrame()
            line.setObjectName("Divider")
            line.setFixedHeight(1)
            self.lay.addWidget(line)
        if isinstance(row, Card):
            row.setProperty("inlist", True)
            row.hover_radius = 8
            row.lay.setContentsMargins(16, 12, 16, 12)
        self.lay.addWidget(row)
        return row


def hbox(*widgets, spacing=6):
    """Yatay sıra. None = boşluk; (widget, 1) = kalan genişliği bu widget alır
    (uzun başlıkların erken satır kırmasını önler)."""
    row = QWidget()
    lay = QHBoxLayout(row)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(spacing)
    for widget in widgets:
        if widget is None:
            lay.addStretch(1)
        elif isinstance(widget, tuple):
            lay.addWidget(widget[0], widget[1])
        else:
            lay.addWidget(widget)
    return row


class PressButton(QPushButton):
    """Basılıyken %97 ölçekle çizilir: dokunsal geri bildirim anında başlar, eylemi bekletmez.
    Yerleşim değişmez (yalnızca çizim ölçeklenir); stil sayfası aynen uygulanır."""

    def paintEvent(self, event):
        if not self.isDown():
            super().paintEvent(event)
            return
        painter = QStylePainter(self)
        center = QRectF(self.rect()).center()
        painter.translate(center)
        painter.scale(0.97, 0.97)
        painter.translate(-center)
        option = QStyleOptionButton()
        self.initStyleOption(option)
        painter.drawControl(QStyle.ControlElement.CE_PushButton, option)


def button(text, on_click=None, primary=False, warn=False, width=None):
    widget = PressButton(text)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    widget.setFocusPolicy(Qt.FocusPolicy.TabFocus)  # mor odak halkası yalnızca klavyeyle gelinince görünür
    if primary:
        widget.setProperty("primary", True)
    if warn:
        widget.setProperty("warn", True)
    if width:
        widget.setFixedWidth(width)
    if on_click:
        widget.clicked.connect(on_click)
    return widget


def icon_button(glyph, tooltip, on_click):
    """Yuvarlak, simgeli küçük düğme (ör. eski haline getir)."""
    widget = PressButton(glyph)
    widget.setObjectName("IconButton")
    widget.setFixedSize(40, 40)  # tıklama alanı 40 px; görünen daire 28 px (stil sayfasında margin)
    widget.setFont(theme.icon_font(13))
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    widget.setToolTip(tooltip)
    widget.setAccessibleName(tooltip)
    widget.clicked.connect(on_click)
    return widget


def info_button(on_click):
    widget = PressButton("i")
    widget.setObjectName("InfoButton")
    widget.setFixedSize(40, 40)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    widget.setToolTip(t("ui.bilgi_ipucu"))
    widget.clicked.connect(on_click)
    return widget


def banner(text, tone, *buttons):
    """Renkli şerit; isteğe bağlı düğmeler sağda."""
    frame = QFrame()
    frame.setProperty("banner", tone)
    lay = QHBoxLayout(frame)
    lay.setContentsMargins(12, 7, 12, 7)
    lab = QLabel(text)
    lab.setWordWrap(True)
    lay.addWidget(lab, 1)
    for item in buttons:
        lay.addWidget(item)
    return frame


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            # Silinme bir sonraki olay döngüsüne kalır; o ana kadar eski içerik
            # yenisinin üstünde görünmesin diye hemen gizlenir.
            widget.hide()
            widget.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


class Page(QWidget):
    """Sayfa tabanı: üstte başlık alanı, altında kaydırılabilir içerik.

    İçerik ilk gösterimde (veya boştayken önceden) bir kez kurulur; durum
    değişince yalnızca ilgili satırlar güncellenir.
    """

    shown = Signal()

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.c = app.c
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)
        self.header = QVBoxLayout()
        self.header.setSpacing(4)
        outer.addLayout(self.header)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.body_widget = QWidget()
        self.body_widget.setObjectName("PageBody")
        # İçerik üstte, boşluk alttaki esnek alanda. setAlignment(AlignTop) kullanılmaz: içerik
        # pencereye sığınca Qt yüksekliği sizeHint ile keser, sarılan etiketler satırları sıkıştırır.
        column = QVBoxLayout(self.body_widget)
        column.setContentsMargins(0, 0, 10, 12)
        column.setSpacing(0)
        content = QWidget()
        self.body = QVBoxLayout(content)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(12)
        column.addWidget(content)
        column.addStretch(1)
        self.scroll.setWidget(self.body_widget)
        outer.addWidget(self.scroll, 1)
        self.built = False
        self.stale = False  # veri değişti, sayfa görünmüyordu: açılınca yeniden kurulur

    def clear(self):
        clear_layout(self.header)
        clear_layout(self.body)

    def build(self):
        """Alt sınıflar içeriği kurar."""
        self.built = True

    def ensure_built(self):
        if self.built and self.stale:
            self.data_reloaded()
        elif not self.built:
            self.build()

    def on_show(self, highlight=None):
        self.ensure_built()

    def tweak_updated(self, tweak_id):
        """Bir ayarın durumu değişince çağrılır; varsayılan: hiçbir şey."""

    def data_reloaded(self):
        """Tarama bittiğinde veya toplu değişiklik sonrası: yeniden kur. Kaydırma konumu korunur (içerik bir an
        boşalınca Qt değeri 0'a kırpar; sayfa en üste zıplamasın)."""
        self.stale = False
        if self.built:
            bar = self.scroll.verticalScrollBar()
            position = bar.value()
            # Yeniden kurulurken gövde eski yüksekliğinde tutulur: aralık çökmez, konum hemen geri yüklenir.
            # Eskiden 0 ms sonra yükleniyordu; yeni içeriğin yüksekliği henüz hesaplanmadığından değer 0'a kırpılıyordu.
            body = self.body_widget
            body.setMinimumHeight(body.height())
            self.clear()
            self.build()
            bar.setValue(position)

            def release():
                body.setMinimumHeight(0)
                bar.setValue(min(position, bar.maximum()))
            QTimer.singleShot(0, release)

    def scroll_top(self):
        self.scroll.verticalScrollBar().setValue(0)


class FlowLayout(QLayout):
    """Öğeleri yan yana dizer, sığmayanı alt satıra kaydırır (dar pencerede yatay taşma olmaz)."""

    def __init__(self, parent=None, spacing=6):
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(spacing)
        self._items = []

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._place(QRect(0, 0, width, 0), move=False)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._place(rect, move=True)

    def sizeHint(self):
        width = sum(i.sizeHint().width() for i in self._items) + self.spacing() * max(0, len(self._items) - 1)
        return QSize(width, max((i.sizeHint().height() for i in self._items), default=0))

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        return size

    def _place(self, rect, move):
        x, y, line = rect.x(), rect.y(), 0
        for item in self._items:
            hint = item.sizeHint()
            if x > rect.x() and x + hint.width() > rect.right() + 1:
                x, y, line = rect.x(), y + line + self.spacing(), 0
            if move:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self.spacing()
            line = max(line, hint.height())
        return y + line - rect.y()


def flow(*widgets, spacing=6):
    widget = QWidget()
    lay = FlowLayout(widget, spacing)
    for item in widgets:
        lay.addWidget(item)
    return widget


def grid(columns=2, spacing=8):
    widget = QWidget()
    lay = QGridLayout(widget)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(spacing)
    for column in range(columns):
        lay.setColumnStretch(column, 1)
    return widget, lay


def open_target(opener):
    """Rehberdeki "Ayarı aç" düğmesi. Yalnızca beyaz listedeki hedefler açılır."""
    if validate_opener(opener):
        _log.error("İzin verilmeyen açma hedefi reddedildi: %s", opener)
        return False
    kind, target = opener["tur"], opener["hedef"]
    try:
        if kind in ("ms-settings", "uri", "program"):
            os.startfile(target)  # noqa: S606 - hedef beyaz listede doğrulandı
        elif kind == "denetim_masasi":
            subprocess.Popen(["control.exe", target], creationflags=powershell.CREATE_NO_WINDOW)
        _log.info("Açıldı: %s", target)
        return True
    except OSError as exc:
        _log.error("Açılamadı (%s): %s", target, exc)
        return False
