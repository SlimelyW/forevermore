"""Site için ekran görüntüleri (site/img/<sayfa>_<dil>.png), EKRANDA GÖSTERMEDEN çizilir.

    py -3.12 -m tests.site_gorselleri

Önizleme modunda çalışır (hiçbir ayar değişmez), ve
önizleme şeridi gizlenmiş olarak. Oyunlar ekranı için geçici bir klasörde "Örnek Oyun" oluşturulur.
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
TEMP = Path(tempfile.mkdtemp(prefix="forevermore_site_"))
os.environ["LOCALAPPDATA"] = str(TEMP / "lad")
sys.path.insert(0, str(PROJECT))
os.chdir(PROJECT)

from PySide6.QtCore import QTimer, Qt  # noqa: E402
from PySide6.QtWidgets import QFrame  # noqa: E402

from app.core import i18n, log  # noqa: E402
from app.ui import app as app_module, widgets as w  # noqa: E402
from app.ui.controller import MODE_PREVIEW, Controller  # noqa: E402

LANG = sys.argv[1] if len(sys.argv) > 1 else "tr"
OUT = PROJECT / "site" / "img"
PAGES = {"ozet": "ozet", "oyunlar": "oyunlar", "PLC": "placebo"}


def seed_game():
    folder = TEMP / "Oyunlar" / "OrnekOyun"
    (folder / "Bin").mkdir(parents=True)
    (folder / "Bin" / "OrnekOyun.exe").write_bytes(b"")
    name = "Örnek Oyun" if LANG == "tr" else "Sample Game"
    game = {"id": "OYUN-ORNEK", "ad": name, "klasor": str(folder), "kaynak": "steam",
            "exe": str(folder / "Bin" / "OrnekOyun.exe"), "anti_cheat": [], "profil": {"cekirdek_secimi": "tum"}}
    data = TEMP / "lad" / "Forevermore"
    data.mkdir(parents=True)
    (data / "oyunlar.json").write_text(json.dumps({"oyunlar": [game]}, ensure_ascii=False), encoding="utf-8")


seed_game()
log.setup()
i18n.load(LANG)
qt_app = app_module.create_app()
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


def run():
    if window.scanning or not window.c.fresh:
        QTimer.singleShot(300, run)
        return
    window.navigate("ozet")
    settle(80)  # canlı izleme birkaç örnek toplasın
    OUT.mkdir(parents=True, exist_ok=True)
    for key, name in PAGES.items():
        window.navigate(key)
        settle()
        hide_preview_notes(window.pages[key])
        settle()
        image = window.grab()
        if key == "ozet":  # bulgular bu bilgisayara özel (disk, program adları): sitede gösterilmez
            image = image.copy(0, 0, image.width(), 515)
        image.save(str(OUT / f"{name}_{LANG}.png"))
    window.close()
    qt_app.quit()


QTimer.singleShot(100, run)
qt_app.exec()
print("çizildi:", ", ".join(f"{n}_{LANG}.png" for n in PAGES.values()))
