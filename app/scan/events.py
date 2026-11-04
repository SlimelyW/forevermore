"""Olay günlükleri (Event Log): son 7 günde tekrar eden hatalar.

Gizlilik: olay mesajlarının tam metni ALINMAZ (içinde dosya yolu, kullanıcı adı
olabilir). Yalnızca kaynak, olay numarası, tarih ve bilinen olaylarda servis
veya program adı (ör. 'chrome.exe') okunur.
"""

from collections import defaultdict

from app.core import powershell

DAYS = 7

_EVENTS_PS = rf"""
$start = (Get-Date).AddDays(-{DAYS})
function Pack($e) {{
  $p0 = $null
  if ($e.Properties.Count -gt 0) {{ $p0 = [string]$e.Properties[0].Value }}
  [pscustomobject]@{{ P=$e.ProviderName; I=$e.Id; V=[int]$e.Level; T=$e.TimeCreated.ToString('yyyy-MM-dd'); A=$p0 }}
}}
$main = @(Get-WinEvent -FilterHashtable @{{LogName='System','Application'; Level=1,2; StartTime=$start}} -MaxEvents 4000 -ErrorAction SilentlyContinue | ForEach-Object {{ Pack $_ }})
$extra = @(Get-WinEvent -FilterHashtable @{{LogName='System'; ProviderName='Microsoft-Windows-WHEA-Logger','Display'; Level=1,2,3; StartTime=$start}} -MaxEvents 500 -ErrorAction SilentlyContinue | ForEach-Object {{ Pack $_ }})
[pscustomobject]@{{main=$main; extra=$extra}}
"""

SCM = "Service Control Manager"
SERVICE_FAILURE_IDS = {7000, 7001, 7009, 7011, 7022, 7023, 7024, 7026, 7031, 7032, 7034, 7043}
APP_CRASH = {("Application Error", 1000), ("Application Hang", 1002)}
UNEXPECTED_SHUTDOWN = ("Microsoft-Windows-Kernel-Power", 41)
BUGCHECK_PROVIDERS = {"Microsoft-Windows-WER-SystemErrorReporting", "BugCheck"}
DISPLAY_DRIVER = {("Display", 4101), ("nvlddmkm", 13), ("nvlddmkm", 14), ("nvlddmkm", 153),
                  ("amdkmdag", 4101), ("amdwddmg", 4101)}
DISK_PROVIDERS = {"disk", "Ntfs", "Microsoft-Windows-Ntfs", "storahci", "stornvme", "iaStorA", "iaStorAC", "volmgr"}
WHEA = "Microsoft-Windows-WHEA-Logger"
# Çok yaygın ve genelde zararsız olaylar; "en sık hatalar" listesini kirletmesin.
NOISE = {("Microsoft-Windows-DistributedCOM", 10016), ("Microsoft-Windows-DistributedCOM", 10010),
         ("DCOM", 10016), ("DCOM", 10010)}


def _counter():
    return {"adet": 0, "gunler": set()}


def _finish(groups, key_name):
    rows = []
    for key, value in groups.items():
        rows.append({key_name: key, "adet": value["adet"], "gun_sayisi": len(value["gunler"])})
    return sorted(rows, key=lambda r: r["adet"], reverse=True)


def collect_events():
    data = powershell.run_object(_EVENTS_PS, timeout=120)
    events = powershell.as_list(data.get("main")) + powershell.as_list(data.get("extra"))

    services = defaultdict(_counter)
    apps = defaultdict(_counter)
    other = defaultdict(_counter)
    totals = {"beklenmeyen_kapanma": _counter(), "mavi_ekran": _counter(),
              "ekran_surucusu": _counter(), "disk": _counter(), "donanim_whea": _counter()}

    for e in events:
        provider, event_id, day = e.get("P") or "", e.get("I"), e.get("T")
        bucket = None
        if provider == SCM and event_id in SERVICE_FAILURE_IDS and e.get("A"):
            bucket = services[e["A"]]
        elif (provider, event_id) in APP_CRASH and e.get("A"):
            bucket = apps[e["A"].lower()]
        elif (provider, event_id) == UNEXPECTED_SHUTDOWN:
            bucket = totals["beklenmeyen_kapanma"]
        elif provider in BUGCHECK_PROVIDERS and event_id == 1001:
            bucket = totals["mavi_ekran"]
        elif (provider, event_id) in DISPLAY_DRIVER:
            bucket = totals["ekran_surucusu"]
        elif provider in DISK_PROVIDERS and e.get("V") in (1, 2):
            bucket = totals["disk"]
        elif provider == WHEA:
            bucket = totals["donanim_whea"]
        elif e.get("V") in (1, 2) and (provider, event_id) not in NOISE:
            bucket = other[f"{provider} #{event_id}"]
        if bucket is not None:
            bucket["adet"] += 1
            bucket["gunler"].add(day)

    return {
        "gun": DAYS,
        "incelenen_olay": len(events),
        "servis_hatalari": _finish(services, "servis")[:15],
        "program_cokmeleri": _finish(apps, "program")[:15],
        "ozet": {k: {"adet": v["adet"], "gun_sayisi": len(v["gunler"])} for k, v in totals.items()},
        "diger_sik_hatalar": _finish(other, "kaynak")[:10],
    }
