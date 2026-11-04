"""Bu bilgisayardaki tüm switch ayarlarının durumunu SALT OKUNUR modda gösterir.

Değişiklik yapan her sistem çağrısı engellenir (ReadOnlySystem); engellenen
bir çağrı olursa sonunda listelenir. Yedek dosyası geçici bir klasöre yazılır.

Çalıştırma (proje klasöründe):
    py -3.12 -m tests.durum_okuma
"""

import sys
import tempfile
from pathlib import Path

from app.core.i18n import t
from app.engine import catalog
from app.engine.backup import BackupStore
from app.engine.compat import SystemProfile
from app.engine.engine import Engine
from app.engine.system import ReadOnlySystem, WindowsSystem


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    guarded = ReadOnlySystem(WindowsSystem())
    with tempfile.TemporaryDirectory() as tmp:
        profile = SystemProfile.detect()
        engine = Engine(system=guarded, store=BackupStore(Path(tmp)), profile=profile)
        print(f"Profil: Windows {profile.windows_version} build {profile.build}, {profile.form}, "
              f"GPU {profile.gpu_vendors}, aynı hesap: {profile.same_account}\n")
        for tweak in catalog.tweaks():
            if tweak["sinif"] != "SWITCH":
                continue
            avail = engine.availability(tweak)
            if not avail.visible:
                key, params = avail.reasons[0]
                print(f"{tweak['id']:<9} GİZLİ    {t(key, **params)}")
                continue
            state = engine.read_state(tweak)
            shown = state.values if state.status == "secim" else state.status
            warn = f"  [uyarı: {t(avail.warnings[0][0])}]" if avail.warnings else ""
            print(f"{tweak['id']:<9} {str(shown):<8} {tweak['ad'][:60]}{warn}")
            if tweak["islem"]["kontrol"] == "switch" and state.status != "acik":
                for line in engine.preview(tweak, True):
                    print(f"{'':19}→ {line}")
    print("\nEngellenen yazma girişimi:", guarded.blocked or "yok")


if __name__ == "__main__":
    main()
