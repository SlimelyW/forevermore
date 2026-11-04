"""Arayüzün görüntüsünü EKRANDA GÖSTERMEDEN dosyaya çizer.

Pencere `WA_DontShowOnScreen` ile kurulur: ekranda hiçbir şey belirmez, odak
alınmaz, ekran görüntüsü alınmaz; yalnızca uygulamanın kendi penceresi PNG
dosyalarına çizilir. Önizleme modunda çalışır (hiçbir ayar değişmez).

Çalıştırma (proje klasöründe, PySide6 kurulu olmalı):
    py -3.12 -m tests.arayuz_goruntu [cikti_klasoru]

Dil: PCOPT_DIL ortam değişkeni (ör. "en"); verilmezse Türkçe.
Seçici çizim: PCOPT_SAYFALAR="SYS,ozet,pencereler" yalnızca bu sayfaları (ve "pencereler" verilirse
onay pencerelerini) çizer; PCOPT_OLCEK=0.6 görüntüleri küçültür (okuması daha az yer kaplar).
"""

import os
import sys
import tempfile
import time

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["LOCALAPPDATA"] = os.environ.get("PCOPT_TEST_LOCALAPPDATA") or tempfile.mkdtemp(prefix="pcopt_test_")
sys.path.insert(0, PROJECT)
os.chdir(PROJECT)

from PySide6.QtCore import QTimer, Qt  # noqa: E402

from app.core import i18n, log  # noqa: E402
from app.ui import app as app_module, dialogs  # noqa: E402
from app.ui.controller import MODE_PREVIEW, Controller  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="pcopt_shots_")
os.makedirs(OUT, exist_ok=True)
log.setup()
i18n.load(os.environ.get("PCOPT_DIL") or "tr")
qt_app = app_module.create_app()
start = time.perf_counter()
window = app_module.MainWindow(Controller(MODE_PREVIEW))
window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
if os.environ.get("PCOPT_PENCERE"):  # ör. 900x560: en küçük pencerede yerleşim kontrolü
    window.resize(*(int(v) for v in os.environ["PCOPT_PENCERE"].split("x")))
window.show()  # WA_DontShowOnScreen: ekranda görünmez
qt_app.processEvents()
first_paint = time.perf_counter() - start
timings = {}


WANTED = {k.strip() for k in os.environ.get("PCOPT_SAYFALAR", "").split(",") if k.strip()}
SCALE = float(os.environ.get("PCOPT_OLCEK") or 1)
FULL = os.environ.get("PCOPT_TAM") == "1"  # sayfanın kaydırılan kısmı da: içerik ayrı görüntü (<ad>_tam.png)


def shot(name, widget=None):
    for _ in range(3):  # sarılan metinlerin yüksekliği birkaç olay turunda oturur
        qt_app.processEvents()
        time.sleep(0.05)
    image = (widget or window).grab()
    if SCALE != 1:
        image = image.scaledToWidth(int(image.width() * SCALE), Qt.TransformationMode.SmoothTransformation)
    image.save(os.path.join(OUT, f"{name}.png"))


def run():
    if window.scanning or not window.c.fresh:
        QTimer.singleShot(300, run)
        return
    timings["hazir"] = round(time.perf_counter() - start, 2)
    window.navigate("ozet")
    QTimer.singleShot(4000, pages)  # canlı izleme birkaç örnek toplasın


def pages():
    sample = window.pages["ozet"].last_sample or {}
    timings["canli_olcum_ms"] = sample.get("olcum_ms")
    for key in ["ozet", "pc_detay", "profiller", "oyunlar", "DISP", "SYS", "baslangic", "PERF", "GPU", "CPU", "PWR", "NET", "INP", "AUD",
                "QOL", "PLC", "elle", "degisiklikler", "rapor", "olcum", "boost", "kaldirici", "ayarlar", "lisans", "bilgi"]:
        if WANTED and key not in WANTED:
            continue
        t0 = time.perf_counter()
        window.navigate(key)
        qt_app.processEvents()
        timings[key] = round((time.perf_counter() - t0) * 1000)
        shot(key)
        body = getattr(window.pages.get(key), "body_widget", None)
        if FULL and body is not None:
            shot(f"{key}_tam", body)
    if WANTED and "pencereler" not in WANTED:
        window.close()
        qt_app.quit()
        return
    by_id, avail = window.c.by_id, window.c.availability
    from app.core import consent
    for name, dialog in [
            ("bilgi_penceresi", dialogs.InfoDialog(window, by_id["SYS-001"], avail.get("SYS-001"))),
            ("dikkatli_onay", dialogs.ConfirmCarefulDialog(window, by_id["SYS-001"], avail.get("SYS-001"))),
            ("riskli_1_ac", dialogs.RiskStepOneDialog(window, by_id["PERF-003"], avail.get("PERF-003"), True)),
            ("riskli_1_kapat", dialogs.RiskStepOneDialog(window, by_id["PERF-003"], avail.get("PERF-003"), False)),
            ("riskli_2", dialogs.RiskStepTwoDialog(window, by_id["PERF-003"], True)),
            ("kismen", dialogs.PartialStateDialog(window, by_id["NET-009"])),
            ("baslangic_onayi", dialogs.ConsentDialog(consent.text())),
            ("dil_secimi", dialogs.LanguageDialog(i18n.available(), i18n.current()))]:
        dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        dialog.show()
        shot(name, dialog)
        dialog.close()
    window.close()
    qt_app.quit()


QTimer.singleShot(100, run)
qt_app.exec()
print(f"ilk çizim: {first_paint:.2f}s, tüm durumlar ve tarama hazır: {timings.pop('hazir')}s")
print("sayfa geçişi (ms):", timings)
print("görüntüler:", OUT)
print("engellenen yazma:", window.c.engine.system.blocked)
