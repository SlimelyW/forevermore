"""Uygulamanın kullandığı klasörler.

- Program klasörü: .exe'nin (veya geliştirirken proje klasörünün) bulunduğu yer.
  data/ ve lang/ burada durur; sen güncelleyebilirsin.
- Kullanıcı veri klasörü: %LOCALAPPDATA%\\Forevermore. Log, yedek ve raporlar
  buraya yazılır; .exe nerede olursa olsun yazma izni sorunu çıkmaz.

Uygulamanın eski adı "PC Optimizer" idi. Eski veri klasörü (%LOCALAPPDATA%\\PCOptimizer)
varsa ve yenisi henüz yoksa, ilk açılışta bir kez KOPYALANIR (taşınmaz, silinmez);
böylece eski yedekler ve "Eski haline getir" kayıtları çalışmaya devam eder.
"""

import os
import shutil
import sys
from pathlib import Path

APP_NAME = "Forevermore"
LEGACY_APP_NAME = "PCOptimizer"


def app_dir():
    if getattr(sys, "frozen", False):  # PyInstaller ile derlenmiş .exe
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def _resource_dir(name):
    """Veri klasörü. .exe'nin yanında bir `data`/`lang` klasörü varsa o kullanılır
    (güncelleme için yeni dosyaları oraya koymak yeterli); yoksa .exe'nin içine
    gömülü varsayılan kopya kullanılır."""
    beside = app_dir() / name
    if beside.is_dir() or not getattr(sys, "frozen", False):
        return beside
    return Path(getattr(sys, "_MEIPASS", app_dir())) / name


def data_dir():
    return _resource_dir("data")


def lang_dir():
    return _resource_dir("lang")


def tools_dir():
    """Kullanıcının koyduğu yardımcı araçlar (ör. nvidiaProfileInspector.exe): .exe'nin yanındaki tools klasörü."""
    return app_dir() / "tools"


def in_user_profile(path):
    """Yol kullanıcı profilinin (İndirilenler, Masaüstü...) içinde mi: oraya yönetici olmayan programlar da yazabilir.
    shortcut: ACL okunmuyor, profil altı = riskli sayılır; gerçek yazma izni gerekirse GetNamedSecurityInfo ile."""
    try:
        Path(path).resolve().relative_to(Path(os.path.expanduser("~")).resolve())
        return True
    except ValueError:
        return False


def _local_appdata():
    return Path(os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local"))


def user_data_path():
    """Kullanıcı veri klasörünün yolu; OLUŞTURMAZ (salt okuyan kod için)."""
    return _local_appdata() / APP_NAME


def user_data_dir():
    path = user_data_path()
    if not path.is_dir():
        _migrate_legacy(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def legacy_data_dir():
    return _local_appdata() / LEGACY_APP_NAME


def _migrate_legacy(target):
    """Eski adın veri klasörünü yeni klasöre bir kez kopyalar. Hata olursa eskisi olduğu gibi kalır."""
    legacy = legacy_data_dir()
    if not legacy.is_dir():
        return
    temp = target.with_name(target.name + ".tasiniyor")
    try:
        shutil.rmtree(temp, ignore_errors=True)
        shutil.copytree(legacy, temp, ignore=shutil.ignore_patterns("*.log", "*.log.*"))
        temp.rename(target)
        (target / "eski_klasorden_tasindi.txt").write_text(
            f"Bu klasör {legacy} klasöründen kopyalandı. Eski klasör silinmedi.\n", encoding="utf-8")
    except OSError:
        shutil.rmtree(temp, ignore_errors=True)


def atomic_write(path, data):
    """Geçici dosyaya yazıp diske zorlar, sonra yerine koyar: ani kapanmada eski ya da yeni hâl kalır, yarım dosya kalmaz."""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as handle:
        handle.write(data.encode("utf-8") if isinstance(data, str) else data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def _sub(name):
    path = user_data_dir() / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_dir():
    return _sub("logs")


def reports_dir():
    return _sub("reports")


def backups_dir():
    return _sub("backups")
