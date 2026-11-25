"""Canlı sistem verileri (Görev Yöneticisi mantığı), SALT OKUNUR.

Windows'un kendi performans sayaçları (PDH, pdh.dll) ve GlobalMemoryStatusEx
ctypes ile okunur; ek kütüphane ve PowerShell yoktur. Sayaç adları
`PdhAddEnglishCounterW` ile İngilizce verilir, Türkçe Windows'ta da çalışır.

Hiçbir veri dosyaya yazılmaz veya dışarı gönderilmez; süreç adları yalnızca
ekranda gösterilir.
"""

import ctypes
import os
import re
import time
from ctypes import wintypes

from app.core import log

_log = log.get("live")

PDH_FMT_DOUBLE = 0x00000200
PDH_FMT_NOCAP100 = 0x00008000
PDH_MORE_DATA = 0x800007D2
PDH_VALID = (0, 1)  # PDH_CSTATUS_VALID_DATA, PDH_CSTATUS_NEW_DATA


class _Value(ctypes.Structure):
    _fields_ = [("CStatus", wintypes.DWORD), ("doubleValue", ctypes.c_double)]


class _Item(ctypes.Structure):
    _fields_ = [("szName", wintypes.LPWSTR), ("FmtValue", _Value)]


class _MemoryStatus(ctypes.Structure):
    _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def memory():
    status = _MemoryStatus()
    status.dwLength = ctypes.sizeof(_MemoryStatus)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
    return status.ullTotalPhys, status.ullTotalPhys - status.ullAvailPhys


class PdhQuery:
    """Bir grup PDH sayacı; `collect()` hepsini tek seferde okur."""

    def __init__(self):
        self.pdh = ctypes.WinDLL("pdh.dll")
        self.pdh.PdhOpenQueryW.argtypes = [wintypes.LPCWSTR, ctypes.c_size_t, ctypes.POINTER(ctypes.c_void_p)]
        self.pdh.PdhAddEnglishCounterW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, ctypes.c_size_t,
                                                   ctypes.POINTER(ctypes.c_void_p)]
        self.pdh.PdhCollectQueryData.argtypes = [ctypes.c_void_p]
        self.pdh.PdhGetFormattedCounterValue.argtypes = [ctypes.c_void_p, wintypes.DWORD,
                                                         ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(_Value)]
        self.pdh.PdhGetFormattedCounterArrayW.argtypes = [ctypes.c_void_p, wintypes.DWORD,
                                                          ctypes.POINTER(wintypes.DWORD),
                                                          ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        self.pdh.PdhCloseQuery.argtypes = [ctypes.c_void_p]
        for name in ("PdhOpenQueryW", "PdhAddEnglishCounterW", "PdhCollectQueryData",
                     "PdhGetFormattedCounterValue", "PdhGetFormattedCounterArrayW", "PdhCloseQuery"):
            getattr(self.pdh, name).restype = wintypes.DWORD
        self.handle = ctypes.c_void_p()
        status = self.pdh.PdhOpenQueryW(None, 0, ctypes.byref(self.handle))
        if status:
            raise OSError(f"PdhOpenQuery: {status:#x}")
        self.counters = {}

    def add(self, key, path):
        counter = ctypes.c_void_p()
        if self.pdh.PdhAddEnglishCounterW(self.handle, path, 0, ctypes.byref(counter)) == 0:
            self.counters[key] = counter
            return True
        return False

    def collect(self):
        return self.pdh.PdhCollectQueryData(self.handle) == 0

    def value(self, key, fmt=PDH_FMT_DOUBLE):
        counter = self.counters.get(key)
        if counter is None:
            return None
        value = _Value()
        if self.pdh.PdhGetFormattedCounterValue(counter, fmt, None, ctypes.byref(value)) != 0:
            return None
        return value.doubleValue if value.CStatus in PDH_VALID else None

    def array(self, key, fmt=PDH_FMT_DOUBLE | PDH_FMT_NOCAP100):
        """Joker (*) sayaçların örnek adı -> değer listesi."""
        counter = self.counters.get(key)
        if counter is None:
            return []
        size, count = wintypes.DWORD(0), wintypes.DWORD(0)
        status = self.pdh.PdhGetFormattedCounterArrayW(counter, fmt, ctypes.byref(size), ctypes.byref(count), None)
        if status != PDH_MORE_DATA or not size.value:
            return []
        buffer = (ctypes.c_byte * size.value)()
        if self.pdh.PdhGetFormattedCounterArrayW(counter, fmt, ctypes.byref(size), ctypes.byref(count), buffer) != 0:
            return []
        items = ctypes.cast(buffer, ctypes.POINTER(_Item))
        return [(items[i].szName, items[i].FmtValue.doubleValue)
                for i in range(count.value) if items[i].FmtValue.CStatus in PDH_VALID]

    def close(self):
        if self.handle:
            self.pdh.PdhCloseQuery(self.handle)
            self.handle = ctypes.c_void_p()


VRAM_PATH = r"\GPU Adapter Memory(*)\Dedicated Usage"
_LUID = re.compile(r"luid_0x([0-9a-fA-F]+)_0x([0-9a-fA-F]+)")


def main_adapter():
    """(luid, toplam_bayt) oyunlarda kullanılan kart (DXGI); okunamazsa (None, None)."""
    from app.scan import gpus  # noqa: WPS433 - yalnızca Windows'ta anlamlı
    try:
        adapters = gpus.dxgi_adapters()
    except Exception:
        _log.exception("DXGI kart listesi okunamadı")
        return None, None
    main = next((a for a in adapters if a.get("yuksek_performans")), adapters[0] if adapters else None)
    return (main["luid"], main["vram_mb"] * 2 ** 20) if main and main.get("vram_mb") else (None, None)


def vram_used(items, luid):
    """PDH 'Dedicated Usage' örneklerinden (ad, bayt) o kartın kullanılan belleği; eşleşme yoksa None.
    Örnek adı luid_0xYÜKSEK_0xDÜŞÜK_phys_N; DXGI luid'i YÜKSEK+DÜŞÜK (8+8 onaltılık hane)."""
    used = [value for name, value in items
            if (m := _LUID.search(name)) and f"{int(m[1], 16):08X}{int(m[2], 16):08X}" == luid]
    return sum(used) if used else None


class VramReader:
    """Oyun oturumunda tek sayaçla ekran kartı belleği: read() -> (kullanılan, toplam) bayt veya None."""

    def __init__(self):
        self.query = PdhQuery()
        self.luid, self.total = main_adapter()
        if not (self.luid and self.query.add("v", VRAM_PATH)):
            self.luid = None

    def read(self):
        if self.luid is None or not self.query.collect():
            return None
        used = vram_used(self.query.array("v", PDH_FMT_DOUBLE), self.luid)
        return None if used is None else (used, self.total)

    def close(self):
        self.query.close()


_GPU_ENGINE = re.compile(r"luid_(0x[0-9a-fA-F]+_0x[0-9a-fA-F]+)_phys_(\d+)_eng_(\d+)_engtype_(.*)$")
_PROCESS_SUFFIX = re.compile(r"#\d+$")
_SKIP_PROCESSES = {"_total", "idle", "system", "memory compression"}


class LiveSampler:
    """Her `sample()` çağrısında anlık değerleri döndürür (ilk çağrı yalnızca hazırlar)."""

    BASIC = {
        "cpu": r"\Processor Information(_Total)\% Processor Utility",
        "cpu_eski": r"\Processor(_Total)\% Processor Time",
        "cpu_performans": r"\Processor Information(_Total)\% Processor Performance",
        "cpu_frekans": r"\Processor Information(_Total)\Processor Frequency",
        "disk_bos": r"\PhysicalDisk(_Total)\% Idle Time",
        "disk_okuma": r"\PhysicalDisk(_Total)\Disk Read Bytes/sec",
        "disk_yazma": r"\PhysicalDisk(_Total)\Disk Write Bytes/sec",
        "ag_alinan": r"\Network Interface(*)\Bytes Received/sec",
        "ag_gonderilen": r"\Network Interface(*)\Bytes Sent/sec",
        "gpu": r"\GPU Engine(*)\Utilization Percentage",
        "gpu_bellek": VRAM_PATH,
        "surec_sayisi": r"\System\Processes",
    }
    PROCESSES = {
        "surec_cpu": r"\Process(*)\% Processor Time",
        "surec_bellek": r"\Process(*)\Working Set - Private",
    }

    def __init__(self, with_processes=True, process_every=2):
        self.query = PdhQuery()
        self.missing = [k for k, path in self.BASIC.items() if not self.query.add(k, path)]
        self.proc_query = None
        if with_processes:
            self.proc_query = PdhQuery()
            for key, path in self.PROCESSES.items():
                self.proc_query.add(key, path)
        self.process_every = max(1, process_every)
        self.cpu_count = os.cpu_count() or 1
        self._tick = 0
        self._top = []
        self.vram_luid, self.vram_total = main_adapter()
        self.query.collect()
        if self.proc_query:
            self.proc_query.collect()
        if self.missing:
            _log.info("Okunamayan canlı sayaçlar: %s", ", ".join(self.missing))

    def _gpu(self):
        engines = {}
        for name, value in self.query.array("gpu"):
            match = _GPU_ENGINE.search(name)
            if match:
                engines[match.groups()] = engines.get(match.groups(), 0.0) + value
        if not engines:
            return None
        return min(100.0, max(engines.values()))

    def _processes(self):
        cpu, mem = {}, {}
        for name, value in self.proc_query.array("surec_cpu"):
            base = _PROCESS_SUFFIX.sub("", name)
            if base.lower() not in _SKIP_PROCESSES:
                cpu[base] = cpu.get(base, 0.0) + value / self.cpu_count
        for name, value in self.proc_query.array("surec_bellek"):
            base = _PROCESS_SUFFIX.sub("", name)
            mem[base] = mem.get(base, 0.0) + value
        top = sorted(cpu, key=lambda n: (cpu[n], mem.get(n, 0)), reverse=True)[:6]
        return [{"ad": n, "cpu": round(min(cpu[n], 100.0), 1), "bellek_mb": round(mem.get(n, 0) / 2 ** 20)}
                for n in top]

    def sample(self):
        started = time.perf_counter()
        self.query.collect()
        q = self.query
        cpu = q.value("cpu")
        if cpu is None:
            cpu = q.value("cpu_eski")
        perf, base = q.value("cpu_performans"), q.value("cpu_frekans")
        idle = q.value("disk_bos")
        total, used = memory()
        gpu_items = q.array("gpu_bellek", PDH_FMT_DOUBLE)
        gpu_mem = [v for _, v in gpu_items]
        result = {
            "cpu": None if cpu is None else min(100.0, max(0.0, cpu)),
            "cpu_ghz": round(perf * base / 100 / 1000, 2) if perf and base else None,
            "ram_toplam": total, "ram_kullanilan": used,
            "gpu": self._gpu(),
            "gpu_bellek": max(gpu_mem) if gpu_mem else None,
            # Oyun kartının (kullanılan, toplam) belleği; eşleşmezse None (satır eski haline döner)
            "gpu_bellek_kart": (vram_used(gpu_items, self.vram_luid), self.vram_total) if self.vram_luid else None,
            "disk": None if idle is None else max(0.0, min(100.0, 100.0 - idle)),
            "disk_okuma": q.value("disk_okuma"), "disk_yazma": q.value("disk_yazma"),
            "ag_alinan": sum(v for _, v in q.array("ag_alinan", PDH_FMT_DOUBLE)),
            "ag_gonderilen": sum(v for _, v in q.array("ag_gonderilen", PDH_FMT_DOUBLE)),
            "surec_sayisi": q.value("surec_sayisi"),
        }
        if self.proc_query and self._tick % self.process_every == 0:
            self.proc_query.collect()
            self._top = self._processes()
        self._tick += 1
        result["en_cok"] = self._top
        result["olcum_ms"] = round((time.perf_counter() - started) * 1000, 1)
        return result

    def close(self):
        self.query.close()
        if self.proc_query:
            self.proc_query.close()
