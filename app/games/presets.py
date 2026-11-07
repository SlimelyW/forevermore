"""Oyun başına üç hazır ayar: Görsel öncelik, Dengeli, Performans.

Yalnızca oyun profilinin kalıcı sistem tarafı alanlarını doldurur (öncelik, GPU tercihi); oyunun kendi grafik
ayarlarına dokunmaz. Hazır ayar profil TASLAĞINI doldurur, kullanıcı "Kaydet"e (veya "Önerilen ayarları uygula"ya)
basana kadar hiçbir şey uygulanmaz. Değerler ölçülmüş kazanca değil, mevcut ayarların kanıt/risk değerlendirmesine
dayanır. Oyun sırasında uygulanan alanlar (çekirdek, güç kısması, bildirimler…) oyun izleyiciyle birlikte 7 Kasım 2026'da
kaldırıldı. Bkz. docs/BACKLOG.md D2.
"""

from app.games.profiles import DEFAULT_PROFILE

PRESETS = ("gorsel", "dengeli", "performans")
# Hazır ayarın yönettiği alanlar: öncelik ve GPU tercihi. "fso_kapali" ve "otomatik" hiçbir hazır ayarda değişmez.
PRIORITY = {"gorsel": "Normal", "dengeli": "AboveNormal", "performans": "High"}


def build(preset, dual_gpu):
    """Hazır ayarın profil alanları. dual_gpu: iki ekran kartı var mı."""
    if preset not in PRESETS:
        raise ValueError(preset)
    return {"oncelik": PRIORITY[preset], "gpu_tercihi": "yuksek_performans" if dual_gpu else "varsayilan"}


def recommended_count(profile, dual_gpu):
    """(N, M): "Dengeli" hazır ayarın varsayılandan FARKLI önerdiği M alandan kaçı bu profilde zaten öyle.
    Varsayılanla aynı olan alanlar sayılmaz (yoksa "kapalı" olanların hepsi uygulanmış görünürdü)."""
    advice = build("dengeli", dual_gpu)
    keys = [k for k, v in advice.items() if v != DEFAULT_PROFILE.get(k)]
    return sum(1 for k in keys if profile.get(k) == advice[k]), len(keys)


def current(draft, dual_gpu):
    """Taslak hangi hazır ayarla birebir aynı? (yoksa None)"""
    return next((p for p in PRESETS if all(draft.get(k) == v for k, v in build(p, dual_gpu).items())), None)
