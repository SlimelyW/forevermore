"""Bu bilgisayar için ayar önerileri (Özet sayfası).

Ölçülmüş "şu işlemcide şu kadar FPS" bilgisi veride yok; bu yüzden sıralama kazanç tahmini DEĞİL, şunlara dayanır:
ayarın etki seviyesi, gerçeklik durumu (kanıt), riski ve bu bilgisayarın donanımına özel olup olmadığı.
Yalnızca uygulanabilir (anahtar), bu bilgisayarda görünen, henüz açık olmayan ve etkisi "yok" olmayan ayarlar önerilir.
"""

IMPACT = {"yüksek": 5, "orta": 4, "düşük": 2, "durumsal": 2, "çok düşük": 1, "belirsiz": 1}
REALITY = {"gerçek": 2, "kısmen gerçek": 1, "durumsal": 1}  # placebo, zararlı, tartışmalı önerilmez
HARDWARE_BONUS = 3
LIMIT = 6


def _hardware_match(tweak, gpu_vendors, form):
    """("gpu", üretici) / ("form", "laptop"|"masaustu") / None: ayar bu donanıma özel mi."""
    compat = tweak.get("uyumluluk") or {}
    vendors = compat.get("gpu")
    if vendors:
        common = sorted(set(vendors) & set(gpu_vendors))
        if common:
            return "gpu", common[0]
    rules = compat.get("form") or {}
    if rules.get(form) == "goster" and "gizle" in rules.values():
        return "form", form
    return None


def recommend(tweaks, availability, states, gpu_vendors, form, limit=LIMIT):
    """[{"id", "neden": "gpu"|"form"|"genel", "deger", "skor"}] en yüksek skor önce."""
    result = []
    for tweak in tweaks:
        if tweak["sinif"] != "SWITCH" or tweak.get("liste_yoneticisi") or tweak["kategori"] == "Placebo":
            continue
        if tweak["risk"] not in ("güvenli", "dikkatli") or tweak["islem"].get("yalnizca_kapat"):
            continue
        avail = availability.get(tweak["id"])
        state = states.get(tweak["id"])
        if (avail is not None and not avail.visible) or state is None or state.status not in ("kapali", "kismen"):
            continue
        impact = IMPACT.get(tweak["performans_etkisi"]["seviye"], 0)
        reality = REALITY.get(tweak["gerceklik"]["durum"], 0)
        if not impact or not reality:
            continue
        match = _hardware_match(tweak, gpu_vendors, form)
        score = impact * 2 + reality + (1 if tweak["risk"] == "güvenli" else 0) + (HARDWARE_BONUS if match else 0)
        result.append({"id": tweak["id"], "neden": match[0] if match else "genel", "deger": match[1] if match else None,
                       "skor": score})
    result.sort(key=lambda r: (-r["skor"], r["id"]))
    return result[:limit]
