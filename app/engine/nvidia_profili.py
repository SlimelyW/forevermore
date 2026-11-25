"""NVIDIA için optimize et: tek düğmeli profil (docs/KATALOG_ADAYLARI.md "NVIDIA için optimize et" bölümü).

Yalnızca üreticinin belgesinde ya da bağımsız ölçümde dayanağı olan, görüntü kalitesini düşürmeyen, dizüstünde ısı/pil
maliyeti olmayan ayarlar. Yeni bir yazma yolu YOKTUR: adımlar mevcut ayarların adımlarıdır (nvidia_drs, ekran_yenileme,
registry) ve `Engine.apply_custom` ile yazılır: geri yükleme noktası, yedek, Değişiklikler kaydı, tek tıkla geri alma.

Profile girenler:    Düşük Gecikme Modu = Açık (GPU-002) · Tercih edilen yenileme hızı = en yüksek (GPU-009) ·
                     Ekran yenileme hızı = en yüksek (DISP-001, her monitör) · Oyun Modu = Açık (PERF-001).
G-SYNC açık ekranda: + sürücüde V-Sync = Açık (GPU-006) · Maksimum kare hızı = yenileme hızı − 3 (GPU-007).
Profile GİRMEYENLER: Maksimum performans (GPU-003), doku filtreleme (GPU-004), shader önbelleği (GPU-005), iş parçacıklı
optimizasyon (GPU-008), üçlü arabellek (PLC-026): her birinin (i) penceresinde nedeni yazar (`profil_notu`).

G-SYNC'in monitör için açık olup olmadığı herkese açık NVAPI/DRS ile OKUNAMAZ (docs/EKRAN_KARTI.md); bu yüzden G-SYNC
satırları yalnızca kullanıcı önizlemede "bu ekranda G-SYNC açık" dediğinde plana girer.
"""

from app.core.i18n import t
from app.engine import handlers

PROFIL_ID = "NVIDIA-PROFIL"
SINIR_FARKI = 3   # Blur Busters G-SYNC 101: kare sınırı yenileme hızının en az 3 FPS altı
VSYNC_ACIK = 1199655232  # GPU-006 "Açık" (data/islemler.json nvidia.secenekler)
# Her zaman girenler: (ayar kimliği, DRS değeri)
HER_ZAMAN = (("GPU-002", 1), ("GPU-009", 1))
# Profilin dışında bırakılan, nedeni (i) penceresinde yazan ayarlar (tests/test_nvidia_profili.py bunu denetler)
DISARIDA = ("GPU-003", "GPU-004", "GPU-005", "GPU-008", "PLC-026")
# Profil bu ayarların durumunu da değiştirir: uygulama/geri alma sonrası kartları yeniden okunur.
ILGILI = ("PERF-001", "DISP-001")


def _etiket(tweak, value):
    """DRS değerinin ekrandaki adı (ayarın kendi seçenek listesinden; yoksa ham değer)."""
    for option in tweak["nvidia"]["secenekler"]:
        if option["deger"] == value:
            return option["etiket"]
    return t("ui.ozel_deger_nvidia", deger=value)


def _mevcut(tweak, info):
    """Özelleştirilmemişse sürücü varsayılanı."""
    if info["ozel"]:
        return info["deger"]
    return next((o["deger"] for o in tweak["nvidia"]["secenekler"] if o.get("varsayilan")), None)


def _drs_satiri(tweak_id, tweak, info, value):
    now = _mevcut(tweak, info)
    step = {"tur": "yerlesik", "eylem": "nvidia_drs", "parametreler": {"ayar": tweak["nvidia"]["ayar"]}}
    return {"id": tweak_id, "monitor": None, "simdi": _etiket(tweak, now), "yeni": _etiket(tweak, value),
            "zaten": now == value, "adim": step, "deger": value}


def plan(system, by_id, gsync=False, kayitli=()):
    """Salt okunur (hiçbir şey yazmaz). NVIDIA sürücüsü okunamazsa None.
    {'satirlar': [...], 'hz': birincil ekranın hedef Hz'i | None, 'sinir': kare sınırı | None}
    Satır: id (ayar kimliği), monitor (ad | None), simdi, yeni, zaten (değiştirmeye gerek yok), adim, deger.
    kayitli: kendi yedek kaydı olan ayar kimlikleri; satırları "ayri" (zaten) sayılır, profil onlara yazmaz (Denetim A2 O1)."""
    if not system.nvidia_available():
        return None
    wanted = list(HER_ZAMAN) + ([("GPU-006", VSYNC_ACIK)] if gsync else [])
    ids = [int(by_id[tid]["nvidia"]["ayar"], 16) for tid, _v in wanted] + [int(by_id["GPU-007"]["nvidia"]["ayar"], 16)]
    current = system.get_nvidia_settings(ids)
    rows = [_drs_satiri(tid, by_id[tid], current[int(by_id[tid]["nvidia"]["ayar"], 16)], value) for tid, value in wanted]

    hz = None
    for monitor in system.list_monitors():
        info = system.get_display_refresh(monitor["aygit"])
        target = info["en_yuksek"]
        if hz is None or monitor.get("birincil"):
            hz = target  # kare sınırı birincil ekrana göre
        step = {"tur": "yerlesik", "eylem": "ekran_yenileme",
                "parametreler": {"aygit": monitor["aygit"], "monitor": monitor.get("monitor_yolu", "")}}
        rows.append({"id": "DISP-001", "monitor": monitor["ad"], "simdi": f"{info['hz']} Hz", "yeni": f"{target} Hz",
                     "zaten": info["hz"] >= target, "adim": step, "deger": "en_yuksek"})

    game_step = by_id["PERF-001"]["islem"]["adimlar"][0]
    on = handlers.state(game_step, handlers.snapshot(system, game_step)) == "acik"
    rows.append({"id": "PERF-001", "monitor": None, "simdi": t("ui.nvprofil.acik" if on else "ui.nvprofil.kapali"),
                 "yeni": t("ui.nvprofil.acik"), "zaten": on, "adim": game_step, "deger": game_step["acik"]})

    limit = None
    if gsync:
        if hz:
            limit = max(hz - SINIR_FARKI, 1)
            tweak = by_id["GPU-007"]
            info = current[int(tweak["nvidia"]["ayar"], 16)]
            now = _mevcut(tweak, info)
            step = {"tur": "yerlesik", "eylem": "nvidia_drs", "parametreler": {"ayar": tweak["nvidia"]["ayar"]}}
            rows.append({"id": "GPU-007", "monitor": None,
                         "simdi": _etiket(tweak, now) if now == 0 else f"{now} FPS", "yeni": f"{limit} FPS",
                         "zaten": now == limit, "adim": step, "deger": limit})
    for row in rows:
        if row["id"] in kayitli:
            row["ayri"] = row["zaten"] = True
    return {"satirlar": rows, "hz": hz, "sinir": limit}


def uygulanacaklar(rows):
    """İşaretli satırlardan (adımlar, değerler): zaten istenen durumda olanlar atlanır."""
    todo = [r for r in rows if not r["zaten"]]
    return [r["adim"] for r in todo], [r["deger"] for r in todo]
