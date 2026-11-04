"""Mouse, klavye ve ses cihazları.

Polling rate (fare rapor hızı) Windows'tan güvenilir şekilde OKUNAMAZ; bu
bilgi uygulamada dürüstçe gösterilir ve ölçüm yöntemleri tweaks.json'daki
arastirma_notlari.mouse_polling_rate bölümünden alınır.

Gizlilik: cihazların seri numarası içerebilecek InstanceId değerleri dışarı
çıkarılmaz; yalnızca ad, VID:PID ve bağlantı türü (USB/Bluetooth/dahili) okunur.
Bluetooth cihazının kullanıcının verdiği adı "_yerel" alanında tutulur ve
dışa aktarılan rapora girmez.
"""

from app.core import powershell, registry
from app.core.i18n import t
from app.scan.input_devices import input_devices

AUDIO_ROOT = r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio"
PKEY_DEVICE_DESC = "{a45c254e-df1c-4efd-8020-67d146a850e0},2"
PKEY_INTERFACE_NAME = "{b3f8fa53-0004-438e-9003-51a46e139bfc},6"
PKEY_DEVICE_FORMAT = "{f19f064d-082c-4e27-bc73-6882a1bb8e4c},0"
PKEY_DISABLE_SYSFX = "{1da5d803-d492-4edd-8c23-e0c0ffee7f0e},5"
WAVE_FORMAT_EXTENSIBLE = 0xFFFE

# USB üretici kimlikleri (VID) → ad. Yalnızca oyuncu çevre birimlerinde yaygın olanlar.
USB_VENDORS = {"046D": "Logitech", "1532": "Razer", "1038": "SteelSeries", "1B1C": "Corsair",
               "0951": "HyperX", "03F0": "HP/HyperX", "258A": "Glorious/Sinowealth", "3554": "Pulsar/VXE",
               "1E7D": "ROCCAT", "0B05": "ASUS", "045E": "Microsoft", "093A": "Pixart", "1A2C": "China OEM",
               "373B": "Lamzu/Compx", "25A7": "Areson", "0E8F": "GreenAsia"}

def collect_input():
    """Fare/klavyeler (gerçek ad ve VID:PID, bkz. input_devices.py) ve Windows fare/klavye ayarları."""
    devices = []
    for d in input_devices():
        vendor = USB_VENDORS.get((d["vid_pid"] or "")[:4])
        devices.append(dict(d, tur="+".join(d["turler"]), uretici=vendor))

    mouse = registry.values("HKCU", r"Control Panel\Mouse")
    keyboard = registry.values("HKCU", r"Control Panel\Keyboard")
    sticky = registry.read("HKCU", r"Control Panel\Accessibility\StickyKeys", "Flags")
    return {
        "cihazlar": devices,
        "fare": {
            "ivme_acik": mouse.get("MouseSpeed", "1") != "0",
            "isaretci_hizi": mouse.get("MouseSensitivity"),
        },
        "klavye": {
            "tekrar_gecikmesi": keyboard.get("KeyboardDelay"),
            "tekrar_hizi": keyboard.get("KeyboardSpeed"),
            "yapiskan_tus_kisayolu_acik": bool(int(sticky) & 4) if sticky and str(sticky).isdigit() else None,
        },
        "polling_rate": {"okunabilir": False},
    }


def parse_wave_format(blob):
    """MMDevices'taki ham biçim değerinden örnekleme hızı/bit derinliği.

    Değerin başında 8 baytlık PROPVARIANT başlığı (VT_BLOB=0x41) olur, ardından
    WAVEFORMATEX gelir. Tutarlılık kontrolü geçmezse None döner.
    """
    if not isinstance(blob, bytes):
        return None
    for offset in (8, 0):
        if len(blob) < offset + 18:
            continue
        b = blob[offset:]
        tag = int.from_bytes(b[0:2], "little")
        channels = int.from_bytes(b[2:4], "little")
        rate = int.from_bytes(b[4:8], "little")
        avg = int.from_bytes(b[8:12], "little")
        align = int.from_bytes(b[12:14], "little")
        bits = int.from_bytes(b[14:16], "little")
        if not (channels and rate and bits and align == channels * bits // 8 and avg == rate * align):
            continue
        valid_bits = bits
        if tag == WAVE_FORMAT_EXTENSIBLE and len(b) >= 20:
            valid_bits = int.from_bytes(b[18:20], "little") or bits
        return {"hz": rate, "bit": valid_bits, "kanal": channels}
    return None


def _endpoints(flow):
    rows = []
    base = f"{AUDIO_ROOT}\\{flow}"
    for guid in registry.subkeys("HKLM", base):
        path = f"{base}\\{guid}"
        if registry.read("HKLM", path, "DeviceState") != 1:
            continue
        props = path + r"\Properties"
        entry = {
            "ad": registry.read("HKLM", props, PKEY_DEVICE_DESC),
            "_yerel_arabirim": registry.read("HKLM", props, PKEY_INTERFACE_NAME),
        }
        if flow == "Render":
            sysfx = registry.read("HKLM", path + r"\FxProperties", PKEY_DISABLE_SYSFX)
            entry["gelistirmeler"] = {1: "kapali", 0: "acik"}.get(sysfx, "belirtilmemis")
            entry["bicim"] = parse_wave_format(registry.read("HKLM", props, PKEY_DEVICE_FORMAT))
        rows.append(entry)
    return rows


def collect_audio():
    return {
        "cikis": _endpoints("Render"),
        "giris_sayisi": len(_endpoints("Capture")),
        "iletisim_kisma": registry.read("HKCU", r"Software\Microsoft\Multimedia\Audio", "UserDuckingPreference"),
        "not": t("tarama.not.ses"),
    }
