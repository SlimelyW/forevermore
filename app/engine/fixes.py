"""Özet sayfasındaki bulguların "Çöz" eylemleri.

"Çöz" kullanıcıyı ayara yönlendirmez; ilgili ayarı uygulama kendisi değiştirir.
Her çözüm normal ayar akışından geçer: onay seviyesi, geri yükleme noktası,
yedek ve "Değişiklikler" kaydı. Böylece her çözüm tek tıkla geri alınabilir.
Tek istisna geçici dosya temizliğidir; geri alınamaz olduğu açıkça sorulur.

Donanım veya BIOS gerektiren bulgularda (tek kanal RAM, HDD, XMP, disk sağlığı,
olay kayıtları) "Çöz" yoktur; bunları yazılım çözemez.
"""

from app.engine import varsayilan

# bulgu kodu -> (tür, ayar kimliği[, eylem kimliği])
#   "ac":    ayarı uygula (switch'i aç)
#   "eylem": tek seferlik eylemi çalıştır
FIXES = {
    "ekran_hz_dusuk": ("ac", "DISP-001"),
    "oyun_modu_kapali": ("ac", "PERF-001"),
    "arka_plan_kaydi": ("ac", "PERF-002"),
    "guc_tasarrufu": ("ac", "PWR-001"),
    "fare_ivmesi": ("ac", "INP-002"),
    "ses_gelistirme": ("ac", "AUD-001"),
    "gecici_dosya": ("eylem", "PLC-023", "temp"),
}


def fix_for(finding, by_id):
    """Bulgunun çözümü: {'tur', 'id', 'eylem'?} veya None."""
    spec = FIXES.get(finding["kod"])
    if spec is None and finding["kod"] == "tespit" and finding["ilgili"]:
        if finding["ilgili"][0] in varsayilan.SUPPORTED and finding["ilgili"][0] in by_id:
            return {"tur": "varsayilan", "id": finding["ilgili"][0]}  # BİLGİ ayarı: Windows varsayılanına döndür
        spec = ("kapat", finding["ilgili"][0])  # daha önce uygulanmış sorunlu ayarı kapat
    if spec is None:
        return None
    tweak = by_id.get(spec[1])
    if tweak is None or tweak["sinif"] != "SWITCH":
        return None
    control = tweak["islem"]["kontrol"]
    if spec[0] == "eylem":
        if control != "eylem" or not any(a["id"] == spec[2] for a in tweak["islem"]["eylemler"]):
            return None
        return {"tur": "eylem", "id": spec[1], "eylem": spec[2]}
    if control != "switch":
        return None
    if spec[0] == "ac" and tweak["islem"].get("yalnizca_kapat"):
        return None
    return {"tur": spec[0], "id": spec[1]}


def is_resolved(fix, state, done_actions=()):
    """Çözüm şu an geçerli mi? (Durum sistemden okunmuş olmalı.)"""
    if fix["tur"] == "eylem":
        return fix["id"] in done_actions
    if fix["tur"] == "varsayilan":
        return False  # çözülünce yeniden okuma (recheck) bulguyu listeden kaldırır
    if state is None:
        return False
    if fix["tur"] == "ac":
        return state.status == "acik"
    # "Kapat": her adım gerçekten kapalı olmalı. Ne açık ne kapalı olan bir değer
    # (ör. tespit edilen, varsayılandan farklı bir tweak) çözülmüş sayılmaz.
    if state.step_states:
        return all(s in ("kapali", "yok") for s in state.step_states)
    return state.status == "kapali"
