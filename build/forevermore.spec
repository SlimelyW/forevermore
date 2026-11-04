# -*- mode: python ; coding: utf-8 -*-
# PyInstaller tarifi. Doğrudan değil, tools\derle.ps1 (veya derle.bat) ile çalıştır.
#
# Varsayılan: KLASÖR -> dist\Forevermore\Forevermore.exe (+ yanında Qt kitaplıkları)
#   Qt (PySide6) LGPLv3 lisanslıdır; kitaplıkların ayrı dosyalar olarak dağıtılması
#   bu lisansın koşullarını karşılamanın en açık yoludur. Ayrıca daha hızlı açılır ve
#   antivirüslerde daha az yanlış alarm verir.
# PCOPT_ONEFILE=1 ise TEK DOSYA -> dist\Forevermore.exe (yalnızca kişisel deneme için;
#   satışta kullanma, bkz. THIRD-PARTY-NOTICES.txt)

import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
ONEFILE = os.environ.get("PCOPT_ONEFILE") == "1"

# data\ ve lang\ programın içine gömülür. Kullanıcı .exe'nin yanına bir data\
# klasörü koyarsa uygulama gömülü kopya yerine onu kullanır.
datas = [(os.path.join(ROOT, "data"), "data"), (os.path.join(ROOT, "lang"), "lang")]

a = Analysis(
    [os.path.join(ROOT, "baslat.py")],
    pathex=[ROOT],
    datas=datas,
    excludes=["tests", "tools", "PIL", "numpy", "tkinter", "customtkinter",
              "PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtWebEngineCore"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe_args = dict(
    name="Forevermore",
    console=False,          # siyah komut penceresi açılmaz
    upx=False,              # UPX sıkıştırma antivirüs yanlış alarmlarını artırır; kapalı
    version=os.path.join(SPECPATH, "surum_bilgisi.txt"),
    icon=os.path.join(SPECPATH, "forevermore.ico"),  # tools\logo_uret.py üretir
    uac_admin=False,        # yönetici izni uygulamanın içinden istenir; reddedilirse salt okunur açılır
)

if ONEFILE:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], **exe_args)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, **exe_args)
    coll = COLLECT(exe, a.binaries, a.datas, name="Forevermore", upx=False)
