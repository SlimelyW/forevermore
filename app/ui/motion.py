"""Hareket jetonları ve küçük animasyonlar (docs/TASARIM_ESASLARI.md §6, §7, §13).

İlke: eylem HEMEN çalışır, animasyon yalnızca onu yumuşatır; hiçbir animasyon bir işi bekletmez.
Yalnızca opaklık ve çizimle konum (toggle düğmesi) canlandırılır; genişlik/yükseklik animasyonu yok.
Sık eylemlerde (toggle, satır, sekme) hareket en az; nadir anlarda (sayfa açılışı, başarı bildirimi) biraz daha belirgin.
Süreler 0 olur: "Hareketi azalt" açıkken, Windows'ta "Animasyon efektleri" kapalıyken (Windows'un
prefers-reduced-motion karşılığı), pencere küçültülmüş/arka plandayken ve ölçüm sürerken. Boşta hiçbir döngü çalışmaz."""

import ctypes
import functools
import os

from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QPropertyAnimation, QRectF, QVariantAnimation
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsOpacityEffect

from app.core import settings
from app.ui import theme

# Süre jetonları (ms). Hiçbiri 300'ü geçmez; çıkış girişten kısa.
PRESS_MS = 90        # basma geri bildirimi (düğme ölçeği anında; renk durumu)
HOVER_MS = 120       # üstüne gelme parlaması
TOGGLE_MS = 160      # aç/kapa düğmesinin topuzu
REVEAL_MS = 160      # bölüm açılırken solarak gelme
PAGE_MS = 180        # sayfa geçişi
PAGE_FROM = 0.35     # sayfa solması zaten görünür bir değerden başlar (boş ekran anı yok)

EASE = QEasingCurve.Type.OutCubic  # giriş: hızlı başlar, yavaşlar
_spring = QEasingCurve(QEasingCurve.Type.OutBack)
_spring.setOvershoot(0.9)          # hafif yay: yalnızca toggle gibi küçük öğelerde
SPRING = _spring
_paused = set()      # duraklatma sebepleri: "olcum" (Önce/Sonra), "arka_plan" (küçültüldü / odak yok)


@functools.lru_cache(maxsize=1)
def windows_animations_off():
    """Windows Ayarlar > Erişilebilirlik > Görsel efektler > Animasyon efektleri kapalı mı (SPI_GETCLIENTAREAANIMATION).
    Açılışta bir kez okunur."""
    try:
        value = ctypes.c_int(1)
        ok = ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(value), 0)
        return bool(ok) and not value.value
    except (AttributeError, OSError):
        return False


def reduced():
    forced = os.environ.get("PCOPT_HAREKET")  # testler: "azalt" hep kapalı, "ac" hep açık
    if forced == "ac":
        return False
    return bool(_paused) or forced == "azalt" or bool(settings.get("hareket_azalt")) or windows_animations_off()


def set_paused(on, reason="olcum"):
    (_paused.add if on else _paused.discard)(reason)


def ms(value):
    return 0 if reduced() else value


def _fade(widget, start, end, duration, done=None):
    """Opaklık animasyonu; bitince efekt kaldırılır (etkin efekt çizimi yavaşlatır, kalıcı bırakılmaz)."""
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(start)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(start)
    anim.setEndValue(end)
    anim.setEasingCurve(EASE)

    def finished():
        widget.setGraphicsEffect(None)
        if done:
            done()
    anim.finished.connect(finished)
    anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)


def expand(widget, show):
    """Bölümü açar/kapatır. Yerleşim anında değişir (yükseklik animasyonu yok: yalnızca opaklık ve çizim
    canlandırılır); açılırken içerik solarak gelir, kapanırken anında gizlenir. Kaydırma konumu korunur,
    sayfa yeniden kurulmaz. Hareketi azalt açıksa solma da yok."""
    if show:
        widget.setVisible(True)
        if ms(REVEAL_MS):
            _fade(widget, 0.0, 1.0, ms(REVEAL_MS))
    else:
        widget.setVisible(False)


def fade_in(widget):
    """Sayfa belirirken kısa solma; görünür bir değerden başlar ki geçişte boş ekran anı olmasın."""
    if ms(PAGE_MS):
        _fade(widget, PAGE_FROM, 1.0, PAGE_MS)


class HoverFade:
    """QFrame türevine karıştırılır (önce yazılır): `hover = True` olunca üstüne gelindiğinde yeşil bir yıkama ve
    ince çerçeve 120 ms'de belirir, çıkınca söner. Süper sınıfın çizimi bozulmaz, üstüne çizilir."""

    hover = False
    hover_radius = 12

    def _hover_to(self, target):
        anim = getattr(self, "_hover_anim", None)
        if anim is None:  # tembel: yüzlerce satırda sınıf başına nesne açılmaz
            self._hover_value = 0.0
            anim = self._hover_anim = QVariantAnimation(self)
            anim.setEasingCurve(EASE)
            anim.valueChanged.connect(self._hover_step)
        anim.stop()
        anim.setDuration(ms(HOVER_MS if target > self._hover_value else PRESS_MS))  # çıkış girişten kısa
        anim.setStartValue(self._hover_value)
        anim.setEndValue(target)
        if anim.duration():
            anim.start()
        else:
            self._hover_step(target)

    def _hover_step(self, value):
        self._hover_value = value
        self.update()

    def enterEvent(self, event):
        if self.hover:
            self._hover_to(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.hover:
            self._hover_to(0.0)
        super().leaveEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        value = getattr(self, "_hover_value", 0.0)
        if self.hover and value > 0.01:
            accent = QColor(theme.palette()["accent"])
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            fill, line = QColor(accent), QColor(accent)
            fill.setAlpha(int(24 * value))
            line.setAlpha(int(140 * value))
            painter.setBrush(fill)
            painter.setPen(QPen(line, 1))
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5),
                                    self.hover_radius, self.hover_radius)
