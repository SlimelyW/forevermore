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

import glob
import os
import sys
import tempfile
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # boruya yönlenince cp1252 hatası vermesin
PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["LOCALAPPDATA"] = os.environ.get("PCOPT_TEST_LOCALAPPDATA") or tempfile.mkdtemp(prefix="pcopt_test_")
sys.path.insert(0, PROJECT)
os.chdir(PROJECT)

if os.environ.get("PCOPT_ORNEK_OYUN") == "1":  # Oyunlar sayfası dolu hâliyle çizilsin: geçici klasörde tek örnek oyun
    import json
    _folder = os.path.join(os.environ["LOCALAPPDATA"], "OrnekOyun")
    os.makedirs(os.path.join(_folder, "Bin"), exist_ok=True)
    _exe = os.path.join(_folder, "Bin", "OrnekOyun.exe")
    if os.environ.get("PCOPT_ORNEK_EXE"):  # gerçek bir exe verilirse Windows'un büyük simgesi kapağa çizilir
        _exe = os.environ["PCOPT_ORNEK_EXE"]
    else:
        open(_exe, "wb").close()
    os.makedirs(os.path.join(os.environ["LOCALAPPDATA"], "Forevermore"), exist_ok=True)
    with open(os.path.join(os.environ["LOCALAPPDATA"], "Forevermore", "oyunlar.json"), "w", encoding="utf-8") as _f:
        json.dump({"oyunlar": [{"id": "OYUN-ORNEK", "ad": "Örnek Oyun", "klasor": _folder, "kaynak": "steam", "exe": _exe,
                                "anti_cheat": [], "profil": {}}]}, _f, ensure_ascii=False)

if os.environ.get("PCOPT_KAPAKLI_OYUNLAR") == "1":  # Oyunlar sayfası: gömülü kapağı olan 15 Steam dışı oyun (kapak çizim süresi ölçümü)
    import json
    _list = []
    for _entry in json.load(open(os.path.join(PROJECT, "data", "oyun_kapaklari.json"), encoding="utf-8"))["kapaklar"]:
        _folder = os.path.join(os.environ["LOCALAPPDATA"], "Kapakli", _entry["ad"].replace(":", ""))
        os.makedirs(_folder, exist_ok=True)
        _exe = os.path.join(_folder, _entry["exe"][0].replace("*", "x"))
        open(_exe, "wb").close()
        _list.append({"id": "OYUN-%010x" % abs(hash(_entry["ad"]) % 16 ** 10), "ad": _entry["ad"], "klasor": _folder, "kaynak": "Epic",
                      "exe": _exe, "anti_cheat": [], "profil": {}})
    os.makedirs(os.path.join(os.environ["LOCALAPPDATA"], "Forevermore"), exist_ok=True)
    with open(os.path.join(os.environ["LOCALAPPDATA"], "Forevermore", "oyunlar.json"), "w", encoding="utf-8") as _f:
        json.dump({"oyunlar": _list}, _f, ensure_ascii=False)

from PySide6.QtCore import QTimer, Qt  # noqa: E402
from PySide6.QtGui import QFontDatabase, QGuiApplication  # noqa: E402

from app.core import i18n, log  # noqa: E402
from app.ui import app as app_module, dialogs, theme  # noqa: E402
from app.ui.controller import MODE_PREVIEW, Controller  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="pcopt_shots_")
os.makedirs(OUT, exist_ok=True)
log.setup()
i18n.load(os.environ.get("PCOPT_DIL") or "tr")
qt_app = app_module.create_app()


def load_system_fonts():
    """QT_QPA_PLATFORM=offscreen eklentisi Windows yazı tiplerini görmez (her harf kutucuk çıkar). Yalnızca o durumda
    uygulamanın kullandığı sistem yazı tiplerini dosyadan yükler ve temayı yeniden uygular. Normal platformda dokunmaz."""
    if QGuiApplication.platformName() != "offscreen":
        return 0
    fonts = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    names = ("segoeui*.ttf", "seguisym.ttf", "seguiemj.ttf", "SegUIVar.ttf", "SegoeIcons.ttf", "segmdl2.ttf", "verdana*.ttf",
             "consola*.ttf", "arial.ttf", "arialbd.ttf", "ARIALUNI.ttf", "malgun*.ttf", "msyh*.ttc", "YuGoth*.ttc")
    loaded = sum(1 for pattern in names for f in glob.glob(os.path.join(fonts, pattern))
                 if QFontDatabase.addApplicationFont(f) >= 0)
    theme._icon_family = None  # simge yazı tipi de yeniden aranır
    app_module.apply_language(qt_app)  # uygulama yazı tipi
    app_module.apply_theme(qt_app)
    return loaded


print(f"yüklenen yazı tipi dosyası: {load_system_fonts()}")
start = time.perf_counter()
window = app_module.MainWindow(Controller(MODE_PREVIEW))
window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
if os.environ.get("PCOPT_PENCERE"):  # ör. 900x560: en küçük pencerede yerleşim kontrolü (900'den darı: dar kip denemesi)
    window.setMinimumSize(0, 0)
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
                "QOL", "EXP", "SND", "PLC", "elle", "rehber", "degisiklikler", "rapor", "olcum", "boost", "kaldirici", "temizlik", "ayarlar", "lisans", "bilgi"]:
        if WANTED and key not in WANTED:
            continue
        t0 = time.perf_counter()
        window.navigate(key)
        qt_app.processEvents()
        timings[key] = round((time.perf_counter() - t0) * 1000)
        shot(key)
        if key == "oyunlar" and os.environ.get("PCOPT_OYUN_ACIK"):  # N. oyunun alt sayfası (oyun_alt) ve Gelişmiş açık hâli
            page = window.pages["oyunlar"]
            page.editing, page.opened, page.draft = page.store.games[int(os.environ["PCOPT_OYUN_ACIK"])]["id"], True, None
            page.data_reloaded()
            qt_app.processEvents()
            shot("oyun_alt")
            page.advanced_open = True
            page.data_reloaded()
            qt_app.processEvents()
            shot("oyun_alt_gelismis", page.body_widget)
            page.handle_escape()
            qt_app.processEvents()
        body = getattr(window.pages.get(key), "body_widget", None)
        if FULL and body is not None:
            shot(f"{key}_tam", body)
    if os.environ.get("PCOPT_PANEL"):  # yalnızca "araclar" (kategoriler artık şeritte: kategori sayfası görüntüsünde görünür); panel açıkken ayrı görüntü (ad: panel_<ad>)
        for group in os.environ["PCOPT_PANEL"].split(","):
            window._open_panel(group)
            shot(f"panel_{group}")
            window._close_panel(refocus=False)
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
