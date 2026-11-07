"""Canlı FPS: oyun oturumu SÜRERKEN, kullanıcı açtıysa (Ayarlar > Genel "Canlı FPS", varsayılan KAPALI).

Intel PresentMon (presentmon.py ile aynı program) tek bir ETW oturumu olarak çalışır; oyuna enjekte olmaz, oyun sürecine
tanıtıcı açmaz. Çıktı CSV olarak boru hattından (--output_stdout) okunur, dosyaya YAZILMAZ; ham kare saklanmaz: kare
süreleri saniyelik FPS'e indirgenir ve yalnızca özet (en düşük/ortalama/en yüksek, düşüş geçmişi) tutulur.
Ağa hiçbir şey gitmez. Oyun odakta değilken PresentMon durdurulur (hem yük hem yanlış sayım olmasın diye).

Düşüş uyarısı MUTLAK eşik değildir (FPS sınırı koyanlara yanlış alarm verirdi): FPS, son 30 sn ortalamasının %60'ının altına
5 sn kesintisiz inerse bir düşüş sayılır; oyunun ilk 30 sn'sinde (ortalama oluşana kadar) uyarı verilmez.
Bkz. docs/GUVENLIK.md "Canlı FPS".
"""

import collections
import subprocess
import threading
import time

from app.core import log, powershell
from app.measure import presentmon

_log = log.get("canli_fps")

SESSION = "ForevermoreCanli"   # ölçüm sayfasının oturumundan (ForevermoreOlcum) ayrı: ikisi birbirini kapatmaz
WINDOW_SN = 30                 # taban: son 30 sn ortalaması; aynı zamanda ısınma süresi
DROP_RATIO = 0.6               # tabanın %60'ının altı
DROP_SN = 5                    # kesintisiz bu kadar saniye
NOT_FOCUS_GRACE_SN = 3         # kısa alt-tab'da PresentMon sürekli kapanıp açılmasın
NO_FRAMES_SN = 10              # odaktayken bu kadar süre kare gelmezse "ölçüm alınamıyor" (0 FPS DENMEZ)
QUICK_EXIT_SN = 5              # PresentMon bu kadar sürede kapanırsa başlatılamamış sayılır, tekrar denenmez
PID_REFRESH_SN = 5
NOTE_LIMIT = 300


class SecondBinner:
    """Kare sürelerini (ms) saniyelik FPS'e çevirir. Boru hattı kare kare değil toplu gelebilir; bu yüzden saat değil
    kare sürelerinin toplamı (1000 ms) ölçüt alınır."""

    def __init__(self):
        self.total, self.count = 0.0, 0

    def add(self, ms):
        """Bir saniye dolduysa FPS, yoksa None."""
        if not ms or ms <= 0:
            return None
        self.total += ms
        self.count += 1
        if self.total < 1000:
            return None
        fps = self.count * 1000.0 / self.total
        self.total, self.count = 0.0, 0
        return fps

    def reset(self):
        self.total, self.count = 0.0, 0


class DropDetector:
    """Saniyelik FPS değerlerinden ani düşüşü bulur. Yalnızca mantık: saat, iş parçacığı, PresentMon yok (test edilebilir).

    Taban = düşük sayılmayan son 30 sn'nin ortalaması (düşüş saniyeleri tabana girmez, yoksa uzun düşüş kendini normal
    sayardı). Düşüş 30 sn'yi geçerse yeni normal kabul edilir: taban o seviyeye yeniden kurulur, tekrar uyarı verilmez."""

    def __init__(self):
        self.history = collections.deque(maxlen=WINDOW_SN)
        self.streak = []
        self.seconds = 0     # oyun odaktayken geçen saniye
        self.alarm = None    # açık düşüş: {"sn", "onceki_fps", "en_dusuk_fps"}

    def baseline(self):
        return sum(self.history) / len(self.history) if len(self.history) >= WINDOW_SN else None

    def add(self, fps):
        """Düşüş bittiyse kaydı (dict), yoksa None döndürür. Düşüş sürerken self.alarm doludur."""
        self.seconds += 1
        base = self.baseline()
        if base is None or fps >= base * DROP_RATIO:
            return self._recover(fps)
        self.streak.append(fps)
        if len(self.streak) == DROP_SN:
            self.alarm = {"sn": self.seconds - DROP_SN + 1, "onceki_fps": round(base), "en_dusuk_fps": round(min(self.streak))}
        elif self.alarm is not None:
            self.alarm["en_dusuk_fps"] = min(self.alarm["en_dusuk_fps"], round(fps))
            if len(self.streak) >= WINDOW_SN:  # yeni normal
                record = self._close()
                self.history = collections.deque(self.streak, maxlen=WINDOW_SN)
                self.streak = []
                return record
        return None

    def _recover(self, fps):
        record = self._close()
        self.streak = []
        self.history.append(fps)
        return record

    def _close(self):
        if self.alarm is None:
            return None
        record = dict(self.alarm, sure_sn=len(self.streak))
        self.alarm = None
        return record

    def pause(self):
        """Oyun odaktan çıktı: devam eden düşüş kapanır, taban korunur (odağa dönüşteki yükleme düşüşü sayılmasın)."""
        record = self._close()
        self.streak = []
        return record


def _decode(raw):
    return (raw.replace(b"\x00", b"") if b"\x00" in raw else raw).decode("utf-8", errors="replace").strip()


class LiveFps:
    """Bir oyun için canlı FPS. start() / stop(); sonuçlar on_second(fps) ve on_drop(kayıt) ile, anlık durum snapshot() ile.

    desktop: presentmon.Desktop benzeri (processes(), foreground()); launch(args) -> Popen benzeri. İkisi testler içindir."""

    def __init__(self, exe_name, exe=None, on_second=None, on_drop=None, desktop=None, launch=None, clock=time.monotonic,
                 wait=None, on_fail=None):
        self.name = (exe_name or "").lower()
        self.exe = exe
        self.on_second = on_second or (lambda _fps: None)
        self.on_drop = on_drop or (lambda _record: None)
        self.on_fail = on_fail or (lambda _durum: None)  # başlatılamadı/durdu: arayüz özelliği kapatır (iş parçacığından çağrılır)
        self.desktop = desktop
        self.launch = launch or self._popen
        self.clock = clock
        self._stop = threading.Event()
        self._wait = wait or self._stop.wait
        self._thread = None
        self._lock = threading.Lock()
        self._state = {"durum": "basliyor", "fps": None, "dusus": None, "ayrinti": ""}
        self.detector = DropDetector()
        self._binner = SecondBinner()
        self._focused = False
        self._last_frame = self.clock()
        self._proc = None
        self._reader = None
        self._started = 0.0
        self._dlock = threading.Lock()  # DropDetector'a okuma iş parçacığı ve denetim döngüsü birlikte dokunur

    # ------------------------------------------------------------------ dışarıya
    def snapshot(self):
        with self._lock:
            return dict(self._state, dusus=dict(self._state["dusus"]) if self._state["dusus"] else None)

    def _set(self, **changes):
        with self._lock:
            self._state.update(changes)

    def start(self):
        self._thread = threading.Thread(target=self._run, name="canli-fps", daemon=True)
        self._thread.start()

    def stop(self):
        """Durdurur ve açık düşüş varsa kaydını kapatır."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=8)
        self._pause_detector()

    # ------------------------------------------------------------------ PresentMon
    def _args(self):
        return [self.exe, "--process_name", self.name, "--output_stdout", "--stop_existing_session",
                "--session_name", SESSION, "--no_console_stats"]

    @staticmethod
    def _popen(args):
        return subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                creationflags=powershell.CREATE_NO_WINDOW)

    def _begin(self):
        self._proc = self.launch(self._args())
        self._started = self.clock()
        self._last_frame = self.clock()
        self._binner.reset()
        self._set(durum="basliyor")
        self._reader = threading.Thread(target=self._read, args=(self._proc,), name="canli-fps-okuma", daemon=True)
        self._reader.start()

    def _end(self):
        proc, self._proc = self._proc, None
        if proc is None:
            return
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        self._binner.reset()

    def _read(self, proc):
        """PresentMon çıktısı: başlıktan önceki satırlar (hata iletisi) not olarak tutulur, sonrası kare satırları."""
        columns, notes = None, []
        try:
            for raw in proc.stdout:
                line = _decode(raw)
                if not line:
                    continue
                cells = [c.strip() for c in line.split(",")]
                if columns is None:
                    lowered = [c.lower() for c in cells]
                    frame = next((lowered.index(c) for c in presentmon.FRAME_COLUMNS if c in lowered), None)
                    if frame is not None and "application" in lowered:
                        columns = frame
                    elif sum(len(n) for n in notes) < NOTE_LIMIT:
                        notes.append(line[:NOTE_LIMIT])
                        self._set(ayrinti=" | ".join(notes)[:NOTE_LIMIT])
                    continue
                self._frame(cells, columns)
        except (OSError, ValueError):
            pass  # PresentMon durdurulunca boru kapanır
        except Exception:
            _log.exception("Canlı FPS çıktısı okunamadı")
            self._fail("baslamadi")

    def _fail(self, durum):
        """Bir kez: durum yazılır, döngü durur (yeniden denenmez), arayüze haber verilir."""
        self._set(durum=durum, fps=None, dusus=None)
        if self._stop.is_set():
            return
        self._stop.set()
        try:
            self.on_fail(durum)
        except Exception:
            _log.exception("Canlı FPS hata geri çağrısı")

    def _frame(self, cells, column):
        if not self._focused:  # alt-tab: oyun arkada kare üretiyorsa sayılmaz
            return
        try:
            ms = float(cells[column])
        except (IndexError, ValueError):
            return
        self._last_frame = self.clock()
        fps = self._binner.add(ms)
        if fps is not None:
            self._second(fps)

    def _pause_detector(self):
        with self._dlock:
            record = self.detector.pause()
        self._close_drop(record)

    def _second(self, fps):
        with self._dlock:
            record = self.detector.add(fps)
            alarm = dict(self.detector.alarm) if self.detector.alarm else None
        self._close_drop(record)
        self._set(durum="olculuyor", fps=round(fps), dusus=alarm)
        try:
            self.on_second(fps)
        except Exception:
            _log.exception("Canlı FPS geri çağrısı")

    def _close_drop(self, record):
        if record is None:
            return
        try:
            self.on_drop(record)
        except Exception:
            _log.exception("Canlı FPS düşüş geri çağrısı")

    # ------------------------------------------------------------------ denetim döngüsü (1 sn)
    def _run(self):
        if not self.exe:
            self.exe = presentmon.find_presentmon()
        if not self.exe:
            self._fail("presentmon_yok")
            return
        try:
            self.desktop = self.desktop or presentmon.Desktop()
            self._loop()
        except Exception:
            _log.exception("Canlı FPS durdu")
            self._fail("baslamadi")
        finally:
            self._end()

    def _loop(self):
        pids, last_pids, not_focused_since = set(), -PID_REFRESH_SN, None
        while not self._stop.is_set():
            now = self.clock()
            if now - last_pids >= PID_REFRESH_SN:
                pids = {pid for pid, exe in self.desktop.processes() if exe == self.name}
                last_pids = now
            focused = self.desktop.foreground() in pids
            if focused:
                not_focused_since = None
            elif not_focused_since is None:
                not_focused_since = now
            self._focused = focused or (not_focused_since is not None and now - not_focused_since < NOT_FOCUS_GRACE_SN
                                        and self._proc is not None)
            if focused and self._proc is None:
                self._begin()
            elif not self._focused and self._proc is not None:
                self._pause_detector()
                self._end()
                self._set(durum="duraklatildi", fps=None, dusus=None)
            if self._proc is not None:
                self._watch(now)
            self._wait(1.0)

    def _watch(self, now):
        code = self._proc.poll()
        if code is not None:  # PresentMon kapandı
            quick = now - self._started < QUICK_EXIT_SN
            _log.info("PresentMon kapandı (kod %s, %s): %s", code, "hızlı" if quick else "sonradan",
                      self._state["ayrinti"])
            self._proc = None
            if quick:  # hızlı kapanan PresentMon tekrar tekrar başlatılmaz; ayar yeniden açılınca denenir
                self._fail("baslamadi")
            else:
                self._set(durum="duraklatildi", fps=None)
        elif self._focused and now - self._last_frame > NO_FRAMES_SN and self._state["durum"] != "kare_yok":
            self._set(durum="kare_yok", fps=None, dusus=None)  # ETW oturumu sessizce olay vermiyor olabilir
