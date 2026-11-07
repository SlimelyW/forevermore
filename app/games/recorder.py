"""Oyun oturumu kaydı: yalnızca oyun oturumu SÜRERKEN, kullanıcı açtıysa (Ayarlar > Genel, varsayılan KAPALI).

Ham örnek saklanmaz: örnekler akarken özetlenir (en düşük/ortalama/en yüksek, eşik üstünde geçen süre, arka planda en çok
işlemci kullanan programlar). Özet yalnızca bu bilgisayarda, kullanıcı klasöründeki oyun_oturum_gecmisi.json içinde (son 10
oturum) tutulur; ağa hiçbir şey gitmez. Oyun yokken hiçbir iş parçacığı ya da sayaç çalışmaz.
FPS (en düşük/ortalama/en yüksek ve düşüş geçmişi) yalnızca "Canlı FPS" ayrıca açıksa ve canlı ölçüm çalışıyorsa özete girer
(app/measure/live_fps.py); kayıt kapalıysa FPS özeti yerel geçmişe YAZILMAZ. Bkz. docs/GUVENLIK.md "Oyun oturumu kaydı".
"""

import json
import threading
import time

from app.core import log, paths

_log = log.get("kayit")

INTERVAL = 5.0
CPU_HIGH = 90.0   # bu değerin üstünde geçen süre raporlanır
RAM_HIGH = 90.0
HISTORY_LIMIT = 10
TOP_PROCESSES = 3
OWN_PROCESSES = {"forevermore", "python", "pythonw"}
DROP_LIMIT = 20   # oturum başına saklanan düşüş sayısı


class _Stat:
    def __init__(self):
        self.count, self.total, self.low, self.high = 0, 0.0, None, None

    def add(self, value):
        if value is None:
            return
        self.count += 1
        self.total += value
        self.low = value if self.low is None else min(self.low, value)
        self.high = value if self.high is None else max(self.high, value)

    def result(self):
        if not self.count:
            return None
        return {"min": round(self.low, 1), "ort": round(self.total / self.count, 1), "maks": round(self.high, 1)}


class SessionStats:
    """Akan özet: bellek kullanımı örnek sayısından bağımsızdır."""

    def __init__(self, game_exe="", interval=INTERVAL):
        self.interval = interval
        self.game = (game_exe or "").lower().removesuffix(".exe")
        self.stats = {key: _Stat() for key in ("cpu", "gpu", "ram", "disk")}
        self.samples = self.cpu_high = self.ram_high = 0
        self.process_cpu = {}

    def add(self, sample):
        self.samples += 1
        self.stats["cpu"].add(sample.get("cpu"))
        self.stats["gpu"].add(sample.get("gpu"))
        self.stats["disk"].add(sample.get("disk"))
        total, used = sample.get("ram_toplam"), sample.get("ram_kullanilan")
        ram = used / total * 100 if total and used is not None else None
        self.stats["ram"].add(ram)
        self.cpu_high += (sample.get("cpu") or 0) >= CPU_HIGH
        self.ram_high += (ram or 0) >= RAM_HIGH
        for item in sample.get("en_cok") or []:
            name = str(item.get("ad", ""))
            if name.lower() not in OWN_PROCESSES and name.lower() != self.game:
                self.process_cpu[name] = self.process_cpu.get(name, 0.0) + float(item.get("cpu") or 0)

    def summary(self, seconds):
        """{"sure", "ornek", "cpu"/"gpu"/"ram"/"disk": {min, ort, maks}, "cpu_yuksek_sn", "ram_yuksek_sn", "arka_plan": [...]}"""
        top = sorted(self.process_cpu.items(), key=lambda kv: kv[1], reverse=True)[:TOP_PROCESSES]
        result = {"sure": round(seconds), "ornek": self.samples,
                  "cpu_yuksek_sn": round(self.cpu_high * self.interval), "ram_yuksek_sn": round(self.ram_high * self.interval),
                  "arka_plan": [{"ad": name, "cpu": round(total / max(1, self.samples), 1)} for name, total in top
                                if total / max(1, self.samples) >= 1.0]}
        for key, stat in self.stats.items():
            result[key] = stat.result()
        return result


class FpsStats:
    """Canlı FPS özeti (saniyelik değerler akarken özetlenir; ham değer saklanmaz). İki iş parçacığından çağrılabilir."""

    def __init__(self):
        self._lock = threading.Lock()
        self._stat = _Stat()
        self.drops = []

    def add(self, fps):
        with self._lock:
            self._stat.add(fps)

    def drop(self, record):
        with self._lock:
            if len(self.drops) < DROP_LIMIT:
                self.drops.append(dict(record))

    def result(self):
        """{"fps": {min, ort, maks}, "fps_dususleri": [...]} ya da hiç FPS alınmadıysa {}."""
        with self._lock:
            stat = self._stat.result()
            return {"fps": stat, "fps_dususleri": list(self.drops)} if stat else {}


def _default_factory():
    from app.scan.live import LiveSampler  # noqa: WPS433 (yalnızca Windows'ta)
    return LiveSampler(with_processes=True, process_every=1)


class SessionRecorder:
    """Oyun başlayınca start(), bitince stop() (özet döner). Örnekleme kendi iş parçacığında, 5 saniyede bir."""

    def __init__(self, game_exe="", factory=None, interval=INTERVAL):
        self.factory = factory or _default_factory
        self.interval = interval
        self.stats = SessionStats(game_exe, interval)
        self.fps = FpsStats()
        self._stop = threading.Event()
        self._thread = None
        self._started = None

    def start(self):
        self._started = time.monotonic()
        self._thread = threading.Thread(target=self._loop, name="oyun-kaydi", daemon=True)
        self._thread.start()

    def _loop(self):
        try:
            sampler = self.factory()
        except Exception:
            _log.exception("Oyun kaydı başlatılamadı")
            return
        try:
            sampler.sample()  # ilk çağrı yalnızca hazırlar
            while not self._stop.wait(self.interval):
                self.stats.add(sampler.sample())
        except Exception:
            _log.exception("Oyun kaydı örneği alınamadı")  # o ana kadarki özet korunur
        finally:
            try:
                sampler.close()
            except Exception:
                pass

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3)
        return dict(self.stats.summary(time.monotonic() - (self._started or time.monotonic())), **self.fps.result())


# --------------------------------------------------------------------------- geçmiş (yalnızca yerel dosya)
def history_path():
    return paths.user_data_dir() / "oyun_oturum_gecmisi.json"


def load_history(path=None):
    try:
        data = json.loads((path or history_path()).read_text(encoding="utf-8"))
        return [e for e in data if isinstance(e, dict)][-HISTORY_LIMIT:] if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def add_history(game, summary, when, path=None):
    """Son HISTORY_LIMIT oturumu tutar (atomik yazım). Yazılamazsa sessizce atlanır: kayıt oyunu ya da uygulamayı bozmaz."""
    path = path or history_path()
    entries = load_history(path) + [dict(summary, oyun=game["ad"], oyun_id=game["id"], tarih=when)]
    try:
        paths.atomic_write(path, json.dumps(entries[-HISTORY_LIMIT:], ensure_ascii=False, indent=1))
    except OSError:
        _log.warning("Oturum geçmişi yazılamadı")


def latest_for(game_id, path=None):
    return next((e for e in reversed(load_history(path)) if e.get("oyun_id") == game_id), None)
