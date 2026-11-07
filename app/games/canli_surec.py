"""Oyun sürerken canlı süreç listesi (BACKLOG C8): "Uygulamalar" (pencereli) ve "Arka plan" (pencereli olmayan) grupları,
her grupta toplam CPU% ve en çok kullanan 5 program. SALT OKUNUR; veri yalnızca bellekte (dosyaya/günlüğe yazılmaz, ağa gitmez).

Yalnızca Oyunlar sayfası görünürken, oyun sürerken ve "Oyun oturumu kaydı" açıksa çalışır (karar sayfada, bkz. page_games);
koşul bozulunca `stop()` ile iş parçacığı ve sayaç tamamen kapanır. Oyunun kendisi ve Forevermore listeden çıkarılır.
Aynı adlı süreçler (svchost...) tek satırda toplanır; CPU% toplam çekirdek sayısına bölünür (Görev Yöneticisi gibi).
"""

import json
import os
import re
import threading

from app.core import i18n, log, paths
from app.games.recorder import OWN_PROCESSES

_log = log.get("canli_surec")

INTERVAL = 2.0
TOP = 5
MIN_CPU = 0.1   # bunun altı satır olmaz (sıfırlardan oluşan liste gürültü)
_SKIP = {"_total", "idle", "system", "memory compression"}
_SUFFIX = re.compile(r"#\d+$")
_names = None


def _norm(name):
    return _SUFFIX.sub("", str(name)).lower().removesuffix(".exe")


def friendly(name):
    """Bilinen sistem/uygulama adı için sade ad (data/surec_adlari.json), yoksa ham ad."""
    global _names
    if _names is None:
        try:
            _names = json.loads((paths.data_dir() / "surec_adlari.json").read_text(encoding="utf-8"))["adlar"]
        except (OSError, ValueError, KeyError):
            _names = {}
    entry = _names.get(_norm(name))
    if isinstance(entry, dict):
        return entry.get(i18n.current()) or entry.get("en") or _SUFFIX.sub("", name)
    return entry or _SUFFIX.sub("", name)


def build(rows, windowed, cpu_count, game=""):
    """rows: [(PDH örnek adı, % Processor Time)]; windowed: pencereli süreç adları (küçük harf, .exe'siz).
    -> {"uygulamalar": {"toplam", "liste": [{"ad", "cpu"}]}, "arka_plan": {...}}"""
    skip = _SKIP | OWN_PROCESSES | {_norm(game)}
    cpu = {}
    for name, value in rows:
        key = _norm(name)
        if key not in skip:
            cpu[key] = cpu.get(key, 0.0) + max(0.0, value) / max(1, cpu_count)
    result = {}
    for group, wanted in (("uygulamalar", True), ("arka_plan", False)):
        members = {k: v for k, v in cpu.items() if (k in windowed) == wanted}
        top = sorted(members, key=members.get, reverse=True)
        result[group] = {"toplam": round(min(sum(members.values()), 100.0), 1),
                         "liste": [{"ad": friendly(k), "cpu": round(min(members[k], 100.0), 1)}
                                   for k in top if members[k] >= MIN_CPU][:TOP]}
    return result


class _Pdh:
    """Gerçek kaynak: \\Process(*)\\% Processor Time + pencereli süreçler (presentmon.Desktop)."""

    def __init__(self):
        from app.measure import presentmon  # noqa: WPS433
        from app.scan.live import PdhQuery  # noqa: WPS433
        self.query = PdhQuery()
        self.query.add("cpu", r"\Process(*)\% Processor Time")
        self.query.collect()
        self.desktop = presentmon.Desktop()

    def rows(self):
        self.query.collect()
        return self.query.array("cpu")

    def windowed(self):
        names = dict(self.desktop.processes())
        return {_norm(names[pid]) for pid in self.desktop.windows() if pid in names}

    def close(self):
        self.query.close()


class LiveProcesses:
    """start() / stop(); son sonuç snapshot() ile. source: rows(), windowed(), close() (testler için sahte)."""

    def __init__(self, game_exe="", source=None, interval=INTERVAL, cpu_count=None):
        self.game = game_exe or ""
        self._source_factory = source or _Pdh
        self.interval = interval
        self.cpu_count = cpu_count or os.cpu_count() or 1
        self._stop = threading.Event()
        self._thread = None
        self._lock = threading.Lock()
        self._snap = None

    def snapshot(self):
        with self._lock:
            return self._snap

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if not self.running:
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="canli-surec", daemon=True)
            self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3)
        self._thread = None
        with self._lock:
            self._snap = None  # eski veri gösterilmesin

    def step(self, source):
        snap = build(source.rows(), source.windowed(), self.cpu_count, self.game)
        with self._lock:
            self._snap = snap

    def _run(self):
        source = None
        try:
            source = self._source_factory()
            while not self._stop.wait(self.interval):
                self.step(source)
        except Exception:
            _log.exception("Canlı süreç listesi durdu")
        finally:
            if source is not None:
                source.close()
