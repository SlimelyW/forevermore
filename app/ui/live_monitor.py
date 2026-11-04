"""Canlı izleme iş parçacığı.

Saniyede bir örnek alır ve Qt sinyaliyle ana iş parçacığına verir. Yalnızca
Özet sayfası görünürken çalışır (`set_active`); sayfa gizlenince veya pencere
küçültülünce durur, işlemci harcamaz.
"""

import threading

from PySide6.QtCore import QObject, Signal

from app.core import log

_log = log.get("live")


def _default_factory():
    from app.scan.live import LiveSampler  # noqa: WPS433 - yalnızca Windows'ta yüklenir
    return LiveSampler()


class LiveMonitor(QObject):
    sampled = Signal(object)
    failed = Signal()

    def __init__(self, factory=None, interval=1.0):
        super().__init__()
        self.factory = factory or _default_factory
        self.interval = interval
        self._active = threading.Event()
        self._stop = threading.Event()
        self._thread = None
        self._owners = set()
        self._window_active = True

    def set_window_active(self, on):
        """Pencere öndeyken True; başka pencereye geçilince/küçültülünce örnekleme durur (boşta CPU ~0)."""
        self._window_active = on
        self._sync()

    def _sync(self):
        if self._stop.is_set():
            return
        if self._owners and self._window_active:
            if self._thread is None:
                self._thread = threading.Thread(target=self._loop, name="canli-izleme", daemon=True)
                self._thread.start()
            self._active.set()
        else:
            self._active.clear()

    def set_active(self, on, owner=None):
        """Bir sayfa görünür olunca on=True, gizlenince False. Birden fazla sayfa (Özet, PC
        Detayları) aynı izleyiciyi kullanır; görünür sayfa kalmayınca izleme durur."""
        if self._stop.is_set():
            return
        key = id(owner)
        if on:
            self._owners.add(key)
        else:
            self._owners.discard(key)
        self._sync()

    def _loop(self):
        try:
            sampler = self.factory()
        except Exception:
            _log.exception("Canlı izleme başlatılamadı")
            self.failed.emit()
            return
        try:
            while not self._stop.is_set():
                if not self._active.wait(0.5):
                    continue
                try:
                    sample = sampler.sample()
                    if self._stop.is_set():
                        break
                    self.sampled.emit(sample)
                except RuntimeError:  # pencere kapanırken sinyal nesnesi silinmiş olabilir
                    break
                except Exception:
                    _log.exception("Canlı örnek alınamadı")
                    self.failed.emit()
                    return
                self._stop.wait(self.interval)
        finally:
            try:
                sampler.close()
            except Exception:
                pass

    def stop(self):
        self._stop.set()
        self._active.set()  # bekleyen döngü uyansın ve çıksın
