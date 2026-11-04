"""Log dosyası ayarı.

Her işlem %LOCALAPPDATA%\\Forevermore\\logs\\forevermore.log dosyasına yazılır.
Log satırları da gizlilik filtresinden geçer; kullanıcı log dosyasını sana
gönderdiğinde içinde kişisel bilgi olmaz.
"""

import atexit
import logging
import logging.handlers
import queue

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
    _configured = True


def get(name):
    return logging.getLogger(f"pcopt.{name}")
