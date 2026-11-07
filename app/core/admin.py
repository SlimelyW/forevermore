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
PROCESS_CREATE_PROCESS = 0x0080
PROC_THREAD_ATTRIBUTE_PARENT_PROCESS = 0x00020000
EXTENDED_STARTUPINFO_PRESENT = 0x00080000


class _StartupInfoEx(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR), ("lpDesktop", wintypes.LPWSTR),
                ("lpTitle", wintypes.LPWSTR), ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD), ("dwXSize", wintypes.DWORD),
                ("dwYSize", wintypes.DWORD), ("dwXCountChars", wintypes.DWORD), ("dwYCountChars", wintypes.DWORD),
                ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD), ("wShowWindow", wintypes.WORD),
                ("cbReserved2", wintypes.WORD), ("lpReserved2", ctypes.c_void_p), ("hStdInput", wintypes.HANDLE),
                ("hStdOutput", wintypes.HANDLE), ("hStdError", wintypes.HANDLE), ("lpAttributeList", ctypes.c_void_p)]


class _ProcessInformation(ctypes.Structure):
    _fields_ = [("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE), ("dwProcessId", wintypes.DWORD),
                ("dwThreadId", wintypes.DWORD)]


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


def run_unelevated(exe, args):
    """Komutu masaüstü kabuğunun (Explorer) yetkisiyle başlatır: yeni süreç üst süreci Explorer sayılır ve onun token'ını
    alır, bizim yönetici token'ımızı almaz. Başlatılamazsa False döner; yönetici yetkisiyle çalıştırmaya ASLA düşmez.
    shortcut: Explorer'ı da yönetici olarak açmış kullanıcıda yetki düşmez; ayrım gerekirse TokenElevation okunur."""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32.GetShellWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.InitializeProcThreadAttributeList.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                                                           ctypes.POINTER(ctypes.c_size_t)]
    kernel32.UpdateProcThreadAttribute.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_size_t, ctypes.c_void_p,
                                                   ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p]
    kernel32.DeleteProcThreadAttributeList.argtypes = [ctypes.c_void_p]
    kernel32.CreateProcessW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, wintypes.BOOL,
                                        wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR, ctypes.c_void_p,
                                        ctypes.POINTER(_ProcessInformation)]
    shell_window = user32.GetShellWindow()
    pid = wintypes.DWORD()
    if not shell_window or not user32.GetWindowThreadProcessId(shell_window, ctypes.byref(pid)):
        return False
    shell = kernel32.OpenProcess(PROCESS_CREATE_PROCESS, False, pid.value)
    if not shell:
        return False
    try:
        size = ctypes.c_size_t()
        kernel32.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
        attributes = ctypes.create_string_buffer(size.value)
        if not kernel32.InitializeProcThreadAttributeList(attributes, 1, 0, ctypes.byref(size)):
            return False
        try:
            parent = wintypes.HANDLE(shell)
            if not kernel32.UpdateProcThreadAttribute(attributes, 0, PROC_THREAD_ATTRIBUTE_PARENT_PROCESS, ctypes.byref(parent),
                                                      ctypes.sizeof(parent), None, None):
                return False
            startup = _StartupInfoEx(cb=ctypes.sizeof(_StartupInfoEx), lpAttributeList=ctypes.addressof(attributes))
            process = _ProcessInformation()
            command = ctypes.create_unicode_buffer(f"{subprocess.list2cmdline([exe])} {args or ''}".strip())
            if not kernel32.CreateProcessW(None, command, None, None, False, EXTENDED_STARTUPINFO_PRESENT, None, None,
                                           ctypes.byref(startup), ctypes.byref(process)):
                return False   # ör. program yönetici istiyor (740): güvenlik için yükseltilmez
            kernel32.CloseHandle(process.hProcess)
            kernel32.CloseHandle(process.hThread)
            return True
        finally:
            kernel32.DeleteProcThreadAttributeList(attributes)
    finally:
        kernel32.CloseHandle(shell)


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
