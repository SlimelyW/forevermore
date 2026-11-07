"""Oyun süreçleri: "oyun açık mı" algılayıcısı ve eski oyun oturumu günlüğünün geri alınması.

Oyun izleyici (oyun açılınca ayar uygulayıp kapanınca geri alan GameWatcher) 7 Kasım 2026'da KALDIRILDI
(docs/KARAR_GUNLUGU.md). Kalan:
- GameDetector: yalnızca Canlı FPS veya oyun oturumu kaydı açıkken, 2 saniyede bir süreç listesine bakar
  (CreateToolhelp32Snapshot; çok hafif) ve listedeki oyunun açılıp kapandığını haber verir. HİÇBİR ayar uygulamaz.
  Anti-cheat süreçleri (profiles.PROTECTED_EXES) oyun sayılmaz.
- GameSession.recover: eski sürümde oyun sırasında kapanan uygulamanın bıraktığı günlüğü (oyun_oturumu.json)
  açılışta ve kaldırırken geri alır (servisler, Steam önceliği, güç planı, bildirimler).
"""

import ctypes
import json
import re
import threading
from ctypes import wintypes

from app.core import log, paths
from app.games.profiles import PROTECTED_EXES

_log = log.get("games")

PAUSE_SERVICES = ("SysMain", "DiagTrack", "MapsBroker", "WerSvc")
SEARCH_SERVICE = "WSearch"
TOAST_KEY = r"Software\Microsoft\Windows\CurrentVersion\PushNotifications"
BELOW_NORMAL_PRIORITY_CLASS = 0x4000
NORMAL_PRIORITY_CLASS = 0x20
JOURNAL_PRIORITIES = (None, 0, NORMAL_PRIORITY_CLASS, BELOW_NORMAL_PRIORITY_CLASS, 0x40, 0x80, 0x8000)  # gerçek zamanlı yok


class ProcessOps:
    """Gerçek Windows süreç işlemleri (testlerde sahtesi kullanılır)."""

    TH32CS_SNAPPROCESS = 0x2
    QUERY_LIMITED = 0x1000
    SET_INFORMATION = 0x0200

    class _Entry(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD),
                    ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                    ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]

    def __init__(self):
        self.k = ctypes.WinDLL("kernel32", use_last_error=True)
        self.k.OpenProcess.restype = ctypes.c_void_p
        self.k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.k.CloseHandle.argtypes = [ctypes.c_void_p]
        self.k.CreateToolhelp32Snapshot.restype = ctypes.c_void_p

    def list_processes(self):
        """[(pid, exe adı küçük harf)]"""
        snap = self.k.CreateToolhelp32Snapshot(self.TH32CS_SNAPPROCESS, 0)
        if not snap or snap == ctypes.c_void_p(-1).value:
            return []
        result = []
        try:
            entry = self._Entry()
            entry.dwSize = ctypes.sizeof(self._Entry)
            ok = self.k.Process32FirstW(ctypes.c_void_p(snap), ctypes.byref(entry))
            while ok:
                result.append((entry.th32ProcessID, entry.szExeFile.lower()))
                ok = self.k.Process32NextW(ctypes.c_void_p(snap), ctypes.byref(entry))
        finally:
            self.k.CloseHandle(snap)
        return result

    def _open(self, pid, access):
        handle = self.k.OpenProcess(access, False, pid)
        if not handle:
            raise PermissionError(f"OpenProcess reddedildi (hata {ctypes.get_last_error()})")
        return handle

    def process_path(self, pid):
        try:
            handle = self._open(pid, self.QUERY_LIMITED)
        except PermissionError:
            return None
        try:
            size = wintypes.DWORD(1024)
            buffer = ctypes.create_unicode_buffer(1024)
            if self.k.QueryFullProcessImageNameW(ctypes.c_void_p(handle), 0, buffer, ctypes.byref(size)):
                return buffer.value
            return None
        finally:
            self.k.CloseHandle(handle)

    def set_priority(self, pid, priority_class):
        handle = self._open(pid, self.SET_INFORMATION | self.QUERY_LIMITED)
        try:
            if not self.k.SetPriorityClass(ctypes.c_void_p(handle), priority_class):
                raise PermissionError(f"SetPriorityClass hata {ctypes.get_last_error()}")
        finally:
            self.k.CloseHandle(handle)



def journal_ok(journal):
    """Günlük kullanıcının yazabildiği klasörde: yalnızca start()'ın yazabileceği değerler kabul edilir."""
    if not isinstance(journal, dict):
        return False
    services, steam, plan, toast = (journal.get(k) for k in ("servisler", "steam", "guc_plani", "bildirim"))
    return (isinstance(services or [], list) and all(name in (*PAUSE_SERVICES, SEARCH_SERVICE) for name in services or [])
            and (plan is None or re.fullmatch(r"[0-9a-fA-F-]{36}", str(plan)) is not None)
            and (toast is None or (isinstance(toast, dict) and {"var", "deger"} <= toast.keys()))
            and isinstance(steam or [], list)
            and all(isinstance(e, list) and len(e) == 2 and isinstance(e[0], int) and e[1] in JOURNAL_PRIORITIES for e in steam or []))


class GameSession:
    """Eski sürümün oyun-sırası ayar günlüğünü geri alır (yeni ayar UYGULAMAZ)."""

    def __init__(self, system, ops, journal_path=None):
        self.system, self.ops = system, ops
        self.journal_path = journal_path or (paths.user_data_dir() / "oyun_oturumu.json")
        self.journal = None

    def stop(self):
        """Günlükteki her şeyi geri alır."""
        journal = self.journal
        if journal is None:
            return
        failed = False
        for name in journal.get("servisler") or []:
            try:
                info = self.system.get_service(name)
                self.system.set_service(name, info["baslangic"] if info else "Manual", True)
            except Exception as exc:
                failed = True
                _log.warning("Servis yeniden başlatılamadı (%s): %s", name, exc)
        for helper_pid, previous in journal.get("steam") or []:
            try:
                self.ops.set_priority(helper_pid, previous or NORMAL_PRIORITY_CLASS)
            except Exception:
                pass  # Steam kapanmış olabilir
        if journal.get("guc_plani"):
            try:
                self.system.set_active_scheme(journal["guc_plani"])
            except Exception as exc:
                failed = True
                _log.warning("Güç planı geri alınamadı: %s", exc)
        toast = journal.get("bildirim")
        if toast:
            try:
                if toast["var"]:
                    self.system.write_reg("HKCU", TOAST_KEY, "ToastEnabled", toast["deger"], "REG_DWORD")
                else:
                    self.system.delete_reg_value("HKCU", TOAST_KEY, "ToastEnabled")
            except Exception as exc:
                failed = True
                _log.warning("Bildirim ayarı geri alınamadı: %s", exc)
        self.journal = None
        if failed:
            return  # günlük dosyası kalır: recover() sonraki açılışta yeniden dener
        try:
            self.journal_path.unlink()
        except OSError:
            pass

    def recover(self):
        """Önceki oturumdan kalan günlük varsa (uygulama oyun sırasında kapanmış): geri al."""
        try:
            self.journal = json.loads(self.journal_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        if not journal_ok(self.journal):
            _log.warning("Oyun oturumu günlüğü geçersiz, yok sayıldı")
            self.journal = None
            try:
                self.journal_path.unlink()
            except OSError:
                pass
            return False
        _log.info("Yarım kalan oyun oturumu geri alınıyor: %s", self.journal.get("ad"))
        self.stop()
        return True


class GameDetector:
    """Yalnızca "oyun açık mı": listedeki oyun açılınca ("basladi") ve kapanınca ("bitti") on_event(tür, oyun) çağrılır.
    Canlı FPS ve oyun oturumu kaydı bununla başlar/biter. Hiçbir ayar uygulamaz, geri almaz."""

    def __init__(self, games, ops=None, on_event=None, interval=2.0):
        self.games = games  # çağrılınca [oyun] döner (exe'si olan oyunlar)
        self.ops = ops or ProcessOps()
        self.on_event = on_event or (lambda *_a: None)
        self.interval = interval
        self.active = None  # (oyun, pid)
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._loop, name="oyun-algilayici", daemon=True)
            self._thread.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception:
                _log.exception("Oyun algılayıcı hatası")
            self._stop.wait(self.interval)

    def tick(self):
        processes = self.ops.list_processes()
        if self.active:
            game, pid = self.active
            if not any(p == pid for p, _ in processes):
                self.active = None
                self.on_event("bitti", game)
            return
        games = {}
        for game in self.games():
            games.setdefault(game["exe"].rsplit("\\", 1)[-1].lower(), []).append(game)
        for pid, exe in processes:
            if exe in PROTECTED_EXES or exe not in games:
                continue
            path = (self.ops.process_path(pid) or "").lower()
            game = next((g for g in games[exe] if not path or g["exe"].lower() == path), None)
            if game is None:
                continue
            self.active = (game, pid)
            self.on_event("basladi", game)
            return
