"""Donanım ve sistem taraması: Windows sürümü, CPU, GPU, RAM, anakart,
ekranlar, laptop/masaüstü.

Gizlilik: seri numarası, ürün anahtarı, bilgisayar adı, kullanıcı adı OKUNMAZ.
"""

import ctypes
import os
import re
import subprocess
from ctypes import wintypes

from app.core import powershell, registry
from app.engine import resolvers
from app.scan import gpus as gpu_module

# SMBIOS bellek türleri (Win32_PhysicalMemory.SMBIOSMemoryType)
MEMORY_TYPES = {20: "DDR", 21: "DDR2", 24: "DDR3", 26: "DDR4", 27: "LPDDR", 28: "LPDDR2",
                29: "LPDDR3", 30: "LPDDR4", 34: "DDR5", 35: "LPDDR5"}
FORM_FACTORS = {8: "DIMM", 12: "SODIMM", 0: "bilinmiyor"}
# Win32_SystemEnclosure.ChassisTypes: taşınabilir kasa türleri
PORTABLE_CHASSIS = {8, 9, 10, 11, 12, 14, 18, 21, 30, 31, 32}
DESKTOP_CHASSIS = {3, 4, 5, 6, 7, 13, 15, 16, 17, 23, 24, 35, 36}

_HARDWARE_PS = r"""
$cs = Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer, Model, PCSystemType, TotalPhysicalMemory
$cpu = @(Get-CimInstance Win32_Processor | Select-Object Name, Manufacturer, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed)
$ram = @(Get-CimInstance Win32_PhysicalMemory | Select-Object Capacity, Speed, ConfiguredClockSpeed, SMBIOSMemoryType, FormFactor, DeviceLocator, BankLabel, Manufacturer, PartNumber)
$gpu = @(Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, AdapterCompatibility, @{n='DriverDate';e={ if ($_.DriverDate) { $_.DriverDate.ToString('yyyy-MM-dd') } }})
$bb = Get-CimInstance Win32_BaseBoard | Select-Object Manufacturer, Product
$bios = Get-CimInstance Win32_BIOS | Select-Object SMBIOSBIOSVersion, @{n='Tarih';e={ if ($_.ReleaseDate) { $_.ReleaseDate.ToString('yyyy-MM-dd') } }}
$chassis = @((Get-CimInstance Win32_SystemEnclosure).ChassisTypes)
$battery = @(Get-CimInstance Win32_Battery).Count
[pscustomobject]@{cs=$cs; cpu=$cpu; ram=$ram; gpu=$gpu; bb=$bb; bios=$bios; chassis=$chassis; battery=$battery}
"""


# ---------------------------------------------------------------------------
# Windows ve bellek durumu (ctypes, PowerShell gerekmez)
# ---------------------------------------------------------------------------

class _MemoryStatus(ctypes.Structure):
    _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


class _PowerStatus(ctypes.Structure):
    _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte),
                ("BatteryLifePercent", ctypes.c_ubyte), ("SystemStatusFlag", ctypes.c_ubyte),
                ("BatteryLifeTime", wintypes.DWORD), ("BatteryFullLifeTime", wintypes.DWORD)]


def memory_status():
    status = _MemoryStatus()
    status.dwLength = ctypes.sizeof(_MemoryStatus)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
    return {
        "toplam_gb": round(status.ullTotalPhys / 1024 ** 3, 1),
        "bos_gb": round(status.ullAvailPhys / 1024 ** 3, 1),
        "kullanim_yuzde": int(status.dwMemoryLoad),
    }


def power_status():
    status = _PowerStatus()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
        return {}
    return {
        "prizde": {0: False, 1: True}.get(status.ACLineStatus),
        "pil_var": status.BatteryFlag != 128,
        "pil_yuzde": None if status.BatteryLifePercent == 255 else int(status.BatteryLifePercent),
        "pil_tasarrufu": bool(status.SystemStatusFlag & 1),
    }


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except OSError:
        return False


def collect_system():
    key = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
    build = int(registry.read("HKLM", key, "CurrentBuild", "0") or 0)
    product = registry.read("HKLM", key, "ProductName", "") or ""
    # Windows 11'de ProductName hâlâ "Windows 10 ..." yazar; build ile düzeltilir.
    major = "11" if build >= 22000 else "10"
    if major == "11":
        product = product.replace("Windows 10", "Windows 11")
    uptime_ms = ctypes.windll.kernel32.GetTickCount64
    uptime_ms.restype = ctypes.c_ulonglong
    return {
        "windows": {
            "ad": product,
            "surum": major,
            "surum_kodu": registry.read("HKLM", key, "DisplayVersion", "") or "",
            "build": build,
            "ubr": registry.read("HKLM", key, "UBR"),
            "edisyon": registry.read("HKLM", key, "EditionID", "") or "",
        },
        "acik_kalma_saat": round(uptime_ms() / 3_600_000, 1),
        "bellek": memory_status(),
        "guc": power_status(),
        "yonetici": is_admin(),
    }


# ---------------------------------------------------------------------------
# Ekranlar (ctypes ile; çoklu monitörde her ekran ayrı okunur)
# ---------------------------------------------------------------------------

class _DisplayDevice(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("DeviceName", wintypes.WCHAR * 32),
                ("DeviceString", wintypes.WCHAR * 128), ("StateFlags", wintypes.DWORD),
                ("DeviceID", wintypes.WCHAR * 128), ("DeviceKey", wintypes.WCHAR * 128)]


class _DevMode(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", wintypes.WCHAR * 32), ("dmSpecVersion", wintypes.WORD),
        ("dmDriverVersion", wintypes.WORD), ("dmSize", wintypes.WORD),
        ("dmDriverExtra", wintypes.WORD), ("dmFields", wintypes.DWORD),
        ("dmPositionX", wintypes.LONG), ("dmPositionY", wintypes.LONG),
        ("dmDisplayOrientation", wintypes.DWORD), ("dmDisplayFixedOutput", wintypes.DWORD),
        ("dmColor", ctypes.c_short), ("dmDuplex", ctypes.c_short),
        ("dmYResolution", ctypes.c_short), ("dmTTOption", ctypes.c_short),
        ("dmCollate", ctypes.c_short), ("dmFormName", wintypes.WCHAR * 32),
        ("dmLogPixels", wintypes.WORD), ("dmBitsPerPel", wintypes.DWORD),
        ("dmPelsWidth", wintypes.DWORD), ("dmPelsHeight", wintypes.DWORD),
        ("dmDisplayFlags", wintypes.DWORD), ("dmDisplayFrequency", wintypes.DWORD),
        ("dmICMMethod", wintypes.DWORD), ("dmICMIntent", wintypes.DWORD),
        ("dmMediaType", wintypes.DWORD), ("dmDitherType", wintypes.DWORD),
        ("dmReserved1", wintypes.DWORD), ("dmReserved2", wintypes.DWORD),
        ("dmPanningWidth", wintypes.DWORD), ("dmPanningHeight", wintypes.DWORD),
    ]


ENUM_CURRENT_SETTINGS = -1
ATTACHED_TO_DESKTOP = 0x1
PRIMARY_DEVICE = 0x4
DM_PELSWIDTH = 0x80000
DM_PELSHEIGHT = 0x100000
DM_DISPLAYFREQUENCY = 0x400000
CDS_UPDATEREGISTRY = 0x1
CDS_TEST = 0x2
DISP_CHANGE_SUCCESSFUL = 0


def attached_display_devices():
    """Masaüstüne bağlı ekranlar: [{'aygit': Windows ekran aygıt adı (DISPLAY1 gibi), 'ad': monitör adı}]."""
    user32 = ctypes.windll.user32
    result = []
    i = 0
    while True:
        adapter = _DisplayDevice()
        adapter.cb = ctypes.sizeof(_DisplayDevice)
        if not user32.EnumDisplayDevicesW(None, i, ctypes.byref(adapter), 0):
            break
        i += 1
        if not adapter.StateFlags & ATTACHED_TO_DESKTOP:
            continue
        monitor = _DisplayDevice()
        monitor.cb = ctypes.sizeof(_DisplayDevice)
        name = adapter.DeviceString
        if user32.EnumDisplayDevicesW(adapter.DeviceName, 0, ctypes.byref(monitor), 0) and monitor.DeviceString:
            name = monitor.DeviceString
        result.append({"aygit": adapter.DeviceName, "ad": name, "birincil": bool(adapter.StateFlags & PRIMARY_DEVICE)})
    return result


def _current_mode(device):
    mode = _DevMode()
    mode.dmSize = ctypes.sizeof(_DevMode)
    if not ctypes.windll.user32.EnumDisplaySettingsW(device, ENUM_CURRENT_SETTINGS, ctypes.byref(mode)):
        raise OSError(f"Ekran ayarı okunamadı: {device}")
    return mode


def _refresh_rates(device, width, height):
    """Bu çözünürlükte sürücünün desteklediği yenileme hızları."""
    rates = set()
    mode = _DevMode()
    mode.dmSize = ctypes.sizeof(_DevMode)
    j = 0
    while j < 5000 and ctypes.windll.user32.EnumDisplaySettingsW(device, j, ctypes.byref(mode)):
        j += 1
        if (mode.dmPelsWidth, mode.dmPelsHeight) == (width, height) and mode.dmDisplayFrequency > 1:
            rates.add(mode.dmDisplayFrequency)
    return sorted(rates)


ORIENTATIONS = {0: "yatay", 1: "dikey", 2: "yatay_ters", 3: "dikey_ters"}


def display_layout():
    """Masaüstündeki ekranların yerleşimi (salt okunur): [{'aygit', 'ad', 'birincil', 'x', 'y',
    'genislik', 'yukseklik', 'yon'}]. Konum sanal masaüstü pikselidir; yön ORIENTATIONS anahtarı.
    Okunamayan ekran listeye girmez."""
    result = []
    for item in attached_display_devices():
        try:
            mode = _current_mode(item["aygit"])
        except OSError:
            continue
        result.append({**item, "x": mode.dmPositionX, "y": mode.dmPositionY,
                       "genislik": mode.dmPelsWidth, "yukseklik": mode.dmPelsHeight,
                       "yon": ORIENTATIONS.get(mode.dmDisplayOrientation, "yatay")})
    return result


DM_POSITION = 0x20
DM_DISPLAYORIENTATION = 0x80


def layout_overlaps(rects, rect):
    """rect = (x, y, genişlik, yükseklik) diğer dikdörtgenlerden biriyle kesişiyor mu (kenar teması serbest)."""
    x, y, width, height = rect
    return any(x < ox + ow and ox < x + width and y < oy + oh and oy < y + height for ox, oy, ow, oh in rects)


def set_display_layout(device, x, y, orientation):
    """Ekranın konumunu (sanal masaüstü pikseli) ve yönünü değiştirir (önce CDS_TEST ile denenir).
    Birincil ekran (0,0)'da kalır, konumu değişmez. Ekranlar üst üste binemez."""
    codes = {name: code for code, name in ORIENTATIONS.items()}
    if orientation not in codes:
        raise ValueError(f"Bilinmeyen yön: {orientation}")
    layout = display_layout()
    me = next((item for item in layout if item["aygit"].lower() == device.lower()), None)
    if me is None:
        raise OSError(f"Ekran bulunamadı: {device}")
    if me["birincil"]:
        x, y = me["x"], me["y"]
    width, height = me["genislik"], me["yukseklik"]
    if (me["yon"] in ("dikey", "dikey_ters")) != (orientation in ("dikey", "dikey_ters")):
        width, height = height, width
    others = [(o["x"], o["y"], o["genislik"], o["yukseklik"]) for o in layout if o is not me]
    if layout_overlaps(others, (x, y, width, height)):
        raise ValueError("Ekranlar üst üste binemez")
    mode = _current_mode(device)
    mode.dmPositionX, mode.dmPositionY, mode.dmDisplayOrientation = x, y, codes[orientation]
    mode.dmPelsWidth, mode.dmPelsHeight = width, height
    mode.dmFields = DM_POSITION | DM_DISPLAYORIENTATION | DM_PELSWIDTH | DM_PELSHEIGHT
    change = ctypes.windll.user32.ChangeDisplaySettingsExW
    if change(device, ctypes.byref(mode), None, CDS_TEST, None) != DISP_CHANGE_SUCCESSFUL:
        raise OSError("Sürücü bu ekran yerleşimini kabul etmedi")
    code = change(device, ctypes.byref(mode), None, CDS_UPDATEREGISTRY, None)
    if code != DISP_CHANGE_SUCCESSFUL:
        raise OSError(f"Ekran yerleşimi değiştirilemedi (kod {code})")


def display_refresh(device):
    """{'hz': şu anki, 'en_yuksek': bu çözünürlükteki en yüksek, 'hizlar': [...]}. Salt okunur."""
    current = _current_mode(device)
    rates = _refresh_rates(device, current.dmPelsWidth, current.dmPelsHeight) or [current.dmDisplayFrequency]
    return {"hz": current.dmDisplayFrequency, "en_yuksek": max(rates + [current.dmDisplayFrequency]), "hizlar": rates}


def set_display_refresh(device, hz):
    """Çözünürlüğü koruyarak yalnızca yenileme hızını değiştirir (önce CDS_TEST ile denenir)."""
    mode = _current_mode(device)
    if hz not in _refresh_rates(device, mode.dmPelsWidth, mode.dmPelsHeight):
        raise ValueError(f"{hz} Hz bu çözünürlükte desteklenmiyor")
    mode.dmDisplayFrequency = hz
    mode.dmFields = DM_PELSWIDTH | DM_PELSHEIGHT | DM_DISPLAYFREQUENCY
    change = ctypes.windll.user32.ChangeDisplaySettingsExW
    if change(device, ctypes.byref(mode), None, CDS_TEST, None) != DISP_CHANGE_SUCCESSFUL:
        raise OSError(f"Sürücü {hz} Hz ayarını kabul etmedi")
    code = change(device, ctypes.byref(mode), None, CDS_UPDATEREGISTRY, None)
    if code != DISP_CHANGE_SUCCESSFUL:
        raise OSError(f"Yenileme hızı değiştirilemedi (kod {code})")


def display_modes(device):
    """{'cozunurluk': '2560x1440', 'hz': 144, 'modlar': {'2560x1440': [144, 120, 60], ...}} (büyükten küçüğe)."""
    current = _current_mode(device)
    modes = {}
    mode = _DevMode()
    mode.dmSize = ctypes.sizeof(_DevMode)
    j = 0
    while j < 5000 and ctypes.windll.user32.EnumDisplaySettingsW(device, j, ctypes.byref(mode)):
        j += 1
        if mode.dmDisplayFrequency > 1 and mode.dmPelsWidth >= 640:
            modes.setdefault(f"{mode.dmPelsWidth}x{mode.dmPelsHeight}", set()).add(mode.dmDisplayFrequency)
    ordered = sorted(modes, key=lambda r: tuple(int(x) for x in r.split("x")), reverse=True)
    return {"cozunurluk": f"{current.dmPelsWidth}x{current.dmPelsHeight}", "hz": current.dmDisplayFrequency,
            "modlar": {r: sorted(modes[r], reverse=True) for r in ordered}}


def set_display_mode(device, width, height, hz):
    """Çözünürlük ve yenileme hızını birlikte değiştirir (önce CDS_TEST ile denenir).
    Yalnızca sürücünün listelediği modlar kabul edilir."""
    if hz not in display_modes(device)["modlar"].get(f"{width}x{height}", []):
        raise ValueError(f"{width}x{height}@{hz} bu ekranda desteklenmiyor")
    mode = _current_mode(device)
    mode.dmPelsWidth, mode.dmPelsHeight, mode.dmDisplayFrequency = width, height, hz
    mode.dmFields = DM_PELSWIDTH | DM_PELSHEIGHT | DM_DISPLAYFREQUENCY
    change = ctypes.windll.user32.ChangeDisplaySettingsExW
    if change(device, ctypes.byref(mode), None, CDS_TEST, None) != DISP_CHANGE_SUCCESSFUL:
        raise OSError(f"Sürücü {width}x{height}@{hz} modunu kabul etmedi")
    code = change(device, ctypes.byref(mode), None, CDS_UPDATEREGISTRY, None)
    if code != DISP_CHANGE_SUCCESSFUL:
        raise OSError(f"Ekran modu değiştirilemedi (kod {code})")


def collect_displays():
    user32 = ctypes.windll.user32
    displays = []
    i = 0
    while True:
        adapter = _DisplayDevice()
        adapter.cb = ctypes.sizeof(_DisplayDevice)
        if not user32.EnumDisplayDevicesW(None, i, ctypes.byref(adapter), 0):
            break
        i += 1
        if not adapter.StateFlags & ATTACHED_TO_DESKTOP:
            continue
        current = _DevMode()
        current.dmSize = ctypes.sizeof(_DevMode)
        if not user32.EnumDisplaySettingsW(adapter.DeviceName, ENUM_CURRENT_SETTINGS, ctypes.byref(current)):
            continue
        width, height, hz = current.dmPelsWidth, current.dmPelsHeight, current.dmDisplayFrequency

        max_hz_here = hz
        max_res = (width, height)
        mode = _DevMode()
        mode.dmSize = ctypes.sizeof(_DevMode)
        j = 0
        while j < 5000 and user32.EnumDisplaySettingsW(adapter.DeviceName, j, ctypes.byref(mode)):
            j += 1
            if (mode.dmPelsWidth, mode.dmPelsHeight) == (width, height):
                max_hz_here = max(max_hz_here, mode.dmDisplayFrequency)
            if mode.dmPelsWidth * mode.dmPelsHeight > max_res[0] * max_res[1]:
                max_res = (mode.dmPelsWidth, mode.dmPelsHeight)

        monitor = _DisplayDevice()
        monitor.cb = ctypes.sizeof(_DisplayDevice)
        monitor_name = ""
        if user32.EnumDisplayDevicesW(adapter.DeviceName, 0, ctypes.byref(monitor), 0):
            monitor_name = monitor.DeviceString
        displays.append({
            "aygit": adapter.DeviceName,
            "monitor": monitor_name,
            "ekran_karti": adapter.DeviceString,
            "birincil": bool(adapter.StateFlags & PRIMARY_DEVICE),
            "cozunurluk": f"{width}x{height}",
            "yenileme_hz": hz,
            "bu_cozunurlukte_en_yuksek_hz": max_hz_here,
            "en_yuksek_cozunurluk": f"{max_res[0]}x{max_res[1]}",
        })
    _add_monitor_details(displays)
    return displays


def _add_monitor_details(displays):
    """EDID adı, üretici kodu, dahili/harici, bağlantı, ölçek. Okunamazsa alanlar boş kalır."""
    from app.scan.displays import monitors  # noqa: WPS433
    details = {m["aygit"].lower(): m for m in monitors()}
    for display in displays:
        m = details.get(display["aygit"].lower())
        display.update({
            "monitor": (m["edid_ad"] if m else "") or "",
            "uretici_kodu": m["uretici_kodu"] if m else "",
            "urun_kodu": m["urun_kodu"] if m else "",
            "uretici_adi": m["uretici"] if m else "",
            "dahili": bool(m and m["dahili"]),
            "baglanti": m["baglanti"] if m else "",
            "olcek_yuzde": (m["olcek"] or {}).get("yuzde") if m else None,
        })


# ---------------------------------------------------------------------------
# RAM yorumlama
# ---------------------------------------------------------------------------

_CHANNEL_RE = re.compile(r"channel\s*([A-H])\b", re.IGNORECASE)
_DIMM_RE = re.compile(r"DIMM[_\s-]?([A-H])\d", re.IGNORECASE)


def analyze_ram(modules):
    if not modules:
        return {"moduller": [], "kanal": "bilinmiyor"}
    channels = set()
    parsed = []
    for m in modules:
        text = f"{m.get('BankLabel') or ''} {m.get('DeviceLocator') or ''}"
        match = _CHANNEL_RE.search(text) or _DIMM_RE.search(text)
        if match:
            channels.add(match.group(1).upper())
        parsed.append({
            "kapasite_gb": round((m.get("Capacity") or 0) / 1024 ** 3),
            "tur": MEMORY_TYPES.get(m.get("SMBIOSMemoryType"), "bilinmiyor"),
            "form": FORM_FACTORS.get(m.get("FormFactor"), "diğer"),
            "modul_hizi": m.get("Speed"),
            "calisan_hiz": m.get("ConfiguredClockSpeed"),
            "uretici": (m.get("Manufacturer") or "").strip(),
            "parca_no": (m.get("PartNumber") or "").strip(),
            "yuva": (m.get("DeviceLocator") or "").strip(),
        })
    if len(parsed) == 1:
        channel = "tek"
    elif len(channels) >= 2:
        channel = "cift_veya_fazla"
    elif len(channels) == 1:
        channel = "tek"
    else:
        channel = "muhtemelen_cift"  # birden fazla modül var ama yuva adları okunamadı

    # XMP/EXPO Windows'tan doğrudan okunamaz. Yalnızca masaüstü DIMM'lerde,
    # JEDEC taban hızında çalışıyorsa "kapalı olabilir" denir.
    xmp = "bilinmiyor"
    first = parsed[0]
    speed = first["calisan_hiz"] or 0
    if first["form"] == "DIMM" and speed:
        if (first["tur"] == "DDR4" and speed <= 2666) or (first["tur"] == "DDR5" and speed <= 4800):
            xmp = "kapali_olabilir"
        else:
            xmp = "acik_olabilir"
    elif first["form"] == "SODIMM" or first["tur"].startswith("LP"):
        xmp = "laptop_uygulanmaz"
    below_rated = any(m["modul_hizi"] and m["calisan_hiz"] and m["calisan_hiz"] < m["modul_hizi"] for m in parsed)
    return {
        "moduller": parsed,
        "toplam_gb": sum(m["kapasite_gb"] for m in parsed),
        "kanal": channel,
        "xmp_expo": xmp,
        "modul_hizinin_altinda": below_rated,
    }


def _form_factor(chassis, pc_system_type, battery_count):
    types = set(chassis or [])
    if types & PORTABLE_CHASSIS or pc_system_type == 2:
        return "laptop"
    if types & DESKTOP_CHASSIS:
        return "masaustu"
    return "laptop" if battery_count else "masaustu"


def _smi_exe():
    """Mutlak yol: yükseltilmiş tarama PATH'teki (kullanıcının değiştirebildiği) kopyayı çalıştırmasın."""
    old = os.path.join(powershell.SYSTEM32[:3], "Program Files", "NVIDIA Corporation", "NVSMI", "nvidia-smi.exe")
    return old if os.path.isfile(old) else os.path.join(powershell.SYSTEM32, "nvidia-smi.exe")


def _nvidia_smi():
    """nvidia-smi (NVIDIA sürücüsüyle gelir) ile salt okunur bilgi."""
    try:
        proc = subprocess.run(
            [_smi_exe(), "--query-gpu=name,driver_version,memory.total,temperature.gpu,pstate",
             "--format=csv,noheader,nounits"],
            capture_output=True, timeout=15, creationflags=powershell.CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    rows = []
    for line in proc.stdout.decode("utf-8", errors="replace").splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == 5:
            rows.append({"ad": parts[0], "surucu": parts[1], "vram_mb": parts[2],
                         "sicaklik_c": parts[3], "guc_durumu": parts[4], "bar1_mb": None})
    for row, bar1 in zip(rows, _nvidia_bar1()):
        row["bar1_mb"] = bar1
    return rows


def _nvidia_bar1():
    """Kart başına BAR1 boyutu (MiB), nvidia-smi sırasıyla. Resizable BAR kapalıyken 256 MiB'dir;
    açıkken kartın belleği kadar (genelde GB'lar) olur. Okunamazsa boş liste."""
    try:
        proc = subprocess.run([_smi_exe(), "-q", "-d", "MEMORY"], capture_output=True, timeout=15,
                              creationflags=powershell.CREATE_NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []
    sizes, in_bar1 = [], False
    for line in proc.stdout.decode("utf-8", errors="replace").splitlines():
        text = line.strip()
        if text.startswith("BAR1 Memory Usage"):
            in_bar1 = True
        elif in_bar1 and text.startswith("Total"):
            match = re.search(r":\s*(\d+)\s*MiB", text)
            sizes.append(int(match.group(1)) if match else None)
            in_bar1 = False
    return sizes


def link_gpus(gpus, adapters, displays):
    """WMI kart listesine Windows'un rolünü ve sürdüğü ekranları ekler; ekranlara da kartın rolünü.

    rol: "yuksek_performans" (oyunlarda kullanılan), "guc_tasarrufu" (pil dostu, genelde dahili),
    "tek" (tek kart) veya None (okunamadı). Eşleştirme kart adıyla yapılır.

    Ekranı süren kart, ekranın kendi bağdaştırıcısından (EnumDisplayDevices -> ekran_karti) alınır. DXGI çıkışları
    yalnızca o bilgi yoksa kullanılır: hibrit laptopta DXGI, dahili kartın ekranını harici kartın altında da
    gösterebilir (raporda "NVIDIA DISPLAY1'i sürüyor" ile "ekranı AMD sürüyor" çelişkisi buradandı).
    """
    by_name = {a["ad"].casefold(): a for a in adapters}

    def owner(display):
        name = (display.get("ekran_karti") or "").strip().casefold()
        if name:
            return by_name.get(name)
        return next((a for a in adapters if display.get("aygit", "").casefold() in
                     {e.casefold() for e in a["ekranlar"]}), None)

    single = len(adapters) == 1
    for gpu in gpus:
        adapter = by_name.get((gpu.get("ad") or "").strip().casefold())
        if adapter is None:
            gpu.update(rol=None, vram_mb=None, ekran_suruyor=[], birincil_ekran=False)
            continue
        role = "tek" if single else ("yuksek_performans" if adapter["yuksek_performans"]
                                     else "guc_tasarrufu" if adapter["guc_tasarrufu"] else None)
        driven = [d for d in displays if owner(d) is adapter]
        gpu.update(rol=role, vram_mb=adapter["vram_mb"], ekran_suruyor=[d["aygit"] for d in driven],
                   birincil_ekran=any(d["birincil"] for d in driven))
    for display in displays:
        adapter = owner(display)
        display["gpu_rol"] = None if adapter is None else ("tek" if single else "yuksek_performans"
                                                           if adapter["yuksek_performans"] else "guc_tasarrufu"
                                                           if adapter["guc_tasarrufu"] else None)


def collect_hardware():
    data = powershell.run_object(_HARDWARE_PS, timeout=60)
    cs = data.get("cs") or {}
    cpus = powershell.as_list(data.get("cpu"))
    cpu = cpus[0] if cpus else {}
    gpus = []
    for g in powershell.as_list(data.get("gpu")):
        vendor = resolvers.gpu_vendor(g.get("Name") or "", g.get("AdapterCompatibility") or "")
        gpus.append({
            "ad": g.get("Name"),
            "uretici": vendor,
            "surucu_surumu": g.get("DriverVersion"),
            "surucu_tarihi": g.get("DriverDate"),
        })
    displays = collect_displays()
    link_gpus(gpus, gpu_module.dxgi_adapters(), displays)
    chassis = powershell.as_list(data.get("chassis"))
    battery = data.get("battery") or 0
    efficiency = resolvers.cpu_efficiency_classes()
    return {
        "bilgisayar": {
            "uretici": cs.get("Manufacturer"),
            "model": cs.get("Model"),
            "tur": _form_factor(chassis, cs.get("PCSystemType"), battery),
        },
        "cpu": {
            "ad": (cpu.get("Name") or resolvers.cpu_name()).strip(),
            "cekirdek": cpu.get("NumberOfCores"),
            "is_parcacigi": cpu.get("NumberOfLogicalProcessors"),
            "temel_mhz": cpu.get("MaxClockSpeed"),
            "hibrit": len(efficiency) > 1 if efficiency else None,
            "x3d_cift_ccd": resolvers.check_condition({"ad": "x3d_cift_ccd"}),
        },
        "gpu": gpus,
        "nvidia_smi": _nvidia_smi() if any(g["uretici"] == "NVIDIA" for g in gpus) else None,
        "ram": analyze_ram(powershell.as_list(data.get("ram"))),
        "anakart": {
            "uretici": (data.get("bb") or {}).get("Manufacturer"),
            "model": (data.get("bb") or {}).get("Product"),
            "bios_surumu": (data.get("bios") or {}).get("SMBIOSBIOSVersion"),
            "bios_tarihi": (data.get("bios") or {}).get("Tarih"),
        },
        "ekranlar": displays,
    }
