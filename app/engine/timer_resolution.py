"""Zamanlayıcı çözünürlüğü (timer resolution), kendi kodumuz (ISLC vb. araç gömülmez).

- NtQueryTimerResolution / NtSetTimerResolution (ntdll.dll). Belgelenmemiş ama Windows'un çok
  uzun süredir sunduğu çağrılar; timeBeginPeriod'un daha ince (0,5 ms) hâlidir.
- Windows 10 2004'ten beri istek yalnızca isteyen süreci etkiler. Windows 11'de diğer
  programları da etkilemesi için GlobalTimerResolutionRequests değeri gerekir (CPU-009).
- İstek, uygulama açık kaldığı sürece geçerlidir; uygulama kapanınca Windows kendiliğinden
  bırakır. Kalıcı bir sistem değişikliği yoktur, yedek gerekmez.
- Etkisi BELİRSİZ: kare süresi tutarlılığına küçük etki bildirilir, geniş ölçüm yoktur.
  Laptopta pil tüketimini artırır. Önce / Sonra'daki "Sleep(1) hassasiyeti" ile ölçülebilir.

Birim: 100 ns (10000 = 1 ms, 5000 = 0,5 ms).
"""

import ctypes
import statistics
import time
from ctypes import byref, c_ulong

from app.core import log

_log = log.get("timer")

CHOICES = (0, 10000, 5000)  # 0: Windows'a bırak
_held = 0


def query():
    """{'en_kaba': ms, 'en_ince': ms, 'su_an': ms} veya okunamazsa None."""
    try:
        coarsest, finest, current = c_ulong(), c_ulong(), c_ulong()
        status = ctypes.windll.ntdll.NtQueryTimerResolution(byref(coarsest), byref(finest), byref(current))
    except (AttributeError, OSError):
        return None
    if status != 0:
        return None
    return {"en_kaba": coarsest.value / 10000, "en_ince": finest.value / 10000, "su_an": current.value / 10000}


def hold(resolution):
    """Bu süreç için çözünürlük ister (0: önceki isteği bırakır). Gerçekleşen değeri (ms) döndürür."""
    global _held
    ntdll = ctypes.windll.ntdll
    actual = c_ulong()
    if _held:
        ntdll.NtSetTimerResolution(c_ulong(_held), False, byref(actual))
        _held = 0
    if resolution:
        if ntdll.NtSetTimerResolution(c_ulong(int(resolution)), True, byref(actual)) != 0:
            raise OSError("NtSetTimerResolution başarısız")
        _held = int(resolution)
        _log.info("Zamanlayıcı çözünürlüğü istendi: %s ms (gerçekleşen %s ms)", resolution / 10000,
                  actual.value / 10000)
    return actual.value / 10000 if actual.value else None


def sleep_test(count=200):
    """Sleep(1)'in gerçekte kaç ms sürdüğü: {'ortalama', 'p99'} (ms). Ayrı bir süreçte çalıştırılır ki
    ölçen programın kendi isteği sonucu değiştirmesin (bkz. app/__main__.py --uyku-testi)."""
    kernel32 = ctypes.windll.kernel32
    durations = []
    for _ in range(count):
        start = time.perf_counter()
        kernel32.Sleep(1)
        durations.append((time.perf_counter() - start) * 1000)
    durations.sort()
    return {"ortalama": round(statistics.fmean(durations), 3),
            "p99": round(durations[min(len(durations) - 1, int(len(durations) * 0.99))], 3)}
