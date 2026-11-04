"""Donma avı: her SWITCH ayarını gerçek arayüz yolundan aç/kapat; sahte sistem yavaş (yazma 3 sn, okuma 50 ms).
Ana iş parçacığı 250 ms'den uzun olay işlemezse yığını örnekler. Gerçek bilgisayara hiçbir şey yazılmaz.
Kullanım: YAZ=0.2 OKU=0.005 python tools/donma_avi_sahte.py <proje klasörü>"""
import collections, os, sys, tempfile, threading, time, traceback
from pathlib import Path
ROOT = sys.argv[1]
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="bekci_")
sys.path.insert(0, ROOT); os.chdir(ROOT)
from app.core import i18n
from app.engine.backup import BackupStore
from app.engine.engine import Engine
from tests.fake_system import FakeResolver, FakeSystem
from tests.test_motor import DESKTOP
from tests.test_arayuz import FakeSampler, MINIMAL_SCAN

WRITE = ("set_", "write_", "delete_", "export_", "create_", "run_", "apply", "enable", "disable")
WRITE_S, READ_S = float(os.environ.get("YAZ", "3")), float(os.environ.get("OKU", "0.05"))


class SlowSystem(FakeSystem):
    def __getattribute__(self, name):
        attr = super().__getattribute__(name)
        if callable(attr) and not name.startswith("_") and name not in ("state_copy",):
            def slow(*a, **k):
                time.sleep(WRITE_S if name.startswith(WRITE) else READ_S)
                return attr(*a, **k)
            return slow
        return attr


i18n.load("tr")
from app.ui import app as m, dialogs
qt = m.create_app()
dialogs.confirm_careful = lambda *a, **k: True
dialogs.confirm_risky = lambda *a, **k: True
dialogs.ask_restore_point = lambda *a, **k: ("olustur", False)
dialogs.ask_yes_no = lambda *a, **k: True
dialogs.show_message = lambda *a, **k: None
m.MainWindow._start_background = lambda self: None
m.MainWindow.start_scan = lambda self: None
m.MainWindow.live_sampler_factory = FakeSampler
from app.core import autostart
autostart.is_enabled = lambda: False
from app.games import discovery
discovery.discover = lambda errors=None: []
from app.ui.controller import Controller

tmp = tempfile.mkdtemp()
system = SlowSystem()
engine = Engine(system=system, store=BackupStore(Path(tmp)), profile=DESKTOP, resolver=FakeResolver(), is_admin=lambda: True)
c = Controller("normal", engine=engine, cache_file=Path(tmp) / "c.json")
c.scan = dict(MINIMAL_SCAN)
c.refresh_all()
win = m.MainWindow(c)
win.reload_pages()

main_id = threading.get_ident()
beat = [time.perf_counter()]
stalls = collections.Counter()
worst = {}
current = [None]


def watchdog():
    while True:
        time.sleep(0.05)
        gap = time.perf_counter() - beat[0]
        if gap > 0.25:
            frame = sys._current_frames().get(main_id)
            stack = [f"{Path(f.filename).name}:{f.lineno} {f.name}" for f in traceback.extract_stack(frame)
                     if "pcoptimizer" in f.filename and "bekci" not in f.filename][-6:]
            stalls[(current[0], " <- ".join(reversed(stack)))] += 1


threading.Thread(target=watchdog, daemon=True).start()


def pump_until(flag, limit=60):
    end = time.perf_counter() + limit
    longest = 0
    while not flag and time.perf_counter() < end:
        t0 = time.perf_counter()
        qt.processEvents()
        longest = max(longest, time.perf_counter() - t0)
        beat[0] = time.perf_counter()
        time.sleep(0.01)
    return longest


only = set(filter(None, os.environ.get("AYARLAR", "").split(",")))
targets = [tw for tw in c.tweaks if tw["sinif"] == "SWITCH" and c.availability.get(tw["id"]) and c.availability[tw["id"]].visible
           and (not only or tw["id"] in only)]
print("ayar sayısı:", len(targets), flush=True)
results = []
for tw in targets:
    cat = tw.get("kategori_id")
    if cat in win.pages:
        win.navigate(cat)
    for desired in (True, False):
        current[0] = f"{tw['id']}:{'ac' if desired else 'kapat'}"

        flag = []
        t0 = time.perf_counter()
        win.toggle(tw, desired, lambda: flag.append(1))
        beat[0] = time.perf_counter()
        longest = pump_until(flag)
        results.append((round(longest * 1000), current[0], round(time.perf_counter() - t0, 1)))
results.sort(reverse=True)
print("en uzun tek olay turu (ms), ayar, toplam sn:")
for row in results[:15]:
    print("  ", row)
print("donma örnekleri (ayar, ana iş parçacığı yığını) x 50ms:")
for (tid, stack), n in stalls.most_common(15):
    print(f"  {n:4d}  {tid}  {stack}")
win.worker.shutdown()
sys.stdout.flush(); os._exit(0)
