"""Faz 0 başlangıç ölçümü: ekran dışı, önizleme modu (hiçbir ayar değişmez). Faz 4 aynısıyla karşılaştırır.
Kullanım: python tools/olcum_baslangic.py <proje klasörü>  ->  tek JSON satırı yazar."""
import ctypes, json, os, sys, tempfile, time
from ctypes import wintypes

T0 = time.perf_counter()
PROJECT = sys.argv[1]
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="pcopt_olcum_")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, PROJECT)
os.chdir(PROJECT)

from PySide6.QtCore import QTimer, Qt  # noqa: E402
from app.core import i18n, log  # noqa: E402
from app.ui import app as app_module  # noqa: E402
from app.ui.controller import MODE_PREVIEW, Controller  # noqa: E402


class PMC(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
        (n, ctypes.c_size_t) for n in ("Peak", "WorkingSetSize", "a", "b", "c", "d", "PagefileUsage", "PeakPagefile")]


k32 = ctypes.WinDLL("kernel32")
psapi = ctypes.WinDLL("psapi")
k32.GetCurrentProcess.restype = wintypes.HANDLE
me = wintypes.HANDLE(k32.GetCurrentProcess())


def mem_mb():
    p = PMC(); p.cb = ctypes.sizeof(p)
    psapi.GetProcessMemoryInfo(me, ctypes.byref(p), p.cb)
    return round(p.WorkingSetSize / 2**20, 1), round(p.PagefileUsage / 2**20, 1)


def cpu_s():
    c, e, k, u = (wintypes.FILETIME() for _ in range(4))
    k32.GetProcessTimes(me, ctypes.byref(c), ctypes.byref(e), ctypes.byref(k), ctypes.byref(u))
    v = lambda f: (f.dwHighDateTime << 32 | f.dwLowDateTime) / 1e7
    return v(k) + v(u)


log.setup()
i18n.load("tr")
qt = app_module.create_app()
t_import = time.perf_counter() - T0
win = app_module.MainWindow(Controller(MODE_PREVIEW))
win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
win.show()
qt.processEvents()
t_paint = time.perf_counter() - T0
out = {"ice_aktarma_s": round(t_import, 2), "ilk_cizim_s": round(t_paint, 2)}
PAGES = ["ozet", "SYS", "PERF", "GPU", "CPU", "oyunlar", "degisiklikler", "ayarlar", "bilgi"]


def ready():
    if win.scanning or not win.c.fresh:
        QTimer.singleShot(200, ready)
        return
    out["hazir_s"] = round(time.perf_counter() - T0, 2)
    out["hazir_bellek_mb"] = mem_mb()
    first, second = {}, {}
    for key in PAGES:
        t = time.perf_counter(); win.navigate(key); qt.processEvents(); first[key] = round((time.perf_counter() - t) * 1000)
    for key in PAGES:
        t = time.perf_counter(); win.navigate(key); qt.processEvents(); second[key] = round((time.perf_counter() - t) * 1000)
    out["sayfa_ilk_ms"], out["sayfa_tekrar_ms"] = first, second
    win.navigate("ozet")
    out["_cpu0"] = cpu_s()
    QTimer.singleShot(15000, idle)


def idle():
    out["bosta_cpu_yuzde_15s"] = round((cpu_s() - out.pop("_cpu0")) / 15 * 100 / os.cpu_count(), 2)
    out["bosta_bellek_mb"] = mem_mb()
    out["cekirdek"] = os.cpu_count()
    print(json.dumps(out, ensure_ascii=False))
    win.close(); qt.quit()


QTimer.singleShot(0, ready)
qt.exec()
