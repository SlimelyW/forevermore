"""Sistem taraması. Tüm bölümler yalnızca OKUMA yapar.

Kullanım:
    from app.scan import run_scan
    result = run_scan(progress=lambda sira, toplam, bolum: ...)
"""

import datetime
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.core import log
from app.engine import catalog, resolvers
from app.scan import checks, events, findings, gaming, hardware, network, peripherals, software, storage

_log = log.get("scan")

SECTIONS = [
    ("sistem", hardware.collect_system),
    ("donanim", hardware.collect_hardware),
    ("surecler", software.collect_processes),
    ("baslangic", software.collect_startup),
    ("servisler", software.collect_services),
    ("olaylar", events.collect_events),
    ("oyun", gaming.collect_gaming),
    ("guvenlik", gaming.collect_security),
    ("ag", network.collect_network),
    ("giris", peripherals.collect_input),
    ("ses", peripherals.collect_audio),
    ("depolama", storage.collect_storage),
]


def run_scan(progress=None, max_workers=6):
    """Taramayı çalıştırır ve sonucu sözlük olarak döndürür.

    Bir bölüm hata verirse diğerleri devam eder; hata `hatalar` altında
    bölüm adıyla tutulur ve log'a yazılır.
    """
    started = time.monotonic()
    resolvers.clear_cache()
    checks._bcd_elements.cache_clear()
    result = {
        "zaman": datetime.datetime.now().isoformat(timespec="seconds"),
        "bolumler": {},
        "hatalar": {},
        "sureler": {},
    }
    _log.info("Tarama başladı")

    def timed(name, func):
        t0 = time.monotonic()
        try:
            return name, func(), None, time.monotonic() - t0
        except Exception as exc:
            return name, None, exc, time.monotonic() - t0

    done = 0
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(timed, name, func) for name, func in SECTIONS]
        for future in as_completed(futures):
            name, data, error, seconds = future.result()
            done += 1
            result["sureler"][name] = round(seconds, 1)
            if error is None:
                result["bolumler"][name] = data
            else:
                result["hatalar"][name] = str(error)
                _log.error("Tarama bölümü başarısız (%s): %s", name, error)
            if progress:
                progress(done, len(SECTIONS), name)

    try:
        result["tespitler"] = checks.evaluate(catalog.tweaks(), result["bolumler"])
    except Exception as exc:
        result["tespitler"] = []
        result["hatalar"]["tespit"] = str(exc)
        _log.error("Tespit kontrolleri başarısız: %s", exc)
    try:
        result["onyukleme_secenekleri"] = checks.boot_warnings()
    except Exception as exc:
        _log.error("Önyükleme seçenekleri okunamadı: %s", exc)
    result["bulgular"] = findings.build(result)
    result["toplam_sure"] = round(time.monotonic() - started, 1)
    _log.info("Tarama bitti: %s sn, %d bulgu, %d hata",
              result["toplam_sure"], len(result["bulgular"]), len(result["hatalar"]))
    return result
