"""Oyun başına üç hazır ayar: Görsel öncelik, Dengeli, Performans.

Yalnızca oyun profilinin sistem tarafı alanlarını doldurur (öncelik, GPU tercihi, çekirdek seçimi, oyun sırasında
uygulananlar); oyunun kendi grafik ayarlarına dokunmaz. Hazır ayar profil TASLAĞINI doldurur, kullanıcı gözden geçirip
"Kaydet"e basana kadar hiçbir şey uygulanmaz. Değerler ölçülmüş kazanca değil, mevcut ayarların kanıt/risk
değerlendirmesine dayanır; durumsal (standby temizleme) ve riskli (servis duraklatma, Windows Search) seçenekler
hiçbir hazır ayarda açılmaz. Bkz. docs/BACKLOG.md D2.
"""

PRESETS = ("gorsel", "dengeli", "performans")
# Hazır ayarın yönettiği alanlar. "fso_kapali", "otomatik" ve "cekirdekler" hiçbir hazır ayarda değişmez
# (özel çekirdek listesi yalnızca "ozel" seçimde anlamlıdır, hazır ayarlar onu kullanmaz).
OFF = {"servisleri_duraklat": False, "windows_search_durdur": False, "standby_temizle": False,
       "pencereyi_kucult": False}


def _cores(topology, preference):
    """İstenen çekirdek seçimlerinden bu bilgisayarda mümkün olan ilki; yoksa "tum"."""
    available = {"tum"}
    if topology.get("hibrit"):
        available.add("performans")
    if topology.get("vcache_l3") is not None:
        available.add("vcache")
    return next((p for p in preference if p in available), "tum")


def build(preset, topology, dual_gpu):
    """Hazır ayarın profil alanları. topology: cpu_topology.read() sonucu; dual_gpu: iki ekran kartı var mı."""
    if preset not in PRESETS:
        raise ValueError(preset)
    gpu = "yuksek_performans" if dual_gpu else "varsayilan"
    if preset == "gorsel":
        return {**OFF, "oncelik": "Normal", "gpu_tercihi": gpu, "cekirdek_secimi": "tum", "guc_kismasi_muaf": False,
                "steam_dusuk_oncelik": False, "guc_plani": False, "bildirimleri_kapat": False}
    if preset == "dengeli":
        return {**OFF, "oncelik": "AboveNormal", "gpu_tercihi": gpu, "cekirdek_secimi": _cores(topology, ("vcache",)),
                "guc_kismasi_muaf": True, "steam_dusuk_oncelik": False, "guc_plani": False, "bildirimleri_kapat": True}
    return {**OFF, "oncelik": "High", "gpu_tercihi": gpu, "cekirdek_secimi": _cores(topology, ("vcache", "performans")),
            "guc_kismasi_muaf": True, "steam_dusuk_oncelik": True, "guc_plani": True, "bildirimleri_kapat": True}


def current(draft, topology, dual_gpu):
    """Taslak hangi hazır ayarla birebir aynı? (yoksa None)"""
    return next((p for p in PRESETS if all(draft.get(k) == v for k, v in build(p, topology, dual_gpu).items())), None)
