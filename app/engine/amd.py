"""AMD Radeon sürücü ayarları: AMD'nin ADLX kütüphanesi (amdadlx64.dll, sürücüyle gelir), ctypes ile.

Arabirim sıraları AMD'nin resmi deposundaki C başlıklarından alındı:
github.com/GPUOpen-LibrariesAndSDKs/ADLX (SDK/Include/ISystem.h, I3DSettings.h, ADLXDefines.h; MIT).
Uygulamaya AMD dosyası gömülmez.

- IADLXSystem: GetHybridGraphicsType(0), GetGPUs(1), QueryInterface(2), GetDisplaysServices(3), ...,
  Get3DSettingsServices(7) (Acquire/Release YOK).
- IADLXDisplayServices: Acquire, Release, QueryInterface, GetNumberOfDisplays(3), GetDisplays(4), ...,
  GetGPUScaling(11), GetScalingMode(12) (IDisplays.h)
- IADLXDisplayList: ..., Size(3), ..., At_DisplayList(11); IADLXDisplay: ..., Name(6), ..., UniqueId(13)
- IADLXDisplayGPUScaling: ..., IsSupported(3), IsEnabled(4), SetEnabled(5);
  IADLXDisplayScalingMode: ..., IsSupported(3), GetMode(4), SetMode(5) (IDisplaySettings.h)
  ADLX_SCALE_MODE: PRESERVE_ASPECT_RATIO=0, FULL_PANEL=1, CENTERED=2 (ADLXDefines.h)
- IADLXGPUList: Acquire, Release, QueryInterface, Size(3), ..., At_GPUList(11)
- IADLXGPU: Acquire, Release, QueryInterface, VendorId(3), ASICFamilyType, Type, IsExternal(6), Name(7)
- IADLX3DSettingsServices: Acquire, Release, QueryInterface, GetAntiLag(3), GetChill(4), GetBoost(5),
  GetImageSharpening(6), GetEnhancedSync(7)
- IADLX3DAntiLag / IADLX3DEnhancedSync: ..., IsSupported(3), IsEnabled(4), SetEnabled(5)
- IADLX3DChill: ..., IsSupported(3), IsEnabled(4), GetFPSRange(5), GetMinFPS(6), GetMaxFPS(7),
  SetEnabled(8), SetMinFPS(9), SetMaxFPS(10)
- IADLX3DBoost: ..., IsSupported(3), IsEnabled(4), GetResolutionRange(5), GetResolution(6), SetEnabled(7)
"""

import ctypes
from ctypes import POINTER, byref, c_char_p, c_int, c_uint, c_uint8, c_uint64, c_void_p

from app.core import log

_log = log.get("amd")

ADLX_OK = 0
FEATURES = {
    # özellik: (3DSettingsServices'teki Get indeksi, IsSupported, IsEnabled, SetEnabled)
    "anti_lag": (3, 3, 4, 5),
    "chill": (4, 3, 4, 8),
    "boost": (5, 3, 4, 7),
    "enhanced_sync": (7, 3, 4, 5),
}


def _vcall(obj, index, restype, *args, argtypes=()):
    vtable = ctypes.cast(obj, POINTER(POINTER(c_void_p)))[0]
    func = ctypes.WINFUNCTYPE(restype, c_void_p, *argtypes)(vtable[index])
    return func(obj, *args)


def _release(obj):
    if obj:
        _vcall(obj, 1, ctypes.c_long)


class _Adlx:
    """with _Adlx() as system: ... — başlatır ve sonunda ADLXTerminate çağırır."""

    def __enter__(self):
        self.dll = ctypes.WinDLL("amdadlx64.dll")
        version = c_uint64()
        if self.dll.ADLXQueryFullVersion(byref(version)) != ADLX_OK:
            raise OSError("ADLX sürümü okunamadı")
        self.system = c_void_p()
        init = self.dll.ADLXInitialize
        init.argtypes = (c_uint64, POINTER(c_void_p))
        if init(version.value, byref(self.system)) != ADLX_OK or not self.system:
            raise OSError("ADLX başlatılamadı")
        return self.system

    def __exit__(self, *_exc):
        try:
            self.dll.ADLXTerminate()
        except OSError:
            pass


def _gpus(system):
    """[(gpu işaretçisi, ad)] — çağıran serbest bırakır."""
    gpu_list = c_void_p()
    if _vcall(system, 1, c_int, byref(gpu_list), argtypes=(c_void_p,)) != ADLX_OK:
        return []
    result = []
    try:
        size = _vcall(gpu_list, 3, c_uint)
        for i in range(size):
            gpu = c_void_p()
            if _vcall(gpu_list, 11, c_int, c_uint(i), byref(gpu), argtypes=(c_uint, c_void_p)) != ADLX_OK:
                continue
            name = c_char_p()
            _vcall(gpu, 7, c_int, byref(name), argtypes=(c_void_p,))
            result.append((gpu, (name.value or b"").decode("utf-8", errors="replace")))
    finally:
        _release(gpu_list)
    return result


def _feature(services, gpu, key):
    getter = FEATURES[key][0]
    obj = c_void_p()
    if _vcall(services, getter, c_int, gpu, byref(obj), argtypes=(c_void_p, c_void_p)) != ADLX_OK:
        return None
    return obj


def _bool(obj, index):
    value = c_uint8()
    if _vcall(obj, index, c_int, byref(value), argtypes=(c_void_p,)) != ADLX_OK:
        return None
    return bool(value.value)


def read_settings():
    """{GPU adı: {özellik: {'destek': bool, 'acik': bool}}} — yalnızca okur. ADLX yoksa {}."""
    result = {}
    try:
        with _Adlx() as system:
            services = c_void_p()
            if _vcall(system, 7, c_int, byref(services), argtypes=(c_void_p,)) != ADLX_OK:
                return {}
            try:
                for gpu, name in _gpus(system):
                    try:
                        values = {}
                        for key, (_g, supported, enabled, _s) in FEATURES.items():
                            obj = _feature(services, gpu, key)
                            if obj is None:
                                continue
                            try:
                                values[key] = {"destek": _bool(obj, supported), "acik": _bool(obj, enabled)}
                            finally:
                                _release(obj)
                        result[name] = values
                    finally:
                        _release(gpu)
            finally:
                _release(services)
    except (OSError, AttributeError) as exc:
        _log.info("ADLX kullanılamıyor: %s", exc)
        return {}
    return result


def set_feature(gpu_name, key, enabled):
    """Bir özelliği açar/kapatır. Desteklenmiyorsa veya ADLX reddederse OSError."""
    set_index = FEATURES[key][3]
    with _Adlx() as system:
        services = c_void_p()
        if _vcall(system, 7, c_int, byref(services), argtypes=(c_void_p,)) != ADLX_OK:
            raise OSError("ADLX 3D ayar servisi alınamadı")
        try:
            gpus = _gpus(system)
            try:
                gpu = next((g for g, name in gpus if name == gpu_name), None)
                if gpu is None:
                    raise OSError(f"AMD ekran kartı bulunamadı: {gpu_name}")
                obj = _feature(services, gpu, key)
                if obj is None:
                    raise OSError(f"{key} okunamadı")
                try:
                    if not _bool(obj, FEATURES[key][1]):
                        raise OSError(f"{key} bu kartta desteklenmiyor")
                    code = _vcall(obj, set_index, c_int, c_uint8(1 if enabled else 0), argtypes=(c_uint8,))
                    if code != ADLX_OK:
                        raise OSError(f"ADLX {key} değiştiremedi ({code})")
                finally:
                    _release(obj)
            finally:
                for g, _n in gpus:
                    _release(g)
        finally:
            _release(services)


# ---------------------------------------------------------------------------
# Ekran ölçeklemesi (AMD Software > Ekran > GPU Ölçekleme ve Ölçekleme modu)
# Değer: 0 = ölçeklemeyi monitör yapar (GPU ölçekleme kapalı); 1/2/3 = GPU ölçekler,
# sırasıyla en-boy oranını koru / tam panel / ortala (ADLX_SCALE_MODE + 1).
# ---------------------------------------------------------------------------
SCALING_VALUES = (0, 1, 2, 3)


def _displays(services):
    """[(ekran işaretçisi, ad, benzersiz kimlik)] — çağıran serbest bırakır."""
    display_list = c_void_p()
    if _vcall(services, 4, c_int, byref(display_list), argtypes=(c_void_p,)) != ADLX_OK:
        return []
    result = []
    try:
        for i in range(_vcall(display_list, 3, c_uint)):
            display = c_void_p()
            if _vcall(display_list, 11, c_int, c_uint(i), byref(display), argtypes=(c_uint, c_void_p)) != ADLX_OK:
                continue
            name, unique = c_char_p(), ctypes.c_size_t()
            _vcall(display, 6, c_int, byref(name), argtypes=(c_void_p,))
            _vcall(display, 13, c_int, byref(unique), argtypes=(c_void_p,))
            result.append((display, (name.value or b"").decode("utf-8", errors="replace"), str(unique.value)))
    finally:
        _release(display_list)
    return result


def _scaling_objects(services, display):
    gpu_scaling, mode = c_void_p(), c_void_p()
    if _vcall(services, 11, c_int, display, byref(gpu_scaling), argtypes=(c_void_p, c_void_p)) != ADLX_OK:
        gpu_scaling = None
    if _vcall(services, 12, c_int, display, byref(mode), argtypes=(c_void_p, c_void_p)) != ADLX_OK:
        mode = None
    return gpu_scaling, mode


def _scaling_value(gpu_scaling, mode):
    if gpu_scaling is None or not _bool(gpu_scaling, 3):
        return None
    if not _bool(gpu_scaling, 4):
        return 0
    current = c_int(0)
    if mode is not None and _bool(mode, 3):
        _vcall(mode, 4, c_int, byref(current), argtypes=(c_void_p,))
    return current.value + 1


def _with_displays(callback):
    with _Adlx() as system:
        services = c_void_p()
        if _vcall(system, 3, c_int, byref(services), argtypes=(c_void_p,)) != ADLX_OK:
            raise OSError("ADLX ekran servisi alınamadı")
        try:
            displays = _displays(services)
            try:
                return callback(services, displays)
            finally:
                for display, _n, _u in displays:
                    _release(display)
        finally:
            _release(services)


def read_scaling():
    """[{'ad', 'kimlik', 'deger'}] — AMD kartına bağlı ekranlar; deger None = desteklenmiyor. ADLX yoksa []."""
    def read(services, displays):
        result = []
        for display, name, unique in displays:
            gpu_scaling, mode = _scaling_objects(services, display)
            try:
                result.append({"ad": name, "kimlik": unique, "deger": _scaling_value(gpu_scaling, mode)})
            finally:
                _release(gpu_scaling)
                _release(mode)
        return result
    try:
        return _with_displays(read)
    except (OSError, AttributeError) as exc:
        _log.info("ADLX ekran ölçeklemesi okunamadı: %s", exc)
        return []


def set_scaling(unique_id, value):
    value = int(value)
    if value not in SCALING_VALUES:
        raise ValueError(f"geçersiz ölçekleme: {value}")
    _log.info("AMD ölçekleme (%s): %s", unique_id, value)

    def write(services, displays):
        display = next((d for d, _n, u in displays if u == str(unique_id)), None)
        if display is None:
            raise OSError("AMD ekranı bulunamadı")
        gpu_scaling, mode = _scaling_objects(services, display)
        try:
            if gpu_scaling is None or not _bool(gpu_scaling, 3):
                raise OSError("GPU ölçekleme bu ekranda desteklenmiyor")
            code = _vcall(gpu_scaling, 5, c_int, c_uint8(1 if value else 0), argtypes=(c_uint8,))
            if code != ADLX_OK:
                raise OSError(f"ADLX GPU ölçeklemeyi değiştiremedi ({code})")
            if value and mode is not None and _bool(mode, 3):
                code = _vcall(mode, 5, c_int, c_int(value - 1), argtypes=(c_int,))
                if code != ADLX_OK:
                    raise OSError(f"ADLX ölçekleme modunu değiştiremedi ({code})")
        finally:
            _release(gpu_scaling)
            _release(mode)
    _with_displays(write)
