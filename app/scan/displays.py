"""Monitörler: EDID'deki gerçek ad, bağlantı türü, Windows ölçeği (%) ve ölçekleme modu.

Windows'un ekran yapılandırma arabirimi (user32 QueryDisplayConfig /
DisplayConfigGetDeviceInfo / SetDisplayConfig) ctypes ile kullanılır. Belgeler:
learn.microsoft.com/windows/win32/api/winuser/nf-winuser-querydisplayconfig ve
wingdi.h (DISPLAYCONFIG_* yapıları).

- Monitör adı: DISPLAYCONFIG_TARGET_DEVICE_NAME.monitorFriendlyDeviceName; Windows bu
  adı EDID'den alır. EDID'de ad yoksa (çoğu dahili laptop paneli) ad UYDURULMAZ:
  "Dahili ekran" / "Ekran N" ile EDID üretici kodu ve ürün kodu gösterilir.
- Ölçek (%): BELGELENMEMİŞ DisplayConfigGetDeviceInfo/SetDeviceInfo türleri (-3 / -4).
  Windows'un Ayarlar uygulaması ve açık kaynak araçlar (ör. SetDPI, MIT) bunu kullanır;
  Windows sürümüyle değişebilir. Değer "önerilen ölçeğe göre adım" olarak gelir.
- Ölçekleme modu: DISPLAYCONFIG_PATH_TARGET_INFO.scaling (belgelenmiş) yalnızca OKUNUR.
  SetDisplayConfig ile değiştirmek bu bilgisayarda denendi, mod değişmedi (docs/EKRAN.md).

Okuma salt okunurdur; yazma yalnızca set_* fonksiyonlarıyla, motor üzerinden yapılır.
"""

import ctypes
from ctypes import Structure, Union, byref, c_int32, c_long, c_uint16, c_uint32, c_ubyte, c_wchar

from app.core import log

_log = log.get("displays")

QDC_ONLY_ACTIVE_PATHS = 0x2
GET_SOURCE_NAME = 1
GET_TARGET_NAME = 2
GET_DPI_SCALE = -3   # belgelenmemiş
SET_DPI_SCALE = -4   # belgelenmemiş
ERROR_SUCCESS = 0

# Windows'un ölçek basamakları (Ayarlar > Ekran > Ölçek listesi)
DPI_STEPS = (100, 125, 150, 175, 200, 225, 250, 300, 350, 400, 450, 500)

SCALING = {1: "kimlik", 2: "ortala", 3: "germe", 4: "oran", 5: "ozel", 128: "tercih"}

INTERNAL_TECH = {6, 11, 13, 0x80000000}  # LVDS, eDP, UDI gömülü, dahili
CONNECTIONS = {0: "VGA", 4: "DVI", 5: "HDMI", 10: "DisplayPort", 15: "Miracast", 16: "USB-C"}

# EDID üretici kodları (PNP kimliği) — bilinen tablo, tahmin değil
VENDORS = {"AUS": "ASUS", "AUO": "AU Optronics", "BOE": "BOE", "SDC": "Samsung Display", "SAM": "Samsung",
           "LGD": "LG Display", "GSM": "LG", "DEL": "Dell", "ACR": "Acer", "AOC": "AOC", "BNQ": "BenQ",
           "MSI": "MSI", "HPN": "HP", "HWP": "HP", "LEN": "Lenovo", "CMN": "Innolux", "SHP": "Sharp",
           "VSC": "ViewSonic", "GBT": "Gigabyte", "PHL": "Philips", "IVM": "iiyama", "SNY": "Sony",
           "ENC": "EIZO", "NEC": "NEC", "XMI": "Xiaomi", "HKC": "HKC", "KTC": "KTC", "AOU": "AOC"}


class _Luid(Structure):
    _fields_ = [("LowPart", c_uint32), ("HighPart", c_long)]


class _Rational(Structure):
    _fields_ = [("Numerator", c_uint32), ("Denominator", c_uint32)]


class _SourceInfo(Structure):
    _fields_ = [("adapterId", _Luid), ("id", c_uint32), ("modeInfoIdx", c_uint32), ("statusFlags", c_uint32)]


class _TargetInfo(Structure):
    _fields_ = [("adapterId", _Luid), ("id", c_uint32), ("modeInfoIdx", c_uint32), ("outputTechnology", c_uint32),
                ("rotation", c_uint32), ("scaling", c_uint32), ("refreshRate", _Rational),
                ("scanLineOrdering", c_uint32), ("targetAvailable", c_int32), ("statusFlags", c_uint32)]


class _PathInfo(Structure):
    _fields_ = [("sourceInfo", _SourceInfo), ("targetInfo", _TargetInfo), ("flags", c_uint32)]


class _ModeUnion(Union):
    _fields_ = [("raw", c_ubyte * 48)]


class _ModeInfo(Structure):
    _fields_ = [("infoType", c_uint32), ("id", c_uint32), ("adapterId", _Luid), ("mode", _ModeUnion)]


class _Header(Structure):
    _fields_ = [("type", c_int32), ("size", c_uint32), ("adapterId", _Luid), ("id", c_uint32)]


class _SourceName(Structure):
    _fields_ = [("header", _Header), ("viewGdiDeviceName", c_wchar * 32)]


class _TargetName(Structure):
    _fields_ = [("header", _Header), ("flags", c_uint32), ("outputTechnology", c_uint32),
                ("edidManufactureId", c_uint16), ("edidProductCodeId", c_uint16), ("connectorInstance", c_uint32),
                ("monitorFriendlyDeviceName", c_wchar * 64), ("monitorDevicePath", c_wchar * 128)]


class _DpiGet(Structure):
    _fields_ = [("header", _Header), ("minScaleRel", c_int32), ("curScaleRel", c_int32), ("maxScaleRel", c_int32)]


class _DpiSet(Structure):
    _fields_ = [("header", _Header), ("scaleRel", c_int32)]


def _user32():
    return ctypes.windll.user32


def _query():
    """(paths, modes) dizileri: yalnızca etkin ekran yolları."""
    user32 = _user32()
    for _ in range(3):  # sorgu arasında yapılandırma değişirse tekrar dene
        n_paths, n_modes = c_uint32(), c_uint32()
        if user32.GetDisplayConfigBufferSizes(QDC_ONLY_ACTIVE_PATHS, byref(n_paths), byref(n_modes)) != ERROR_SUCCESS:
            raise OSError("GetDisplayConfigBufferSizes başarısız")
        paths = (_PathInfo * n_paths.value)()
        modes = (_ModeInfo * n_modes.value)()
        code = user32.QueryDisplayConfig(QDC_ONLY_ACTIVE_PATHS, byref(n_paths), paths, byref(n_modes), modes, None)
        if code == ERROR_SUCCESS:
            return paths[:n_paths.value], paths, modes, n_paths.value, n_modes.value
        if code != 122:  # ERROR_INSUFFICIENT_BUFFER
            raise OSError(f"QueryDisplayConfig başarısız ({code})")
    raise OSError("QueryDisplayConfig başarısız")


def _header(struct, kind, adapter, target_id):
    struct.header.type = kind
    struct.header.size = ctypes.sizeof(struct)
    struct.header.adapterId = adapter
    struct.header.id = target_id
    return struct


def _device_info(struct):
    return _user32().DisplayConfigGetDeviceInfo(byref(struct.header)) == ERROR_SUCCESS


def edid_code(manufacture_id, product_id):
    """EDID üretici kodu (3 harf) ve ürün kodu (4 onaltılık hane)."""
    value = ((manufacture_id & 0xFF) << 8) | (manufacture_id >> 8)  # EDID'de büyük sonlu
    letters = "".join(chr(((value >> shift) & 0x1F) + 64) for shift in (10, 5, 0))
    if not letters.isalpha():
        letters = ""
    return letters, f"{product_id:04X}"


def _dpi(path):
    info = _header(_DpiGet(), GET_DPI_SCALE, path.sourceInfo.adapterId, path.sourceInfo.id)
    if not _device_info(info):
        return None
    recommended = -info.minScaleRel
    steps = [DPI_STEPS[i] for i in range(len(DPI_STEPS)) if 0 <= i <= recommended + info.maxScaleRel]
    current_index = recommended + info.curScaleRel
    if not 0 <= recommended < len(DPI_STEPS) or not 0 <= current_index < len(DPI_STEPS):
        return None
    return {"yuzde": DPI_STEPS[current_index], "onerilen": DPI_STEPS[recommended], "secenekler": steps}


def monitors():
    """Etkin monitörler: [{aygit, ad, edid_ad, uretici_kodu, urun_kodu, uretici, dahili, baglanti,
    monitor_yolu, olcekleme, olcek}]. Okunamazsa boş liste."""
    try:
        active, *_rest = _query()
    except (OSError, AttributeError) as exc:
        _log.warning("Ekran yapılandırması okunamadı: %s", exc)
        return []
    result = []
    for path in active:
        source = _header(_SourceName(), GET_SOURCE_NAME, path.sourceInfo.adapterId, path.sourceInfo.id)
        target = _header(_TargetName(), GET_TARGET_NAME, path.targetInfo.adapterId, path.targetInfo.id)
        if not _device_info(source):
            continue
        has_target = _device_info(target)
        tech = path.targetInfo.outputTechnology
        code, product = edid_code(target.edidManufactureId, target.edidProductCodeId) if has_target else ("", "")
        friendly = target.monitorFriendlyDeviceName.strip() if has_target and target.flags & 0x1 else ""
        result.append({
            "aygit": source.viewGdiDeviceName,
            "edid_ad": friendly,
            "uretici_kodu": code,
            "urun_kodu": product if code else "",
            "uretici": VENDORS.get(code, ""),
            "dahili": tech in INTERNAL_TECH,
            "baglanti": "dahili" if tech in INTERNAL_TECH else CONNECTIONS.get(tech, "diger"),
            "monitor_yolu": target.monitorDevicePath if has_target else "",
            "olcekleme": SCALING.get(path.targetInfo.scaling, "bilinmiyor"),
            "olcek": _dpi(path),
        })
    return result


def find_device(monitor_path, fallback):
    """Monitör yolundan (kalıcı) şu anki \\\\.\\DISPLAYn adını bulur; ekran numaraları yeniden
    başlatınca değişebildiği için geri alma bununla yapılır."""
    if monitor_path:
        for item in monitors():
            if item["monitor_yolu"].lower() == monitor_path.lower():
                return item["aygit"]
    return fallback


def _path_for(device):
    _active, paths, modes, n_paths, n_modes = _query()
    for i in range(n_paths):
        source = _header(_SourceName(), GET_SOURCE_NAME, paths[i].sourceInfo.adapterId, paths[i].sourceInfo.id)
        if _device_info(source) and source.viewGdiDeviceName.lower() == device.lower():
            return paths, modes, n_paths, n_modes, i
    raise OSError(f"Ekran bulunamadı: {device}")


def set_scale(device, percent):
    """Windows ölçeğini (%) değiştirir. BELGELENMEMİŞ arabirim; anında uygulanır."""
    paths, _modes, _n_paths, _n_modes, i = _path_for(device)
    path = paths[i]
    info = _dpi(path)
    if info is None or int(percent) not in info["secenekler"]:
        raise ValueError(f"%{percent} bu ekranda desteklenmiyor")
    recommended = DPI_STEPS.index(info["onerilen"])
    struct = _header(_DpiSet(), SET_DPI_SCALE, path.sourceInfo.adapterId, path.sourceInfo.id)
    struct.scaleRel = DPI_STEPS.index(int(percent)) - recommended
    if _user32().DisplayConfigSetDeviceInfo(byref(struct.header)) != ERROR_SUCCESS:
        raise OSError("Ölçek değiştirilemedi")


def label(display, index):
    """Ekranın görünen adı. EDID'de ad varsa o (üretici adıyla); yoksa UYDURULMAZ:
    "Dahili ekran" / "Ekran N" ve parantez içinde üretici ile EDID kodu."""
    from app.core.i18n import t  # noqa: WPS433

    name = (display.get("monitor") or display.get("edid_ad") or "").strip()
    if name.lower().startswith("generic"):
        name = ""
    vendor = display.get("uretici_adi") or display.get("uretici") or ""
    if name:
        return f"{vendor} {name}" if vendor and vendor.lower() not in name.lower() else name
    code = f"{display.get('uretici_kodu') or ''} {display.get('urun_kodu') or ''}".strip()
    base = t("ui.ekran_dahili") if display.get("dahili") else t("ui.ekran_adi", no=index)
    extra = ", ".join(x for x in (vendor, code) if x)
    return f"{base} ({extra})" if extra else base
