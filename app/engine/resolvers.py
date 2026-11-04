"""Yer tutucu çözümleyiciler ve koşul denetimleri.

tweaks_app.json içindeki bazı işlemler sisteme göre değişen değerler içerir,
örneğin `{{ag_arabirim_guid}}` (ağ kartının kimliği) veya `{{amd_gpu_anahtari}}`
(AMD ekran kartının registry alt anahtarı). Bu modül çalışma anında bu
değerleri bulur. Bulamazsa ayar gizlenir; asla tahmin edilmez.

Bu modüldeki her şey yalnızca OKUMA yapar; sistemde hiçbir ayarı değiştirmez.
"""

import ctypes
import functools
import re
import subprocess
import threading
from ctypes import wintypes

from app.core import powershell, registry

PLACEHOLDER_RE = re.compile(r"\{\{([a-z_]+)\}\}")

DISPLAY_CLASS = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
AUDIO_RENDER = r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Render"
PKEY_DEVICE_DESC = "{a45c254e-df1c-4efd-8020-67d146a850e0},2"
DEVICE_STATE_ACTIVE = 1
NDIS_MEDIUM_WIFI = 9  # NdisPhysicalMediumNative802_11

X3D_DUAL_CCD_RE = re.compile(r"\b(7900X3D|7950X3D|9900X3D|9950X3D)\b", re.IGNORECASE)


def _shared_cache(func):
    """lru_cache + kilit: tarama ve durum iş parçacıkları aynı anda sorunca tek süreç açılsın (eskiden 7 powershell.exe)."""
    cached, lock = functools.lru_cache(maxsize=None)(func), threading.Lock()

    @functools.wraps(func)
    def wrapper():
        with lock:
            return cached()
    wrapper.cache_clear = cached.cache_clear
    return wrapper


# ---------------------------------------------------------------------------
# Yer tutucu yardımcıları
# ---------------------------------------------------------------------------

def find_placeholders(obj):
    """Bir veri yapısındaki tüm `{{ad}}` yer tutucularının adlarını döndürür."""
    found = set()
    if isinstance(obj, str):
        found.update(PLACEHOLDER_RE.findall(obj))
    elif isinstance(obj, dict):
        for value in obj.values():
            found |= find_placeholders(value)
    elif isinstance(obj, list):
        for value in obj:
            found |= find_placeholders(value)
    return found


def substitute(obj, context):
    """Yer tutucuları `context` sözlüğündeki değerlerle değiştirilmiş kopya döndürür."""
    if isinstance(obj, str):
        return PLACEHOLDER_RE.sub(lambda m: str(context[m.group(1)]), obj)
    if isinstance(obj, dict):
        return {key: substitute(value, context) for key, value in obj.items()}
    if isinstance(obj, list):
        return [substitute(value, context) for value in obj]
    return obj


# ---------------------------------------------------------------------------
# Sistem bilgisi (önbellekli, salt okunur)
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=None)
def cpu_name():
    name = registry.read("HKLM", r"HARDWARE\DESCRIPTION\System\CentralProcessor\0", "ProcessorNameString")
    return (name or "").strip()


@functools.lru_cache(maxsize=None)
def cpu_efficiency_classes():
    """Çekirdeklerin verimlilik sınıflarını döndürür (P/E çekirdek tespiti).

    Birden fazla farklı sınıf varsa işlemci hibrittir (ör. Intel 12. nesil+
    P ve E çekirdekleri). Okunamazsa boş küme döner.
    """
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    func = kernel32.GetLogicalProcessorInformationEx
    func.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD)]
    func.restype = wintypes.BOOL

    relation_processor_core = 0
    length = wintypes.DWORD(0)
    func(relation_processor_core, None, ctypes.byref(length))
    if length.value == 0:
        return frozenset()
    buffer = ctypes.create_string_buffer(length.value)
    if not func(relation_processor_core, buffer, ctypes.byref(length)):
        return frozenset()

    classes = set()
    raw = buffer.raw[: length.value]
    offset = 0
    # SYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX: Relationship(4) Size(4)
    # ardından PROCESSOR_RELATIONSHIP: Flags(1) EfficiencyClass(1) ...
    while offset + 10 <= len(raw):
        size = int.from_bytes(raw[offset + 4: offset + 8], "little")
        if size == 0:
            break
        classes.add(raw[offset + 9])
        offset += size
    return frozenset(classes)


@functools.lru_cache(maxsize=None)
def display_adapters():
    """Ekran kartlarını registry'den okur: [{anahtar, ad, saglayici, ulps_var}]."""
    adapters = []
    for sub in registry.subkeys("HKLM", DISPLAY_CLASS):
        if not sub.isdigit():
            continue  # "Properties" gibi erişimi kısıtlı anahtarlar atlanır
        path = DISPLAY_CLASS + "\\" + sub
        desc = registry.read("HKLM", path, "DriverDesc")
        if not desc:
            continue
        adapters.append({
            "anahtar": sub,
            "ad": desc,
            "saglayici": registry.read("HKLM", path, "ProviderName") or "",
            "ulps_var": registry.read("HKLM", path, "EnableUlps") is not None,
        })
    return tuple(adapters)


def gpu_vendor(name, provider=""):
    text = f"{name} {provider}".lower()
    if "nvidia" in text:
        return "NVIDIA"
    if "amd" in text or "radeon" in text or "advanced micro devices" in text or "ati " in text:
        return "AMD"
    if "intel" in text:
        return "Intel"
    return None


def gpu_vendors():
    """Sistemdeki gerçek ekran kartı üreticileri (sanal/temel sürücüler hariç)."""
    return sorted({v for v in (gpu_vendor(a["ad"], a["saglayici"]) for a in display_adapters()) if v})


@functools.lru_cache(maxsize=None)
def monitor_count():
    return ctypes.windll.user32.GetSystemMetrics(80)  # SM_CMONITORS


_primed = {}


def prime_from_scan(scan):
    """Taramanın zaten okuduğu bilgileri yeniden okumamak için önbelleğe koyar."""
    storage = (scan.get("bolumler") or {}).get("depolama")
    if storage:
        _primed["disk_types"] = tuple(d["tur"] for d in storage.get("diskler", []))


@_shared_cache
def _disk_media_rows():
    return tuple(str(row.get("tur", "")) for row in powershell.run_json(
        "Get-PhysicalDisk | Select-Object @{n='tur';e={[string]$_.MediaType}}"))


def physical_disk_media_types():
    """Fiziksel disklerin türleri (ör. 'HDD', 'SSD'). Okunamazsa None."""
    if "disk_types" not in _primed:
        try:
            _primed["disk_types"] = _disk_media_rows()
        except powershell.PowerShellError:
            return None
    return _primed["disk_types"]


@_shared_cache
def physical_net_adapters():
    """Fiziksel ağ bağdaştırıcıları (takılı olmayanlar hariç). Okunamazsa None.

    Gizlilik: MAC adresi okunmaz.
    """
    try:
        rows = powershell.run_json(
            "Get-NetAdapter -Physical | Where-Object Status -ne 'Not Present' | "
            "Select-Object Name, InterfaceDescription, InterfaceGuid, NdisPhysicalMedium, LinkSpeed, "
            "@{n='HizBit';e={[uint64]$_.Speed}}, @{n='Durum';e={[string]$_.Status}}"
        )
    except powershell.PowerShellError:
        return None
    return tuple(rows)


@_shared_cache
def _power_scheme_list():
    try:
        proc = subprocess.run(
            ["powercfg", "/list"],
            capture_output=True,
            timeout=15,
            creationflags=powershell.CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    # GUID'ler dil ayarından bağımsızdır; metnin geri kalanı önemsizdir.
    return proc.stdout.decode("utf-8", errors="replace").lower()


NET_CLASS = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}"


@functools.lru_cache(maxsize=None)
def _nic_class_keys():
    """Ağ kartı arabirim GUID'i (küçük harf) → sürücü registry anahtarı."""
    keys = {}
    for sub in registry.subkeys("HKLM", NET_CLASS):
        if sub.isdigit():
            path = NET_CLASS + "\\" + sub
            guid = registry.read("HKLM", path, "NetCfgInstanceId")
            if guid:
                keys[guid.lower()] = path
    return keys


def _nic_key(adapter_name):
    for a in physical_net_adapters() or ():
        if a.get("Name") == adapter_name and a.get("InterfaceGuid"):
            return _nic_class_keys().get(a["InterfaceGuid"].lower())
    return None


def nic_property(adapter_name, keyword):
    """Ağ kartı gelişmiş özelliğinin değeri, doğrudan registry'den (PowerShell'den
    yaklaşık 1000 kat hızlı). Değer yazılmamışsa sürücünün varsayılanı. Yoksa None."""
    key = _nic_key(adapter_name)
    if key is None:
        return None
    value = registry.read("HKLM", key, keyword)
    if value is None:
        value = registry.read("HKLM", f"{key}\\Ndi\\Params\\{keyword}", "default")
    return None if value is None else str(value)


def nic_valid_values(adapter_name, keyword):
    """Sürücünün kabul ettiği değerler; özellik yoksa boş küme."""
    key = _nic_key(adapter_name)
    if key is None:
        return set()
    return set(registry.values("HKLM", f"{key}\\Ndi\\Params\\{keyword}\\enum"))


def clear_cache():
    """Yeniden tarama öncesi önbelleği temizler."""
    _primed.clear()
    for func in (cpu_name, cpu_efficiency_classes, display_adapters, monitor_count,
                 physical_net_adapters, _power_scheme_list, _nic_class_keys, _disk_media_rows):
        func.cache_clear()


# ---------------------------------------------------------------------------
# Koşullar: True / False / None (None = doğrulanamadı)
# ---------------------------------------------------------------------------

def _cond_hdd_var(_params):
    types = physical_disk_media_types()
    if types is None:
        return None
    return any(t in ("HDD", "3") for t in types)


def _cond_wifi_var(_params):
    adapters = physical_net_adapters()
    if adapters is None:
        return None
    return any(a.get("NdisPhysicalMedium") == NDIS_MEDIUM_WIFI for a in adapters)


def _cond_guc_plani_mevcut(params):
    listing = _power_scheme_list()
    if listing is None:
        return None
    return params["guid"].lower() in listing


def _cond_x3d_cift_ccd(_params):
    name = cpu_name()
    if not name:
        return None
    return bool(X3D_DUAL_CCD_RE.search(name))


def _cond_hibrit_cpu(_params):
    classes = cpu_efficiency_classes()
    if not classes:
        return None
    return len(classes) > 1


def _cond_hibrit_gpu(_params):
    # İki veya daha fazla gerçek ekran kartı (ör. Intel iGPU + NVIDIA dGPU).
    return sum(1 for a in display_adapters() if gpu_vendor(a["ad"], a["saglayici"])) >= 2


def _cond_cpu_saglayici(params):
    name = cpu_name().lower()
    if not name:
        return None
    return params["saglayici"].lower() in name


def _cond_coklu_monitor(_params):
    return monitor_count() >= 2


def _cond_onedrive_kurulu(_params):
    """OneDrive programı kurulu mu (kullanıcı veya tüm kullanıcılar için kurulum klasörleri)."""
    import os  # noqa: WPS433
    places = (("LOCALAPPDATA", ("Microsoft", "OneDrive", "OneDrive.exe")),
              ("ProgramFiles", ("Microsoft OneDrive", "OneDrive.exe")),
              ("ProgramFiles(x86)", ("Microsoft OneDrive", "OneDrive.exe")))
    return any(os.environ.get(var) and os.path.isfile(os.path.join(os.environ[var], *parts)) for var, parts in places)


def _cond_gpu_saglayici(params):
    return params["saglayici"] in gpu_vendors()


def _cond_windows_ozelligi_mevcut(params):
    return _features_present(tuple(params["ozellikler"]))


@functools.lru_cache(maxsize=None)
def _features_present(features):
    """Bu Windows sürümünde özellik var mı; oturum boyunca değişmez (uygunluk tazelemesi her seferinde PowerShell açıyordu)."""
    try:
        rows = powershell.run_json(
            f"{powershell.features_query(features)} | Select-Object FeatureName",
            timeout=60,
        )
    except powershell.PowerShellError:
        return None  # genelde yönetici izni olmadığında
    return len(rows) > 0


CONDITIONS = {
    "hdd_var": _cond_hdd_var,
    "wifi_var": _cond_wifi_var,
    "guc_plani_mevcut": _cond_guc_plani_mevcut,
    "x3d_cift_ccd": _cond_x3d_cift_ccd,
    "hibrit_cpu": _cond_hibrit_cpu,
    "hibrit_gpu": _cond_hibrit_gpu,
    "cpu_saglayici": _cond_cpu_saglayici,
    "coklu_monitor": _cond_coklu_monitor,
    "onedrive_kurulu": _cond_onedrive_kurulu,
    "gpu_saglayici": _cond_gpu_saglayici,
    "windows_ozelligi_mevcut": _cond_windows_ozelligi_mevcut,
}


def check_condition(cond):
    """Tek bir koşulu değerlendirir. `degil: true` sonucu tersine çevirir."""
    func = CONDITIONS.get(cond["ad"])
    if func is None:
        return None
    try:
        result = func(cond.get("parametreler", {}))
    except Exception:  # okuma hatası ayarı göstermek için sebep değildir
        return None
    if result is None:
        return None
    return (not result) if cond.get("degil") else result


# ---------------------------------------------------------------------------
# Çözümleyiciler: yer tutucu değerlerinin listesini döndürür
# ---------------------------------------------------------------------------

def _res_ag_arabirimleri(_params):
    """Bağlı (Up) fiziksel ağ kartları: ad ve arabirim GUID'i."""
    adapters = physical_net_adapters() or ()
    return [
        {"ag_bagdastirici": a["Name"], "ag_arabirim_guid": a["InterfaceGuid"]}
        for a in adapters
        if a.get("Durum") == "Up" and a.get("InterfaceGuid")
    ]


def _res_ag_ozellik_destekleyen(params):
    """Belirtilen gelişmiş özellik anahtar kelimesini destekleyen ağ kartları."""
    adapters = physical_net_adapters() or ()
    wanted = params["anahtarlar"]
    if params.get("yalnizca_kablolu"):
        adapters = [a for a in adapters if a.get("NdisPhysicalMedium") != NDIS_MEDIUM_WIFI]
    needed = {str(params.get("acik", "0")), str(params.get("kapali", "1"))}
    result = []
    for adapter in adapters:
        for keyword in wanted:
            valid = nic_valid_values(adapter["Name"], keyword)
            # Özellik yoksa veya açık/kapalı değerleri sürücü kabul etmiyorsa atla.
            if valid and needed.issubset(valid):
                result.append({"ag_bagdastirici": adapter["Name"], "ag_ozellik": keyword})
    return result


def _res_amd_gpu_anahtarlari(_params):
    """EnableUlps değeri bulunan AMD ekran kartı alt anahtarları (ör. 0000)."""
    return [
        {"amd_gpu_anahtari": a["anahtar"]}
        for a in display_adapters()
        if a["ulps_var"] and gpu_vendor(a["ad"], a["saglayici"]) == "AMD"
    ]


def _res_ses_cikis_cihazlari(_params):
    """Etkin ses çıkış cihazları (hoparlör, kulaklık...)."""
    result = []
    for sub in registry.subkeys("HKLM", AUDIO_RENDER):
        path = AUDIO_RENDER + "\\" + sub
        if registry.read("HKLM", path, "DeviceState") != DEVICE_STATE_ACTIVE:
            continue
        name = registry.read("HKLM", path + r"\Properties", PKEY_DEVICE_DESC)
        result.append({"ses_cihazi": sub, "ses_cihazi_adi": name or sub})
    return result


def _res_ekranlar(_params):
    """Masaüstüne bağlı ekranlar (her monitör ayrı)."""
    from app.scan.displays import label, monitors  # noqa: WPS433
    from app.scan.hardware import attached_display_devices  # noqa: WPS433
    details = {m["aygit"].lower(): m for m in monitors()}
    result = []
    for index, d in enumerate(attached_display_devices(), 1):
        m = details.get(d["aygit"].lower())
        result.append({"ekran_aygiti": d["aygit"], "ekran_adi": label(m, index) if m else d["ad"],
                       "monitor_yolu": m["monitor_yolu"] if m else ""})
    return result


RESOLVERS = {
    "ekranlar": _res_ekranlar,
    "ag_arabirimleri": _res_ag_arabirimleri,
    "ag_ozellik_destekleyen": _res_ag_ozellik_destekleyen,
    "amd_gpu_anahtarlari": _res_amd_gpu_anahtarlari,
    "ses_cikis_cihazlari": _res_ses_cikis_cihazlari,
}


# ---------------------------------------------------------------------------
# Ana giriş noktası
# ---------------------------------------------------------------------------

class Resolution:
    """Bir ayarın bu bilgisayarda gösterilip gösterilmeyeceği ve somut değerleri."""

    def __init__(self, visible, contexts=None, reason=""):
        self.visible = visible
        self.contexts = contexts or []  # her biri bir yer tutucu sözlüğü
        self.reason = reason

    def __repr__(self):
        return f"Resolution(visible={self.visible}, n={len(self.contexts)}, reason={self.reason!r})"


def resolve(islem):
    """İşlemin yer tutucularını çözer.

    Döndürür: Resolution. `visible=False` ise ayar arayüzde gizlenmelidir.
    `contexts` listesi, işlemin her bir somut kopyası için yer tutucu
    değerlerini içerir (ör. iki ağ kartı varsa iki sözlük).
    """
    needed = find_placeholders(islem)
    spec = islem.get("cozumleyici")

    if not spec:
        if needed:
            return Resolution(False, reason=f"Çözümleyicisi olmayan yer tutucu: {sorted(needed)}")
        return Resolution(True, [{}])

    func = RESOLVERS.get(spec["ad"])
    if func is None:
        return Resolution(False, reason=f"Bilinmeyen çözümleyici: {spec['ad']}")
    try:
        contexts = func(spec.get("parametreler", {}))
    except Exception as exc:
        return Resolution(False, reason=f"Çözümleyici hatası: {exc}")
    if not contexts:
        return Resolution(False, reason="Bu bilgisayarda uygun donanım/değer bulunamadı")

    missing = needed - set(contexts[0])
    if missing:
        return Resolution(False, reason=f"Çözülemeyen yer tutucu: {sorted(missing)}")
    return Resolution(True, contexts)


def expand_steps(islem, resolution):
    """Çözülmüş bağlamlarla işlemin adımlarını somut adımlara genişletir."""
    steps = []
    for context in resolution.contexts:
        for step in islem.get("adimlar", []):
            steps.append(substitute(step, context))
    return steps
