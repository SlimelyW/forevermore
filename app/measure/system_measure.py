"""Sistem ölçümü (SALT OKUNUR): açılış süresi, başlangıç öğeleri, servisler, boştaki CPU/RAM, süreç sayısı."""

import time

from app.core import log, powershell

_log = log.get("measure")

BOOT_TYPES = {0: "soguk", 1: "hizli_baslangic", 2: "hazirda_bekletme"}


def read_boot_info():
    """Son açılış süresi.

    1) Microsoft-Windows-Diagnostics-Performance/Operational, olay 100: Windows'un ölçtüğü
       açılış süresi (BootTime). Yönetici izni gerekir; bazı bilgisayarlarda kaydedilmez.
    2) Yedek: çekirdek başlangıcı (Kernel-General 12) ile oturum açma (Winlogon 7001) arası.
       Bu süre şifre ekranında beklenen zamanı da içerir; yalnızca kabaca karşılaştırılabilir.
    Açılış türü Kernel-Boot olay 27'den okunur (hızlı başlangıç / soğuk açılış).
    """
    data = powershell.run_object(
        "$r = [ordered]@{}; "
        "$e = Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Diagnostics-Performance/Operational';"
        "Id=100} -MaxEvents 1 -ErrorAction SilentlyContinue; "
        "if ($e) { $r.ms = [int64]$e.Properties[5].Value; $r.olay = $e.TimeCreated.ToString('s') }; "
        "$k = Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Kernel-General';"
        "Id=12} -MaxEvents 1 -ErrorAction SilentlyContinue; "
        "$w = Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Winlogon';"
        "Id=7001} -MaxEvents 1 -ErrorAction SilentlyContinue; "
        "if ($k -and $w -and $w.TimeCreated -gt $k.TimeCreated) { "
        "$r.oturum_sn = ($w.TimeCreated - $k.TimeCreated).TotalSeconds; $r.baslangic = $k.TimeCreated.ToString('s') }; "
        "$b = Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Kernel-Boot'; Id=27} "
        "-MaxEvents 1 -ErrorAction SilentlyContinue; "
        "if ($b) { $r.tur = [int]$b.Properties[0].Value }; [pscustomobject]$r", timeout=60) or {}
    result = {"tur": BOOT_TYPES.get(data.get("tur"), "bilinmiyor")}
    if data.get("ms"):
        result.update(sure_sn=round(data["ms"] / 1000, 1), kaynak="olay_100")
    elif data.get("oturum_sn") is not None:
        result.update(sure_sn=round(data["oturum_sn"], 1), kaynak="oturum_acma")
    else:
        result.update(sure_sn=None, kaynak="yok")
    return result


def measure(system, sampler_factory, seconds=30, progress=None, sleep=None):
    """Sistem ölçümü. seconds: boştaki CPU/RAM için örnekleme süresi (saniyede bir örnek)."""
    values, details = {}, {}
    try:
        boot = system.get_boot_info()
        details["acilis"] = boot
        if boot.get("sure_sn") is not None:
            values["acilis_sn"] = boot["sure_sn"]
    except Exception as exc:
        _log.warning("Açılış süresi okunamadı: %s", exc)
    try:
        values["baslangic_uygulama"] = sum(1 for i in system.list_startup_items() if i["etkin"])
    except Exception as exc:
        _log.warning("Başlangıç uygulamaları okunamadı: %s", exc)
    try:
        values["baslangic_gorev"] = sum(1 for i in system.list_logon_tasks() if i["etkin"])
    except Exception as exc:
        _log.warning("Görevler okunamadı: %s", exc)
    try:
        services = system.list_services()
        values["otomatik_servis"] = sum(1 for s in services if s["baslangic"] in ("Automatic", "AutomaticDelayed"))
        values["calisan_servis"] = sum(1 for s in services if s["calisiyor"])
    except Exception as exc:
        _log.warning("Servisler okunamadı: %s", exc)

    try:  # zamanlayıcı hassasiyeti (ayrı süreçte); bkz. app/engine/timer_resolution.py
        precision = system.get_sleep_precision()
        values["uyku_1ms"] = precision["ortalama"]
        details["uyku_1ms_p99"] = precision["p99"]
    except Exception as exc:
        _log.warning("Sleep(1) ölçülemedi: %s", exc)

    sleep = sleep or time.sleep
    sampler = sampler_factory()
    cpu, ram, procs = [], [], []
    try:
        for second in range(seconds):
            sleep(1)
            sample = sampler.sample()
            if sample.get("cpu") is not None:
                cpu.append(sample["cpu"])
            if sample.get("ram_kullanilan"):
                ram.append(sample["ram_kullanilan"] / 2 ** 30)
            if sample.get("surec_sayisi") is not None:
                procs.append(sample["surec_sayisi"])
            if progress:
                progress(second + 1, seconds)
    finally:
        sampler.close()
    if cpu:
        values["bosta_cpu"] = round(sum(cpu) / len(cpu), 1)
        details["bosta_cpu_en_yuksek"] = round(max(cpu), 1)
    if ram:
        values["bosta_ram_gb"] = round(sum(ram) / len(ram), 2)
    if procs:
        values["surec_sayisi"] = round(sum(procs) / len(procs))
    details["ornek_sayisi"] = len(cpu)
    return values, details
