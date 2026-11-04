"""Güç planı, oyun ayarları (Game Mode, Game Bar/DVR, HAGS, VRR...) ve
güvenlik özelliklerinin (VBS/HVCI, Defender) durumu."""

import re
import subprocess

from app.core import powershell, registry

POWER_SCHEMES = {
    "381b4222-f694-41f0-9685-ff5bb260df2e": "dengeli",
    "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c": "yuksek_performans",
    "a1841308-3541-4fab-bc81-f71556f20b4a": "guc_tasarrufu",
    "e9a42b02-d5df-448d-aa00-03f14749eb61": "nihai_performans",
}
OVERLAYS = {
    "": "dengeli",
    "00000000-0000-0000-0000-000000000000": "dengeli",
    "ded574b5-45a0-4f42-8737-46345c09c238": "en_iyi_performans",
    "961cc777-2547-4f9d-8174-7d86181b8a7a": "en_iyi_verimlilik",
    "3af9b8d9-7c97-431d-ad78-34a8bfea439f": "daha_iyi_performans",
}
GUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)

_SECURITY_PS = r"""
$dg = $null; $mp = $null; $av = @(); $mm = $null
try { $dg = Get-CimInstance -Namespace root\Microsoft\Windows\DeviceGuard -ClassName Win32_DeviceGuard -ErrorAction Stop | Select-Object VirtualizationBasedSecurityStatus, SecurityServicesRunning } catch {}
try { $mp = Get-MpComputerStatus -ErrorAction Stop | Select-Object RealTimeProtectionEnabled, AntivirusEnabled, IsTamperProtected } catch {}
try { $av = @(Get-CimInstance -Namespace root\SecurityCenter2 -ClassName AntiVirusProduct -ErrorAction Stop | Select-Object displayName, productState) } catch {}
try { $mm = Get-MMAgent -ErrorAction Stop | Select-Object MemoryCompression } catch {}
[pscustomobject]@{dg=$dg; mp=$mp; av=$av; mm=$mm}
"""


def _dx_flags():
    value = registry.read("HKCU", r"Software\Microsoft\DirectX\UserGpuPreferences", "DirectXUserGlobalSettings") or ""
    flags = {}
    for part in value.split(";"):
        if "=" in part:
            key, _, val = part.partition("=")
            flags[key.strip()] = val.strip()
    return flags


def _active_scheme():
    guid = (registry.read("HKLM", r"SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes",
                          "ActivePowerScheme") or "").lower()
    name = ""
    try:
        proc = subprocess.run(["powercfg", "/getactivescheme"], capture_output=True, timeout=15,
                              creationflags=powershell.CREATE_NO_WINDOW)
        # powercfg yönlendirilmiş çıktıyı konsol (OEM) kod sayfasıyla yazar; plan adı Windows dilindedir.
        text = proc.stdout.decode("oem", errors="replace")
        match = re.search(r"\(([^)]*)\)\s*$", text.strip())
        name = match.group(1) if match else ""
        if not guid:
            found = GUID_RE.search(text)
            guid = found.group(0).lower() if found else ""
    except (OSError, subprocess.TimeoutExpired):
        pass
    return {"guid": guid, "ad": name, "tur": POWER_SCHEMES.get(guid, "ozel")}


def _overlay():
    key = r"SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes"
    ac = (registry.read("HKLM", key, "ActiveOverlayAcPowerScheme") or "").lower()
    dc = (registry.read("HKLM", key, "ActiveOverlayDcPowerScheme") or "").lower()
    return {"prizde": OVERLAYS.get(ac, "bilinmiyor"), "pilde": OVERLAYS.get(dc, "bilinmiyor")}


def collect_gaming():
    hkcu_gamebar = r"Software\Microsoft\GameBar"
    dvr = r"Software\Microsoft\Windows\CurrentVersion\GameDVR"
    dx = _dx_flags()
    hags = registry.read("HKLM", r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "HwSchMode")
    return {
        "guc_plani": _active_scheme(),
        "guc_modu": _overlay(),
        "oyun_modu": registry.read("HKCU", hkcu_gamebar, "AutoGameModeEnabled", 1) == 1,
        "game_bar": {
            "yakalama_acik": registry.read("HKCU", dvr, "AppCaptureEnabled", 1) == 1,
            "arka_plan_kaydi": registry.read("HKCU", dvr, "HistoricalCaptureEnabled", 0) == 1,
            "game_dvr": registry.read("HKCU", r"System\GameConfigStore", "GameDVR_Enabled", 1) == 1,
        },
        "hags": {2: "acik", 1: "kapali"}.get(hags, "bilinmiyor"),
        "vrr_windows": {"1": "acik", "0": "kapali"}.get(dx.get("VRROptimizeEnable"), "ayarlanmamis"),
        "pencereli_oyun_iyilestirme": {"1": "acik", "0": "kapali"}.get(dx.get("SwapEffectUpgradeEnable"), "ayarlanmamis"),
        "arka_plan_uygulamalari": {
            "ilke": registry.read("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\AppPrivacy", "LetAppsRunInBackground"),
            "kullanici_kapatti": registry.read(
                "HKCU", r"Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications",
                "GlobalUserDisabled", 0) == 1,
        },
        "fare_ivmesi": registry.read("HKCU", r"Control Panel\Mouse", "MouseSpeed", "1") != "0",
    }


def collect_security():
    data = powershell.run_object(_SECURITY_PS, timeout=60)
    dg = data.get("dg") or {}
    running = powershell.as_list(dg.get("SecurityServicesRunning"))
    mp = data.get("mp")
    others = [a.get("displayName") for a in powershell.as_list(data.get("av"))
              if a.get("displayName") and "defender" not in a["displayName"].lower()]
    mm = data.get("mm")
    return {
        "vbs": {0: "kapali", 1: "etkin_calismiyor", 2: "calisiyor"}.get(dg.get("VirtualizationBasedSecurityStatus"), "bilinmiyor"),
        "hvci_calisiyor": (2 in running) if dg else None,
        "defender_gercek_zamanli": mp.get("RealTimeProtectionEnabled") if mp else None,
        "kurcalama_korumasi": mp.get("IsTamperProtected") if mp else None,
        "diger_antivirusler": others,
        "bellek_sikistirma": mm.get("MemoryCompression") if mm else None,
    }
