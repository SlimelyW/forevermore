"""Oyun süreçleri: "oyun açık mı" algılayıcısı ve oyun-sırası seçenekleri (GameSession).

Oyun izleyici (oyun açılınca ayar uygulayıp kapanınca geri alan GameWatcher) 7 Kasım 2026'da KALDIRILDI
(docs/KARAR_GUNLUGU.md). Bu dosyada ARKA PLANDA KENDİLİĞİNDEN ayar uygulayan bir şey yoktur:
- GameDetector: yalnızca Canlı FPS / oyun oturumu kaydı açıkken ya da "Hazırla"dan sonra oyun kapanana kadar,
  2 saniyede bir süreç listesine bakar (CreateToolhelp32Snapshot; çok hafif) ve oyunun açılıp kapandığını haber verir.
  HİÇBİR ayar uygulamaz. Anti-cheat süreçleri (profiles.PROTECTED_EXES) oyun sayılmaz.
- GameSession: oyun-sırası seçenekleri YALNIZCA kullanıcı düğmeye basınca uygulanır (start), oyun kapanınca ya da "Geri al"
  ile geri alınır (stop); uygulama çökerse artakalanı açılışta recover geri alır.
"""

import ctypes
import json
import re
import threading
from ctypes import wintypes

from app.core import log, paths
from app.core.i18n import t
from app.games import discovery, profiles
from app.games.profiles import PROTECTED_EXES

_log = log.get("games")

PAUSE_SERVICES = ("SysMain", "DiagTrack", "MapsBroker", "WerSvc")
SEARCH_SERVICE = "WSearch"
TOAST_KEY = r"Software\Microsoft\Windows\CurrentVersion\PushNotifications"  # eski sürümün anahtarı (yalnızca geri alma)
DND_KEY = r"Software\Microsoft\Windows\CurrentVersion\Notifications\Settings"
DND_VALUE = "NOC_GLOBAL_SETTING_TOASTS_ENABLED"  # Windows 11 Rahatsız etme düğmesi (0 = açık); gerçek PC'de DENENMEDİ
HIGH_PERFORMANCE_PLAN = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
STEAM_HELPERS = ("steamwebhelper.exe",)
MOTOR_IDS = ("oyunsirasi-rahatsiz", "oyunsirasi-guc",
             *(f"oyunsirasi-servis-{name}" for name in (*PAUSE_SERVICES, SEARCH_SERVICE)))
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



def journal_ok(journal):
    """Günlük kullanıcının yazabildiği klasörde: yalnızca uygulamanın yazabileceği değerler kabul edilir."""
    if not isinstance(journal, dict):
        return False
    services, steam, plan, toast, motor = (journal.get(k) for k in ("servisler", "steam", "guc_plani", "bildirim", "motor"))
    return (isinstance(services or [], list) and all(name in (*PAUSE_SERVICES, SEARCH_SERVICE) for name in services or [])
            and (plan is None or re.fullmatch(r"[0-9a-fA-F-]{36}", str(plan)) is not None)
            and (toast is None or (isinstance(toast, dict) and {"var", "deger"} <= toast.keys()))
            and isinstance(motor or [], list) and all(cid in MOTOR_IDS for cid in motor or [])
            and isinstance(steam or [], list)
            and all(isinstance(e, list) and len(e) == 2 and isinstance(e[0], int) and e[1] in JOURNAL_PRIORITIES for e in steam or []))


def _reg_step(root, path, name, kind):
    return {"tur": "registry", "kok": root, "yol": path, "ad": name, "veri_turu": kind,
            "acik": None, "kapali": None, "yoksa": None}


class GameSession:
    """Oyun-sırası seçenekleri: yalnızca kullanıcı "Hazırla" / "Oyunu başlat"a basınca `start`, oyun kapanınca ya da "Geri al"
    ile `stop`. Arka planda kendi başına çalışan hiçbir şey yoktur.

    Kayıt defteri, güç planı ve servis değişiklikleri MOTORDAN geçer (`engine.apply_custom`: yedek, Değişiklikler, geri
    alma); süreç işlemleri (Steam yardımcı önceliği) yalnızca günlüğe yazılır. Her değişiklikten ÖNCE günlük
    (oyun_oturumu.json) yazılır: uygulama oyun sırasında çökerse sonraki açılışta `recover` hepsini geri alır.
    Eski sürümün günlük alanları (servisler, guc_plani, bildirim) da geri alınır."""

    def __init__(self, system, ops, journal_path=None, engine=None):
        self.system, self.ops, self.engine = system, ops, engine
        self.journal_path = journal_path or (paths.user_data_dir() / "oyun_oturumu.json")
        self.journal = None

    @property
    def active(self):
        """Geri alınacak bir şey var mı (hazırlanmış oturum)."""
        return self.journal is not None

    def _save(self):
        paths.atomic_write(self.journal_path, json.dumps(self.journal, ensure_ascii=False))

    def _apply(self, change_id, name, step, value):
        self.journal["motor"].append(change_id)
        self._save()  # önce günlük: değişiklik yarım kalsa da geri alınır
        result = self.engine.apply_custom(change_id, name, [step], [value], confirmed=True)
        if not result.ok:
            self.journal["motor"].remove(change_id)
            self._save()
            raise RuntimeError(result.key)

    def start(self, game):
        """Oyunda AÇIK ve izin verilen seçenekleri uygular; [(anahtar, başarılı, açıklama)] döner. Açıklama: "" /
        "zaten" (değişiklik gerekmedi) / "indiriyor" (Steam indirmesi sürüyor) / hata metni."""
        if self.engine is None:
            raise RuntimeError("motor yok")
        if self.journal is not None:
            self.stop()
        elif self.journal_path.exists():
            self.recover()
        if self.journal is not None or self.journal_path.exists():
            return [("onceki_oturum", False, "geri alinamadi")]
        keys = profiles.runtime_selected(game)  # anti-cheat süzgeci burada da: arayüze güvenilmez
        results = []
        self.journal = {"oyun": game["id"], "ad": game["ad"], "motor": [], "steam": []}

        def attempt(key, func):
            try:
                results.append((key, True, func() or ""))
            except Exception as exc:
                _log.warning("Oyun-sırası seçeneği uygulanamadı (%s, %s): %s", game["ad"], key, exc)
                results.append((key, False, str(exc)))

        def dnd():
            current = self.system.read_reg("HKCU", DND_KEY, DND_VALUE)
            if current and current[0] == 0:
                return "zaten"
            self._apply("oyunsirasi-rahatsiz", t("oyun.degisiklik.rahatsiz", ad=game["ad"]),
                        _reg_step("HKCU", DND_KEY, DND_VALUE, "REG_DWORD"), 0)

        def plan():
            if self.system.get_active_scheme().lower() == HIGH_PERFORMANCE_PLAN:
                return "zaten"
            self._apply("oyunsirasi-guc", t("oyun.degisiklik.guc", ad=game["ad"]),
                        {"tur": "guc_plani", "acik": HIGH_PERFORMANCE_PLAN, "kapali": HIGH_PERFORMANCE_PLAN},
                        HIGH_PERFORMANCE_PLAN)

        def services(names):
            def run():
                stopped = 0
                for name in names:
                    info = self.system.get_service(name)
                    if info and info["calisiyor"]:
                        self._apply(f"oyunsirasi-servis-{name}", t("oyun.degisiklik.servis", ad=game["ad"], servis=name),
                                    {"tur": "servis", "ad": name}, {"baslangic": info["baslangic"], "calisiyor": False})
                        stopped += 1
                return "" if stopped else "zaten"
            return run

        def helper_priority():
            for pid, exe in self.ops.list_processes():
                if exe in STEAM_HELPERS:
                    previous = self.ops.get_priority(pid)
                    self.journal["steam"].append([pid, previous])
                    self._save()
                    self.ops.set_priority(pid, BELOW_NORMAL_PRIORITY_CLASS)

        def steam_warning():
            return "indiriyor" if discovery.steam_downloading() else "zaten"

        if "hazirla_rahatsiz_etme" in keys:
            attempt("hazirla_rahatsiz_etme", dnd)
        if "hazirla_guc_plani" in keys:
            attempt("hazirla_guc_plani", plan)
        if "hazirla_servisler" in keys:
            attempt("hazirla_servisler", services(PAUSE_SERVICES))
        if "hazirla_search" in keys:
            attempt("hazirla_search", services((SEARCH_SERVICE,)))
        if "hazirla_steam_oncelik" in keys:
            attempt("hazirla_steam_oncelik", helper_priority)
        if "hazirla_steam_uyari" in keys:
            attempt("hazirla_steam_uyari", steam_warning)
        if not (self.journal["motor"] or self.journal["steam"]):  # geri alınacak bir şey yok
            self.journal = None
            try:
                self.journal_path.unlink()
            except OSError:
                pass
        return results

    def stop(self):
        """Günlükteki her şeyi geri alır. Biri geri alınamazsa günlük kalır; `recover` sonraki açılışta yeniden dener."""
        journal = self.journal
        if journal is None:
            return
        failed = False
        for change_id in journal.get("motor") or []:
            try:
                if self.engine is None:
                    raise RuntimeError("motor yok")
                if self.engine.store.has(change_id):
                    result = self.engine.revert(change_id, confirmed=True)
                    if not result.ok:
                        raise RuntimeError(result.key)
            except Exception as exc:
                failed = True
                _log.warning("Oyun-sırası değişikliği geri alınamadı (%s): %s", change_id, exc)
        for name in journal.get("servisler") or []:
            try:
                info = self.system.get_service(name)
                self.system.set_service(name, info["baslangic"] if info else "Manual", True)
            except Exception as exc:
                failed = True
                _log.warning("Servis yeniden başlatılamadı (%s): %s", name, exc)
        steam = journal.get("steam") or []
        try:  # PID yeniden başlatmadan sonra başka sürece geçmiş olabilir: yalnızca hâlâ Steam yardımcısıysa (Denetim A B4)
            helpers = {pid for pid, exe in self.ops.list_processes() if exe in STEAM_HELPERS} if steam else set()
        except Exception:
            helpers = set()
        for helper_pid, previous in steam:
            if helper_pid not in helpers:
                continue  # Steam kapanmış ya da PID başka sürecin
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
            return  # günlük dosyası kalır
        try:
            self.journal_path.unlink()
        except OSError:
            pass

    def recover(self, before=None):
        """Önceki oturumdan kalan günlük varsa (uygulama oyun sırasında kapanmış): geri al. before (time.time() değeri) verilirse
        yalnızca o andan ÖNCE yazılmış günlük geri alınır; sonradan başlayan oturuma (kullanıcının yeni "Hazırla"sı) dokunulmaz."""
        try:
            if before is not None and self.journal_path.stat().st_mtime > before:
                return False
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
