"""Microsoft Store ve debloat ile kaldırılmış Windows uygulamalarını geri yükleme.

Durum tek PowerShell çağrısıyla okunur (salt okunur): her paket bu kullanıcıda kurulu mu, sistemde dosyası
(AppxManifest.xml) duruyor mu, hazır (provisioned) paket var mı; ayrıca Windows Update, AppX Deployment
(AppXSvc), ClipSVC ve Store yükleme hizmetinin durumu, son 24 saatteki AppX dağıtım hataları ve son 7 günde
AppXSvc'nin başlatılamadığı / beklenmedik durduğu Hizmet Denetimi Yöneticisi kayıtları.

Geri yükleme sırası:
1. Store ve Windows 11 (derleme >= 22000): `wsreset -i` (Store'u arka planda indirip kurar; internet gerekir).
2. Dosyalar duruyorsa: `Add-AppxPackage -DisableDevelopmentMode -Register <AppxManifest.xml>`.
3. Sonuç her zaman yeniden okunarak doğrulanır; kurulu görünmüyorsa "başarılı" denmez, sebep yazılır.

Paket dosyaları silinmişse bu yöntemler çalışmaz; kullanıcıya onarım yolları gösterilir (sahte başarı yok).
"""

import time

from app.core import log, powershell

_log = log.get("store")

# (paket adı, metin anahtarı)
PACKAGES = (
    ("Microsoft.WindowsStore", "store"),
    ("Microsoft.DesktopAppInstaller", "app_installer"),
    ("Microsoft.StorePurchaseApp", "store_satin_alma"),
    ("Microsoft.XboxIdentityProvider", "xbox_kimlik"),
    ("Microsoft.GamingApp", "xbox"),
    ("Microsoft.XboxGamingOverlay", "oyun_cubugu"),
    ("Microsoft.Xbox.TCUI", "xbox_tcui"),
    ("Microsoft.WindowsCalculator", "hesap_makinesi"),
    ("Microsoft.Windows.Photos", "fotograflar"),
    ("Microsoft.WindowsCamera", "kamera"),
    ("Microsoft.ScreenSketch", "ekran_alintisi"),
    ("Microsoft.WindowsNotepad", "not_defteri"),
    ("Microsoft.Paint", "paint"),
)
NAMES = tuple(name for name, _key in PACKAGES)
SERVICES = ("wuauserv", "AppXSvc", "ClipSVC", "InstallService")
WINDOWS_11 = 22000

_STATUS_PS = r"""
$names = @(%NAMES%)
$allErr = $null
try { $all = @(Get-AppxPackage -AllUsers -ErrorAction Stop) } catch { $all = @(); $allErr = $_.Exception.Message }
$mine = @(Get-AppxPackage)
try { $prov = @(Get-AppxProvisionedPackage -Online -ErrorAction Stop) } catch { $prov = @() }
$pk = foreach ($n in $names) {
  $m = $mine | Where-Object Name -eq $n | Select-Object -First 1
  $a = $all | Where-Object Name -eq $n | Sort-Object Version -Descending | Select-Object -First 1
  $p = $prov | Where-Object DisplayName -eq $n | Select-Object -First 1
  $manifest = $null
  if ($a -and $a.InstallLocation) { $c = Join-Path $a.InstallLocation 'AppxManifest.xml'; if (Test-Path -LiteralPath $c) { $manifest = $c } }
  if (-not $manifest -and $p) { $c = Join-Path $env:ProgramFiles ('WindowsApps\' + $p.PackageName + '\AppxManifest.xml'); if (Test-Path -LiteralPath $c) { $manifest = $c } }
  [pscustomobject]@{ad=$n; kurulu=[bool]$m; surum=$(if ($m) { [string]$m.Version } else { $null }); manifest=$manifest; saglanmis=[bool]$p}
}
$sv = foreach ($s in @(%SERVICES%)) {
  $x = Get-Service -Name $s -ErrorAction SilentlyContinue
  [pscustomobject]@{ad=$s; durum=$(if ($x) { [string]$x.Status } else { 'yok' }); baslangic=$(if ($x) { [string]$x.StartType } else { $null })}
}
$ev = @(Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-AppXDeploymentServer/Operational'; Level=2; StartTime=(Get-Date).AddDays(-1)} -MaxEvents 50 -ErrorAction SilentlyContinue).Count
$dn = (Get-Service -Name AppXSvc -ErrorAction SilentlyContinue).DisplayName
$scm = @(Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Service Control Manager'; Id=7000,7001,7009,7011,7022,7023,7024,7026,7031,7034; StartTime=(Get-Date).AddDays(-7)} -MaxEvents 500 -ErrorAction SilentlyContinue | Where-Object { @($_.Properties | Where-Object { $v = [string]$_.Value; $v -like '*(AppXSVC)*' -or ($dn -and $v -eq $dn) }).Count }).Count
[pscustomobject]@{derleme=[Environment]::OSVersion.Version.Build; paketler=@($pk); servisler=@($sv); tum_kullanici_hatasi=$allErr; dagitim_hatasi_24s=$ev; appx_hizmet_hatasi_7g=$scm}
"""


def _script(template, **values):
    for key, items in values.items():
        template = template.replace(f"%{key}%", ",".join(powershell.quote(i) for i in items))
    return template


def status(run=powershell.run_object):
    """{derleme, paketler: [{ad, kurulu, surum, manifest, saglanmis, anahtar}], servisler, uyarilar}."""
    data = run(_script(_STATUS_PS, NAMES=NAMES, SERVICES=SERVICES), 120)
    keys = dict(PACKAGES)
    packages = powershell.as_list(data.get("paketler"))
    for item in packages:
        item["anahtar"] = keys.get(item["ad"], item["ad"])
    data["paketler"] = packages
    data["servisler"] = powershell.as_list(data.get("servisler"))
    data["uyarilar"] = problems(data)
    return data


def problems(data, failed=False):
    """Geri yüklemeyi etkileyebilecek sistem durumları: [(anahtar, parametreler)]. AppX dağıtım hataları
    yalnızca geri yükleme başarısızsa gösterilir (sağlam sistemlerde de günde onlarca kayıt olabiliyor)."""
    found = []
    services = {s["ad"]: s for s in data.get("servisler") or []}
    wu = services.get("wuauserv") or {}
    if wu.get("baslangic") == "Disabled":
        found.append(("store_geri.uyari.wu_kapali", {}))
    appx = services.get("AppXSvc") or {}
    if appx.get("durum") == "yok" or appx.get("baslangic") == "Disabled":
        found.append(("store_geri.uyari.appx_yok", {}))
    elif data.get("appx_hizmet_hatasi_7g"):  # Hizmet Denetimi Yöneticisi kaydı: başlatılamadı / beklenmedik durdu
        found.append(("store_geri.uyari.appx_hizmet_hata", {"adet": data["appx_hizmet_hatasi_7g"]}))
    if failed and data.get("dagitim_hatasi_24s"):
        found.append(("store_geri.uyari.appx_hata", {"adet": data["dagitim_hatasi_24s"]}))
    if data.get("tum_kullanici_hatasi"):
        found.append(("store_geri.uyari.tum_kullanici", {"hata": data["tum_kullanici_hatasi"]}))
    return found


def restore(package, info, build, run=powershell.run, read=status, sleep=time.sleep, wait_seconds=90):
    """Bir paketi geri yükler ve doğrular. Dönen: {basarili, yontemler: [...], neden, hata}.
    neden: None | "dosya_yok" | "kayit_hatasi" | "dogrulanamadi"."""
    tried, error = [], None

    def installed():
        current = next((p for p in read()["paketler"] if p["ad"] == package), {})
        return bool(current.get("kurulu"))

    if package == "Microsoft.WindowsStore" and build >= WINDOWS_11:
        tried.append("wsreset -i")
        try:
            run("Start-Process -FilePath wsreset.exe -ArgumentList '-i' -WindowStyle Hidden", 60)
            for _ in range(max(1, wait_seconds // 10)):  # wsreset -i arka planda indirir: kurulana kadar beklenir
                sleep(10)
                if installed():
                    return {"basarili": True, "yontemler": tried, "neden": None, "hata": None}
        except powershell.PowerShellError as exc:
            error = str(exc)
    manifest = info.get("manifest")
    if manifest:
        tried.append("Add-AppxPackage -Register")
        try:
            run(f"Add-AppxPackage -DisableDevelopmentMode -Register {powershell.quote(manifest)}", 300)
        except powershell.PowerShellError as exc:
            error = str(exc)
    if installed():
        return {"basarili": True, "yontemler": tried, "neden": None, "hata": None}
    reason = "dosya_yok" if not manifest and not info.get("saglanmis") else "kayit_hatasi" if error else "dogrulanamadi"
    _log.warning("Geri yüklenemedi (%s): %s %s", package, reason, error or "")
    return {"basarili": False, "yontemler": tried, "neden": reason, "hata": error}

