"""Oyun üstü küçük FPS kutusu (Ayarlar > Genel, varsayılan KAPALI). Bkz. docs/GUVENLIK.md "Oyun üstü FPS kutusu".

Oyuna DOKUNMAZ: enjeksiyon, oyun belleği okuma, oyun penceresine kanca YOK. Kendi sürecimizde üstte duran, tıklanamayan,
odak almayan ayrı bir penceredir; bu yüzden özel tam ekran modunda görünmez. Veri yalnızca canlı FPS'in anlık durumu ve
(ayar açıksa) mevcut ekran kartı belleği okuyucusudur. Solma yok: oyun öndeyken motion.py zaten hareketi kapatır.
Alt+H kısayolu kutuyla yaşar; başka program kullanıyorsa sessizce vazgeçilir (kutu çalışmaya devam eder).
"""

import ctypes
from ctypes import wintypes

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel

from app.core import log
from app.core.i18n import t

_log = log.get("fps_kutusu")

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_NOREPEAT = 0x4000  # tuş basılı tutulunca kutu yanıp sönmesin
VK_H = 0x48
HOTKEY_ID = 0x4648
REFRESH_MS = 1000
MARGIN = 12
OPACITY = 0.92
SHOWN = ("olculuyor", "kare_yok")  # diğer durumlarda oyun ekranda değil veya ölçüm yok: kutu gizli


def text_for(snap, vram=None):
    """Kutunun metni; None = gizli. Kare gelmiyorsa "0 FPS" değil "—" (kare gelmemesi 0 FPS demek değildir)."""
    if snap["durum"] not in SHOWN:
        return None
    text = t("ui.fps_widget.fps", fps=snap["fps"] if snap["durum"] == "olculuyor" else "—")
    return text if vram is None else f"{text} · {t('ui.fps_widget.vram', yuzde=vram)}"


class FpsWidget(QLabel):
    """source() -> metin veya None (None = gizli). Saniyede bir okunur; stop() ile tamamen kapanır."""

    def __init__(self, source, user32=None):
        flags = (Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                 | Qt.WindowType.WindowTransparentForInput | Qt.WindowType.WindowDoesNotAcceptFocus)
        super().__init__(None, flags)
        self.setObjectName("FpsWidget")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)  # odak oyunda kalmalı: canlı FPS ona bakıyor
        # WA_TranslucentBackground YOK: QLabel'in arka planı çizilmez, yazı oyunun üstünde okunmaz olur (ekran dışı çizimde görüldü).
        # Tıklanamaz pencere katmanlıdır; opaklığı bu satır verir, yoksa Windows'ta görünmeyebilir (katman özelliği yazılmaz).
        self.setWindowOpacity(OPACITY)
        self.source = source
        self.user_hidden = False
        self.user32 = user32 or ctypes.windll.user32
        self.hwnd = wintypes.HWND(int(self.winId()))
        self.hotkey = bool(self.user32.RegisterHotKey(self.hwnd, HOTKEY_ID, MOD_ALT | MOD_NOREPEAT, VK_H))
        if not self.hotkey:
            _log.info("Alt+H başka bir programda kayıtlı; kısayol kullanılmıyor")
        self.timer = QTimer(self)
        self.timer.setInterval(REFRESH_MS)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        self.refresh()

    def refresh(self):
        text = None if self.user_hidden else self.source()
        if text is None:
            self.hide()
            return
        self.setText(text)
        self.adjustSize()
        if not self.isVisible():
            # shortcut: yalnızca ana ekran; oyun ikinci ekrandaysa kutu orada görünmez, gerçek ihtiyaç çıkarsa oyunun ekranı bulunur
            area = QGuiApplication.primaryScreen().geometry()
            self.move(area.left() + MARGIN, area.top() + MARGIN)
            self.show()

    def toggle(self):
        self.user_hidden = not self.user_hidden
        self.refresh()

    def stop(self):
        self.timer.stop()
        if self.hotkey:
            self.user32.UnregisterHotKey(self.hwnd, HOTKEY_ID)
            self.hotkey = False
        self.hide()
        self.deleteLater()

    def nativeEvent(self, event_type, message):
        if event_type == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                self.toggle()
                return True, 0
        return super().nativeEvent(event_type, message)
