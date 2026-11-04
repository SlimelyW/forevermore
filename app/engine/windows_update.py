"""Windows Update modları: Varsayılan / Güvenlik (ertelemeli) / 2100'e kadar duraklat.

- Güvenlik: Chris Titus Tech WinUtil "Security (Recommended) Settings" ile aynı ilke değerleri
  (functions/public/Invoke-WPFUpdatessecurity.ps1, github.com/ChrisTitusTech/winutil, MIT):
  özellik güncellemeleri 365 gün, kalite güncellemeleri 4 gün ertelenir; sürücüler Windows
  Update'ten gelmez; otomatik indirir, kurmadan önce bildirir. WinUtil'in servis değişiklikleri
  (BITS, wuauserv El ile; UsoSvc Otomatik) Windows varsayılanı olduğu için yazılmaz.
- 2100'e kadar duraklat: Ayarlar > Windows Update > "Güncellemeleri duraklat" düğmesinin yazdığı
  değerler (HKLM\\SOFTWARE\\Microsoft\\WindowsUpdate\\UX\\Settings), bitiş tarihi 2100. BELGELENMEMİŞ;
  topluluk kaynaklarına dayanır ve Windows sürümüyle değişebilir. WinUtil'in "Disable" modu
  (servisleri kapatma, güncelleme klasörünü silme) bilerek kullanılmaz: geri alınabilir değildir.
- Varsayılan: uygulamanın yaptığı değişiklik geri alınır (önceki değerler yedekten döner).
"""

import datetime

POLICY = r"SOFTWARE\Policies\Microsoft\Windows"
UX = r"SOFTWARE\Microsoft\WindowsUpdate\UX\Settings"
CHANGE_ID = "WU-MOD"
PAUSE_END = "2100-01-01T00:00:00Z"

SECURITY = (
    (POLICY + r"\Device Metadata", "PreventDeviceMetadataFromNetwork", 1),
    (POLICY + r"\DriverSearching", "DontPromptForWindowsUpdate", 1),
    (POLICY + r"\DriverSearching", "DontSearchWindowsUpdate", 1),
    (POLICY + r"\DriverSearching", "DriverUpdateWizardWuSearchEnabled", 0),
    (POLICY + r"\WindowsUpdate", "ExcludeWUDriversInQualityUpdate", 1),
    (POLICY + r"\WindowsUpdate", "DeferFeatureUpdates", 1),
    (POLICY + r"\WindowsUpdate", "DeferFeatureUpdatesPeriodInDays", 365),
    (POLICY + r"\WindowsUpdate", "DeferQualityUpdates", 1),
    (POLICY + r"\WindowsUpdate", "DeferQualityUpdatesPeriodInDays", 4),
    (POLICY + r"\WindowsUpdate\AU", "AUOptions", 3),
    (POLICY + r"\WindowsUpdate\AU", "AUPowerManagement", 0),
)
PAUSE_START_NAMES = ("PauseFeatureUpdatesStartTime", "PauseQualityUpdatesStartTime")
PAUSE_END_NAMES = ("PauseFeatureUpdatesEndTime", "PauseQualityUpdatesEndTime", "PauseUpdatesExpiryTime")
MODES = ("varsayilan", "guvenlik", "duraklat")


def _step(path, name, kind):
    return {"tur": "registry", "kok": "HKLM", "yol": path, "ad": name, "veri_turu": kind,
            "acik": None, "kapali": None, "yoksa": None}


def steps():
    """Modların dokunduğu tüm değerler (hepsi yedeklenir; geri almada önceki hâline döner)."""
    result = [_step(path, name, "REG_DWORD") for path, name, _value in SECURITY]
    result += [_step(UX, name, "REG_SZ") for name in PAUSE_START_NAMES + PAUSE_END_NAMES]
    return result


def values(mode, now=None):
    """steps() sırasıyla yazılacak değerler; None = bu değere dokunma."""
    if mode == "guvenlik":
        return [value for _path, _name, value in SECURITY] + [None] * (len(PAUSE_START_NAMES) + len(PAUSE_END_NAMES))
    if mode == "duraklat":
        start = (now or datetime.datetime.now(datetime.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return [None] * len(SECURITY) + [start] * len(PAUSE_START_NAMES) + [PAUSE_END] * len(PAUSE_END_NAMES)
    raise ValueError(mode)


def detect(system):
    """Şu anki mod: "duraklat", "guvenlik" veya "varsayilan" (tanınmayan karışık durumlar dahil)."""
    expiry = system.read_reg("HKLM", UX, "PauseUpdatesExpiryTime")
    if expiry and str(expiry[0]).startswith("2100"):
        return "duraklat"
    for path, name, value in SECURITY:
        found = system.read_reg("HKLM", path, name)
        if found is None or found[0] != value:
            return "varsayilan"
    return "guvenlik"
