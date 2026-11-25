"""Gerçek sistem, önizleme modu (yazma yok), ekran dışı: her sayfayı aç, her yönetici kartını yenile; ana iş parçacığı
150 ms'den uzun bloke olursa yığını örnekle.
Kullanım: python tools/donma_avi.py <proje klasörü>  (yazma yok; sahte yavaş sistemle: tools/donma_avi_sahte.py)"""
import collections, os, sys, tempfile, threading, time, traceback
from pathlib import Path
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="gbekci_"); os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["PCOPT_HAREKET"] = "azalt"
sys.path.insert(0, sys.argv[1]); os.chdir(sys.argv[1])
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget
from app.core import i18n, log
from app.ui import app as m
from app.ui.controller import MODE_PREVIEW, Controller
log.setup(); i18n.load("tr"); qt = m.create_app()
win = m.MainWindow(Controller(MODE_PREVIEW)); win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True); win.show()
main_id = threading.get_ident(); beat = [time.perf_counter()]; stalls = collections.Counter(); label = ["acilis"]
def dog():
    while True:
        time.sleep(0.03)
        if time.perf_counter() - beat[0] > 0.15:
            st = [f"{Path(f.filename).name}:{f.lineno} {f.name}" for f in traceback.extract_stack(sys._current_frames()[main_id])
                  if "pcoptimizer" in f.filename and "gercek_bekci" not in f.filename]
            stalls[(label[0], " <- ".join(reversed(st[-12:])))] += 1
threading.Thread(target=dog, daemon=True).start()
tick = QTimer(); tick.timeout.connect(lambda: beat.__setitem__(0, time.perf_counter())); tick.start(10)
def pump(sec):
    end = time.perf_counter() + sec
    while time.perf_counter() < end:
        qt.processEvents(); beat[0] = time.perf_counter(); time.sleep(0.01)
while win.scanning or not win.c.fresh:
    pump(0.2)
label[0] = "hazir"; pump(1)
for key in list(win.pages):
    label[0] = f"sayfa:{key}"; win.navigate(key); pump(0.8)
    for card in win.pages[key].findChildren(QWidget):
        if type(card).__module__.endswith("managers_ui") and hasattr(card, "refresh"):
            label[0] = f"yenile:{key}:{type(card).__name__}"
            try: card.refresh()
            except Exception as exc: print("hata", label[0], exc)
            pump(0.3)
print("ana iş parçacığı bloke (x30 ms), etiket, yığın:")
for (lab, st), n in stalls.most_common(25):
    print(f"{n*30:6d} ms  {lab}  {st}")
sys.stdout.flush(); os._exit(0)
