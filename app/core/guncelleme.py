"""Uygulama güncellemesi (kullanıcı bir kez sorulduğunda "evet" derse günde bir denetim; "hayır" derse hiç bağlanmaz;
Ayarlar > Sistem'den değiştirilir, "Şimdi denetle" düğmesi her durumda çalışır).

Ağ: yalnızca GitHub'ın herkese açık sürüm listesine (api.github.com) ve sürüm dosyasına (github.com/<depo>/releases/download)
bağlanır. Hiçbir veri gönderilmez (GET; sürüm numarası bile yok). Kod ve paket güveni GİTHUB'a değil İMZAYA dayanır:

  1. en son sürüm etiketi çalışan sürümden büyük olmalı
  2. indirilen zip güvenli açılır (yol kaçışı, boyut ve dosya sayısı sınırı)
  3. açılan klasör yapımcının genel anahtarıyla doğrulanır (integrity.check_folder == "orijinal") ve imzalı sürüm
     çalışan sürümden büyük olmalı (sürüm düşürme / eski pakete döndürme engellenir)
  4. değişimi, uygulama kapanınca kendi yazdığımız sabit bir PowerShell betiği yapar; betiğe yollar ARGÜMAN olarak verilir
     (komut metnine gömülmez). Değişim yarıda kalırsa eski klasör geri konur.
"""

import datetime
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from app import __version__
from app.core import admin, integrity, log, paths, powershell

_log = log.get("guncelleme")

REPO = "SlimelyW/forevermore"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
DOWNLOAD_PREFIX = f"https://github.com/{REPO}/releases/download/"
ASSET = "Forevermore.zip"
TIMEOUT = 20
CHECK_INTERVAL = datetime.timedelta(hours=24)
MAX_API_BYTES = 1024 * 1024
MAX_ZIP_BYTES = 400 * 1024 * 1024
MAX_UNPACKED_BYTES = 1536 * 1024 * 1024
MAX_FILES = 20000
CREATE_NO_WINDOW = 0x08000000
NEW_PROCESS_GROUP = 0x00000200

# Sabit betik: yollar argüman olarak gelir. Eski klasör ".eski" adıyla yedeklenir; hata olursa geri konur.
SWAP_SCRIPT = r"""param([int]$ProcId, [string]$Install, [string]$Staging, [string]$Exe, [string]$Log = '')
$ErrorActionPreference = 'Stop'
try { Wait-Process -Id $ProcId -Timeout 60 -ErrorAction SilentlyContinue } catch {}
$old = $Install + '.eski'
$done = $false
try {
    if (Test-Path -LiteralPath $old) { Remove-Item -LiteralPath $old -Recurse -Force }
    Rename-Item -LiteralPath $Install -NewName (Split-Path $old -Leaf)
    Move-Item -LiteralPath $Staging -Destination $Install
    # Taşınan dosyalar %LOCALAPPDATA%'daki (kullanıcının yazabildiği) izinleri taşır; kurulum yerinin izinlerine döndür
    & icacls.exe $Install /reset /T /C /Q | Out-Null
    $tools = Join-Path $old 'tools'
    if (Test-Path -LiteralPath $tools) { Copy-Item -LiteralPath $tools -Destination (Join-Path $Install 'tools') -Recurse }
    $done = $true
} catch {
    # Sessiz geri dönüş olmasın: uygulama açılışta bir kez durum satırında söyler (onceki_degisim_hatasi)
    if ($Log) { try { ((Get-Date -Format s) + ' ' + $_) | Out-File -LiteralPath $Log -Encoding utf8 } catch {} }
    if (Test-Path -LiteralPath $old) {
        if (Test-Path -LiteralPath $Install) { Remove-Item -LiteralPath $Install -Recurse -Force -ErrorAction SilentlyContinue }
        Rename-Item -LiteralPath $old -NewName (Split-Path $Install -Leaf)
    }
}
Start-Process -FilePath (Join-Path $Install $Exe)
if ($done) { Remove-Item -LiteralPath $old -Recurse -Force -ErrorAction SilentlyContinue }
"""


class GuncellemeHatasi(Exception):
    """`kod`: kısa ayırt edici (lang anahtarı ui.guncelleme.hata.<kod>), args[0] ayrıntı."""

    def __init__(self, kod, mesaj=""):
        super().__init__(mesaj or kod)
        self.kod = kod


def _version(text):
    """"2.2.0" -> (2, 2, 0, 1, 0); "2.2.0-beta.1" -> (2, 2, 0, 0, 1): ön sürüm aynı numaralı kararlı sürümden küçüktür."""
    try:
        core, _, pre = str(text).strip().lstrip("vV").partition("-")
        numbers = tuple(int(part) for part in core.split("."))
        if not pre:
            return numbers + (1, 0)
        return numbers + (0, int(pre.rsplit(".", 1)[-1]) if "." in pre else 0)
    except ValueError:
        raise GuncellemeHatasi("surum", f"geçersiz sürüm: {text!r}")


def http_get(url, limit=MAX_API_BYTES):
    if not url.startswith("https://"):
        raise GuncellemeHatasi("adres", "yalnızca https")
    request = urllib.request.Request(url, headers={"User-Agent": "Forevermore", "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310 - https denetlendi
            data = response.read(limit + 1)
    except (urllib.error.URLError, OSError) as exc:
        raise GuncellemeHatasi("baglanti", str(exc)) from exc
    if len(data) > limit:
        raise GuncellemeHatasi("boyut", "yanıt çok büyük")
    return data


def denetim_vakti(denetle, son_deneme, simdi):
    """Açılıştaki otomatik denetim yapılmalı mı? Yalnızca açıkça True ise (None = hiç sorulmadı: bağlanma) ve son denemeden
    CHECK_INTERVAL geçtiyse. `son_deneme`: ISO metni; bozuksa/boşsa/gelecekteyse (saat geri alınmış) denetlenir."""
    if denetle is not True:
        return False
    try:
        last = datetime.datetime.fromisoformat(son_deneme or "")
    except ValueError:
        return True
    return not (last <= simdi and simdi - last < CHECK_INTERVAL)


def kontrol(get=http_get, current=__version__):
    """Daha yeni sürüm varsa {"surum", "url", "boyut"}, yoksa None."""
    try:
        data = json.loads(get(API_URL).decode("utf-8"))
        tag = data["tag_name"]
        assets = data.get("assets") or []
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise GuncellemeHatasi("yanit", "sürüm bilgisi okunamadı") from exc
    if _version(tag) <= _version(current):
        return None
    asset = next((a for a in assets if isinstance(a, dict) and a.get("name") == ASSET), None)
    url = (asset or {}).get("browser_download_url") or ""
    if not url.startswith(DOWNLOAD_PREFIX):
        raise GuncellemeHatasi("yanit", "sürüm dosyası bulunamadı")
    try:
        size = int(asset.get("size") or 0)
    except (TypeError, ValueError):
        size = 0
    return {"surum": str(tag).lstrip("vV"), "url": url, "boyut": size}


def indir(url, dest, get=http_get):
    if not url.startswith(DOWNLOAD_PREFIX):
        raise GuncellemeHatasi("adres", "beklenmeyen indirme adresi")
    Path(dest).write_bytes(get(url, MAX_ZIP_BYTES))


def _safe_extract(zip_path, staging):
    try:
        archive = zipfile.ZipFile(zip_path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise GuncellemeHatasi("paket", "zip açılamadı") from exc
    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_FILES or sum(i.file_size for i in infos) > MAX_UNPACKED_BYTES:
            raise GuncellemeHatasi("paket", "paket çok büyük")
        root = Path(staging).resolve()
        for info in infos:
            name = info.filename
            target = (root / name).resolve()
            if name.startswith(("/", "\\")) or ":" in name or ".." in Path(name).parts or root not in target.parents and target != root:
                raise GuncellemeHatasi("paket", f"güvenli olmayan yol: {name!r}")
        archive.extractall(root)


def hazirla(zip_path, staging, public_hex=None, current=__version__):
    """Zip'i açar ve imzasını doğrular; program klasörünün yolunu döndürür. Biri tutmazsa tümü reddedilir."""
    staging = Path(staging)
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    try:
        _safe_extract(zip_path, staging)
        candidates = [p.parent.parent for p in staging.rglob(f"{integrity.BUNDLE}/{integrity.MANIFEST}")]
        if len(candidates) != 1:
            raise GuncellemeHatasi("paket", "paket klasörü bulunamadı")
        folder = candidates[0]
        if not (folder / "Forevermore.exe").is_file():
            raise GuncellemeHatasi("paket", "Forevermore.exe yok")
        if any(p.name.lower() in integrity.USER_FOLDERS for p in folder.iterdir()):  # imza kapsamı dışı: gerçek pakette yok
            raise GuncellemeHatasi("paket", "pakette imzasız klasör var")
        result = integrity.check_folder(folder, public_hex)
        if result["durum"] != "orijinal":
            raise GuncellemeHatasi("imza", f"imza doğrulanamadı: {result['durum']}")
        if _version(result["surum"]) <= _version(current):
            raise GuncellemeHatasi("eski", f"paket sürümü {result['surum']} çalışan sürümden yeni değil")
        return folder
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def degisim_komutu(folder, pid, install_dir, script_path, log_path):
    """Betiği çalıştıracak komut satırı (liste; kabuk yok). Yollar ayrı argümanlardır."""
    # RemoteSigned yeter: betiği uygulama yerelde yazar (internetten gelmiş işareti yok). Pencereyi CREATE_NO_WINDOW gizler.
    return ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "RemoteSigned",
            "-File", str(script_path), "-ProcId", str(pid), "-Install", str(install_dir), "-Staging", str(folder),
            "-Exe", "Forevermore.exe", "-Log", str(log_path)]


def hata_dosyasi():
    """Değişim betiğinin hata kaydı. Güncelleme klasöründe: yöneticiyken korumalı (yönetici betik kullanıcının yazabildiği
    yere yazmasın; bağlantı hilesiyle başka dosyanın üzerine yazdırılamasın). Denetim A S3."""
    return paths.update_dir(admin.is_admin()) / "degisim_hatasi.txt"


def onceki_degisim_hatasi():
    """Son değişim başarısız olup eski sürüme dönüldüyse True; kayıt silinir (açılışta bir kez gösterilir)."""
    path = hata_dosyasi()
    try:
        detail = path.read_text(encoding="utf-8-sig", errors="replace")
        path.unlink()
    except OSError:
        return False
    _log.warning("Güncelleme değişimi başarısız, eski sürüme dönüldü: %s", detail.strip()[:2000])
    return True


def degisimi_baslat(folder):
    """Uygulama kapanınca klasörü değiştirecek betiği başlatır. Yalnızca paketlenmiş .exe'de çalışır."""
    if not getattr(sys, "frozen", False):
        raise GuncellemeHatasi("kaynak", "yalnızca paketlenmiş sürümde")
    if integrity.check_folder(folder)["durum"] != "orijinal":  # klasör doğrulamadan beri kullanıcının yazabildiği yerde durdu
        raise GuncellemeHatasi("imza", "paket doğrulamadan sonra değişti")
    install = Path(paths.app_dir())
    script = Path(folder).parent / "degistir.ps1"
    script.write_text(SWAP_SCRIPT, encoding="utf-8-sig")  # PowerShell 5.1 Türkçe yolları doğru okusun
    subprocess.Popen(degisim_komutu(folder, os.getpid(), install, script, hata_dosyasi()), close_fds=True,
                     env=powershell.clean_env(),
                     creationflags=CREATE_NO_WINDOW | NEW_PROCESS_GROUP)  # noqa: S603 - sabit betik, argümanlı
    _log.info("Güncelleme değişimi başlatıldı: %s", folder)


def staging_dir():
    return paths.update_dir(admin.is_admin()) / "yeni"


def indir_ve_hazirla(info, get=http_get):
    """Arka plan işi: indir -> doğrula. Hazır klasörü döndürür; hata GuncellemeHatasi."""
    work = staging_dir().parent
    work.mkdir(parents=True, exist_ok=True)
    zip_path = work / ASSET
    try:
        indir(info["url"], zip_path, get)
        return hazirla(zip_path, staging_dir())
    finally:
        zip_path.unlink(missing_ok=True)
