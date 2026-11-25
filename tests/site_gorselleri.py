"""Site için ekran görüntüleri (<sayfa>_<dil>.png), EKRANDA GÖSTERMEDEN çizilir.

    py -3.12 -m tests.site_gorselleri <dil> [<çıktı klasörü>]    (varsayılan: site/img)

Önizleme modunda çalışır (hiçbir ayar değişmez), önizleme şeridi gizlenmiş olarak. Kişisel veri sızmasın diye:
LOCALAPPDATA/APPDATA geçici klasöre yönlendirilir, "Örnek Oyun" ve Temizlik için SAHTE dosyalar orada üretilir
(bitince silinir); Özet'in bu bilgisayara özel bulgular bölümü kırpılır. Çıktıyı siteye koymadan önce elle incele.
"""

import glob
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
TEMP = Path(tempfile.mkdtemp(prefix="forevermore_site_"))
os.environ["LOCALAPPDATA"] = str(TEMP / "lad")
os.environ["APPDATA"] = str(TEMP / "roaming")
sys.path.insert(0, str(PROJECT))
os.chdir(PROJECT)

from PySide6.QtCore import QTimer, Qt  # noqa: E402
from PySide6.QtGui import QFontDatabase, QGuiApplication  # noqa: E402
from PySide6.QtWidgets import QFrame, QLabel  # noqa: E402

from app.core import i18n, log  # noqa: E402
from app.engine import cleaners  # noqa: E402
from app.ui import app as app_module, theme, widgets as w  # noqa: E402
from app.ui.controller import MODE_PREVIEW, Controller  # noqa: E402

LANG = sys.argv[1] if len(sys.argv) > 1 else "tr"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else PROJECT / "site" / "img"
PAGES = {"ozet": "ozet", "SYS": "ayarlar", "oyunlar": "oyunlar", "temizlik": "temizlik", "GPU": "ekran_karti"}
MB = 1024 * 1024


def fake_file(path, size, age_days=0):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.truncate(size)
    if age_days:
        old = time.time() - age_days * 86400
        os.utime(path, (old, old))


def seed():
    folder = TEMP / "Oyunlar" / "OrnekOyun"
    (folder / "Bin").mkdir(parents=True)
    (folder / "Bin" / "OrnekOyun.exe").write_bytes(b"")
    name = "Örnek Oyun" if LANG == "tr" else "Sample Game"
    game = {"id": "OYUN-ORNEK", "ad": name, "klasor": str(folder), "kaynak": "steam",
            "exe": str(folder / "Bin" / "OrnekOyun.exe"), "anti_cheat": [], "profil": {"cekirdek_secimi": "tum"}}
    data = TEMP / "lad" / "Forevermore"
    data.mkdir(parents=True)
    (data / "oyunlar.json").write_text(json.dumps({"oyunlar": [game]}, ensure_ascii=False), encoding="utf-8")
    lad, roaming = TEMP / "lad", TEMP / "roaming"  # Temizlik: sahte dosyalar
    fake_file(roaming / "discord" / "Cache" / "f_000001", 312 * MB)
    fake_file(roaming / "discord" / "GPUCache" / "data_0", 24 * MB)
    fake_file(lad / "Steam" / "htmlcache" / "Cache" / "data_1", 148 * MB)
    fake_file(lad / "Microsoft" / "Windows" / "Explorer" / "thumbcache_256.db", 38 * MB)
    fake_file(lad / "CrashDumps" / "ornek.exe.1234.dmp", 96 * MB)
    fake_file(lad / "Temp" / "kurulum.log", 3 * MB, 40)
    for n in range(6):
        fake_file(roaming / "Microsoft" / "Windows" / "Recent" / f"belge{n}.lnk", 2048)


seed()
cleaners._default_processes = lambda: []  # noqa: SLF001 (bu bilgisayarda açık Discord/Steam görünmesin)
log.setup()
i18n.load(LANG)
qt_app = app_module.create_app()


def load_system_fonts():
    """offscreen eklentisi Windows yazı tiplerini görmez (her harf kutucuk); uygulamanın yazı tiplerini dosyadan yükler."""
    if QGuiApplication.platformName() != "offscreen":
        return
    fonts = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    for pattern in ("segoeui*.ttf", "seguisym.ttf", "seguiemj.ttf", "SegUIVar.ttf", "SegoeIcons.ttf", "segmdl2.ttf",
                    "verdana*.ttf", "consola*.ttf", "arial.ttf", "arialbd.ttf", "ARIALUNI.ttf"):
        for f in glob.glob(os.path.join(fonts, pattern)):
            QFontDatabase.addApplicationFont(f)
    theme._icon_family = None  # noqa: SLF001
    app_module.apply_language(qt_app)
    app_module.apply_theme(qt_app)


load_system_fonts()
window = app_module.MainWindow(Controller(MODE_PREVIEW))
window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
window.show()


def settle(rounds=8):
    for _ in range(rounds):
        qt_app.processEvents()
        time.sleep(0.05)


def hide_preview_notes(page):
    """Önizleme şeridi ve sayfa içindeki "bu modda uygulanmaz" uyarıları yalnızca bu çizimde gizlenir."""
    w.clear_layout(window.banner_area)
    for frame in page.findChildren(QFrame):
        if frame.property("banner"):
            frame.hide()
    ortak = i18n.t("ui.oyun_bulundu").split("{adet}")[1].split("{kalan}")[0]  # gerçek tarama sayısı örnek oyunla çelişir
    for label in page.findChildren(QLabel):
        if ortak in label.text():
            label.hide()


def run():
    if window.scanning or not window.c.fresh:
        QTimer.singleShot(300, run)
        return
    window.navigate("ozet")
    settle(80)  # canlı izleme birkaç örnek toplasın
    OUT.mkdir(parents=True, exist_ok=True)
    for key, name in PAGES.items():
        window.navigate(key)
        settle(40 if key in ("temizlik", "oyunlar") else 8)  # taramalar bitsin
        hide_preview_notes(window.pages[key])
        settle()
        image = window.grab()
        if key == "ozet":  # bulgular bu bilgisayara özel (disk, program adları): sitede gösterilmez
            image = image.copy(0, 0, image.width(), 430)
        else:  # alttaki "tarama tamamlandı" satırı çıkar
            image = image.copy(0, 0, image.width(), image.height() - 36)
        image.save(str(OUT / f"{name}_{LANG}.png"))
    window.close()
    qt_app.quit()


QTimer.singleShot(100, run)
qt_app.exec()
shutil.rmtree(TEMP, ignore_errors=True)
print("çizildi:", ", ".join(f"{n}_{LANG}.png" for n in PAGES.values()), "->", OUT)
