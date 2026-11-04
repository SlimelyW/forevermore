"""Tek kopya: uygulama zaten açıksa (tepside de olsa) ikinci açılış onun penceresini öne getirir ve kapanır.

Arkadaşın raporunda aynı anda 6 Forevermore süreci (777 MB) vardı: tepsiye küçültüp yeniden açmak veya
Windows'la başlayan kopya açıkken programı tekrar çalıştırmak yeni bir kopya başlatıyordu.
Yalnızca Windows API'si (adlandırılmış mutex + kayıtlı pencere mesajı); ağ veya ek kütüphane yok.
"""

import ctypes

MUTEX_NAME = "Local\\Forevermore-tek-ornek"
MESSAGE_NAME = "Forevermore-pencereyi-goster"
ERROR_ALREADY_EXISTS = 183
HWND_BROADCAST = 0xFFFF
_handle = None  # süreç boyunca açık kalır; süreç kapanınca Windows bırakır


def show_message_id():
    return ctypes.windll.user32.RegisterWindowMessageW(MESSAGE_NAME)


def claim():
    """Bu süreç ilk kopyaysa True. Değilse çalışan kopyaya 'pencereni göster' der ve False döner."""
    global _handle
    try:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateMutexW.restype = ctypes.c_void_p
        _handle = kernel.CreateMutexW(None, False, MUTEX_NAME)
        if not _handle or ctypes.get_last_error() != ERROR_ALREADY_EXISTS:
            return True
        ctypes.windll.user32.PostMessageW(HWND_BROADCAST, show_message_id(), 0, 0)
        return False
    except (AttributeError, OSError):  # Windows dışı
        return True


def allow_from_unelevated(hwnd):
    """Yönetici olarak açık pencere, yönetici olmayan ikinci açılışın mesajını da alabilsin (UIPI)."""
    try:
        ctypes.windll.user32.ChangeWindowMessageFilterEx(ctypes.c_void_p(hwnd), show_message_id(), 1, None)
    except (AttributeError, OSError):
        pass
