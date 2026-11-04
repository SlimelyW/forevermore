"""Sistem Koruması (Sistem Geri Yükleme): durum okuma ve kullanıcı onayıyla sistem sürücüsünde açma.

Durum tek PowerShell çağrısıyla (salt okunur):
- Grup ilkesi: HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows NT\\SystemRestore `DisableSR` / `DisableConfig`
  (SystemRestore.admx'teki adlar). Biri 1 ise koruma ZORLA AÇILMAZ; sebebi kullanıcıya anlatılır.
- Sürücüde açık mı: SPP\\Clients altındaki `{09F7EDC5-...}` listesinde sistem biriminin GUID'i var mı (yönetici
  gerekir; okunamazsa None = bilinmiyor).
- VSS ve swprv hizmetleri, Windows'un nokta sıklığı sınırı (`SystemRestorePointCreationFrequency`, yoksa 1440 dk),
  disk boyutu / boş alan, gölge depolama sınırı (Win32_ShadowStorage.MaxSpace).

Açma sırası: (devre dışıysa VSS/swprv -> El ile, Windows varsayılanı) -> Enable-ComputerRestore -> vssadmin ile
gölge depolama sınırı -> durum yeniden okunur -> ilk geri yükleme noktası (restore_point.ensure, liste
karşılaştırmasıyla doğrulanır). Windows sıklık sınırı noktayı sessizce atlayabilir: bu durum ayrıca bildirilir.
"""

from app.core import log, powershell
from app.engine import restore_point

_log = log.get("sistem_koruma")

GB = 1024 ** 3
DEFAULT_FREQUENCY_MIN = 1440      # anahtar yoksa Windows 24 saatte bir nokta oluşturur
MIN_LIMIT_GB = 2                  # bundan az yer ayrılabiliyorsa açılmaz (birkaç nokta bile sığmaz)
MAX_LIMIT_GB = 15
SERVICES = ("VSS", "swprv")

_STATUS_PS = r"""
$d = $env:SystemDrive
$pol = Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows NT\SystemRestore' -ErrorAction SilentlyContinue
$sr = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\SystemRestore' -ErrorAction SilentlyContinue
$vol = Get-CimInstance Win32_Volume -Filter "DriveLetter='$d'" -ErrorAction SilentlyContinue
$disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$d'" -ErrorAction SilentlyContinue
$key = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\SPP\Clients'
$on = $null
if (-not (Test-Path $key)) { $on = $false }
else {
  try {
    $c = (Get-ItemProperty $key -ErrorAction Stop).'{09F7EDC5-294E-4180-AF6A-FB0E6A0E9513}'
    if ($vol) { $on = [bool](@($c | Where-Object { $_ -like ($vol.DeviceID + '*') }).Count) }
  } catch { $on = $null }
}
$max = $null
if ($vol) {
  $ss = Get-CimInstance Win32_ShadowStorage -ErrorAction SilentlyContinue | Where-Object { $_.Volume.DeviceID -eq $vol.DeviceID } | Select-Object -First 1
  if ($ss) { $max = [double]$ss.MaxSpace }
}
$sv = foreach ($s in @('VSS','swprv')) {
  $x = Get-Service -Name $s -ErrorAction SilentlyContinue
  [pscustomobject]@{ad=$s; durum=$(if ($x) { [string]$x.Status } else { 'yok' }); baslangic=$(if ($x) { [string]$x.StartType } else { $null })}
}
[pscustomobject]@{
  surucu=$d
  ilke_kapali=[bool]($pol -and $pol.DisableSR -eq 1)
  ilke_ayar_kapali=[bool]($pol -and $pol.DisableConfig -eq 1)
  acik=$on
  siklik_dk=$(if ($sr -and $null -ne $sr.SystemRestorePointCreationFrequency) { [int]$sr.SystemRestorePointCreationFrequency } else { $null })
  boyut=$(if ($disk) { [double]$disk.Size } else { $null })
  bos=$(if ($disk) { [double]$disk.FreeSpace } else { $null })
  golge_sinir=$max
  servisler=@($sv)
}
"""


def status(run=powershell.run_object):
    data = run(_STATUS_PS, 60)
    data["servisler"] = powershell.as_list(data.get("servisler"))
    if data.get("siklik_dk") is None:
        data["siklik_dk"] = DEFAULT_FREQUENCY_MIN
    return data


def limit_gb(size, free):
    """Gölge depolama sınırı: diskin %5'i, boş alanın en fazla %20'si, 15 GB tavan. Yer yetmiyorsa None."""
    if not size or free is None:
        return None
    gb = int(min(size * 0.05, free * 0.20, MAX_LIMIT_GB * GB) // GB)
    return gb if gb >= MIN_LIMIT_GB else None


def blocker(data):
    """Açmayı engelleyen durum (metin anahtarı) ya da None. Grup ilkesi zorla aşılmaz."""
    if data.get("ilke_kapali"):
        return "ilke"
    if data.get("ilke_ayar_kapali"):
        return "ilke_ayar"
    if any(s["durum"] == "yok" for s in data["servisler"]):
        return "servis_yok"
    if limit_gb(data.get("boyut"), data.get("bos")) is None:
        return "disk"
    return None


def disabled_services(data):
    return [s["ad"] for s in data["servisler"] if s.get("baslangic") == "Disabled"]


def enable(system, data, run=powershell.run, read=status, ensure=restore_point.ensure):
    """Sistem korumasını açar ve ilk noktayı oluşturur. Dönen: {basarili, adimlar: [(anahtar, tamam, ayrıntı)],
    nokta: RestorePointResult | None, sinir_gb, neden}. `basarili` = koruma geri okumada açık görünüyor."""
    steps = []
    drive = data["surucu"]
    gb = limit_gb(data.get("boyut"), data.get("bos"))
    for name in disabled_services(data):
        try:
            run(f"Set-Service -Name {name} -StartupType Manual -ErrorAction Stop", 30)
            steps.append(("servis", True, name))
        except powershell.PowerShellError as exc:
            steps.append(("servis", False, f"{name}: {exc}"))
    try:
        run(f"Enable-ComputerRestore -Drive {powershell.quote(drive + chr(92))} -ErrorAction Stop", 120)
        steps.append(("ac", True, drive))
    except powershell.PowerShellError as exc:
        steps.append(("ac", False, str(exc)))
        _log.error("Sistem koruması açılamadı: %s", exc)
        return {"basarili": False, "adimlar": steps, "nokta": None, "sinir_gb": gb, "neden": "ac"}
    try:
        # vssadmin çıktısı dile göre değişir: başarı çıkış koduyla anlaşılır, değer aşağıda WMI'dan geri okunur
        run(f"vssadmin resize shadowstorage /for={drive} /on={drive} /maxsize={gb}GB | Out-Null; "
            "if ($LASTEXITCODE) { throw \"vssadmin $LASTEXITCODE\" }", 60)
    except powershell.PowerShellError as exc:
        steps.append(("sinir", False, str(exc)))
    after = read()
    if after.get("acik") is not True:
        _log.error("Sistem koruması açıldı denildi ama geri okumada açık değil: %s", after.get("acik"))
        return {"basarili": False, "adimlar": steps, "nokta": None, "sinir_gb": gb, "neden": "dogrulanamadi"}
    limit = after.get("golge_sinir")
    if not any(k == "sinir" for k, _ok, _d in steps):
        ok = bool(limit) and abs(limit - gb * GB) < GB
        steps.append(("sinir", ok, f"{(limit or 0) / GB:.1f} GB"))
    point = ensure(system)
    _log.info("Sistem koruması açıldı (%s, sınır %s GB), ilk nokta: %s", drive, gb, point)
    return {"basarili": True, "adimlar": steps, "nokta": point, "sinir_gb": gb,
            "neden": None if point.ok else ("siklik" if after.get("siklik_dk") else "nokta")}
