"""Kanıt döngüsü: önce/sonra TEKRARLI ölçümlerden tek dürüst sonuç. Ölçüm yapmaz; yalnızca karşılaştırır.

DÜRÜSTLÜK: fark, tekrarlar arasındaki yayılımla (gürültü) kıyaslanır; yüzde üretilmez, tek ölçüm çifti sonuç sayılmaz.
Eşikler (gürültünün 1 katı / 2 katı, %3 taban) gerçek oyunla SINANMADI: docs/EL_TESTLERI.md.
"""

from app.measure import METRICS

TEKRAR = 3
EN_AZ_TEKRAR = 2            # bir tarafta bundan az tekrar varsa gürültü bilinmez: karar verilmez
OYUN_SN, SISTEM_SN = 20, 10  # tekrar başına süre
GURULTU_TABANI = 0.03       # tekrarlar birbirine çok yakın çıksa da %3 altı fark gürültü sayılır (Önce/Sonra sayfasıyla aynı)
# Sıfıra yakın değerlerde %3 anlamsız kalır: bundan küçük mutlak fark gürültü sayılır (yüzde puanı / GB / süreç)
MUTLAK_TABAN = {"bosta_cpu": 1.0, "disk_yuk": 1.0, "bosta_ram_gb": 0.1, "surec_sayisi": 3}
# Süreç sayısı bir sayımdır: %3 tabanı (210 süreçte 6) Boost'un kapattığı 5 programı hep "fark yok" yapıyordu (Denetim YAYIN K10)
YUZDESIZ = ("surec_sayisi",)
KARAR_METRIKLERI = {"oyun": ("fps_ort", "fps_1"),
                    "sistem": ("bosta_cpu", "bosta_ram_gb", "disk_yuk", "surec_sayisi")}


def ortalama(runs):
    """Tekrarların metrik başına ortalaması (kayıt ve "Rakamları göster" için)."""
    result = {}
    for key in {k for run in runs for k in run}:
        values = [run[key] for run in runs if run.get(key) is not None]
        if values:
            result[key] = round(sum(values) / len(values), 2)
    return result


def karsilastir(once, sonra, kind):
    """once / sonra: tekrar başına {metrik: değer} listeleri.

    Döner: {"karar", "tekrar": (önce, sonra), "satirlar": [(metrik, önce ort., sonra ort., seviye, iyi_mi)]}
    seviye: 0 = fark gürültünün içinde, 1 = gürültünün 1-2 katı, 2 = iki katından büyük. iyi_mi: seviye 0'da None.
    karar: "yetersiz" / "fark_yok" / "kucuk" / "belirgin" / "karisik" (bir ölçüm iyileşti, bir başkası kötüleşti)."""
    rows = []
    for metric in KARAR_METRIKLERI[kind]:
        a = [run[metric] for run in once if run.get(metric) is not None]
        b = [run[metric] for run in sonra if run.get(metric) is not None]
        if len(a) < EN_AZ_TEKRAR or len(b) < EN_AZ_TEKRAR:
            continue  # tek değerle yayılım bilinmez: bu ölçüm karara girmez (Denetim YAYIN K9)
        mean_a, mean_b = sum(a) / len(a), sum(b) / len(b)
        floor = 0 if metric in YUZDESIZ else abs(mean_a) * GURULTU_TABANI
        noise = max(max(a) - min(a), max(b) - min(b), floor, MUTLAK_TABAN.get(metric, 0))
        if min(len(a), len(b)) < TEKRAR:
            noise *= 2  # iki tekrarda yayılım az görünür: hiçbir şey değişmeden %27 "fark var" çıkıyordu (Denetim YAYIN K2)
        diff = mean_b - mean_a
        level = 0 if abs(diff) < noise or not diff else 1 if abs(diff) < 2 * noise else 2
        better = None if level == 0 else (diff < 0) == METRICS[metric][0]
        rows.append((metric, round(mean_a, 2), round(mean_b, 2), level, better))
    counts = (len(once), len(sonra))
    if min(counts) < EN_AZ_TEKRAR or not rows:
        verdict = "yetersiz"
    elif any(r[4] is True for r in rows) and any(r[4] is False for r in rows):
        verdict = "karisik"
    else:
        verdict = ("fark_yok", "kucuk", "belirgin")[max(r[3] for r in rows)]
    return {"karar": verdict, "tekrar": counts, "satirlar": rows}
