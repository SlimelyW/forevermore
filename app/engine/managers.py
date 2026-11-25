"""Başlangıç / servis / aygıt yöneticileri için Windows okuma ve yazma kodu.

Autoruns, MSI aracı veya benzeri üçüncü parti program GÖMÜLMEZ; her şey
Windows'un kendi kayıt defteri, API'leri ve PowerShell komutlarıyla yapılır.

Okuma fonksiyonları salt okunurdur. Yazma fonksiyonları yalnızca
`WindowsSystem` üzerinden ve motorun yedek akışıyla çağrılır.

Gizlilik: komut satırları ve dosya yolları (kullanıcı klasörü içerebilir)
yalnızca ekranda gösterilir; rapora, önbelleğe ve log'a yazılmaz.
"""

import ctypes
import datetime
import hashlib
import os
import winreg
from ctypes import wintypes

from app.core import log, powershell, registry

_log = log.get("managers")

# ---------------------------------------------------------------------------
# Başlangıç uygulamaları (Run anahtarları + başlangıç klasörleri + StartupApproved)
# ---------------------------------------------------------------------------

APPROVED = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved"
RUN_LOCATIONS = [
    # (konum kodu, kök, Run yolu, StartupApproved yolu)
    ("kayit_kullanici", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Run", APPROVED + r"\Run"),
    ("kayit_tum", "HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run", APPROVED + r"\Run"),
    ("kayit_32", "HKLM", r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run", APPROVED + r"\Run32"),
]


def _startup_folders():
    appdata = os.environ.get("APPDATA", "")
    programdata = os.environ.get("ProgramData", r"C:\ProgramData")
    return [
        ("klasor_kullanici", "HKCU", os.path.join(appdata, r"Microsoft\Windows\Start Menu\Programs\Startup")),
        ("klasor_tum", "HKLM", os.path.join(programdata, r"Microsoft\Windows\Start Menu\Programs\StartUp")),
    ]


def item_id(prefix, *parts):
    return prefix + "-" + hashlib.sha1("|".join(parts).lower().encode("utf-8")).hexdigest()[:10]


def approved_enabled(data):
    """StartupApproved verisi: ilk baytı çift ise (02, 06) etkin, tek ise (03, 07) devre dışı. Yoksa etkin."""
    if not data:
        return True
    return data[0] % 2 == 0


def list_startup_items():
    items = []
    for location, root, run_path, approved_path in RUN_LOCATIONS:
        for name, value in registry.values(root, run_path).items():
            if not name:
                continue
            raw = registry.read(root, approved_path, name)
            items.append({
                "id": item_id("BAS", root, approved_path, name), "ad": name, "komut": str(value),
                "konum": location, "etkin": approved_enabled(raw),
                "onay": {"kok": root, "yol": approved_path, "ad": name},
            })
    for location, root, folder in _startup_folders():
        try:
            names = sorted(os.listdir(folder))
        except OSError:
            continue
        for name in names:
            if name.lower() == "desktop.ini" or os.path.isdir(os.path.join(folder, name)):
                continue
            path = APPROVED + r"\StartupFolder"
            raw = registry.read(root, path, name)
            items.append({
                "id": item_id("BAS", root, path, name), "ad": os.path.splitext(name)[0],
                "komut": os.path.join(folder, name), "konum": location, "etkin": approved_enabled(raw),
                "onay": {"kok": root, "yol": path, "ad": name},
            })
    return items


def get_startup_approved(root, path, name):
    """Ham değer (onaltılık metin) veya yoksa None."""
    data = registry.read(root, path, name)
    return bytes(data).hex() if isinstance(data, (bytes, bytearray)) else None


def _filetime_now():
    epoch = datetime.datetime(1601, 1, 1, tzinfo=datetime.timezone.utc)
    ticks = int((datetime.datetime.now(datetime.timezone.utc) - epoch).total_seconds() * 10_000_000)
    return ticks.to_bytes(8, "little")


def set_startup_approved(root, path, name, enabled):
    """Görev Yöneticisi'nin yaptığı gibi: 02 00.. = etkin, 03 00 00 00 + zaman = devre dışı."""
    data = bytes([2, 0, 0, 0]) + bytes(8) if enabled else bytes([3, 0, 0, 0]) + _filetime_now()
    write_startup_approved_raw(root, path, name, data.hex())


def write_startup_approved_raw(root, path, name, hex_value):
    access = winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE | winreg.KEY_WOW64_64KEY
    if hex_value is None:
        try:
            with winreg.OpenKey(registry.ROOTS[root], path, 0, access) as key:
                winreg.DeleteValue(key, name)
        except FileNotFoundError:
            pass
        return
    with winreg.CreateKeyEx(registry.ROOTS[root], path, 0, access) as key:
        winreg.SetValueEx(key, name, 0, winreg.REG_BINARY, bytes.fromhex(hex_value))


# ---------------------------------------------------------------------------
# Oturum açılışında / önyüklemede çalışan zamanlanmış görevler (Microsoft dışı)
# ---------------------------------------------------------------------------

def list_logon_tasks():
    rows = powershell.run_json(
        "Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskPath -notlike '\\Microsoft\\*' -and "
        "($_.Triggers | Where-Object { $_.CimClass.CimClassName -in "
        "'MSFT_TaskLogonTrigger','MSFT_TaskBootTrigger' }) } | Select-Object TaskPath, TaskName, "
        "@{n='s';e={[string]$_.State}}, @{n='k';e={[string](@($_.Actions)[0].Execute)}}", timeout=90)
    return [{"id": item_id("GRV", r["TaskPath"], r["TaskName"]), "ad": r["TaskName"], "yol": r["TaskPath"],
             "komut": r.get("k") or "", "etkin": r.get("s") != "Disabled"} for r in rows or []]


# ---------------------------------------------------------------------------
# Servisler (Win32 servisleri; sürücüler hariç)
# ---------------------------------------------------------------------------

class _ServiceStatusProcess(ctypes.Structure):
    _fields_ = [(n, wintypes.DWORD) for n in (
        "dwServiceType", "dwCurrentState", "dwControlsAccepted", "dwWin32ExitCode", "dwServiceSpecificExitCode",
        "dwCheckPoint", "dwWaitHint", "dwProcessId", "dwServiceFlags")]


class _EnumServiceStatusProcess(ctypes.Structure):
    _fields_ = [("lpServiceName", wintypes.LPWSTR), ("lpDisplayName", wintypes.LPWSTR),
                ("ServiceStatusProcess", _ServiceStatusProcess)]


SERVICE_START = {2: "Automatic", 3: "Manual", 4: "Disabled", 0: "Boot", 1: "System"}

# Kapatılırsa Windows açılmayabilir, ağ/ses/oturum bozulabilir: yönetici listesinde kilitli.
PROTECTED_SERVICES = {
    "rpcss", "rpceptmapper", "dcomlaunch", "lsm", "samss", "eventlog", "plugplay", "power", "profsvc",
    "schedule", "winmgmt", "bfe", "mpssvc", "cryptsvc", "dhcp", "dnscache", "nsi", "brokerinfrastructure",
    "coremessagingregistrar", "systemeventsbroker", "gpsvc", "trustedinstaller", "audiosrv",
    "audioendpointbuilder", "lanmanworkstation", "netprofm", "nlasvc", "usermanager", "staterepository",
    "appinfo", "keyiso", "vaultsvc", "wlansvc", "dispbrokerdesktopsvc", "msiserver", "seclogon",
    "sense", "sgrmbroker", "wscsvc", "securityhealthservice", "windefend", "wdnissvc", "wuauserv",
    "usosvc", "waasmedicsvc", "bits", "themes", "fontcache", "eventsystem", "sens", "timebrokersvc",
    "cdpsvc", "lsass", "wininit", "csrss", "tokenbroker", "camsvc", "devicesflowusersvc", "textinputmanagementservice",
}
# Anti-cheat servisleri: hiçbir zaman dokunulmaz (ban riski, oyun açılmaz).
ANTI_CHEAT_SERVICES = {"vgc", "vgk", "beservice", "easyanticheat", "easyanticheat_eos", "faceit", "faceitservice",
                       "esportal", "eaanticheatservice", "atvi-randgrid_sr", "ricochet", "mhyprot3", "xhunter1"}


def _enum_services():
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    advapi.OpenSCManagerW.restype = ctypes.c_void_p
    advapi.EnumServicesStatusExW.argtypes = [ctypes.c_void_p, ctypes.c_int, wintypes.DWORD, wintypes.DWORD,
                                             ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                                             ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
                                             wintypes.LPCWSTR]
    advapi.CloseServiceHandle.argtypes = [ctypes.c_void_p]
    manager = advapi.OpenSCManagerW(None, None, 0x0004)  # SC_MANAGER_ENUMERATE_SERVICE
    if not manager:
        raise OSError("Servis yöneticisi açılamadı")
    try:
        needed, count, resume = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
        advapi.EnumServicesStatusExW(manager, 0, 0x30, 3, None, 0, ctypes.byref(needed), ctypes.byref(count),
                                     ctypes.byref(resume), None)
        buffer = (ctypes.c_byte * (needed.value + 4096))()
        resume = wintypes.DWORD()
        if not advapi.EnumServicesStatusExW(manager, 0, 0x30, 3, buffer, len(buffer), ctypes.byref(needed),
                                            ctypes.byref(count), ctypes.byref(resume), None):
            raise OSError(f"EnumServicesStatusEx hata {ctypes.get_last_error()}")
        entries = ctypes.cast(buffer, ctypes.POINTER(_EnumServiceStatusProcess))
        return [(entries[i].lpServiceName, entries[i].lpDisplayName,
                 entries[i].ServiceStatusProcess.dwCurrentState == 4) for i in range(count.value)]
    finally:
        advapi.CloseServiceHandle(manager)


def _is_windows_service(image_path):
    path = (image_path or "").lower().strip('"')
    windir = os.path.dirname(powershell.SYSTEM32).lower()  # ortam değişkeni HKCU'dan ezilebilir
    return path.startswith(windir) or path.startswith("%systemroot%") or path.startswith("\\systemroot") \
        or path.startswith("system32") or "\\windows\\system32\\" in path


def list_services():
    rows = []
    for name, display, running in _enum_services():
        key = rf"SYSTEM\CurrentControlSet\Services\{name}"
        start = registry.read("HKLM", key, "Start")
        kind = SERVICE_START.get(start, "Manual")
        if kind == "Automatic" and registry.read("HKLM", key, "DelayedAutostart") == 1:
            kind = "AutomaticDelayed"
        lowered = name.lower()
        rows.append({
            "id": "SRV-" + name, "ad": display or name, "servis": name, "baslangic": kind, "calisiyor": running,
            "windows": _is_windows_service(registry.read("HKLM", key, "ImagePath")),
            "kilit": "anti_cheat" if lowered in ANTI_CHEAT_SERVICES or lowered.split("_")[0] in ANTI_CHEAT_SERVICES
            else ("kritik" if lowered in PROTECTED_SERVICES or lowered.split("_")[0] in PROTECTED_SERVICES else None),
        })
    return rows


# ---------------------------------------------------------------------------
# PCI aygıtları ve MSI modu
# ---------------------------------------------------------------------------

MSI_PATH = r"SYSTEM\CurrentControlSet\Enum\{id}\Device Parameters\Interrupt Management\MessageSignaledInterruptProperties"


def msi_key(instance_id):
    return MSI_PATH.format(id=instance_id)


def list_pci_devices():
    rows = powershell.run_json(
        "Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -like 'PCI\\*' } | "
        "Select-Object InstanceId, FriendlyName, @{n='c';e={[string]$_.Class}}", timeout=60)
    devices = []
    for r in rows or []:
        instance = r["InstanceId"]
        key = msi_key(instance)
        value = registry.read("HKLM", key, "MSISupported")
        devices.append({"id": item_id("MSI", instance), "ornek": instance, "ad": r.get("FriendlyName") or instance,
                        "sinif": r.get("c") or "", "msi": None if value is None else value == 1,
                        "anahtar_var": registry.key_exists("HKLM", key)})
    return devices


# ---------------------------------------------------------------------------
# Aygıt güç yönetimi ("Güç tasarrufu için bilgisayarın bu aygıtı kapatmasına izin ver")
# ---------------------------------------------------------------------------

def list_power_managed_devices():
    rows = powershell.run_json(
        "$p = @{}; Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | "
        "ForEach-Object { $p[$_.InstanceId.ToUpper()] = $_ }; "
        "Get-CimInstance -Namespace root/wmi -ClassName MSPower_DeviceEnable -ErrorAction SilentlyContinue | "
        "ForEach-Object { $id = ($_.InstanceName -replace '_\\d+$','').ToUpper(); $d = $p[$id]; "
        "if ($d) { [pscustomobject]@{ i = $_.InstanceName; a = $d.FriendlyName; c = [string]$d.Class; "
        "e = [bool]$_.Enable } } }", timeout=90)
    return [{"id": item_id("GUC", r["i"]), "ornek": r["i"], "ad": r.get("a") or r["i"], "sinif": r.get("c") or "",
             "etkin": bool(r.get("e"))} for r in rows or []]


def get_device_power(instance_name):
    rows = powershell.run_json(
        "Get-CimInstance -Namespace root/wmi -ClassName MSPower_DeviceEnable -ErrorAction SilentlyContinue | "
        f"Where-Object {{ $_.InstanceName -eq {powershell.quote(instance_name)} }} | "
        "Select-Object @{n='e';e={[bool]$_.Enable}}", timeout=60)
    return bool(rows[0]["e"]) if rows else None


def set_device_power(instance_name, enabled):
    powershell.run(
        "Get-CimInstance -Namespace root/wmi -ClassName MSPower_DeviceEnable | "
        f"Where-Object {{ $_.InstanceName -eq {powershell.quote(instance_name)} }} | "
        f"Set-CimInstance -Property @{{Enable=${'true' if enabled else 'false'}}}", timeout=60)


# ---------------------------------------------------------------------------
# Ses aygıtları (kullanılmayan ses uç noktaları, Bluetooth Eller Serbest profili)
# ---------------------------------------------------------------------------

HFP_PREFIX = "BTHENUM\\{0000111E"  # Bluetooth Hands-Free (HFP) hizmeti


def list_audio_pnp_devices():
    """Ses uç noktaları (hoparlör, kulaklık, mikrofon) ve Bluetooth Eller Serbest aygıtları.
    etkin: aygıt devre dışı bırakılmamış (ConfigManagerErrorCode 22 = devre dışı)."""
    rows = powershell.run_json(
        "Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object { [string]$_.Class -eq 'AudioEndpoint' "
        "-or $_.InstanceId -like 'BTHENUM\\{0000111E*' } | ForEach-Object { [pscustomobject]@{ i = $_.InstanceId; "
        "a = $_.FriendlyName; c = [string]$_.Class; d = ([int]$_.ConfigManagerErrorCode -eq 22) } }", timeout=60)
    result = []
    for r in rows or []:
        hfp = r["i"].upper().startswith(HFP_PREFIX)
        result.append({"id": item_id("SESA", r["i"]), "ornek": r["i"], "ad": r.get("a") or r["i"],
                       "sinif": "Bluetooth" if hfp else "AudioEndpoint", "etkin": not r.get("d")})
    return result


def get_device_enabled(instance_id):
    rows = powershell.run_json(
        f"Get-PnpDevice -InstanceId {powershell.quote(instance_id)} -ErrorAction SilentlyContinue | "
        "Select-Object @{n='d';e={[int]$_.ConfigManagerErrorCode -eq 22}}", timeout=60)
    return (not rows[0]["d"]) if rows else None


def set_device_enabled(instance_id, enabled):
    verb = "Enable-PnpDevice" if enabled else "Disable-PnpDevice"
    powershell.run(f"{verb} -InstanceId {powershell.quote(instance_id)} -Confirm:$false -ErrorAction Stop", timeout=60)


# ---------------------------------------------------------------------------
# Görsel efektler (Performans Seçenekleri penceresindeki kutucuklar)
# ---------------------------------------------------------------------------

SPIF = 0x01 | 0x02  # SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE
# ad -> (okuma kodu, yazma kodu, tür)   tür: "pv" = pvParam BOOL, "ui" = uiParam BOOL, "anim" = ANIMATIONINFO
UI_EFFECTS = {
    "pencere_animasyonu": (0x0048, 0x0049, "anim"),        # SPI_GET/SETANIMATION
    "denetim_animasyonu": (0x1042, 0x1043, "pv"),          # SPI_GET/SETCLIENTAREAANIMATION
    "menu_animasyonu": (0x1002, 0x1003, "pv"),             # SPI_GET/SETMENUANIMATION
    "ipucu_animasyonu": (0x1016, 0x1017, "pv"),            # SPI_GET/SETTOOLTIPANIMATION
    "secim_solmasi": (0x1014, 0x1015, "pv"),               # SPI_GET/SETSELECTIONFADE
    "imlec_golgesi": (0x101A, 0x101B, "pv"),               # SPI_GET/SETCURSORSHADOW
    "pencere_golgesi": (0x1024, 0x1025, "pv"),             # SPI_GET/SETDROPSHADOW
    "acilir_kutu_animasyonu": (0x1004, 0x1005, "pv"),      # SPI_GET/SETCOMBOBOXANIMATION
    "liste_kaydirma": (0x1006, 0x1007, "pv"),              # SPI_GET/SETLISTBOXSMOOTHSCROLLING
    "surukerken_icerik": (0x0026, 0x0025, "ui"),           # SPI_GETDRAGFULLWINDOWS / SPI_SETDRAGFULLWINDOWS
}


class _AnimationInfo(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("iMinAnimate", ctypes.c_int)]


def get_ui_effect(name):
    get_code, _set_code, kind = UI_EFFECTS[name]
    spi = ctypes.windll.user32.SystemParametersInfoW
    if kind == "anim":
        info = _AnimationInfo(ctypes.sizeof(_AnimationInfo), 0)
        if not spi(get_code, ctypes.sizeof(info), ctypes.byref(info), 0):
            raise OSError(f"SystemParametersInfo okunamadı: {name}")
        return bool(info.iMinAnimate)
    value = wintypes.BOOL()
    if not spi(get_code, 0, ctypes.byref(value), 0):
        raise OSError(f"SystemParametersInfo okunamadı: {name}")
    return bool(value.value)


def set_ui_effect(name, enabled):
    _get_code, set_code, kind = UI_EFFECTS[name]
    spi = ctypes.windll.user32.SystemParametersInfoW
    if kind == "anim":
        info = _AnimationInfo(ctypes.sizeof(_AnimationInfo), int(bool(enabled)))
        ok = spi(set_code, ctypes.sizeof(info), ctypes.byref(info), SPIF)
    elif kind == "ui":
        ok = spi(set_code, int(bool(enabled)), None, SPIF)
    else:
        ok = spi(set_code, 0, ctypes.c_void_p(int(bool(enabled))), SPIF)
    if not ok:
        raise OSError(f"SystemParametersInfo yazılamadı: {name}")


# ---------------------------------------------------------------------------
# Windows 11 güç modu (overlay): Ayarlar > Güç > Güç modu
# ---------------------------------------------------------------------------

OVERLAY_KEY = r"SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes"
OVERLAY_BALANCED = "00000000-0000-0000-0000-000000000000"


class _SystemPowerStatus(ctypes.Structure):
    _fields_ = [("ACLineStatus", ctypes.c_byte), ("BatteryFlag", ctypes.c_byte), ("BatteryLifePercent", ctypes.c_byte),
                ("SystemStatusFlag", ctypes.c_byte), ("BatteryLifeTime", wintypes.DWORD),
                ("BatteryFullLifeTime", wintypes.DWORD)]


def on_ac_power():
    status = _SystemPowerStatus()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
        return True
    return status.ACLineStatus != 0


def get_power_overlay(source):
    name = "ActiveOverlayAcPowerScheme" if source == "ac" else "ActiveOverlayDcPowerScheme"
    return (registry.read("HKLM", OVERLAY_KEY, name) or OVERLAY_BALANCED).lower()


def set_power_overlay(source, guid):
    """Şu anki güç kaynağı için Windows'un kendi API'si (PowerSetActiveOverlayScheme) kullanılır.
    Diğer kaynak (ör. prizdeyken 'pilde' modu) için değer kayıt defterine yazılır.

    Emin değilim: belgelenmemiş bu API ve kayıt defteri değeri Windows sürümüne göre
    farklı davranabilir; test listesinde ayrıca doğrulanmalıdır.
    """
    current = "ac" if on_ac_power() else "dc"
    if source == current:
        import uuid  # noqa: WPS433
        buffer = (ctypes.c_byte * 16).from_buffer_copy(uuid.UUID(guid).bytes_le)
        result = ctypes.WinDLL("powrprof").PowerSetActiveOverlayScheme(ctypes.byref(buffer))
        if result != 0:
            raise OSError(f"PowerSetActiveOverlayScheme hata {result}")
        return
    name = "ActiveOverlayAcPowerScheme" if source == "ac" else "ActiveOverlayDcPowerScheme"
    access = winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY
    with winreg.OpenKey(registry.ROOTS["HKLM"], OVERLAY_KEY, 0, access) as key:
        winreg.SetValueEx(key, name, 0, winreg.REG_SZ, guid)
