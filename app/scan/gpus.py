"""Ekran kartları: hangisi yüksek performanslı, hangisi güç tasarruflu, hangi ekranı sürüyor.

Windows'un kendi DXGI arabirimi (dxgi.dll) ctypes ile, SALT OKUNUR kullanılır:
- IDXGIFactory6::EnumAdapterByGpuPreference: Windows'un "Grafik ayarları"nda
  "Yüksek performans" ve "Güç tasarrufu" dediği kartları bu sırayla belirler.
  Uygulama başına GPU tercihi (oyunlar) de aynı sırayı kullanır.
- IDXGIAdapter::EnumOutputs: kartın sürdüğü ekranlar (\\\\.\\DISPLAYn adı).

Belgeler: learn.microsoft.com/windows/win32/api/dxgi1_6 (IDXGIFactory6),
dxgi.h (IDXGIAdapter1, DXGI_ADAPTER_DESC1, DXGI_OUTPUT_DESC).
Okunamazsa boş liste döner; tarama bozulmaz.
"""

import ctypes
import uuid
from ctypes import POINTER, byref, c_long, c_size_t, c_uint32, c_ubyte, c_void_p, c_wchar

from app.core import log

_log = log.get("gpus")

IID_IDXGIFactory1 = "770aae78-f26f-4dba-a829-253c83d1b387"
IID_IDXGIFactory6 = "c1b6694f-ff09-44a9-b03c-77900a0a1d17"
IID_IDXGIAdapter1 = "29038f61-3839-4626-91fd-086879011a05"
DXGI_ERROR_NOT_FOUND = 0x887A0002
GPU_PREFERENCE_MINIMUM_POWER = 1
GPU_PREFERENCE_HIGH_PERFORMANCE = 2
FLAG_SOFTWARE = 2
VENDORS = {0x10DE: "NVIDIA", 0x1002: "AMD", 0x1022: "AMD", 0x8086: "Intel", 0x5143: "Qualcomm"}

# vtable sıraları (dxgi.h / dxgi1_6.h)
_RELEASE = 2
_FACTORY1_ENUM_ADAPTERS1 = 12
_FACTORY6_ENUM_BY_PREFERENCE = 29
_ADAPTER_ENUM_OUTPUTS = 7
_ADAPTER1_GET_DESC1 = 10
_OUTPUT_GET_DESC = 7


class _Guid(ctypes.Structure):
    _fields_ = [("bytes", c_ubyte * 16)]

    @classmethod
    def of(cls, text):
        g = cls()
        ctypes.memmove(byref(g), uuid.UUID(text).bytes_le, 16)
        return g


class _AdapterDesc1(ctypes.Structure):
    _fields_ = [("Description", c_wchar * 128), ("VendorId", c_uint32), ("DeviceId", c_uint32),
                ("SubSysId", c_uint32), ("Revision", c_uint32), ("DedicatedVideoMemory", c_size_t),
                ("DedicatedSystemMemory", c_size_t), ("SharedSystemMemory", c_size_t),
                ("LuidLow", c_uint32), ("LuidHigh", c_long), ("Flags", c_uint32)]


class _OutputDesc(ctypes.Structure):
    _fields_ = [("DeviceName", c_wchar * 32), ("Left", c_long), ("Top", c_long), ("Right", c_long),
                ("Bottom", c_long), ("AttachedToDesktop", c_long), ("Rotation", c_uint32),
                ("Monitor", c_void_p)]


def _vcall(obj, index, *args, argtypes=()):
    vtable = ctypes.cast(obj, POINTER(POINTER(c_void_p)))[0]
    func = ctypes.WINFUNCTYPE(c_long, c_void_p, *argtypes)(vtable[index])
    return func(obj, *args)


def _release(obj):
    if obj:
        _vcall(obj, _RELEASE)


def _describe(adapter):
    desc = _AdapterDesc1()
    if _vcall(adapter, _ADAPTER1_GET_DESC1, byref(desc), argtypes=(c_void_p,)) != 0:
        return None
    outputs = []
    i = 0
    while i < 16:
        output = c_void_p()
        if _vcall(adapter, _ADAPTER_ENUM_OUTPUTS, i, byref(output), argtypes=(c_uint32, c_void_p)) != 0:
            break
        out_desc = _OutputDesc()
        if _vcall(output, _OUTPUT_GET_DESC, byref(out_desc), argtypes=(c_void_p,)) == 0 \
                and out_desc.AttachedToDesktop:
            outputs.append(out_desc.DeviceName)
        _release(output)
        i += 1
    return {
        "ad": desc.Description.strip(),
        "uretici": VENDORS.get(desc.VendorId, "diğer"),
        "satici_kimligi": f"{desc.VendorId:04X}",
        "aygit_kimligi": f"{desc.DeviceId:04X}",
        "vram_mb": desc.DedicatedVideoMemory // 2 ** 20,
        "luid": f"{desc.LuidHigh & 0xFFFFFFFF:08X}{desc.LuidLow:08X}",
        "yazilim": bool(desc.Flags & FLAG_SOFTWARE),
        "ekranlar": outputs,
    }


def _enumerate(factory, preference):
    """Bir tercihe göre sıralı kart listesi. preference None: tercihsiz (IDXGIFactory1)."""
    result = []
    for i in range(16):
        adapter = c_void_p()
        if preference is None:
            hr = _vcall(factory, _FACTORY1_ENUM_ADAPTERS1, i, byref(adapter), argtypes=(c_uint32, c_void_p))
        else:
            hr = _vcall(factory, _FACTORY6_ENUM_BY_PREFERENCE, i, preference, byref(_Guid.of(IID_IDXGIAdapter1)),
                        byref(adapter), argtypes=(c_uint32, c_uint32, c_void_p, c_void_p))
        if hr != 0:
            break
        try:
            info = _describe(adapter)
        finally:
            _release(adapter)
        if info and not info["yazilim"]:
            result.append(info)
    return result


def dxgi_adapters():
    """Donanım ekran kartları; her biri için Windows'un yüksek performans / güç tasarrufu rolü.

    Dönen öğe: {ad, uretici, vram_mb, luid, ekranlar: ['\\\\.\\DISPLAY1'], yuksek_performans: bool,
    guc_tasarrufu: bool}. Tek kart varsa iki rol de o karttadır.
    """
    try:
        dxgi = ctypes.windll.dxgi
    except (AttributeError, OSError):
        return []
    factory = c_void_p()
    preference_ok = dxgi.CreateDXGIFactory1(byref(_Guid.of(IID_IDXGIFactory6)), byref(factory)) == 0
    if not preference_ok:
        factory = c_void_p()
        if dxgi.CreateDXGIFactory1(byref(_Guid.of(IID_IDXGIFactory1)), byref(factory)) != 0:
            return []
    try:
        if preference_ok:
            high = _enumerate(factory, GPU_PREFERENCE_HIGH_PERFORMANCE)
            low = _enumerate(factory, GPU_PREFERENCE_MINIMUM_POWER)
        else:
            high = low = _enumerate(factory, None)
    except OSError as exc:
        _log.warning("DXGI ile ekran kartları okunamadı: %s", exc)
        return []
    finally:
        _release(factory)
    if not high:
        return []
    for adapter in high:
        adapter["yuksek_performans"] = preference_ok and adapter["luid"] == high[0]["luid"]
        adapter["guc_tasarrufu"] = preference_ok and adapter["luid"] == low[0]["luid"]
    return high
