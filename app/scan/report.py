"""Tarama raporu: okunabilir metin ve JSON.

Kaydedilen rapor her zaman gizlilik filtresinden geçer ("_yerel" alanlar
çıkarılır, kullanıcı/bilgisayar adı, IP, MAC temizlenir). Kullanıcı bu dosyayı
güvenle sana gönderebilir.
"""

import datetime
import json

from app.core import log, paths, privacy
from app.core.i18n import fmt_date, t, value_label
from app.scan.displays import label as display_label

_log = log.get("report")


def _yes_no(value):
    if value is None:
        return t("deger.bilinmiyor")
    return t("deger.evet") if value else t("deger.hayir")


def _on_off(value):
    if value is None:
        return t("deger.bilinmiyor")
    return t("deger.acik") if value else t("deger.kapali")


def _section(lines, key):
    lines += ["", "=" * 60, t(f"bolum.{key}"), "=" * 60]


def _system(lines, s):
    w = s["windows"]
    lines.append(t("rapor.windows", ad=w["ad"], surum_kodu=w["surum_kodu"], build=w["build"], ubr=w["ubr"]))
    lines.append(t("rapor.acik_kalma", saat=s["acik_kalma_saat"]))
    m = s["bellek"]
    lines.append(t("rapor.bellek", yuzde=m["kullanim_yuzde"], bos=m["bos_gb"], toplam=m["toplam_gb"]))
    power = s.get("guc") or {}
    if power.get("pil_var"):
        state = t("deger.prizde") if power.get("prizde") else t("deger.pilde", yuzde=power.get("pil_yuzde"))
        lines.append(t("rapor.guc", durum=state))


def _hardware(lines, h):
    pc = h["bilgisayar"]
    lines.append(t("rapor.bilgisayar", uretici=pc["uretici"], model=pc["model"], tur=t(f"deger.{pc['tur']}")))
    cpu = h["cpu"]
    lines.append(t("rapor.cpu", ad=cpu["ad"], cekirdek=cpu["cekirdek"], thread=cpu["is_parcacigi"]))
    for gpu in h["gpu"]:
        lines.append(t("rapor.gpu", ad=gpu["ad"], surum=gpu["surucu_surumu"], tarih=gpu["surucu_tarihi"]))
        if gpu.get("rol"):
            driven = len(gpu.get("ekran_suruyor") or [])
            screen = (t("rapor.gpu_rol_ekran", adet=driven) if driven else
                      t("rapor.gpu_rol_ekran_yok") if gpu["rol"] == "yuksek_performans" else "")
            lines.append(t("rapor.gpu_rol", rol=value_label("ui.gpu_rol_kisa", gpu["rol"]), ekran=screen))
    for row in h.get("nvidia_smi") or []:
        lines.append(t("rapor.nvidia_smi", surucu=row["surucu"], vram=row["vram_mb"],
                       sicaklik=row["sicaklik_c"], pstate=row["guc_durumu"]))
    if any(g["uretici"] == "NVIDIA" for g in h["gpu"]):
        lines.append(t("rapor.nvidia_panel"))
    ram = h["ram"]
    if ram.get("moduller"):
        first = ram["moduller"][0]
        lines.append(t("rapor.ram", toplam=ram["toplam_gb"], tur=first["tur"], adet=len(ram["moduller"]),
                       kanal=t(f"deger.kanal_{ram['kanal']}"), hiz=first["calisan_hiz"],
                       modul_hizi=first["modul_hizi"]))
        lines.append(t("rapor.ram_xmp", durum=t(f"deger.xmp_{ram['xmp_expo']}")))
    mb = h["anakart"]
    lines.append(t("rapor.anakart", uretici=mb["uretici"], model=mb["model"], bios=mb["bios_surumu"],
                   tarih=mb["bios_tarihi"]))
    _section(lines, "ekranlar")
    for index, d in enumerate(h["ekranlar"], 1):
        lines.append(t("rapor.ekran", monitor=display_label(d, index), cozunurluk=d["cozunurluk"],
                       hz=d["yenileme_hz"], max_hz=d["bu_cozunurlukte_en_yuksek_hz"],
                       birincil=t("rapor.birincil") if d["birincil"] else ""))
        if d.get("ekran_karti"):
            lines.append(t("rapor.ekran_karti", ad=d["ekran_karti"]))


def _processes(lines, p):
    lines.append(t("rapor.surec_ozet", adet=p["toplam_surec"]))
    for row in p["en_cok_cpu"][:8]:
        lines.append(t("rapor.surec_satir", ad=row["ad"], adet=row["adet"], cpu=row["cpu_yuzde"], bellek=row["bellek_mb"]))
    lines.append(t("rapor.surec_bellek"))
    for row in p["en_cok_bellek"][:8]:
        lines.append(t("rapor.surec_satir", ad=row["ad"], adet=row["adet"], cpu=row["cpu_yuzde"], bellek=row["bellek_mb"]))
    if p["bilinen_arka_plan"]:
        lines.append(t("rapor.arka_plan"))
        for row in p["bilinen_arka_plan"]:
            lines.append(t("rapor.arka_plan_satir", kategori=t(f"surec_kategori.{row['kategori']}"), ad=row["ad"]))


def _startup(lines, s):
    lines.append(t("rapor.baslangic_ozet", etkin=s["etkin_sayisi"], toplam=len(s["ogeler"])))
    for item in s["ogeler"]:
        lines.append(t("rapor.baslangic_satir", durum="[+]" if item["etkin"] else "[-]", ad=item["ad"],
                       konum=t(f"deger.konum_{item['konum']}")))


def _services(lines, s):
    lines.append(t("rapor.servis_ozet", toplam=s["toplam"], calisan=s["calisan"], adet=len(s["ucuncu_parti_calisan"])))
    for row in s["ucuncu_parti_calisan"]:
        lines.append(t("rapor.servis_satir", ad=row["gorunen_ad"] or row["ad"], baslangic=row["baslangic"]))


def _events(lines, e):
    lines.append(t("rapor.olay_ozet", gun=e["gun"], adet=e["incelenen_olay"]))
    for key, value in e["ozet"].items():
        if value["adet"]:
            lines.append(t("rapor.olay_sayac", ad=t(f"olay.{key}"), adet=value["adet"], gun=value["gun_sayisi"]))
    for title, rows, field in (("rapor.olay_servis", e["servis_hatalari"], "servis"),
                               ("rapor.olay_program", e["program_cokmeleri"], "program"),
                               ("rapor.olay_diger", e["diger_sik_hatalar"], "kaynak")):
        if rows:
            lines.append(t(title))
            for row in rows[:8]:
                lines.append(t("rapor.olay_sayac", ad=row[field], adet=row["adet"], gun=row["gun_sayisi"]))


def _gaming(lines, g):
    plan = g["guc_plani"]
    # Bilinen planlar uygulamanın dilinde, özel planlar kendi adıyla gösterilir.
    name = plan["ad"] if plan["tur"] == "ozel" and plan["ad"] else t(f"deger.plan_{plan['tur']}")
    lines.append(t("rapor.guc_plani", ad=name))
    lines.append(t("rapor.guc_modu", prizde=t(f"deger.mod_{g['guc_modu']['prizde']}"),
                   pilde=t(f"deger.mod_{g['guc_modu']['pilde']}")))
    for name, value in (("ad.oyun_modu", _on_off(g["oyun_modu"])),
                        ("ad.arka_plan_kaydi", _on_off(g["game_bar"]["arka_plan_kaydi"])),
                        ("ad.hags", t(f"deger.{g['hags']}")),
                        ("ad.vrr", t(f"deger.{g['vrr_windows']}")),
                        ("ad.pencereli", t(f"deger.{g['pencereli_oyun_iyilestirme']}")),
                        ("ad.arka_plan_uyg", _on_off(g["arka_plan_uygulamalari"]["ilke"] == 2
                                                     or g["arka_plan_uygulamalari"]["kullanici_kapatti"]))):
        lines.append(t("rapor.oyun_ayar", ad=t(name), deger=value))


def _security(lines, s):
    for name, value in (("ad.vbs", t(f"deger.vbs_{s['vbs']}")),
                        ("ad.hvci", _on_off(s["hvci_calisiyor"])),
                        ("ad.defender", _on_off(s["defender_gercek_zamanli"])),
                        ("ad.diger_av", ", ".join(s["diger_antivirusler"]) or "—"),
                        ("ad.bellek_sikistirma", _on_off(s["bellek_sikistirma"]))):
        lines.append(t("rapor.guvenlik_satir", ad=t(name), deger=value))


def _network(lines, n):
    for a in n["bagdastiricilar"]:
        status = f"{int(a['hiz_mbps'])} Mbps" if a["bagli"] and a["hiz_mbps"] else t("rapor.ag_bagli" if a["bagli"] else "rapor.ag_bagli_degil")
        dns = t("deger.dns_elle") if a["dns"]["elle_ayarli"] else t("deger.dns_otomatik")
        providers = [t(f"deger.dns_{p}") if p in ("yerel_ag", "yerel_proxy", "diger_genel") else p
                     for p in a["dns"]["saglayici"]]
        if providers:
            dns += " (" + ", ".join(providers) + ")"
        lines.append(t("rapor.ag_satir", ad=a["ad"], tur=a["tur"], durum=status, dns=dns,
                       nagle=_yes_no(a["nagle_kapali"])))
    lines.append(t("rapor.ag_tcp", otomatik=n["tcp"]["otomatik_ayar"], algo=n["tcp"]["tikaniklik_algoritmasi"]))


def _input(lines, i):
    for d in i["cihazlar"]:
        kinds = " + ".join(value_label("deger.cihaz_turu", k) for k in d.get("turler") or [d["tur"]])
        vendor = ", ".join(x for x in (d.get("vid_pid") and f"VID:PID {d['vid_pid']}", d["uretici"]) if x)
        lines.append(t("rapor.cihaz_satir", tur=kinds, ad=d["ad"],
                       baglanti=value_label("deger.baglanti", d["baglanti"]),
                       uretici=f", {vendor}" if vendor else "", adet=d["adet"]))
    lines.append(t("rapor.fare", ivme=_on_off(i["fare"]["ivme_acik"]), hiz=i["fare"]["isaretci_hizi"]))
    lines.append(t("rapor.klavye", gecikme=i["klavye"]["tekrar_gecikmesi"], hiz=i["klavye"]["tekrar_hizi"]))
    lines.append(t("rapor.polling"))


def _audio(lines, a):
    for d in a["cikis"]:
        fmt = d.get("bicim")
        lines.append(t("rapor.ses_satir", ad=d["ad"],
                       bicim=t("rapor.ses_bicim", hz=fmt["hz"], bit=fmt["bit"]) if fmt else t("deger.bilinmiyor"),
                       gelistirme=t(f"deger.{d['gelistirmeler']}")))


def _storage(lines, s):
    for d in s["diskler"]:
        extra = ""
        if d.get("sicaklik_c") is not None:
            extra = t("rapor.disk_ek", sicaklik=d["sicaklik_c"], asinma=d.get("asinma_yuzde"))
        lines.append(t("rapor.disk_satir", ad=d["ad"], tur=d["tur"], baglanti=d["baglanti"], boyut=d["boyut_gb"],
                       saglik=d["saglik"], sistem=t("rapor.disk_sistem") if d["sistem_diski"] else "", ek=extra))
    for v in s["birimler"]:
        lines.append(t("rapor.birim_satir", surucu=v["surucu"], bos=v["bos_gb"], boyut=v["boyut_gb"],
                       doluluk=v["doluluk_yuzde"]))
    temp = s["gecici_dosyalar"]
    lines.append(t("rapor.gecici", gb=round(sum(v["gb"] for v in temp.values()), 2),
                   eksik="" if all(v["tam_sayildi"] for v in temp.values()) else t("rapor.gecici_eksik")))
    vm = s["sanal_bellek"]
    state = "otomatik" if vm["otomatik"] else ("elle" if vm["dosyalar"] else "yok")
    lines.append(t("rapor.sanal_bellek", durum=t(f"deger.sanal_bellek_{state}")))
    up = s["windows_update"]
    lines.append(t("rapor.update", tarih=up["son_guncelleme"] or "?", gun=up["gecen_gun"] if up["gecen_gun"] is not None else "?",
                   ek=t("rapor.update_reboot") if up["yeniden_baslatma_bekliyor"] else ""))
    for b in s["sorunlu_cihazlar"]:
        lines.append(t("rapor.sorunlu_cihaz", ad=b["ad"], sinif=b["sinif"], kod=b["hata_kodu"]))


_RENDERERS = [
    ("sistem", _system), ("donanim", _hardware), ("surecler", _processes), ("baslangic", _startup),
    ("servisler", _services), ("olaylar", _events), ("oyun", _gaming), ("guvenlik", _security),
    ("ag", _network), ("giris", _input), ("ses", _audio), ("depolama", _storage),
]


def finding_text(finding):
    title = t(f"bulgu.{finding['kod']}.baslik")
    body = t(f"bulgu.{finding['kod']}.aciklama", **finding["params"])
    return title, body


def build_text(result, extra=None):
    """Okunabilir rapor metni (ekranda veya dosyada).
    extra: [(başlık, [satırlar])] — uygulama etkinliği (değişiklikler, oyunlar, ölçümler)."""
    lines = [t("tarama.baslik"), t("tarama.tarih", tarih=fmt_date(result["zaman"])), "",
             t("tarama.gizlilik")]
    _section(lines, "bulgular")
    for f in result["bulgular"]:
        title, body = finding_text(f)
        lines.append(f"[{t('seviye.' + f['seviye'])}] {title}")
        lines.append(f"    {body}")
        if f["ilgili"]:
            lines.append("    " + t("bulgu.ilgili_ayar", idler=", ".join(f["ilgili"])))
    for key, render in _RENDERERS:
        data = result["bolumler"].get(key)
        if data is None:
            continue
        _section(lines, key)
        try:
            render(lines, data)
        except Exception as exc:  # bir bölümün yazımı bozuksa rapor yine üretilsin
            _log.error("Rapor bölümü yazılamadı (%s): %s", key, exc)
            lines.append(t("tarama.bolum_okunamadi", bolum=t(f"bolum.{key}")))
    if result["hatalar"]:
        _section(lines, "hatalar")
        for key in result["hatalar"]:
            lines.append(t("tarama.bolum_okunamadi", bolum=t(f"bolum.{key}") if key != "tespit" else key))
    for title, section_lines in extra or []:
        lines += ["", "=" * 60, title, "=" * 60] + list(section_lines)
    return "\n".join(lines) + "\n"


def export_data(result):
    """Dışa aktarılacak (kişisel bilgi temizlenmiş) veri."""
    data = dict(result)
    data["bulgular"] = [dict(f, metin=" — ".join(finding_text(f))) for f in result["bulgular"]]
    # Hata mesajlarında yol olabilir; rapora yalnızca hangi bölümün okunamadığı girer.
    data["hatalar"] = sorted(result["hatalar"])
    return privacy.scrub(data, export=True)


def save(result, folder=None, extra=None):
    """Raporu .txt ve .json olarak kaydeder; dosya yollarını döndürür."""
    folder = folder or paths.reports_dir()
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    text = privacy.scrub_text(build_text(privacy.scrub(result, export=True), extra))
    data = export_data(result)
    if extra:
        data["uygulama_etkinligi"] = privacy.scrub({title: list(lines) for title, lines in extra}, export=True)
    leaks = privacy.find_leaks(data) + privacy.find_leaks(text)
    if leaks:
        _log.warning("Raporda olası kişisel veri kalıntısı: %s", leaks[:5])
    txt_path = folder / f"forevermore_rapor_{stamp}.txt"
    json_path = folder / f"forevermore_rapor_{stamp}.json"
    txt_path.write_text(text, encoding="utf-8")
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    _log.info("Rapor kaydedildi: %s", txt_path.name)
    return txt_path, json_path
