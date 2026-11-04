"""Yönetici izni ve hesap kontrolü.

- Uygulama yönetici değilse kendini "Yönetici olarak" yeniden başlatır (UAC
  penceresi çıkar).
- Dikkat: Standart kullanıcı hesabında UAC penceresine BAŞKA bir yönetici
  hesabının şifresi girilirse uygulama o hesap adına çalışır ve HKCU
  (kullanıcı ayarları) o hesabın ayarlarını gösterir. Bu durumda kullanıcıya
  ait ayarları değiştirmek yanlış kişiyi etkiler; ayar motoru bu ayarları
  gizler. Bu kontrol `session_user_matches()` ile yapılır.
"""

import ctypes
import os
import subprocess
import sys
from ctypes import wintypes

WTS_CURRENT_SERVER_HANDLE = None
WTS_CURRENT_SESSION = 0xFFFFFFFF
WTS_USER_NAME = 5


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except OSError:
        return False


def relaunch_as_admin(extra_args=()):
    """Uygulamayı yönetici olarak yeniden başlatır. Başlatıldıysa True döner
    (çağıran süreç kapanmalıdır); kullanıcı UAC'yi reddederse False."""
    if getattr(sys, "frozen", False):
        exe, args = sys.executable, list(sys.argv[1:])
    else:
        exe, args = sys.executable, ["-m", "app"] + list(sys.argv[1:])
    params = subprocess.list2cmdline(args + list(extra_args))
    # Yükseltilmiş süreç varsayılan olarak System32'de başlar; "-m app" için
    # çalışma klasörü program klasörü olmalı.
    from app.core import paths
    result = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, str(paths.app_dir()), 1)
    return result > 32


def _process_user():
    size = wintypes.DWORD(257)
    buffer = ctypes.create_unicode_buffer(size.value)
    if ctypes.windll.advapi32.GetUserNameW(buffer, ctypes.byref(size)):
        return buffer.value
    return os.environ.get("USERNAME", "")


def _session_user():
    wtsapi = ctypes.WinDLL("wtsapi32")
    buffer = ctypes.c_wchar_p()
    size = wintypes.DWORD()
    ok = wtsapi.WTSQuerySessionInformationW(WTS_CURRENT_SERVER_HANDLE, WTS_CURRENT_SESSION, WTS_USER_NAME,
                                            ctypes.byref(buffer), ctypes.byref(size))
    if not ok:
        return None
    try:
        return buffer.value
    finally:
        wtsapi.WTSFreeMemory(buffer)


def session_user_matches():
    """Uygulamayı çalıştıran hesap, oturum açmış kullanıcıyla aynı mı?

    Belirlenemezse True döner (çoğu durumda aynıdır) ve log'a yazılmaz;
    kullanıcı adları hiçbir yerde saklanmaz.
    """
    session = _session_user()
    if not session:
        return True
    return session.lower() == _process_user().lower()
