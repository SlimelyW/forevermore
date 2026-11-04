"""Yalnızca Yöneticiler ve SYSTEM'in yazabildiği klasör (yedek ve kaldırıcı verisi).

ProgramData'da her kullanıcı klasör açabilir ve açtığının sahibi olur; yani saldırgan klasörü uygulamadan önce açabilir
veya junction bırakabilir. Bu yüzden klasör ACL'siyle TEK ADIMDA oluşturulur (sonradan icacls araya boşluk bırakırdı);
zaten varsa sahibi denetlenir, güvenilmezse içine bakılmadan kenara alınır.

OW (OWNER RIGHTS) kaydı dosya sahibinin örtük izin değiştirme hakkını kaldırır: aynı sürücüde taşınan dosyanın sahibi
kullanıcı kalır ve bu kayıt olmadan kullanıcı dosyanın izinlerini geri açabilirdi.
"""

import ctypes
import datetime
import os
import stat
import subprocess
from ctypes import wintypes
from pathlib import Path

TRUSTED_OWNERS = {"S-1-5-18", "S-1-5-32-544"}   # SYSTEM, Administrators
READ_EXECUTE = "0x1200a9"
CREATE_NO_WINDOW = 0x08000000
ERROR_ALREADY_EXISTS = 183
CSIDL_COMMON_APPDATA = 0x23
SDDL_REVISION_1 = 1
SE_FILE_OBJECT = 1
OWNER_SECURITY_INFORMATION = 1
TOKEN_QUERY = 8
TOKEN_USER_CLASS = 1

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
_shell32 = ctypes.WinDLL("shell32")
_void_ref = ctypes.POINTER(ctypes.c_void_p)


class _SecurityAttributes(ctypes.Structure):
    _fields_ = [("nLength", wintypes.DWORD), ("lpSecurityDescriptor", ctypes.c_void_p), ("bInheritHandle", wintypes.BOOL)]


_kernel32.GetCurrentProcess.restype = wintypes.HANDLE
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.LocalFree.argtypes = [ctypes.c_void_p]
_kernel32.LocalFree.restype = ctypes.c_void_p
_kernel32.CreateDirectoryW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(_SecurityAttributes)]
_advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
_advapi32.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
                                          ctypes.POINTER(wintypes.DWORD)]
_advapi32.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
_advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, _void_ref,
                                                                           ctypes.POINTER(wintypes.ULONG)]
_advapi32.GetNamedSecurityInfoW.argtypes = [wintypes.LPCWSTR, ctypes.c_int, wintypes.DWORD, _void_ref, _void_ref, _void_ref,
                                            _void_ref, _void_ref]
_advapi32.GetNamedSecurityInfoW.restype = wintypes.DWORD
_shell32.SHGetFolderPathW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR]


def _last_error():
    return ctypes.WinError(ctypes.get_last_error())


def _sid_text(sid):
    text = ctypes.c_void_p()
    if not _advapi32.ConvertSidToStringSidW(sid, ctypes.byref(text)):
        raise _last_error()
    try:
        return ctypes.wstring_at(text.value)
    finally:
        _kernel32.LocalFree(text)


def common_appdata():
    """ProgramData'nın gerçek yolu: ortam değişkeni değil Windows söyler (kullanıcı HKCU\\Environment'tan ezebilirdi)."""
    buffer = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
    result = _shell32.SHGetFolderPathW(None, CSIDL_COMMON_APPDATA, None, 0, buffer)
    if result:
        raise OSError(f"ProgramData bulunamadı: {result:#x}")
    return Path(buffer.value)


def current_sid():
    """Süreci çalıştıran hesabın SID'i (yükseltilmiş süreçte de aynı hesap)."""
    token = wintypes.HANDLE()
    if not _advapi32.OpenProcessToken(_kernel32.GetCurrentProcess(), TOKEN_QUERY, ctypes.byref(token)):
        raise _last_error()
    try:
        size = wintypes.DWORD()
        _advapi32.GetTokenInformation(token, TOKEN_USER_CLASS, None, 0, ctypes.byref(size))
        buffer = ctypes.create_string_buffer(size.value)
        if not _advapi32.GetTokenInformation(token, TOKEN_USER_CLASS, buffer, size, ctypes.byref(size)):
            raise _last_error()
        return _sid_text(ctypes.cast(buffer, _void_ref).contents)  # TOKEN_USER'ın ilk alanı SID işaretçisi
    finally:
        _kernel32.CloseHandle(token)


def sddl(reader=None, owner="BA"):
    """reader (SID veya "BU") yalnızca okur; yazma SYSTEM ve Yöneticilerde. Kalıtım kapalı (P)."""
    aces = ["(A;OICI;FA;;;SY)", "(A;OICI;FA;;;BA)", f"(A;OICI;{READ_EXECUTE};;;OW)"]
    if reader:
        aces.append(f"(A;OICI;{READ_EXECUTE};;;{reader})")
    return (f"O:{owner}" if owner else "") + "D:PAI" + "".join(aces)


def _create(path, descriptor_text):
    """True: oluşturuldu. False: bu adda bir şey zaten var."""
    descriptor = ctypes.c_void_p()
    if not _advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(descriptor_text, SDDL_REVISION_1,
                                                                          ctypes.byref(descriptor), None):
        raise _last_error()
    try:
        attributes = _SecurityAttributes(ctypes.sizeof(_SecurityAttributes), descriptor, False)
        if _kernel32.CreateDirectoryW(str(path), ctypes.byref(attributes)):
            return True
        error = ctypes.get_last_error()
        if error == ERROR_ALREADY_EXISTS:
            return False
        raise ctypes.WinError(error)
    finally:
        _kernel32.LocalFree(descriptor)


def owner_of(path):
    owner, descriptor = ctypes.c_void_p(), ctypes.c_void_p()
    error = _advapi32.GetNamedSecurityInfoW(str(path), SE_FILE_OBJECT, OWNER_SECURITY_INFORMATION, ctypes.byref(owner), None,
                                            None, None, ctypes.byref(descriptor))
    if error:
        raise ctypes.WinError(error)
    try:
        return _sid_text(owner)
    finally:
        _kernel32.LocalFree(descriptor)


def is_link(path):
    """Junction veya sembolik bağlantı: hedefine güvenilmez."""
    return bool(os.lstat(path).st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def trusted(path):
    """Gerçek klasör ve sahibi SYSTEM/Yöneticiler: yönetici olmayan biri böyle bir klasör oluşturamaz."""
    return not is_link(path) and os.path.isdir(path) and owner_of(path) in TRUSTED_OWNERS


def ensure(path, descriptor_text):
    """Güvenilir klasörü döndürür; yoksa oluşturur. Güvenilmeyen önceki içerik okunmadan yanına alınır, silinmez."""
    path = Path(path)
    if _create(path, descriptor_text) or trusted(path):
        return path
    aside = path.with_name(f"{path.name}.supheli_{datetime.datetime.now():%Y%m%d_%H%M%S}")
    os.replace(path, aside)
    from app.core import log  # log, paths üzerinden buraya bağlı: döngüyü önler
    log.get("guvenli_klasor").warning("Sahibi güvenilmeyen klasör kenara alındı: %s", aside.name)
    if not _create(path, descriptor_text):  # kenara alırken biri yeniden açtı
        raise PermissionError(f"Klasör güvenli oluşturulamadı: {path}")
    return path


def reset_acl(path):
    """Taşınan ağacı bulunduğu yerin izinlerine döndürür (aynı sürücüde izinler taşınanla birlikte gelir).
    /L: bağlantının hedefine dokunmaz. False: en az bir öğe sıfırlanamadı."""
    exe = Path(os.environ.get("SystemRoot") or r"C:\Windows") / "System32" / "icacls.exe"
    try:
        done = subprocess.run([str(exe), str(path), "/reset", "/T", "/C", "/L", "/Q"], capture_output=True,
                              creationflags=CREATE_NO_WINDOW, timeout=600)
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0
