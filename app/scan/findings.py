"""Tarama verisinden kullanıcıya gösterilecek bulguları çıkarır.

Her bulgu: {kod, seviye, params, ilgili}. Metinler lang/tr.json'daki
"bulgu.<kod>.baslik" ve "bulgu.<kod>.aciklama" anahtarlarındadır.
Seviyeler: sorun > uyari > bilgi > iyi.
"""

import datetime

SEVERITY_ORDER = {"sorun": 0, "uyari": 1, "bilgi": 2, "iyi": 3}

# Taramanın kendisinin başlattığı süreçler "işlemciyi yoran süreç" sayılmaz.
OWN_PROCESSES = {"powershell", "python", "pythonw", "py", "forevermore", "pcoptimizer", "wmiprvse", "conhost"}

HIGH_CPU_PERCENT = 15
REPEAT_THRESHOLD = 3
DRIVER_OLD_DAYS = 365
UPDATE_OLD_DAYS = 60


def _f(kod, seviye, ilgili=None, **params):
    return {"kod": kod, "seviye": seviye, "ilgili": ilgili or [], "params": params}


def tespit_bulgusu(item):
    level = "sorun" if item["durum"] == "zararlı" else "uyari"
    return _f("tespit", level, [item["id"]], ad=item["ad"], mesaj=item["mesaj"])


def _displays(hw, out):
    displays = hw.get("ekranlar") or []
    low = [d for d in displays if d["yenileme_hz"] + 1 < d["bu_cozunurlukte_en_yuksek_hz"]]
    for d in low:
        out.append(_f("ekran_hz_dusuk", "sorun", ["DISP-001"], monitor=d["monitor"] or d["ekran_karti"],
                      hz=d["yenileme_hz"], max_hz=d["bu_cozunurlukte_en_yuksek_hz"]))
    if displays and not low:
        out.append(_f("ekran_hz_iyi", "iyi"))


def _ram(hw, system, out):
    ram = hw.get("ram") or {}
    modules = ram.get("moduller") or []
    if modules:
        if ram.get("kanal") == "tek":
            out.append(_f("ram_tek_kanal", "uyari"))
        elif ram.get("kanal") == "cift_veya_fazla":
            out.append(_f("ram_cift_kanal", "iyi"))
        if ram.get("xmp_expo") == "kapali_olabilir":
            out.append(_f("ram_xmp", "uyari", hiz=modules[0]["calisan_hiz"]))
        elif ram.get("modul_hizinin_altinda"):
            m = modules[0]
            out.append(_f("ram_yavas", "bilgi", modul=m["modul_hizi"], calisan=m["calisan_hiz"]))
    memory = (system or {}).get("bellek") or {}
    if memory.get("kullanim_yuzde", 0) >= 85:
        out.append(_f("ram_dolu", "uyari", yuzde=memory["kullanim_yuzde"]))
    if 0 < memory.get("toplam_gb", 99) < 7.5:
        out.append(_f("ram_az", "uyari", gb=memory["toplam_gb"]))


def _storage(st, out):
    for disk in st.get("diskler") or []:
        if disk["sistem_diski"] and disk["tur"] == "HDD":
            out.append(_f("sistem_hdd", "uyari"))
        if disk.get("saglik") and disk["saglik"] not in ("Healthy", "0"):
            out.append(_f("disk_saglik", "sorun", ad=disk["ad"], saglik=disk["saglik"]))
        if (disk.get("asinma_yuzde") or 0) >= 80:
            out.append(_f("disk_asinma", "uyari", ad=disk["ad"], asinma=disk["asinma_yuzde"]))
    for vol in st.get("birimler") or []:
        if vol["doluluk_yuzde"] >= 80:
            out.append(_f("disk_dolu", "sorun" if vol["doluluk_yuzde"] >= 90 else "uyari",
                          surucu=vol["surucu"], doluluk=vol["doluluk_yuzde"], bos=vol["bos_gb"]))
    temp_gb = sum(v["gb"] for v in (st.get("gecici_dosyalar") or {}).values())
    if temp_gb >= 2:
        out.append(_f("gecici_dosya", "bilgi", gb=round(temp_gb, 1)))
    update = st.get("windows_update") or {}
    if (update.get("gecen_gun") or 0) >= UPDATE_OLD_DAYS:
        out.append(_f("update_eski", "uyari", ["SYS-014"], gun=update["gecen_gun"]))
    if update.get("yeniden_baslatma_bekliyor"):
        out.append(_f("update_reboot", "bilgi"))
    bad = st.get("sorunlu_cihazlar") or []
    if bad:
        out.append(_f("sorunlu_cihaz", "uyari", liste=", ".join(b["ad"] or "?" for b in bad[:5])))


def _software(procs, startup, out):
    if (startup or {}).get("etkin_sayisi", 0) >= 10:
        out.append(_f("baslangic_cok", "uyari", ["SYS-006"], adet=startup["etkin_sayisi"]))
    for p in (procs or {}).get("en_cok_cpu") or []:
        if p["ad"].lower() not in OWN_PROCESSES and p["cpu_yuzde"] >= HIGH_CPU_PERCENT:
            out.append(_f("yuksek_cpu", "uyari", ad=p["ad"], cpu=round(p["cpu_yuzde"])))
            break
    background = [p["ad"] for p in (procs or {}).get("bilinen_arka_plan") or []
                  if p["kategori"] not in ("tarayici",)]
    if background:
        out.append(_f("arka_plan", "bilgi", ["PERF-011"], liste=", ".join(background[:12])))


def _events(ev, out):
    if not ev:
        return
    days = ev["gun"]
    services = [s for s in ev["servis_hatalari"] if s["adet"] >= REPEAT_THRESHOLD]
    if services:
        out.append(_f("servis_hatasi", "uyari", liste=", ".join(s["servis"] for s in services[:5]), gun=days))
    apps = [a for a in ev["program_cokmeleri"] if a["adet"] >= REPEAT_THRESHOLD]
    if apps:
        out.append(_f("program_cokmesi", "uyari", liste=", ".join(a["program"] for a in apps[:5]), gun=days))
    summary = ev["ozet"]
    for key, kod, level, related in (("mavi_ekran", "mavi_ekran", "sorun", []),
                                     ("disk", "disk_olay", "sorun", []),
                                     ("beklenmeyen_kapanma", "beklenmeyen_kapanma", "uyari", []),
                                     ("ekran_surucusu", "ekran_surucusu", "uyari", ["GPU-019"]),
                                     ("donanim_whea", "whea", "uyari", [])):
        if summary[key]["adet"]:
            out.append(_f(kod, level, related, adet=summary[key]["adet"], gun=days))


def _gpu(hw, out):
    today = datetime.date.today()
    for gpu in hw.get("gpu") or []:
        if not gpu.get("uretici") or not gpu.get("surucu_tarihi"):
            continue
        try:
            age = (today - datetime.date.fromisoformat(gpu["surucu_tarihi"])).days
        except ValueError:
            continue
        if age >= DRIVER_OLD_DAYS:
            out.append(_f("gpu_surucu_eski", "bilgi", ["GPU-019"], ad=gpu["ad"], gun=age))


def _gaming(game, system, hw, security, out):
    if not game:
        return
    if not game.get("oyun_modu"):
        out.append(_f("oyun_modu_kapali", "bilgi", ["PERF-001"]))
    if game["game_bar"].get("arka_plan_kaydi"):
        out.append(_f("arka_plan_kaydi", "uyari", ["PERF-002"]))
    if game["guc_plani"].get("tur") == "guc_tasarrufu":
        out.append(_f("guc_tasarrufu", "uyari", ["PWR-001"]))
    if game["guc_modu"].get("prizde") == "en_iyi_verimlilik":
        out.append(_f("guc_modu_verimlilik", "uyari", ["PWR-002"]))
    if game.get("fare_ivmesi"):
        out.append(_f("fare_ivmesi", "bilgi", ["INP-002"]))
    power = (system or {}).get("guc") or {}
    if (hw.get("bilgisayar") or {}).get("tur") == "laptop" and power.get("prizde") is False:
        out.append(_f("pilde", "bilgi", ["PWR-006"]))
    if (security or {}).get("hvci_calisiyor"):
        out.append(_f("hvci", "bilgi", ["PERF-003"]))


def _audio(audio, out):
    for device in (audio or {}).get("cikis") or []:
        fmt = device.get("bicim")
        if fmt and fmt["hz"] > 48000:
            out.append(_f("ses_ornekleme", "bilgi", ["AUD-002"], ad=device["ad"], hz=fmt["hz"], bit=fmt["bit"]))
    not_off = [d["ad"] for d in (audio or {}).get("cikis") or [] if d.get("gelistirmeler") != "kapali"]
    if not_off:
        out.append(_f("ses_gelistirme", "bilgi", ["AUD-001"], liste=", ".join(not_off)))


def _network(net, out):
    adapters = (net or {}).get("bagdastiricilar") or []
    wired_up = [a for a in adapters if a["tur"] == "kablolu" and a["bagli"]]
    wifi_up = [a for a in adapters if a["tur"] == "wifi" and a["bagli"]]
    for a in wired_up:
        if a["hiz_mbps"] and a["hiz_mbps"] <= 100:
            out.append(_f("ethernet_yavas", "uyari", ad=a["ad"], hiz=int(a["hiz_mbps"])))
    if wifi_up and not wired_up:
        out.append(_f("yalnizca_wifi", "bilgi", ["NET-001"]))


def build(scan):
    sections = scan["bolumler"]
    hw = sections.get("donanim") or {}
    system = sections.get("sistem") or {}
    out = []
    _displays(hw, out)
    _ram(hw, system, out)
    _storage(sections.get("depolama") or {}, out)
    _software(sections.get("surecler"), sections.get("baslangic"), out)
    _events(sections.get("olaylar"), out)
    _gpu(hw, out)
    _gaming(sections.get("oyun"), system, hw, sections.get("guvenlik"), out)
    _audio(sections.get("ses"), out)
    _network(sections.get("ag"), out)
    if (system.get("windows") or {}).get("surum") == "10":
        out.append(_f("windows10", "uyari"))
    out.extend(tespit_bulgusu(item) for item in scan.get("tespitler") or [])
    for option in scan.get("onyukleme_secenekleri") or []:
        out.append(_f(f"onyukleme_{option}", "uyari"))
    if not system.get("yonetici"):
        out.append(_f("yonetici", "bilgi"))
    out.sort(key=lambda f: SEVERITY_ORDER[f["seviye"]])
    return out
