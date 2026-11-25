"""Fare ve klavyeler: gerçek ad (cihazın USB/Bluetooth'a bildirdiği ad) ve VID:PID.

Windows'un aygıt yöneticisi kütüphanesi (cfgmgr32.dll) ctypes ile, SALT OKUNUR kullanılır:
- CM_Get_Device_ID_ListW: takılı fare/klavye aygıtları (sınıf GUID'iyle süzülür)
- CM_Get_Parent: aygıtın üst düğümleri (aynı fiziksel cihaz: HID -> USB)
- CM_Get_DevNode_PropertyW: DEVPKEY_Device_BusReportedDeviceDesc (cihazın kendi bildirdiği ad,
  ör. "NuPhy Air75 HE") ve DEVPKEY_Device_DeviceDesc (Windows'un genel adı)
Belgeler: learn.microsoft.com/windows/win32/api/cfgmgr32 , devpkey.h

Ad yalnızca aynı VID:PID'ye sahip düğümlerden alınır; üst veri yolundan (ör. "PCI to ISA Bridge")
ad alınmaz. Ad yoksa Windows'un verdiği ad kalır (tahmin edilmez).

Gizlilik: aygıt örnek kimlikleri (bazı cihazlarda seri numarası içerir) dışarı verilmez;
yalnızca VID:PID, ad ve bağlantı türü döner.
"""

import ctypes
import uuid
from ctypes import byref, c_ubyte, c_uint32, c_ulong, c_wchar

from app.core import log

_log = log.get("input")

CLASS_MOUSE = "{4d36e96f-e325-11ce-bfc1-08002be10318}"
CLASS_KEYBOARD = "{4d36e96b-e325-11ce-bfc1-08002be10318}"
CM_GETIDLIST_FILTER_CLASS = 0x200
CM_GETIDLIST_FILTER_PRESENT = 0x100
CR_SUCCESS = 0
DEVPROP_TYPE_STRING = 0x12
BUS_REPORTED_DESC = ("540b947e-8b40-45bc-a8a2-6a0b894cbda2", 4)
DEVICE_DESC = ("a45c254e-df1c-4efd-8020-67d146a850e0", 2)
GENERIC_NAMES = ("usb input device", "usb composite device", "hid-compliant", "hid keyboard device",
                 "usb receiver", "usb device", "")


class _Guid(ctypes.Structure):
    _fields_ = [("bytes", c_ubyte * 16)]


class _PropKey(ctypes.Structure):
    _fields_ = [("fmtid", _Guid), ("pid", c_ulong)]


def _key(spec):
    key = _PropKey()
    ctypes.memmove(byref(key.fmtid), uuid.UUID(spec[0]).bytes_le, 16)
    key.pid = spec[1]
    return key


def _cfg():
    return ctypes.windll.cfgmgr32


def _id_list(class_guid):
    cfg = _cfg()
    flags = CM_GETIDLIST_FILTER_CLASS | CM_GETIDLIST_FILTER_PRESENT
    size = c_ulong()
    if cfg.CM_Get_Device_ID_List_SizeW(byref(size), class_guid, flags) != CR_SUCCESS or not size.value:
        return []
    buffer = (c_wchar * size.value)()
    if cfg.CM_Get_Device_ID_ListW(class_guid, buffer, size, flags) != CR_SUCCESS:
        return []
    return [item for item in ctypes.wstring_at(buffer, size.value).split("\0") if item]


def _locate(instance_id):
    node = c_uint32()
    return node.value if _cfg().CM_Locate_DevNodeW(byref(node), instance_id, 0) == CR_SUCCESS else None


def _device_id(node):
    buffer = (c_wchar * 512)()
    return buffer.value if _cfg().CM_Get_Device_IDW(node, buffer, 512, 0) == CR_SUCCESS else ""


def _parent(node):
    parent = c_uint32()
    return parent.value if _cfg().CM_Get_Parent(byref(parent), node, 0) == CR_SUCCESS else None


def _string_property(node, spec):
    key = _key(spec)
    prop_type = c_ulong()
    size = c_ulong(0)
    _cfg().CM_Get_DevNode_PropertyW(node, byref(key), byref(prop_type), None, byref(size), 0)
    if not size.value:
        return ""
    buffer = (c_ubyte * size.value)()
    if _cfg().CM_Get_DevNode_PropertyW(node, byref(key), byref(prop_type), buffer, byref(size), 0) != CR_SUCCESS:
        return ""
    if prop_type.value != DEVPROP_TYPE_STRING:
        return ""
    return ctypes.wstring_at(ctypes.addressof(buffer)).strip()


def vid_pid(instance_id):
    """"VID_19F5&PID_6120" veya Bluetooth "VID&0219F5_PID&6120" / "VID&0002046D_PID&B023" -> (VID, PID)."""
    import re  # noqa: WPS433
    text = instance_id.upper()
    match = re.search(r"VID_([0-9A-F]{4})&PID_([0-9A-F]{4})", text) or \
        re.search(r"VID&[0-9A-F]*?([0-9A-F]{4})_PID&([0-9A-F]{4})", text)
    return (match.group(1), match.group(2)) if match else (None, None)


def _bus(chain):
    for instance_id in chain:
        upper = instance_id.upper()
        if upper.startswith(("BTHENUM", "BTHLE", "BTHLEDEVICE", "BTHHFENUM")):
            return "bluetooth"
        if upper.startswith("USB\\"):
            return "usb"
    return "dahili"


def _is_generic(name):
    low = (name or "").strip().lower()
    return any(low == g or (g and low.startswith(g)) for g in GENERIC_NAMES)


def read_device(instance_id):
    """Tek bir aygıt: {ad, windows_adi, vid, pid, baglanti}."""
    node = _locate(instance_id)
    if node is None:
        return None
    vid, pid = vid_pid(instance_id)
    windows_name = _string_property(node, DEVICE_DESC)
    name = ""
    chain = [instance_id]
    current, depth = node, 0
    while current is not None and depth < 6:
        current_id = _device_id(current) if depth else instance_id
        if depth:
            chain.append(current_id)
        node_vid, node_pid = vid_pid(current_id)
        if vid is None and node_vid:
            vid, pid = node_vid, node_pid
        same_device = node_vid is not None and (node_vid, node_pid) == (vid, pid)
        if same_device and not name:
            reported = _string_property(current, BUS_REPORTED_DESC)
            if reported and not _is_generic(reported):
                name = reported
        if depth and node_vid is None and vid is not None:
            break  # fiziksel cihazın dışına (hub, veri yolu) çıkıldı
        current = _parent(current)
        depth += 1
    return {"ad": name or windows_name, "windows_adi": windows_name, "vid": vid, "pid": pid,
            "baglanti": _bus(chain), "gercek_ad": bool(name)}


def input_devices():
    """Takılı fare ve klavyeler, fiziksel cihaza göre gruplanmış.

    Dönen öğe: {anahtar: "19F5:6120" (VID:PID yoksa Windows adı), ad, vid_pid, turler: ["fare", "klavye"],
    baglanti, gercek_ad, adet}. Okunamazsa boş liste.
    """
    try:
        lists = (("fare", _id_list(CLASS_MOUSE)), ("klavye", _id_list(CLASS_KEYBOARD)))
    except (AttributeError, OSError) as exc:
        _log.warning("Giriş aygıtları okunamadı: %s", exc)
        return []
    groups = {}
    for kind, ids in lists:
        for instance_id in ids:
            try:
                info = read_device(instance_id)
            except OSError:
                continue
            if info is None:
                continue
            vp = f"{info['vid']}:{info['pid']}" if info["vid"] else None
            key = vp or f"{info['baglanti']}:{info['ad']}"
            entry = groups.setdefault(key, {"anahtar": key, "ad": info["ad"], "vid_pid": vp, "turler": [],
                                            "baglanti": info["baglanti"], "gercek_ad": info["gercek_ad"],
                                            "adet": 0})
            if info["gercek_ad"] and not entry["gercek_ad"]:
                entry.update(ad=info["ad"], gercek_ad=True)
            if kind not in entry["turler"]:
                entry["turler"].append(kind)
            entry["adet"] += 1
    return sorted(groups.values(), key=lambda e: (not e["gercek_ad"], e["ad"].lower()))


