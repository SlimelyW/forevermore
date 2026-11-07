"""Gerekmeyen programı kapatma (Boost, adım 2). Önce nazikçe (pencereye kapat isteği), kapanmazsa YALNIZCA kullanıcının
ikinci onayıyla zorla sonlandırma. Korumalı programlar (sistem, güvenlik, kabuk, anti-cheat, başlatıcılar, sürücü
hizmetleri ve bu uygulamanın kendisi) hiçbir yoldan kapatılmaz. Bellek boşaltma / çalışma kümesi küçültme YOKTUR.
"""

import ctypes
import os
import time
from ctypes import wintypes

from app.games.profiles import PROTECTED_EXES

PROTECTED = {
    # Windows çekirdek ve kabuk
    "system", "registry", "smss", "csrss", "wininit", "winlogon", "services", "lsass", "svchost", "dwm", "explorer",
    "fontdrvhost", "sihost", "ctfmon", "taskhostw", "runtimebroker", "searchhost", "searchindexer",
    "startmenuexperiencehost", "shellexperiencehost", "textinputhost", "audiodg", "dllhost", "conhost", "spoolsv",
    "wudfhost", "memcompression", "taskmgr", "applicationframehost", "systemsettings", "lockapp",
    # güvenlik
    "msmpeng", "nissrv", "securityhealthservice", "securityhealthsystray", "smartscreen", "mpdefendercoreservice",
    # ekran kartı / ses sürücü hizmetleri
    "nvcontainer", "nvdisplay.container", "radeonsoftware", "amdrsserv", "atieclxx", "atiesrxx", "igfxem", "rtkauduservice64",
    # bu uygulama
    "python", "pythonw", "py", "forevermore", "pcoptimizer",
}
PROTECTED |= {name[:-4] for name in PROTECTED_EXES if name.endswith(".exe")}  # anti-cheat ve oyun başlatıcıları

WM_CLOSE = 0x0010
PROCESS_TERMINATE = 0x0001


def _normal(name):
    lower = os.path.basename(name or "").lower()
    return lower[:-4] if lower.endswith(".exe") else lower


def is_protected(name):
    return _normal(name) in PROTECTED


class WindowsOps:
    """Gerçek Windows işlemleri (testlerde sahtesi kullanılır)."""

    def __init__(self):
        self.k = ctypes.WinDLL("kernel32", use_last_error=True)
        self.u = ctypes.WinDLL("user32", use_last_error=True)
        self.k.OpenProcess.restype = ctypes.c_void_p
        self.k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.k.TerminateProcess.argtypes = [ctypes.c_void_p, wintypes.UINT]
        self.k.CloseHandle.argtypes = [ctypes.c_void_p]

    def list_processes(self):
        from app.games.runtime import ProcessOps
        return ProcessOps().list_processes()

    def post_close(self, pids):
        """Bu süreçlerin görünür üst düzey pencerelerine kapat isteği gönderir; kaç pencere bulunduğunu döner."""
        pids, count = set(pids), [0]
        callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def visit(hwnd, _):
            pid = wintypes.DWORD()
            self.u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in pids and self.u.IsWindowVisible(hwnd) and not self.u.GetWindow(hwnd, 4):  # 4: sahibi yok
                self.u.PostMessageW(hwnd, WM_CLOSE, 0, 0)
                count[0] += 1
            return True

        self.u.EnumWindows(callback(visit), 0)
        return count[0]

    def terminate(self, pid):
        handle = self.k.OpenProcess(PROCESS_TERMINATE, False, pid)
        if not handle:
            return False
        try:
            return bool(self.k.TerminateProcess(ctypes.c_void_p(handle), 1))
        finally:
            self.k.CloseHandle(handle)


def pids_of(name, ops):
    target = _normal(name)
    return [pid for pid, exe in ops.list_processes() if _normal(exe) == target]


def close_gently(name, ops=None, timeout=6.0, poll=0.25):
    """"korumali" | "yok" | "kapandi" | "calisiyor" (pencere yok veya kullanıcı kapatmadı; zorla kapatma ayrı onay ister)."""
    # Discord gibi "kapatınca tepsiye küçül" programlarda kapat isteği pencereyi yalnızca gizler, süreç kalır (tepsideyse
    # görünür pencere de yoktur): sonuç "calisiyor" olur ve arayüz zorla sonlandırmayı ayrıca sorar (docs/BOOST_DISCORD.md).
    if is_protected(name):
        return "korumali"
    ops = ops or WindowsOps()
    pids = pids_of(name, ops)
    if not pids:
        return "yok"
    ops.post_close(pids)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not pids_of(name, ops):
            return "kapandi"
        time.sleep(poll)
    return "calisiyor"


def running(names, ops=None):
    """Listedeki programlardan şu an çalışanlar (korumalılar elenir)."""
    ops = ops or WindowsOps()
    return [n for n in names if not is_protected(n) and pids_of(n, ops)]


def close_many(names, ops=None, timeout=6.0):
    """Her program için close_gently; {ad: sonuç}. Zorla sonlandırma YAPMAZ."""
    ops = ops or WindowsOps()
    return {name: close_gently(name, ops, timeout) for name in names}


def kill(name, ops=None):
    """Zorla sonlandırır (yalnızca kullanıcının açık onayından sonra çağrılır); sonlandırılan süreç sayısı."""
    if is_protected(name):
        return 0
    ops = ops or WindowsOps()
    return sum(1 for pid in pids_of(name, ops) if ops.terminate(pid))
