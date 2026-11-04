"""Windows DPAPI (CryptProtectData): veriyi bu Windows kullanıcısına bağlı olarak şifreler.

Yedek imza anahtarı bununla saklanır: başka bir bilgisayara veya kullanıcıya kopyalanırsa çözülemez, elle
düzenlenemez (son doğrulama tarihini ileri almak gibi).
"""

import ctypes
from ctypes import wintypes

ENTROPY = b"Forevermore-lisans"


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(data):
    buffer = ctypes.create_string_buffer(data, len(data))
    return _Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))), buffer


def _call(func, data):
    source, _keep = _blob(data)
    entropy, _keep2 = _blob(ENTROPY)
    out = _Blob()
    CRYPTPROTECT_UI_FORBIDDEN = 0x1
    if not func(ctypes.byref(source), None, ctypes.byref(entropy), None, None, CRYPTPROTECT_UI_FORBIDDEN,
                ctypes.byref(out)):
        raise OSError(ctypes.get_last_error() or "DPAPI başarısız")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


def protect(data):
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    return _call(lambda *a: crypt32.CryptProtectData(a[0], "Forevermore", *a[2:]), data)


def unprotect(data):
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    return _call(lambda *a: crypt32.CryptUnprotectData(a[0], None, *a[2:]), data)
