"""Depolama ve bakım: diskler (SSD/HDD, sağlık), doluluk, geçici dosyalar,
sanal bellek, Windows Update ve sorunlu sürücüler.

Gizlilik: disk seri numarası ve birim etiketleri (kullanıcının verdiği adlar)
okunmaz. Geçici dosya klasörlerinin yolu değil yalnızca boyutu raporlanır.
"""

import datetime
import os
import time

from app.core import powershell, registry

_STORAGE_PS = r"""
$pd = @(Get-PhysicalDisk | Select-Object DeviceId, FriendlyName, @{n='Media';e={[string]$_.MediaType}}, @{n='Bus';e={[string]$_.BusType}}, Size, @{n='Health';e={[string]$_.HealthStatus}})
$rel = @()
try {
  $rel = @(Get-PhysicalDisk | ForEach-Object {
    $r = $_ | Get-StorageReliabilityCounter -ErrorAction Stop
    [pscustomobject]@{ DeviceId=$_.DeviceId; Temp=$r.Temperature; Wear=$r.Wear; Hours=$r.PowerOnHours; ReadErr=$r.ReadErrorsUncorrected }
  })
} catch {}
$sys = $null
try { $sys = (Get-Partition -DriveLetter $env:SystemDrive.TrimEnd(':') -ErrorAction Stop | Get-Disk).Number } catch {}
$vol = @(Get-Volume | Where-Object { $_.DriveLetter -and [string]$_.DriveType -eq 'Fixed' } | Select-Object @{n='Harf';e={[string]$_.DriveLetter}}, @{n='FS';e={$_.FileSystem}}, Size, SizeRemaining)
$pf = @(Get-CimInstance Win32_PageFileUsage | Select-Object @{n='Surucu';e={$_.Name.Substring(0,2)}}, AllocatedBaseSize, CurrentUsage, PeakUsage)
$auto = (Get-CimInstance Win32_ComputerSystem).AutomaticManagedPagefile
$hf = $null
try { $hf = (Get-HotFix -ErrorAction Stop | Where-Object InstalledOn | Sort-Object InstalledOn -Descending | Select-Object -First 1).InstalledOn.ToString('yyyy-MM-dd') } catch {}
$bad = @(Get-CimInstance Win32_PnPEntity -Filter 'ConfigManagerErrorCode <> 0' | Where-Object { $_.ConfigManagerErrorCode -notin 22, 32, 45 } | Select-Object Name, PNPClass, ConfigManagerErrorCode)
[pscustomobject]@{pd=$pd; rel=$rel; sys=$sys; vol=$vol; pf=$pf; auto=$auto; hf=$hf; bad=$bad}
"""

# Aygıt Yöneticisi hata kodlarından şunlar arıza sayılmaz ve listelenmez:
# 22 = kullanıcı devre dışı bıraktı, 32 = sürücü servisi bilerek kapatıldı
# (ör. Hyper-V kapalıyken hipervizör cihazları), 45 = cihaz takılı değil.
TEMP_SCAN_LIMIT_SECONDS = 8
TEMP_SCAN_LIMIT_FILES = 200_000


def _folder_size(path, deadline):
    """Klasör boyutu (bayt) ve tamamlanıp tamamlanmadığı. Erişilemeyen dosyalar atlanır."""
    total, files, complete = 0, 0, True
    stack = [path]
    while stack:
        if time.monotonic() > deadline or files > TEMP_SCAN_LIMIT_FILES:
            complete = False
            break
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                            files += 1
                    except OSError:
                        continue
        except OSError:
            continue
    return total, complete


def _temp_files():
    deadline = time.monotonic() + TEMP_SCAN_LIMIT_SECONDS
    result = {}
    for label, path in (("kullanici_temp", os.environ.get("TEMP")),
                        ("windows_temp", os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Temp"))):
        if path and os.path.isdir(path):
            size, complete = _folder_size(path, deadline)
            result[label] = {"gb": round(size / 1024 ** 3, 2), "tam_sayildi": complete}
    return result


def _update_state():
    reboot = (registry.key_exists("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired")
              or registry.key_exists("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending"))
    pause = registry.read("HKLM", r"SOFTWARE\Microsoft\WindowsUpdate\UX\Settings", "PauseUpdatesExpiryTime")
    start = registry.read("HKLM", r"SYSTEM\CurrentControlSet\Services\wuauserv", "Start")
    return {
        "yeniden_baslatma_bekliyor": reboot,
        "duraklatildi_bitis": pause[:10] if isinstance(pause, str) and pause else None,
        "servis_devre_disi": start == 4,
    }


def collect_storage():
    data = powershell.run_object(_STORAGE_PS, timeout=90)
    reliability = {r.get("DeviceId"): r for r in powershell.as_list(data.get("rel"))}
    system_disk = data.get("sys")
    disks = []
    for d in powershell.as_list(data.get("pd")):
        rel = reliability.get(d.get("DeviceId"), {})
        disks.append({
            "ad": d.get("FriendlyName"),
            "tur": {"3": "HDD", "4": "SSD", "HDD": "HDD", "SSD": "SSD"}.get(str(d.get("Media")), "bilinmiyor"),
            "baglanti": d.get("Bus"),
            "boyut_gb": round((d.get("Size") or 0) / 1000 ** 3),
            "saglik": d.get("Health"),
            "sistem_diski": str(d.get("DeviceId")) == str(system_disk),
            "sicaklik_c": rel.get("Temp"),
            "asinma_yuzde": rel.get("Wear"),
            "calisma_saati": rel.get("Hours"),
            "duzeltilemeyen_okuma_hatasi": rel.get("ReadErr"),
        })
    volumes = []
    for v in powershell.as_list(data.get("vol")):
        size, free = v.get("Size") or 0, v.get("SizeRemaining") or 0
        if size:
            volumes.append({
                "surucu": f"{v.get('Harf')}:",
                "dosya_sistemi": v.get("FS"),
                "boyut_gb": round(size / 1024 ** 3, 1),
                "bos_gb": round(free / 1024 ** 3, 1),
                "doluluk_yuzde": round(100 - free * 100 / size),
            })
    pagefiles = [{"surucu": p.get("Surucu"), "ayrilan_mb": p.get("AllocatedBaseSize"),
                  "kullanilan_mb": p.get("CurrentUsage"), "en_yuksek_mb": p.get("PeakUsage")}
                 for p in powershell.as_list(data.get("pf"))]
    last_update = data.get("hf")
    days_since = None
    if last_update:
        days_since = (datetime.date.today() - datetime.date.fromisoformat(last_update)).days
    return {
        "diskler": disks,
        "birimler": volumes,
        "gecici_dosyalar": _temp_files(),
        "depolama_algisi_acik": registry.read(
            "HKCU", r"Software\Microsoft\Windows\CurrentVersion\StorageSense\Parameters\StoragePolicy", "01") == 1,
        "sanal_bellek": {"otomatik": data.get("auto"), "dosyalar": pagefiles},
        "windows_update": {"son_guncelleme": last_update, "gecen_gun": days_since, **_update_state()},
        "sorunlu_cihazlar": [{"ad": b.get("Name"), "sinif": b.get("PNPClass"), "hata_kodu": b.get("ConfigManagerErrorCode")}
                             for b in powershell.as_list(data.get("bad"))],
    }
