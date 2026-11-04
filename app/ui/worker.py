"""Arka plan işleri.

- `run(..., serial=True)`: ayar DEĞİŞİKLİKLERİ tek sıra hâlinde yürür; iki
  değişiklik asla aynı anda yapılmaz.
- `run(..., serial=False)`: tarama ve durum okuma gibi okuma işleri ayrı bir
  havuzda çalışır, arayüzü ve değişiklik sırasını bekletmez.

Sonuçlar Qt sinyaliyle ana iş parçacığına geri verilir (Qt arayüzü yalnızca
ana iş parçacığından güncellenebilir).
"""

import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QObject, QTimer, Signal

from app.core import log

_log = log.get("worker")


class Worker(QObject):
    _deliver = Signal(object, object, object)

    def __init__(self):
        super().__init__()
        self._deliver.connect(self._dispatch)
        self.serial = ThreadPoolExecutor(max_workers=1, thread_name_prefix="degisiklik")
        self.background = ThreadPoolExecutor(max_workers=3, thread_name_prefix="okuma")
        self.closed = False

    def run(self, func, on_done=None, on_error=None, serial=True):
        """func() arka planda çalışır; bitince on_done(sonuç) ana iş parçacığında çağrılır."""
        if self.closed:  # pencere kapanırken gelen gecikmiş işler yok sayılır
            return
        def task():
            try:
                self._deliver.emit(on_done, func(), None)
            except Exception as exc:  # hata arayüzü çökertmesin
                _log.exception("Arka plan işi başarısız")
                self._deliver.emit(on_error, None, exc)
        (self.serial if serial else self.background).submit(task)

    def call_soon(self, func, *args):
        """Arka plan iş parçacığından ana iş parçacığında bir şey çalıştırmak için."""
        self._deliver.emit(lambda _result: func(*args), None, None)

    def _dispatch(self, callback, result, error):
        if callback is None:
            return
        try:
            callback(error if error is not None else result)
        except Exception:
            _log.exception("Arayüz geri çağrısı başarısız")

    def shutdown(self):
        self.closed = True
        for pool in (self.serial, self.background):
            pool.shutdown(wait=False, cancel_futures=True)


class StallWatch(QObject):
    """Arayüz iş parçacığı LIMIT saniyeden uzun olay işlemezse ("yanıt vermiyor") o anki yığını YEREL günlüğe yazar.
    Hiçbir yere gönderilmez; tanılama raporuna günlükle birlikte girer. Donmanın yerini kanıtla bulmak içindir."""

    LIMIT = 2.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self._beat = time.monotonic()
        self._main = threading.get_ident()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(250)
        stop = threading.Event()
        self.destroyed.connect(stop.set)  # pencere kapanınca izleme biter
        threading.Thread(target=self._watch, args=(stop,), name="arayuz_bekcisi", daemon=True).start()

    def _tick(self):
        self._beat = time.monotonic()

    def _watch(self, stop):
        reported = None
        while True:
            before = time.monotonic()
            if stop.wait(0.5):
                return
            beat = self._beat
            if time.monotonic() - before > 5:  # bekçinin kendisi de uyudu: bilgisayar uyku/hazırda bekletmeden döndü
                reported = beat
            if time.monotonic() - beat < self.LIMIT or reported == beat:
                continue
            reported = beat  # aynı takılma bir kez yazılır
            frame = sys._current_frames().get(self._main)  # noqa: SLF001 - tanılama
            stack = "".join(traceback.format_stack(frame)[-12:]) if frame else "?"
            _log.warning("Arayüz %.1f sn yanıt vermedi; ana iş parçacığı şurada:\n%s", time.monotonic() - beat, stack)
