"""Temiz sürücü kurulumu araçları (GPU-019) ve Güvenli Mod.

DDU (Wagnardsoft) ve NVCleanstall (TechPowerUp) ücretsiz ama programa GÖMÜLMEZ: kullanıcı
resmi sayfalarından indirip tools klasörüne koyar. İkisinin de belgelenmiş, güvenilir bir
komut satırı kullanımı olmadığı için yalnızca arayüzleri açılır (docs/EKRAN_KARTI.md).

Güvenli Mod: `bcdedit /set {current} safeboot minimal` (motorun "bcdedit" yerleşik işlemiyle; yedeklenir,
"Eski haline getir" safeboot değerini siler). Uygulama açılışta güvenli önyükleme açık kalmışsa uyarır.
"""

import ctypes

from app.core import integrity, paths, powershell

SAFE_MODE_ID = "GUVENLI-MOD"
SAFE_MODE_STEP = {"tur": "yerlesik", "eylem": "bcdedit", "parametreler": {"eleman": "safeboot"}}
SAFE_MODE_VALUE = "minimal"
RESTART_SECONDS = 15

TOOLS = {
    # araç: (tools altındaki klasör, exe adı kalıbı, resmi indirme sayfası)
    "ddu": ("DDU", "Display Driver Uninstaller*.exe",
            "https://www.wagnardsoft.com/display-driver-uninstaller-DDU-"),
    "nvcleanstall": ("NVCleanstall", "NVCleanstall*.exe",
                     "https://www.techpowerup.com/download/techpowerup-nvcleanstall/"),
}

# Yalnızca tarayıcıda açılır; uygulama sürücü indirmez/kurmaz (Kubilay kararı, docs/SURUCU_INDIRME.md).
DRIVER_PAGES = {
    "NVIDIA": "https://www.nvidia.com/en-us/drivers/",
    "AMD": "https://www.amd.com/en/support/download/drivers.html",
}

# Fare/klavye üreticisinin resmi yazılım sayfası (yalnızca tarayıcıda açılır; elle doğrulandı 7 Kas 2026,
# docs/KLAVYE_FARE_MERKEZI.md). SteelSeries doğrulanamadı: eklenmedi. Anahtar = peripherals.USB_VENDORS adı.
INPUT_VENDOR_PAGES = {
    "Logitech": "https://www.logitechg.com/en-us/software/ghub",
    "Corsair": "https://www.corsair.com/ww/en/s/downloads",
    "Razer": "https://www.razer.com/synapse-4",
    "HyperX": "https://hyperx.com/pages/ngenuity",
}


def driver_pages(gpus):
    """Bu bilgisayardaki kartların resmi sürücü sayfaları: [(üretici, adres)]. Hibrit dizüstünde iki satır olabilir."""
    found = {gpu.get("uretici") for gpu in gpus}
    return [(vendor, url) for vendor, url in DRIVER_PAGES.items() if vendor in found]


def find(tool):
    """tools klasöründeki aracın yolu (yoksa None). Klasör adı büyük/küçük harf duyarsız."""
    folder, pattern, _url = TOOLS[tool]
    base = paths.tools_dir()
    if not base.is_dir():
        return None
    for sub in base.iterdir():
        if sub.is_dir() and sub.name.lower() == folder.lower():
            found = sorted(sub.glob(pattern))
            if found:
                return found[-1]  # birden çok sürüm varsa ada göre en yenisi
    return None


sha256_file = integrity.sha256_file


def tools_in_user_folder():
    """tools klasörü kullanıcı profilinin içindeyse (ör. İndirilenler) standart kullanıcı oraya exe koyabilir;
    uygulama yönetici çalıştığı için bu yetki yükseltme yoludur."""
    return paths.in_user_profile(paths.tools_dir())


def verify(path):
    """Çalıştırmadan önce dosyayı denetler: SHA-256 ve Authenticode imzası.

    Sürüm başına bilinen-iyi özet tutmuyoruz (araçlar sık güncellenir, listeyi biz doğrulayamayız);
    kullanıcı SHA-256'yı resmi sayfadaki/VirusTotal'daki ile karşılaştırabilir. İmza geçerli değilse uyarılır.
    Dönüş: {"sha256", "imza_gecerli", "imzalayan"}.
    """
    try:
        info = powershell.run_object(
            f"$s = Get-AuthenticodeSignature -LiteralPath {powershell.quote(path)}; "
            "[pscustomobject]@{durum = [string]$s.Status; imzalayan = [string]$s.SignerCertificate.Subject}")
    except (powershell.PowerShellError, ValueError):
        info = {}
    return {"sha256": sha256_file(path), "imza_gecerli": info.get("durum") == "Valid",
            "imzalayan": info.get("imzalayan") or ""}


def download_page(tool):
    return TOOLS[tool][2]


def in_safe_mode():
    """GetSystemMetrics(SM_CLEANBOOT): 0 normal, 1 güvenli mod, 2 ağ ile güvenli mod."""
    try:
        return ctypes.windll.user32.GetSystemMetrics(67) != 0
    except (AttributeError, OSError):
        return False
