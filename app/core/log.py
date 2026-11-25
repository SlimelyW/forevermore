"""Log dosyası ayarı.

Her işlem %LOCALAPPDATA%\\Forevermore\\logs\\forevermore.log dosyasına yazılır.
Log satırları da gizlilik filtresinden geçer; kullanıcı log dosyasını sana
gönderdiğinde içinde kişisel bilgi olmaz.
"""

import atexit
import faulthandler
import logging
import logging.handlers
import queue
import sys
import threading

from app.core import paths, privacy

_configured = False


class _PrivacyFilter(logging.Filter):
    def filter(self, record):
        record.msg = privacy.scrub_text(record.getMessage())
        record.args = ()
        return True


def setup():
    global _configured
    if _configured:
        return
    handler = logging.handlers.RotatingFileHandler(
        paths.logs_dir() / "forevermore.log",
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    handler.addFilter(_PrivacyFilter())
    # Diske yazmayı ayrı iş parçacığı yapar: arayüz iş parçacığı disk beklemesin (ör. geri yükleme noktası oluşturulurken
    # Windows birim gölge kopyası yazmaları birkaç saniye dondurabilir). Sınır: ani çökmede kuyruktaki son satırlar kaybolabilir.
    records = queue.SimpleQueue()
    listener = logging.handlers.QueueListener(records, handler)
    listener.start()
    atexit.register(listener.stop)
    root = logging.getLogger("pcopt")
    root.setLevel(logging.INFO)
    root.addHandler(logging.handlers.QueueHandler(records))
    _capture_crashes(root)
    _configured = True


def _capture_crashes(root):
    """Pencereli .exe'de stderr yok: yakalanmamış hatalar (iş parçacıkları ve Qt geri çağrıları dahil) hiçbir yere
    yazılmıyordu. Artık log'a gider. Yerel çökmede (ctypes/Qt) Python yığını cokme.txt'ye düşer; ham yol içerebileceği
    için bir sonraki açılışta gizlilik filtresinden geçip log'a taşınır ve dosya boşaltılır."""
    crash = paths.logs_dir() / "cokme.txt"
    try:
        previous = crash.read_text(encoding="utf-8", errors="replace").strip() if crash.exists() else ""
        if previous:
            root.error("Önceki açılış çöktü:\n%s", previous[-4000:])
        faulthandler.enable(open(crash, "w", encoding="utf-8"), all_threads=True)  # noqa: SIM115 - süreç boyunca açık
    except OSError:
        pass
    sys.excepthook = lambda *exc: root.critical("Yakalanmamış hata", exc_info=exc)
    threading.excepthook = lambda a: root.critical("Yakalanmamış hata (%s)", getattr(a.thread, "name", "?"),
                                                   exc_info=(a.exc_type, a.exc_value, a.exc_traceback))


def get(name):
    return logging.getLogger(f"pcopt.{name}")
