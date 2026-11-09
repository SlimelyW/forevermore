"""NVIDIA sürücü ayarları (DRS) — NVAPI ile kendi kodumuz, ctypes.

Kaynak: NVIDIA'nın resmi NVAPI deposu (github.com/NVIDIA/nvapi, MIT lisansı).
- Fonksiyon kimlikleri: nvapi_interface.h
- Ayar kimlikleri ve değerleri: NvApiDriverSettings.h
- NVDRS_SETTING yapısı: nvapi.h (#pragma pack(4), NVAPI_BINARY_DATA_MAX = 4096)

nvapi64.dll NVIDIA sürücüsüyle gelir; uygulamaya GÖMÜLMEZ. Yalnızca herkese açık
(belgelenmiş) fonksiyonlar kullanılır. Dijital canlılık (DVC) fonksiyonları herkese
açık NVAPI'de olmadığı için uygulanmadı.

Ayarlar NVIDIA Denetim Masası'ndaki "Genel ayarlar"ın karşılığı olan geçerli
genel profile yazılır. Yazmak yönetici izni ister.

Ekran ölçeklemesi (Revizyon 2 Faz 6): NvAPI_DISP_GetDisplayConfig / SetDisplayConfig; yapılar nvapi.h'deki
NV_DISPLAYCONFIG_PATH_INFO_V2 ve NV_DISPLAYCONFIG_PATH_ADVANCED_TARGET_INFO_V1 (#pragma pack(8)).

Yedek yöntem (NVIDIA Profile Inspector, MIT): `npi_import` — yalnızca NVAPI'ye
erişilemezse ve kullanıcı tools klasörüne aracı koyduysa; `-silentImport
-mergeImport` ile (yalnızca -silentImport profili SIFIRLAR).
"""

import ctypes
import os
import subprocess
import tempfile
from ctypes import POINTER, byref, c_char_p, c_int, c_uint8, c_uint16, c_uint32, c_uint64, c_ubyte, c_void_p

from app.core import log, paths, powershell

_log = log.get("nvidia")

IDS = {
    "Initialize": 0x0150E828,
    "DRS_CreateSession": 0x0694D52E,
    "DRS_DestroySession": 0xDAD9CFF8,
    "DRS_LoadSettings": 0x375DBD6B,
    "DRS_SaveSettings": 0xFCBC7E14,
    "DRS_GetCurrentGlobalProfile": 0x617BFF9F,
    "DRS_GetSetting": 0x73BF8338,
    "DRS_SetSetting": 0x577DD202,
    "DRS_RestoreProfileDefaultSetting": 0x53F0381E,
    "DISP_GetDisplayConfig": 0x11ABCCF8,
    "DISP_SetDisplayConfig": 0x5D8CF8DE,
    "DISP_GetDisplayIdByDisplayName": 0xAE457190,
}
NVAPI_OK = 0
NVAPI_SETTING_NOT_FOUND = -160
NVDRS_DWORD_TYPE = 0
LOCATION_CURRENT_PROFILE = 0


class _Binary(ctypes.Structure):
    _pack_ = 4
    _fields_ = [("valueLength", c_uint32), ("valueData", c_ubyte * 4096)]


class _Value(ctypes.Union):
    _pack_ = 4
    _fields_ = [("u32", c_uint32), ("binary", _Binary), ("wsz", c_uint16 * 2048), ("u64", c_uint64)]


class NvdrsSetting(ctypes.Structure):
    _pack_ = 4
    _fields_ = [("version", c_uint32), ("settingName", c_uint16 * 2048), ("settingId", c_uint32),
                ("settingType", c_int), ("settingLocation", c_int), ("isCurrentPredefined", c_uint32),
                ("isPredefinedValid", c_uint32), ("predefined", _Value), ("current", _Value)]


SETTING_VERSION = ctypes.sizeof(NvdrsSetting) | (1 << 16)  # MAKE_NVAPI_VERSION(NVDRS_SETTING_V1, 1)


class NvapiError(Exception):
    def __init__(self, func, status):
        super().__init__(f"{func}: NVAPI durum {status}")
        self.status = status


class _Session:
    """NVAPI oturumu; her çağrıda açılıp kapanır (sürücü ayarları başka yerden değişebilir)."""

    _api = None

    @classmethod
    def api(cls):
        if cls._api is None:
            dll = ctypes.CDLL("nvapi64.dll")
            query = dll.nvapi_QueryInterface
            query.restype = c_void_p
            query.argtypes = [c_uint32]
            funcs = {}
            protos = {
                "Initialize": [],
                "DRS_CreateSession": [ctypes.POINTER(c_void_p)],
                "DRS_DestroySession": [c_void_p],
                "DRS_LoadSettings": [c_void_p],
                "DRS_SaveSettings": [c_void_p],
                "DRS_GetCurrentGlobalProfile": [c_void_p, ctypes.POINTER(c_void_p)],
                "DRS_GetSetting": [c_void_p, c_void_p, c_uint32, ctypes.POINTER(NvdrsSetting)],
                "DRS_SetSetting": [c_void_p, c_void_p, ctypes.POINTER(NvdrsSetting)],
                "DRS_RestoreProfileDefaultSetting": [c_void_p, c_void_p, c_uint32],
            }
            for name, argtypes in protos.items():
                pointer = query(IDS[name])
                if not pointer:
                    raise OSError(f"NVAPI fonksiyonu bulunamadı: {name}")
                funcs[name] = ctypes.CFUNCTYPE(c_int, *argtypes)(pointer)
            status = funcs["Initialize"]()
            if status != NVAPI_OK:
                raise NvapiError("Initialize", status)
            cls._api = funcs
        return cls._api

    def __enter__(self):
        self.f = self.api()
        self.session = c_void_p()
        self._check("DRS_CreateSession", ctypes.byref(self.session))
        self._check("DRS_LoadSettings", self.session)
        self.profile = c_void_p()
        self._check("DRS_GetCurrentGlobalProfile", self.session, ctypes.byref(self.profile))
        return self

    def _check(self, name, *args):
        status = self.f[name](*args)
        if status != NVAPI_OK:
            raise NvapiError(name, status)
        return status

    def __exit__(self, *_exc):
        self.f["DRS_DestroySession"](self.session)


def available():
    try:
        _Session.api()
        return True
    except (OSError, NvapiError) as exc:
        _log.info("NVAPI kullanılamıyor: %s", exc)
        return False


def get_settings(setting_ids):
    """Birden çok ayarı tek oturumda okur: {ayar_id: {'deger', 'ozel'}}."""
    result = {}
    with _Session() as s:
        for setting_id in setting_ids:
            setting = NvdrsSetting()
            setting.version = SETTING_VERSION
            status = s.f["DRS_GetSetting"](s.session, s.profile, setting_id, ctypes.byref(setting))
            if status == NVAPI_SETTING_NOT_FOUND:
                result[setting_id] = {"deger": None, "ozel": False}
            elif status == NVAPI_OK:
                custom = setting.settingLocation == LOCATION_CURRENT_PROFILE and not setting.isCurrentPredefined
                result[setting_id] = {"deger": int(setting.current.u32), "ozel": bool(custom)}
            else:
                raise NvapiError("DRS_GetSetting", status)
    return result


def set_setting(setting_id, value):
    """value None ise ayar sürücü varsayılanına döndürülür."""
    _log.info("NVIDIA ayarı %#010x = %s", setting_id, "varsayılan" if value is None else value)
    with _Session() as s:
        if value is None:
            status = s.f["DRS_RestoreProfileDefaultSetting"](s.session, s.profile, setting_id)
            if status not in (NVAPI_OK, NVAPI_SETTING_NOT_FOUND):
                raise NvapiError("DRS_RestoreProfileDefaultSetting", status)
        else:
            setting = NvdrsSetting()
            setting.version = SETTING_VERSION
            setting.settingId = setting_id
            setting.settingType = NVDRS_DWORD_TYPE
            setting.current.u32 = int(value) & 0xFFFFFFFF
            s._check("DRS_SetSetting", s.session, s.profile, ctypes.byref(setting))
        s._check("DRS_SaveSettings", s.session)


# ---------------------------------------------------------------------------
# Ekran ölçeklemesi (NVIDIA Denetim Masası > Masaüstü boyutunu ve konumunu ayarla)
# ---------------------------------------------------------------------------
# NV_SCALING: "Balanced" değerlerinde kart en yakın modu gönderir, ölçeklemeyi monitör yapar
# (eski adı NV_SCALING_MONITOR_SCALING); "Force GPU" değerlerinde ölçeklemeyi ekran kartı yapar.
SCALING_MONITOR = (6, 1, 7)  # en-boy oranı, tam ekran, ölçekleme yok
SCALING_GPU = (5, 2, 3, 8)  # en-boy oranı, tam ekran, ölçekleme yok, tamsayı
SAVE_TO_PERSISTENCE = 0x2


class _TimingExt(ctypes.Structure):
    _fields_ = [("flag", c_uint32), ("rr", c_uint16), ("rrx1k", c_uint32), ("aspect", c_uint32),
                ("rep", c_uint16), ("status", c_uint32), ("name", c_uint8 * 40)]


class _Timing(ctypes.Structure):
    _fields_ = [("HVisible", c_uint16), ("HBorder", c_uint16), ("HFrontPorch", c_uint16), ("HSyncWidth", c_uint16),
                ("HTotal", c_uint16), ("HSyncPol", c_uint8), ("VVisible", c_uint16), ("VBorder", c_uint16),
                ("VFrontPorch", c_uint16), ("VSyncWidth", c_uint16), ("VTotal", c_uint16), ("VSyncPol", c_uint8),
                ("interlaced", c_uint16), ("pclk", c_uint32), ("etc", _TimingExt)]


class _Advanced(ctypes.Structure):
    # bit alanları (interlaced, primary, ...) tek NvU32 olarak tutulur ve olduğu gibi geri yazılır
    _fields_ = [("version", c_uint32), ("rotation", c_int), ("scaling", c_int), ("refreshRate1K", c_uint32),
                ("flags", c_uint32), ("connector", c_int), ("tvFormat", c_int), ("timingOverride", c_int),
                ("timing", _Timing)]


class _Target(ctypes.Structure):
    _fields_ = [("displayId", c_uint32), ("details", POINTER(_Advanced)), ("targetId", c_uint32)]


class _SourceMode(ctypes.Structure):
    _fields_ = [("width", c_uint32), ("height", c_uint32), ("colorDepth", c_uint32), ("colorFormat", c_int),
                ("x", c_int), ("y", c_int), ("spanning", c_int), ("flags", c_uint32)]


class _Path(ctypes.Structure):
    _fields_ = [("version", c_uint32), ("sourceId", c_uint32), ("targetInfoCount", c_uint32),
                ("targetInfo", POINTER(_Target)), ("sourceModeInfo", POINTER(_SourceMode)),
                ("flags", c_uint32), ("pOSAdapterID", c_void_p)]


PATH_VERSION = ctypes.sizeof(_Path) | (2 << 16)
ADVANCED_VERSION = ctypes.sizeof(_Advanced) | (1 << 16)
_display_funcs = {}


def _display_api():
    if not _display_funcs:
        _Session.api()  # NvAPI_Initialize
        query = ctypes.CDLL("nvapi64.dll").nvapi_QueryInterface
        query.restype = c_void_p
        query.argtypes = [c_uint32]
        protos = {"DISP_GetDisplayConfig": [POINTER(c_uint32), POINTER(_Path)],
                  "DISP_SetDisplayConfig": [c_uint32, POINTER(_Path), c_uint32],
                  "DISP_GetDisplayIdByDisplayName": [c_char_p, POINTER(c_uint32)]}
        for name, argtypes in protos.items():
            pointer = query(IDS[name])
            if not pointer:
                raise OSError(f"NVAPI fonksiyonu bulunamadı: {name}")
            _display_funcs[name] = ctypes.CFUNCTYPE(c_int, *argtypes)(pointer)
    return _display_funcs


def _check(name, status):
    if status != NVAPI_OK:
        raise NvapiError(name, status)


def _display_config():
    """Üç geçişli okuma (nvapi.h'deki kullanım). Dönen nesneler birbirine işaret eder; birlikte tutulur."""
    f = _display_api()
    count = c_uint32()
    _check("DISP_GetDisplayConfig", f["DISP_GetDisplayConfig"](byref(count), None))
    paths_ = (_Path * count.value)()
    for path in paths_:
        path.version = PATH_VERSION
    _check("DISP_GetDisplayConfig", f["DISP_GetDisplayConfig"](byref(count), paths_))
    keep = []
    for path in paths_:
        targets = (_Target * path.targetInfoCount)()
        for target in targets:
            details = _Advanced(version=ADVANCED_VERSION)
            keep.append(details)
            target.details = ctypes.pointer(details)
        source = _SourceMode()
        keep += [targets, source]
        path.targetInfo = targets
        path.sourceModeInfo = ctypes.pointer(source)
    _check("DISP_GetDisplayConfig", f["DISP_GetDisplayConfig"](byref(count), paths_))
    return count.value, paths_, keep


def _display_id(device):
    display_id = c_uint32()
    _check("DISP_GetDisplayIdByDisplayName",
           _display_api()["DISP_GetDisplayIdByDisplayName"](device.encode("ascii"), byref(display_id)))
    return display_id.value


def _find_target(paths_, display_id):
    for path in paths_:
        for i in range(path.targetInfoCount):
            target = path.targetInfo[i]
            if target.displayId == display_id and target.details:
                return target.details.contents
    return None


def get_scaling(device):
    """Windows ekran adının (DISPLAYn) NV_SCALING değeri; ekran NVIDIA kartında değilse None."""
    try:
        display_id = _display_id(device)
        _count, paths_, _keep = _display_config()
    except (OSError, NvapiError) as exc:
        _log.info("NVIDIA ölçekleme okunamadı (%s): %s", device, exc)
        return None
    details = _find_target(paths_, display_id)
    return None if details is None else int(details.scaling)


def set_scaling(device, value):
    """Yalnızca ölçekleme alanı değişir; yapılandırmanın geri kalanı okunduğu gibi geri yazılır."""
    if int(value) not in SCALING_MONITOR + SCALING_GPU:
        raise ValueError(f"geçersiz ölçekleme: {value}")
    _log.info("NVIDIA ölçekleme (%s): %s", device, value)
    display_id = _display_id(device)
    count, paths_, _keep = _display_config()
    details = _find_target(paths_, display_id)
    if details is None:
        raise OSError(f"{device} NVIDIA kartına bağlı değil")
    details.scaling = int(value)
    _check("DISP_SetDisplayConfig", _display_api()["DISP_SetDisplayConfig"](count, paths_, SAVE_TO_PERSISTENCE))


# ---------------------------------------------------------------------------
# Yedek yöntem: NVIDIA Profile Inspector (kullanıcı tools klasörüne koyar)
# ---------------------------------------------------------------------------

def npi_path():
    path = paths.tools_dir() / "nvidiaProfileInspector.exe"
    return path if path.exists() else None


def npi_import(settings, expected_sha256=None):
    """settings: [(ayar_id, değer)] — genel profile birleştirerek (merge) içe aktarır.

    Emin değilim: .nip dosyasında genel profilin adı ("Base Profile") ve aracın eski
    sürümlerinde -mergeImport desteği doğrulanmadı. Geri alınamaz (önceki değerler
    NVAPI olmadan okunamaz); arayüz bunu açıkça sorar.
    """
    exe = npi_path()
    if exe is None:
        raise FileNotFoundError("nvidiaProfileInspector.exe tools klasöründe yok")
    if expected_sha256:  # kullanıcının onayladığı dosya çalıştırmadan önce değiştirilmiş olamaz
        from app.engine import driver_tools  # noqa: WPS433
        if driver_tools.sha256_file(exe) != expected_sha256:
            raise OSError("nvidiaProfileInspector.exe onaydan sonra değişti")
    rows = "".join(
        "<ProfileSetting><SettingNameInfo></SettingNameInfo>"
        f"<SettingID>{sid}</SettingID><SettingValue>{value & 0xFFFFFFFF}</SettingValue>"
        "<ValueType>Dword</ValueType></ProfileSetting>" for sid, value in settings)
    xml = ('<?xml version="1.0" encoding="utf-16"?><ArrayOfProfile><Profile><ProfileName>Base Profile</ProfileName>'
           f"<Executeables /><Settings>{rows}</Settings></Profile></ArrayOfProfile>")
    folder = tempfile.mkdtemp(prefix="pcopt_nip_")
    nip = os.path.join(folder, "forevermore.nip")
    with open(nip, "w", encoding="utf-16") as f:
        f.write(xml)
    _log.info("NVIDIA Profile Inspector ile içe aktarılıyor (%d ayar)", len(settings))
    proc = subprocess.run([str(exe), "-silentImport", "-mergeImport", nip], capture_output=True, timeout=120,
                          creationflags=powershell.CREATE_NO_WINDOW)
    if proc.returncode != 0:
        raise OSError(f"NVIDIA Profile Inspector hata kodu {proc.returncode}")
