"""Bir ayarın bu bilgisayarda gösterilip gösterilmeyeceği.

Windows sürümü/build'i, laptop/masaüstü, ekran kartı üreticisi, koşullar
(HDD var mı, Wi-Fi var mı...) ve yer tutucu çözümü birlikte değerlendirilir.
"""

import ctypes
import struct

from app.core import admin, powershell, registry, settings
from app.engine import resolvers

PORTABLE_CHASSIS = {8, 9, 10, 11, 12, 14, 18, 21, 30, 31, 32}
PLATFORM_ROLE_MOBILE = 2   # PowerDeterminePlatformRoleEx; WMI PCSystemType aynı değeri verir


def chassis_types(raw):
    """Ham SMBIOS tablosundan (GetSystemFirmwareTable 'RSMB') kasa türleri: tip 3 yapısının 5. baytı."""
    length = struct.unpack_from("<I", raw, 4)[0]
    data, i, found = raw[8:8 + length], 0, []
    while i + 4 <= len(data):
        kind, size = data[i], data[i + 1]
        if size < 4 or kind == 127:
            break
        if kind == 3 and size > 5:
            found.append(data[i + 5] & 0x7F)
        end = data.find(b"\0\0", i + size)
        i = end + 2 if end >= 0 else len(data)
    return found


def _native_form():
    """Laptop mu? WMI (PowerShell) olmadan: SMBIOS kasa türü + güç platformu rolü. Okunamazsa None."""
    try:
        k32 = ctypes.WinDLL("kernel32")
        rsmb = int.from_bytes(b"RSMB", "big")
        size = k32.GetSystemFirmwareTable(rsmb, 0, None, 0)
        buf = ctypes.create_string_buffer(size)
        if not size or k32.GetSystemFirmwareTable(rsmb, 0, buf, size) != size:
            return None
        role = ctypes.WinDLL("powrprof").PowerDeterminePlatformRoleEx(2)
        chassis = chassis_types(buf.raw)
    except (OSError, AttributeError, struct.error):
        return None
    if not chassis:
        return None
    return "laptop" if set(chassis) & PORTABLE_CHASSIS or role == PLATFORM_ROLE_MOBILE else "masaustu"


GPU_VENDORS = ("NVIDIA", "AMD", "Intel")


def manual_gpu_vendors():
    """Ekran kartı algılanamadıysa kullanıcının Ekran Kartı sayfasında elle seçtiği marka (yoksa boş)."""
    chosen = settings.get("gpu_markasi_elle")
    return [chosen] if chosen in GPU_VENDORS else []


class SystemProfile:
    def __init__(self, windows_version, build, form, gpu_vendors, same_account=True):
        self.windows_version = windows_version  # "10" veya "11"
        self.build = build
        self.form = form  # "laptop" veya "masaustu"
        self.gpu_vendors = gpu_vendors
        self.same_account = same_account

    @classmethod
    def from_scan(cls, scan):
        sections = scan["bolumler"]
        win = sections["sistem"]["windows"]
        hw = sections.get("donanim") or {}
        vendors = sorted({g["uretici"] for g in hw.get("gpu", []) if g.get("uretici")})
        return cls(win["surum"], win["build"], (hw.get("bilgisayar") or {}).get("tur", "masaustu"),
                   vendors or resolvers.gpu_vendors() or manual_gpu_vendors(), admin.session_user_matches())

    @classmethod
    def detect(cls):
        """Tam tarama yapmadan hızlı tespit."""
        build = int(registry.read("HKLM", r"SOFTWARE\Microsoft\Windows NT\CurrentVersion", "CurrentBuild", "0") or 0)
        # Yerel okuma: arayüz iş parçacığından da çağrılabildiği için PowerShell'e (ve onun sırasına) düşmesin.
        form = _native_form()
        if form is None:
            form = "masaustu"
            try:
                data = powershell.run_object(
                    "[pscustomobject]@{c=@((Get-CimInstance Win32_SystemEnclosure).ChassisTypes); "
                    "p=(Get-CimInstance Win32_ComputerSystem).PCSystemType}")
                if set(powershell.as_list(data.get("c"))) & PORTABLE_CHASSIS or data.get("p") == 2:
                    form = "laptop"
            except powershell.PowerShellError:
                pass
        return cls("11" if build >= 22000 else "10", build, form, resolvers.gpu_vendors() or manual_gpu_vendors(),
                   admin.session_user_matches())


class Availability:
    def __init__(self, visible, reasons=None, warnings=None, resolution=None):
        self.visible = visible
        self.reasons = reasons or []  # gizlenme nedenleri: [(anahtar, parametreler)]
        self.warnings = warnings or []  # gösterilir ama uyarıyla
        self.resolution = resolution

    def __repr__(self):
        return f"Availability(visible={self.visible}, reasons={self.reasons}, warnings={self.warnings})"


def _uses_hkcu(tweak):
    islem = tweak.get("islem") or {}
    steps = list(islem.get("adimlar", [])) + [f["adim"] for f in islem.get("alanlar", [])]
    return any(s.get("kok") == "HKCU" for s in steps)


def check(tweak, profile, resolver=resolvers, resolve=True):
    """`resolver` testlerde sahte koşul/çözümleyici vermek içindir."""
    reasons, warnings = [], []
    uyum = tweak["uyumluluk"]

    win = uyum["windows"]
    if profile.windows_version not in win["surumler"]:
        reasons.append(("uyum.windows_surum", {"surum": profile.windows_version}))
    else:
        min_build = win.get("min_build", {}).get(profile.windows_version)
        if min_build and profile.build < min_build:
            reasons.append(("uyum.windows_build", {"build": min_build}))

    form_rule = uyum["form"].get(profile.form, "goster")
    if form_rule == "gizle":
        reasons.append((f"uyum.form_gizle_{profile.form}", {}))
    elif form_rule == "uyar":
        warnings.append((f"uyum.form_uyar_{profile.form}", {}))

    gpus = uyum.get("gpu")
    if gpus and not set(gpus) & set(profile.gpu_vendors):
        reasons.append(("uyum.gpu", {"gpu": ", ".join(gpus)}))

    for cond in uyum.get("kosullar", []):
        result = resolver.check_condition(cond)
        if result is None:
            reasons.append(("uyum.kosul_bilinmiyor", {"kosul": cond["ad"]}))
        elif not result:
            reasons.append((f"uyum.kosul.{cond['ad']}", {}))

    resolution = None
    if tweak["sinif"] == "SWITCH":
        if not profile.same_account and _uses_hkcu(tweak):
            reasons.append(("uyum.farkli_hesap", {}))
        if resolve and not reasons:
            resolution = resolver.resolve(tweak["islem"])
            if not resolution.visible:
                reasons.append(("uyum.cozulemedi", {"neden": resolution.reason}))
    return Availability(not reasons, reasons, warnings, resolution)
