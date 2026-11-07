"""Uygulamanın kullandığı klasörler.

- Program klasörü: .exe'nin (veya geliştirirken proje klasörünün) bulunduğu yer.
  data/ ve lang/ burada durur; sen güncelleyebilirsin.
- Kullanıcı veri klasörü: %LOCALAPPDATA%\\Forevermore. Log ve raporlar
  buraya yazılır; .exe nerede olursa olsun yazma izni sorunu çıkmaz.
- Korumalı veri klasörü: %ProgramData%\\Forevermore\\<SID>. Yedek ve kaldırıcı verisi burada durur; yalnızca
  Yöneticiler/SYSTEM yazar, çünkü yönetici olarak geri yüklenirler. Hesap başına ayrıdır: HKCU yedeği başka hesaba
  dönmemeli, yedek anahtarı da (DPAPI) hesaba bağlıdır.

Uygulamanın eski adı "PC Optimizer" idi. Eski veri klasörü (%LOCALAPPDATA%\\PCOptimizer)
varsa ve yenisi henüz yoksa, ilk açılışta bir kez KOPYALANIR (taşınmaz, silinmez);
böylece eski yedekler ve "Eski haline getir" kayıtları çalışmaya devam eder.
"""

import os
import secrets
import shutil
import sys
from pathlib import Path

from app.core import dpapi, guvenli_klasor

APP_NAME = "Forevermore"
LEGACY_APP_NAME = "PCOptimizer"
PROTECTED_MARK = "tasindi.txt"
BACKUP_KEY = "yedek_anahtar.dat"
UNINSTALL_BACKUPS = "kaldirici_yedek"


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


def docs_dir():
    """Pakete gömülü docs klasörü (yalnızca sürüm notları: RELEASE_NOTLARI.md)."""
    return _resource_dir("docs")


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


def protected_root():
    return guvenli_klasor.common_appdata() / APP_NAME


def protected_path():
    """Bu hesabın korumalı klasörünün yolu; OLUŞTURMAZ."""
    return protected_root() / guvenli_klasor.current_sid()


def _protected(name):
    """Taşıma bittiyse korumalı klasör; bitmediyse eski yer (salt okunur mod ve taşınamama durumu)."""
    base = protected_path()
    return base / name if os.path.exists(base / PROTECTED_MARK) else _sub(name)


def backups_dir():
    return _protected("backups")


def uninstall_backups_dir():
    return _protected(UNINSTALL_BACKUPS)


def game_settings_dir():
    """Oyun ayar dosyalarının saklanan kopyaları (app/games/oyun_ayar.py)."""
    return _protected("oyun_ayarlari")


def _tree_sizes(root):
    return {path.relative_to(root): path.stat().st_size for path in root.rglob("*") if path.is_file()}


def _copy_backups(source, target):
    if target.is_dir():   # önceki denemede bitti
        return
    temp = target.with_name(target.name + ".tasiniyor")
    shutil.rmtree(temp, ignore_errors=True)
    if source.is_dir():
        shutil.copytree(source, temp)
        if _tree_sizes(source) != _tree_sizes(temp):
            raise OSError("Yedek kopyası eksik")
    else:
        temp.mkdir()
    key = temp / BACKUP_KEY
    if (temp / "yedekler.json").exists() and not key.exists():
        # Anahtar varken imzasız dosya kabul edilmez: kaynak kullanıcı klasörüydü, kullanıcı onayıyla kurtarılır (BackupStore)
        atomic_write(key, dpapi.protect(secrets.token_bytes(32)))
    os.replace(temp, target)


def _move_sessions(source, target):
    target.mkdir(exist_ok=True)
    if not source.is_dir():
        return
    for session in source.iterdir():
        if guvenli_klasor.is_link(session):   # kaynak kullanıcı klasörüydü: bağlantı korumalı klasöre alınmaz
            continue
        temp = target / (session.name + ".tasiniyor")
        shutil.rmtree(temp, ignore_errors=True)
        shutil.move(str(session), str(temp))   # kaldırıcı yedeği GB'larca olabilir: kopyalanmaz, oturum oturum taşınır
        if not guvenli_klasor.reset_acl(temp):
            from app.core import log  # log, paths'e bağlı: döngüyü önler
            log.get("paths").warning("Kaldırıcı yedeğinin izinleri tam sıfırlanamadı: %s", session.name)
        os.replace(temp, target / session.name)


def migrate_to_protected():
    """Korumalı klasörü doğrular; eski yedekleri bir kez oraya geçirir. Yalnızca yönetici sürecinden çağrılır.
    True: bu çağrıda taşındı. OSError: bitmedi, eski veri okunabilir kalır ve sonraki açılışta yeniden denenir.
    İşaret dosyası yazıldıktan sonra kullanıcı klasörü bir daha okunmaz (saldırgan oraya yeni dosya koysa da)."""
    guvenli_klasor.ensure(protected_root(), guvenli_klasor.sddl("BU"))
    sid = guvenli_klasor.current_sid()
    base = guvenli_klasor.ensure(protected_root() / sid, guvenli_klasor.sddl(sid))
    if os.path.exists(base / PROTECTED_MARK):
        return False
    old = user_data_dir()
    _copy_backups(old / "backups", base / "backups")
    _move_sessions(old / UNINSTALL_BACKUPS, base / UNINSTALL_BACKUPS)
    atomic_write(base / PROTECTED_MARK, "Yedekler bu klasöre taşındı; eski klasör backups.tasindi adıyla durur.\n")
    try:
        os.replace(old / "backups", old / "backups.tasindi")  # silinmez: elle kurtarma için durur
    except OSError:
        pass
    return True
