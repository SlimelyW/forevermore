"""Oyun sırasında uygulanan ve oyun kapanınca geri alınan ayarlar.

İzleyici (GameWatcher) yalnızca uygulama açıkken ve en az bir oyunda "oyun sırasında"
ayarı varken çalışır: 2 saniyede bir süreç listesine bakar (CreateToolhelp32Snapshot;
çok hafif). Arka planda sürekli bir sürücü veya kanca YOKTUR.

GÜVENLİK:
- Ayarlar yalnızca oyunun kendi sürecine uygulanır. Anti-cheat süreçlerine (vgc, vgk,
  BEService, EasyAntiCheat...) hiçbir zaman dokunulmaz.
- Korumalı oyunlarda Windows erişimi reddedebilir; o ayar atlanır ve kullanıcıya söylenir.
- Değişiklikler önce bir günlük dosyasına yazılır (oyun_oturumu.json). Uygulama oyun
  sırasında kapanır veya çökerse, bir sonraki açılışta günlükteki her şey geri alınır.

Kullanılan Windows API'leri belgelenmiştir: SetProcessDefaultCpuSets (CPU Sets),
SetProcessInformation(ProcessPowerThrottling), Get/SetPriorityClass. Standby temizliği
NtSetSystemInformation ile yapılır (yarı belgelenmiş; Sysinternals RAMMap'in kullandığı yol).
"""

import ctypes
import json
import re
import threading
import time
from ctypes import wintypes

from app.core import log, paths, settings
from app.engine import closer, cpu_topology
from app.games.profiles import PROTECTED_EXES

_log = log.get("games")

PAUSE_SERVICES = ("SysMain", "DiagTrack", "MapsBroker", "WerSvc")
SEARCH_SERVICE = "WSearch"
HIGH_PERFORMANCE_PLAN = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
TOAST_KEY = r"Software\Microsoft\Windows\CurrentVersion\PushNotifications"
STEAM_HELPERS = ("steamwebhelper.exe",)
BELOW_NORMAL_PRIORITY_CLASS = 0x4000
NORMAL_PRIORITY_CLASS = 0x20
JOURNAL_PRIORITIES = (None, 0, NORMAL_PRIORITY_CLASS, BELOW_NORMAL_PRIORITY_CLASS, 0x40, 0x80, 0x8000)  # gerçek zamanlı yok


class ProcessOps:
    """Gerçek Windows süreç işlemleri (testlerde sahtesi kullanılır)."""

    TH32CS_SNAPPROCESS = 0x2
    QUERY_LIMITED = 0x1000
    SET_LIMITED = 0x2000
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

    def set_cpu_sets(self, pid, cpu_set_ids):
        handle = self._open(pid, self.SET_LIMITED | self.QUERY_LIMITED)
        try:
            array = (wintypes.ULONG * len(cpu_set_ids))(*cpu_set_ids)
            if not self.k.SetProcessDefaultCpuSets(ctypes.c_void_p(handle), array, len(cpu_set_ids)):
                raise PermissionError(f"SetProcessDefaultCpuSets hata {ctypes.get_last_error()}")
        finally:
            self.k.CloseHandle(handle)

    def exempt_power_throttling(self, pid):
        class _State(ctypes.Structure):
            _fields_ = [("Version", wintypes.ULONG), ("ControlMask", wintypes.ULONG), ("StateMask", wintypes.ULONG)]
        handle = self._open(pid, self.SET_INFORMATION)
        try:
            state = _State(1, 0x1, 0x0)  # PROCESS_POWER_THROTTLING_EXECUTION_SPEED kapalı
            if not self.k.SetProcessInformation(ctypes.c_void_p(handle), 4, ctypes.byref(state), ctypes.sizeof(state)):
                raise PermissionError(f"SetProcessInformation hata {ctypes.get_last_error()}")
        finally:
            self.k.CloseHandle(handle)

    def get_priority(self, pid):
        handle = self._open(pid, self.QUERY_LIMITED)
        try:
            return self.k.GetPriorityClass(ctypes.c_void_p(handle))
        finally:
            self.k.CloseHandle(handle)

    def set_priority(self, pid, priority_class):
        handle = self._open(pid, self.SET_INFORMATION | self.QUERY_LIMITED)
        try:
            if not self.k.SetPriorityClass(ctypes.c_void_p(handle), priority_class):
                raise PermissionError(f"SetPriorityClass hata {ctypes.get_last_error()}")
        finally:
            self.k.CloseHandle(handle)

    def purge_standby(self):
        """Standby bellek listesini boşaltır (SeProfileSingleProcessPrivilege gerekir; yönetici)."""
        advapi = ctypes.WinDLL("advapi32", use_last_error=True)

        class _Luid(ctypes.Structure):
            _fields_ = [("Low", wintypes.DWORD), ("High", wintypes.LONG)]

        class _Privileges(ctypes.Structure):
            _fields_ = [("Count", wintypes.DWORD), ("Luid", _Luid), ("Attributes", wintypes.DWORD)]
        token = ctypes.c_void_p()
        advapi.OpenProcessToken(ctypes.c_void_p(self.k.GetCurrentProcess()), 0x0020 | 0x0008, ctypes.byref(token))
        luid = _Luid()
        advapi.LookupPrivilegeValueW(None, "SeProfileSingleProcessPrivilege", ctypes.byref(luid))
        privileges = _Privileges(1, luid, 0x2)
        advapi.AdjustTokenPrivileges(token, False, ctypes.byref(privileges), 0, None, None)
        self.k.CloseHandle(token)
        command = ctypes.c_int(4)  # MemoryPurgeStandbyList
        status = ctypes.WinDLL("ntdll").NtSetSystemInformation(80, ctypes.byref(command), ctypes.sizeof(command))
        if status != 0:
            raise PermissionError(f"NtSetSystemInformation durum {status & 0xFFFFFFFF:#x}")


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
    """Bir oyunun oyun-sırası ayarları ve geri alma günlüğü."""

    def __init__(self, system, ops, journal_path=None, closer_ops=None):
        self.system, self.ops = system, ops
        self.closer_ops = closer_ops  # Boost: program kapatma işlemleri (None: gerçek Windows)
        self.journal_path = journal_path or (paths.user_data_dir() / "oyun_oturumu.json")
        self.journal = None

    def _save(self):
        paths.atomic_write(self.journal_path, json.dumps(self.journal, ensure_ascii=False))

    def start(self, game, pid, topology=None):
        """Ayarları uygular; [(ayar, başarılı, açıklama)] döndürür."""
        if self.journal is None and self.journal_path.exists():
            self.recover()  # geri alınamamış önceki oturumun günlüğü ezilmesin
        profile = game["profil"]
        results = []
        self.journal = {"oyun": game["id"], "ad": game["ad"], "pid": pid, "servisler": [], "guc_plani": None,
                        "bildirim": None, "steam": []}
        self._save()

        def attempt(key, func):
            try:
                func()
                results.append((key, True, ""))
            except Exception as exc:  # korumalı oyunlar erişimi reddedebilir; atla, söyle
                _log.warning("Oyun ayarı uygulanamadı (%s, %s): %s", game["ad"], key, exc)
                results.append((key, False, str(exc)))

        selection = profile.get("cekirdek_secimi", "tum")
        if selection != "tum":
            def cores():
                topo = topology or cpu_topology.read()
                numbers = (profile.get("cekirdekler") or []) if selection == "ozel" else \
                    cpu_topology.preset_ids(topo, selection)
                ids = [c["id"] for c in topo["cpular"] if c["no"] in set(numbers)]
                if not ids:
                    raise ValueError("çekirdek seçilmedi")
                self.ops.set_cpu_sets(pid, ids)
            attempt("cekirdekler", cores)
        if profile.get("guc_kismasi_muaf"):
            attempt("guc_kismasi_muaf", lambda: self.ops.exempt_power_throttling(pid))
        services = list(PAUSE_SERVICES) if profile.get("servisleri_duraklat") else []
        if profile.get("windows_search_durdur"):
            services.append(SEARCH_SERVICE)
        for name in services:
            def stop(name=name):
                info = self.system.get_service(name)
                if info and info["calisiyor"]:
                    self.journal["servisler"].append(name)
                    self._save()
                    self.system.set_service(name, info["baslangic"], False)
            attempt(f"servis:{name}", stop)
        if profile.get("steam_dusuk_oncelik"):
            def steam():
                for helper_pid, exe in self.ops.list_processes():
                    if exe in STEAM_HELPERS:
                        previous = self.ops.get_priority(helper_pid)
                        self.ops.set_priority(helper_pid, BELOW_NORMAL_PRIORITY_CLASS)
                        self.journal["steam"].append([helper_pid, previous])
                self._save()
            attempt("steam_dusuk_oncelik", steam)
        if profile.get("guc_plani"):
            def plan():
                previous = self.system.get_active_scheme()
                if previous.lower() != HIGH_PERFORMANCE_PLAN:
                    self.journal["guc_plani"] = previous
                    self._save()
                    self.system.set_active_scheme(HIGH_PERFORMANCE_PLAN)
            attempt("guc_plani", plan)
        if profile.get("bildirimleri_kapat"):
            def toast():
                previous = self.system.read_reg("HKCU", TOAST_KEY, "ToastEnabled")
                self.journal["bildirim"] = {"var": previous is not None,
                                            "deger": previous[0] if previous else None}
                self._save()
                self.system.write_reg("HKCU", TOAST_KEY, "ToastEnabled", 0, "REG_DWORD")
            attempt("bildirimleri_kapat", toast)
        if profile.get("standby_temizle"):
            attempt("standby_temizle", self.ops.purge_standby)
        if profile.get("boost"):  # en sonda: kapanmayan bir program diğer ayarları geciktirmesin
            attempt("boost", lambda: self._boost(game))
        return results

    def _boost(self, game):
        """Boost listesindeki açık programları NAZİKÇE kapatır (zorla sonlandırma asla otomatik değil, geri alınmaz).
        Oyunun kendisi listede olsa bile kapatılmaz. Kapanmayan olursa ayar "uygulanamadı" diye raporlanır."""
        own = closer._normal(game.get("exe") or "")
        names = [n for n in settings.get("boost_listesi") or [] if closer._normal(n) != own]
        ops = self.closer_ops or closer.WindowsOps()
        results = closer.close_many(closer.running(names, ops), ops, timeout=3.0)
        stuck = [name for name, result in results.items() if result == "calisiyor"]
        if stuck:
            raise RuntimeError("kapanmadı: " + ", ".join(stuck))

    def stop(self):
        """Oyun kapandı: günlükteki her şeyi geri alır."""
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


class GameWatcher:
    """Oyun süreçlerini izler; açılınca ayarları uygular, kapanınca geri alır."""

    def __init__(self, store, system, ops=None, on_event=None, interval=2.0, session=None, games=None):
        self.store, self.system = store, system
        self.games = games or store.runtime_games  # izlenecek oyunlar (ücretsizde yalnız deneme oyunu)
        self.ops = ops or ProcessOps()
        self.on_event = on_event or (lambda *_a: None)
        self.interval = interval
        self.session = session or GameSession(system, self.ops)
        self.active = None  # (oyun, pid)
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._loop, name="oyun-izleyici", daemon=True)
            self._thread.start()

    def stop(self):
        self._stop.set()
        if self.active:
            self.session.stop()
            self.active = None

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception:
                _log.exception("Oyun izleyici hatası")
            self._stop.wait(self.interval)

    def tick(self):
        processes = self.ops.list_processes()
        if self.active:
            game, pid = self.active
            if not any(p == pid for p, _ in processes):
                self.session.stop()
                self.active = None
                self.on_event("bitti", game, [])
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
            results = self.session.start(game, pid)
            self.on_event("basladi", game, results)
            return
