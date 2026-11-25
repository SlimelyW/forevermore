"""Çalışan süreçler, başlangıç uygulamaları ve servisler.

Gizlilik: süreçlerin dosya yolu ve komut satırı OKUNMAZ (içinde kullanıcı adı
olabilir). Yalnızca süreç adı, CPU ve bellek kullanımı alınır.
"""

import json
import os
from collections import defaultdict

from app.core import paths, powershell, registry
from app.core.i18n import t

SAMPLE_SECONDS = 1.5

_PROCESS_PS = rf"""
$a = @(Get-Process | Select-Object Id, ProcessName, CPU)
Start-Sleep -Milliseconds {int(SAMPLE_SECONDS * 1000)}
$b = @(Get-Process | Select-Object Id, ProcessName, CPU, WorkingSet64)
[pscustomobject]@{{a=$a; b=$b}}
"""

_STARTUP_PS = r"""
$items = @(Get-CimInstance Win32_StartupCommand | ForEach-Object {
  $loc = [string]$_.Location
  $kind = if ($loc -match 'Startup') { 'klasor' } elseif ($loc -match '^HKLM') { 'sistem' } else { 'kullanici' }
  [pscustomobject]@{ Name = $_.Name; Tur = $kind }
})
[pscustomobject]@{items=$items}
"""

# Servisin dosya yolu dışarı çıkarılmaz; yalnızca Microsoft'a ait olup olmadığı
# PowerShell içinde hesaplanır.
_SERVICES_PS = r"""
$s = @(Get-CimInstance Win32_Service | ForEach-Object {
  $p = [string]$_.PathName
  $ms = (-not $p) -or ($p -match '(?i)\\Windows\\(system32|SysWOW64|servicing|Microsoft\.NET|WinSxS)\\') -or ($p -match '(?i)Windows Defender|\\Microsoft\\')
  [pscustomobject]@{ Name=$_.Name; DisplayName=$_.DisplayName; StartMode=[string]$_.StartMode; State=[string]$_.State; Ms=$ms }
})
[pscustomobject]@{s=$s}
"""

_STARTUP_APPROVED = [
    ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"),
    ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder"),
    ("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"),
    ("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run32"),
    ("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder"),
]


def _load_known():
    data = json.loads((paths.data_dir() / "bilinen_surecler.json").read_text(encoding="utf-8"))
    return data["kategoriler"]


def _category(name, known):
    lower = name.lower()
    for category, patterns in known.items():
        for pattern in patterns:
            if pattern.endswith("*"):
                if lower.startswith(pattern[:-1]):
                    return category
            elif lower == pattern:
                return category
    return None


def collect_processes():
    data = powershell.run_object(_PROCESS_PS, timeout=60)
    before = {p["Id"]: p.get("CPU") for p in powershell.as_list(data.get("a"))}
    cores = os.cpu_count() or 1
    grouped = defaultdict(lambda: {"adet": 0, "cpu_yuzde": 0.0, "bellek_mb": 0.0})
    for p in powershell.as_list(data.get("b")):
        name = p.get("ProcessName") or "?"
        entry = grouped[name]
        entry["adet"] += 1
        entry["bellek_mb"] += (p.get("WorkingSet64") or 0) / 1024 ** 2
        cpu_now, cpu_before = p.get("CPU"), before.get(p["Id"])
        if cpu_now is not None and cpu_before is not None:
            entry["cpu_yuzde"] += max(0.0, cpu_now - cpu_before) / SAMPLE_SECONDS / cores * 100

    known = _load_known()
    rows = []
    for name, entry in grouped.items():
        if name in ("Idle", "System", "_Total"):
            continue
        rows.append({
            "ad": name,
            "adet": entry["adet"],
            "cpu_yuzde": round(entry["cpu_yuzde"], 1),
            "bellek_mb": round(entry["bellek_mb"]),
            "kategori": _category(name, known),
        })
    by_cpu = sorted(rows, key=lambda r: r["cpu_yuzde"], reverse=True)[:10]
    by_mem = sorted(rows, key=lambda r: r["bellek_mb"], reverse=True)[:10]
    background = sorted((r for r in rows if r["kategori"]), key=lambda r: (r["kategori"], r["ad"].lower()))
    return {
        "toplam_surec": sum(r["adet"] for r in rows),
        "en_cok_cpu": by_cpu,
        "en_cok_bellek": by_mem,
        "bilinen_arka_plan": background,
    }


def _approved_states():
    """Görev Yöneticisi'nde devre dışı bırakılmış başlangıç öğeleri."""
    states = {}
    for root, path in _STARTUP_APPROVED:
        for name, value in registry.values(root, path).items():
            if isinstance(value, bytes) and value:
                # İlk baytın tek olması (03, 07...) "devre dışı" demektir.
                states[name.lower()] = not (value[0] & 1)
    return states


def collect_startup():
    data = powershell.run_object(_STARTUP_PS, timeout=60)
    approved = _approved_states()
    items = []
    seen = set()
    for item in powershell.as_list(data.get("items")):
        name = item.get("Name") or ""
        if (name.lower(), item.get("Tur")) in seen:
            continue  # aynı program hem 32 hem 64 bit Run anahtarında olabilir
        seen.add((name.lower(), item.get("Tur")))
        enabled = approved.get(name.lower(), approved.get(name.lower() + ".lnk", True))
        items.append({"ad": name, "konum": item.get("Tur"), "etkin": enabled})
    items.sort(key=lambda i: (not i["etkin"], i["ad"].lower()))
    return {
        "ogeler": items,
        "etkin_sayisi": sum(1 for i in items if i["etkin"]),
        "not": t("tarama.not.baslangic"),
    }


def collect_services():
    data = powershell.run_object(_SERVICES_PS, timeout=60)
    services = powershell.as_list(data.get("s"))
    third_party_running = [
        {"ad": s["Name"], "gorunen_ad": s.get("DisplayName"), "baslangic": s.get("StartMode")}
        for s in services
        if not s.get("Ms") and s.get("State") == "Running"
    ]
    third_party_running.sort(key=lambda s: (s["gorunen_ad"] or s["ad"]).lower())
    by_name = {s["Name"].lower(): s for s in services}

    def state(name):
        s = by_name.get(name.lower())
        return {"baslangic": s.get("StartMode"), "durum": s.get("State")} if s else None

    return {
        "toplam": len(services),
        "calisan": sum(1 for s in services if s.get("State") == "Running"),
        "ucuncu_parti_calisan": third_party_running,
        # Ayar menülerinde ve "dokunmamalı" uyarılarında kullanılan servisler
        "onemli": {name: state(name) for name in
                   ("Spooler", "SysMain", "WSearch", "DiagTrack", "wuauserv", "WerSvc", "Audiosrv")},
    }
