"""Ses çıkış cihazlarının varsayılan biçimi (örnekleme hızı / bit derinliği), kendi kodumuz.

NirSoft svcl.exe veya başka araç GÖMÜLMEZ. Windows'un Ses denetim masasının
(mmsys.cpl) kullandığı COM arabirimi ctypes ile çağrılır:

- Desteklenen biçimler: IMMDevice -> IAudioClient::IsFormatSupported (özel mod).
  Belgelenmiş API; yalnızca sorar, hiçbir şeyi değiştirmez.
- Şu anki biçim ve yazma: IPolicyConfig::GetDeviceFormat / SetDeviceFormat.
  TEST SONUCU (kullanıcının izniyle, 22.10.2026): okuma doğru; yazma bu bilgisayardaki Realtek
  "Speaker" çıkışında her biçim/karıştırıcı kombinasyonunda 0x80070491 (ERROR_NO_MATCH) ile
  reddedildi, hiçbir şey değişmedi. Bu durumda kullanıcıya Ses denetim masası önerilir.
  Emin değilim: IPolicyConfig BELGELENMEMİŞ bir arabirimdir (Windows'un kendi ses
  paneli ve açık kaynak araçlar kullanır); Windows sürümüyle değişebilir. Yazmadan
  önce GetDeviceFormat'ın kayıt defterindeki biçimle aynı sonucu verdiği doğrulanır.

Biçim değeri "48000/24" gibi metindir: Hz / bit.
"""

import ctypes
import uuid
from ctypes import POINTER, byref, c_long, c_ubyte, c_uint16, c_uint32, c_void_p, c_wchar_p

from app.core import log

_log = log.get("audio")

CLSID_MMDeviceEnumerator = "BCDE0395-E52F-467C-8E3D-C4579291692E"
IID_IMMDeviceEnumerator = "A95664D2-9614-4F35-A746-DE8DB63617E6"
IID_IAudioClient = "1CB9AD4C-DBFA-4C32-B178-C2F568A703B2"
CLSID_PolicyConfigClient = "870AF99C-171D-4F9E-AF0D-E63DF40C2BC9"
IID_IPolicyConfig = "F8679F50-850A-41CF-9C72-430F290290C8"  # Windows 10/11
SUBTYPE_PCM = "00000001-0000-0010-8000-00AA00389B71"
SUBTYPE_FLOAT = "00000003-0000-0010-8000-00AA00389B71"
WAVE_FORMAT_EXTENSIBLE = 0xFFFE
CLSCTX_ALL = 0x17
AUDCLNT_SHAREMODE_EXCLUSIVE = 1
RENDER_PREFIX = "{0.0.0.00000000}."

RATES = (44100, 48000, 88200, 96000, 176400, 192000)
# (bit etiketi, kapsayıcı bit, geçerli bit) — 24 bit iki biçimde denenebilir
BIT_LAYOUTS = ((16, 16, 16), (24, 24, 24), (24, 32, 24), (32, 32, 32))


class _Guid(ctypes.Structure):
    _fields_ = [("bytes", c_ubyte * 16)]

    @classmethod
    def of(cls, text):
        g = cls()
        ctypes.memmove(byref(g), uuid.UUID(text).bytes_le, 16)
        return g


class WaveFormatExtensible(ctypes.Structure):
    _pack_ = 1  # mmreg.h: pshpack1
    _fields_ = [("wFormatTag", c_uint16), ("nChannels", c_uint16), ("nSamplesPerSec", c_uint32),
                ("nAvgBytesPerSec", c_uint32), ("nBlockAlign", c_uint16), ("wBitsPerSample", c_uint16),
                ("cbSize", c_uint16), ("wValidBitsPerSample", c_uint16), ("dwChannelMask", c_uint32),
                ("SubFormat", c_ubyte * 16)]


def _vcall(obj, index, *args, argtypes=()):
    vtable = ctypes.cast(obj, POINTER(POINTER(c_void_p)))[0]
    func = ctypes.WINFUNCTYPE(c_long, c_void_p, *argtypes)(vtable[index])
    return func(obj, *args)


def _release(obj):
    if obj:
        _vcall(obj, 2)


class _Com:
    def __enter__(self):
        self.hr = ctypes.windll.ole32.CoInitializeEx(None, 0)  # COINIT_MULTITHREADED
        return self

    def __exit__(self, *_exc):
        if self.hr in (0, 1):
            ctypes.windll.ole32.CoUninitialize()


def _create(clsid, iid):
    obj = c_void_p()
    hr = ctypes.windll.ole32.CoCreateInstance(byref(_Guid.of(clsid)), None, CLSCTX_ALL, byref(_Guid.of(iid)),
                                              byref(obj))
    if hr != 0:
        raise OSError(f"CoCreateInstance {clsid}: {hr & 0xFFFFFFFF:#x}")
    return obj


def _endpoint_id(subkey):
    return RENDER_PREFIX + subkey.lower()


def _format_text(fmt):
    bits = fmt.wValidBitsPerSample if fmt.wFormatTag == WAVE_FORMAT_EXTENSIBLE and fmt.wValidBitsPerSample \
        else fmt.wBitsPerSample
    return f"{fmt.nSamplesPerSec}/{bits}"


def _make_format(base, rate, container, valid, subtype=SUBTYPE_PCM):
    fmt = WaveFormatExtensible()
    fmt.wFormatTag = WAVE_FORMAT_EXTENSIBLE
    fmt.nChannels = base.nChannels
    fmt.nSamplesPerSec = rate
    fmt.wBitsPerSample = container
    fmt.nBlockAlign = base.nChannels * container // 8
    fmt.nAvgBytesPerSec = rate * fmt.nBlockAlign
    fmt.cbSize = 22
    fmt.wValidBitsPerSample = valid
    fmt.dwChannelMask = base.dwChannelMask if base.wFormatTag == WAVE_FORMAT_EXTENSIBLE else (3 if base.nChannels == 2
                                                                                           else 0)
    ctypes.memmove(fmt.SubFormat, uuid.UUID(subtype).bytes_le, 16)
    return fmt


def _current_format(policy, device_id):
    pointer = c_void_p()
    hr = _vcall(policy, 4, c_wchar_p(device_id), 0, byref(pointer),  # GetDeviceFormat(id, bDefault=0, **fmt)
                argtypes=(c_wchar_p, ctypes.c_int, POINTER(c_void_p)))
    if hr != 0 or not pointer:
        raise OSError(f"GetDeviceFormat: {hr & 0xFFFFFFFF:#x}")
    try:
        size = 18 + ctypes.cast(pointer, POINTER(c_uint16))[8]  # 18 + cbSize
        raw = ctypes.string_at(pointer, min(size, ctypes.sizeof(WaveFormatExtensible)))
    finally:
        ctypes.windll.ole32.CoTaskMemFree(pointer)
    fmt = WaveFormatExtensible()
    ctypes.memmove(byref(fmt), raw, len(raw))
    return fmt, raw.hex()


def device_formats(subkey):
    """{'deger': '48000/24', 'ham': onaltılık, 'desteklenen': [...]} — salt okunur."""
    device_id = _endpoint_id(subkey)
    with _Com():
        policy = enumerator = device = client = None
        try:
            policy = _create(CLSID_PolicyConfigClient, IID_IPolicyConfig)
            current, raw = _current_format(policy, device_id)
            enumerator = _create(CLSID_MMDeviceEnumerator, IID_IMMDeviceEnumerator)
            device = c_void_p()
            hr = _vcall(enumerator, 5, c_wchar_p(device_id), byref(device), argtypes=(c_wchar_p, POINTER(c_void_p)))
            if hr != 0:
                raise OSError(f"GetDevice: {hr & 0xFFFFFFFF:#x}")
            client = c_void_p()
            hr = _vcall(device, 3, byref(_Guid.of(IID_IAudioClient)), CLSCTX_ALL, None, byref(client),
                        argtypes=(POINTER(_Guid), c_uint32, c_void_p, POINTER(c_void_p)))
            if hr != 0:
                raise OSError(f"Activate(IAudioClient): {hr & 0xFFFFFFFF:#x}")
            supported = []
            for rate in RATES:
                for label, container, valid in BIT_LAYOUTS:
                    text = f"{rate}/{label}"
                    if text in supported:
                        continue
                    fmt = _make_format(current, rate, container, valid)
                    # IsFormatSupported(EXCLUSIVE, fmt, NULL): S_OK (0) = destekleniyor
                    if _vcall(client, 7, AUDCLNT_SHAREMODE_EXCLUSIVE, byref(fmt), None,
                              argtypes=(ctypes.c_int, POINTER(WaveFormatExtensible), c_void_p)) == 0:
                        supported.append(text)
            return {"deger": _format_text(current), "ham": raw, "desteklenen": supported}
        finally:
            for obj in (client, device, enumerator, policy):
                _release(obj)


ERROR_NO_MATCH = 0x80070491  # HRESULT_FROM_WIN32(ERROR_NO_MATCH): biçim cihazın listesinde yok


def _supported_layouts(client_check, current, rate, bits):
    """Bu bit derinliği için cihazın kabul ettiği tüm düzenler; 32 bit kapsayıcı önce denenir."""
    layouts = sorted((l for l in BIT_LAYOUTS if l[0] == bits), key=lambda l: -l[1])
    result = []
    for _label, container, valid in layouts:
        fmt = _make_format(current, rate, container, valid)
        if client_check(fmt):
            result.append(fmt)
    return result


def _mix_formats(policy, device_id, fmt):
    """Denenecek karıştırıcı biçimleri: Windows'un şu anki karıştırıcı biçimi (yeni örnekleme
    hızıyla), 32 bit float ve hiç verilmemesi (None)."""
    options = []
    pointer = c_void_p()
    hr = _vcall(policy, 3, c_wchar_p(device_id), byref(pointer),  # GetMixFormat(id, **fmt)
                argtypes=(c_wchar_p, POINTER(c_void_p)))
    if hr == 0 and pointer:
        try:
            size = 18 + ctypes.cast(pointer, POINTER(c_uint16))[8]
            raw = ctypes.string_at(pointer, min(size, ctypes.sizeof(WaveFormatExtensible)))
        finally:
            ctypes.windll.ole32.CoTaskMemFree(pointer)
        mix = WaveFormatExtensible()
        ctypes.memmove(byref(mix), raw, len(raw))
        mix.nSamplesPerSec = fmt.nSamplesPerSec
        mix.nAvgBytesPerSec = fmt.nSamplesPerSec * mix.nBlockAlign
        options.append(mix)
    options.append(_make_format(fmt, fmt.nSamplesPerSec, 32, 32, SUBTYPE_FLOAT))
    options.append(None)
    return options


def _set(policy, device_id, candidates):
    """Adayları sırayla dener; yalnızca ERROR_NO_MATCH'te sonrakine geçer."""
    last = None
    for fmt in candidates:
        for mix in _mix_formats(policy, device_id, fmt):
            hr = _vcall(policy, 6, c_wchar_p(device_id), byref(fmt), byref(mix) if mix is not None else None,
                        argtypes=(c_wchar_p, POINTER(WaveFormatExtensible), c_void_p))  # SetDeviceFormat
            if hr == 0:
                _log.info("Ses biçimi yazıldı: %s (kapsayıcı %s bit, karıştırıcı %s)", _format_text(fmt),
                          fmt.wBitsPerSample, "yok" if mix is None else f"{mix.wBitsPerSample} bit")
                return
            last = hr & 0xFFFFFFFF
            if last != ERROR_NO_MATCH:
                raise OSError(f"SetDeviceFormat: {last:#x}")
    _log.warning("SetDeviceFormat bu cihazda reddedildi: %#x", last)
    from app.engine.handlers import UserFacingError  # noqa: WPS433 - döngüsel içe aktarmayı önlemek için burada
    raise UserFacingError("hata.ses_bicimi_reddedildi", kod=f"{last:#x}")


def set_device_format(subkey, value=None, raw_hex=None):
    """value '48000/24' veya raw_hex (yedekteki ham biçim) yazılır."""
    device_id = _endpoint_id(subkey)
    with _Com():
        policy = enumerator = device = client = None
        try:
            policy = _create(CLSID_PolicyConfigClient, IID_IPolicyConfig)
            current, _raw = _current_format(policy, device_id)
            if raw_hex is not None:
                fmt = WaveFormatExtensible()
                data = bytes.fromhex(raw_hex)
                ctypes.memmove(byref(fmt), data, min(len(data), ctypes.sizeof(fmt)))
                candidates = [fmt]
                _log.info("Ses biçimi yedekten geri yazılıyor: %s -> %s", subkey, _format_text(fmt))
            else:
                rate, bits = (int(x) for x in value.split("/"))
                enumerator = _create(CLSID_MMDeviceEnumerator, IID_IMMDeviceEnumerator)
                device = c_void_p()
                _vcall(enumerator, 5, c_wchar_p(device_id), byref(device), argtypes=(c_wchar_p, POINTER(c_void_p)))
                client = c_void_p()
                hr = _vcall(device, 3, byref(_Guid.of(IID_IAudioClient)), CLSCTX_ALL, None, byref(client),
                            argtypes=(POINTER(_Guid), c_uint32, c_void_p, POINTER(c_void_p)))
                if hr != 0:
                    raise OSError(f"Activate(IAudioClient): {hr & 0xFFFFFFFF:#x}")

                def check(f):
                    return _vcall(client, 7, AUDCLNT_SHAREMODE_EXCLUSIVE, byref(f), None,
                                  argtypes=(ctypes.c_int, POINTER(WaveFormatExtensible), c_void_p)) == 0
                candidates = _supported_layouts(check, current, rate, bits)
                if not candidates:
                    raise ValueError(f"{value} bu cihazda desteklenmiyor")
                _log.info("Ses biçimi değiştiriliyor: %s -> %s", subkey, value)
            _set(policy, device_id, candidates)
        finally:
            for obj in (client, device, enumerator, policy):
                _release(obj)
