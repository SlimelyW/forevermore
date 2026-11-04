"""Uygulamanın kendi ayarları (Windows ayarları değil).

%LOCALAPPDATA%\\Forevermore\\uygulama_ayarlari.json dosyasında tutulur.
"""

import json

from app.core import log, paths

_log = log.get("settings")

DEFAULTS = {
    # Açıksa bilgi (i) penceresinde gerçeklik durumu, Windows sürümü, varsayılan
    # değer ve kaynaklar da gösterilir. Varsayılan: KAPALI.
    "ekstra_bilgi": False,
    # Geri yükleme noktası: "" = oturumdaki ilk değişiklikte sor, "olustur" / "atla" = hep böyle yap.
    "rp_sorma": "",
    # Boost listesi: tek tıkla kapatılacak programların süreç adları (korumalı programlar listeye alınmaz).
    "boost_listesi": [],
    "boost_ayarlari": [],
    # Açıksa pencere kapatılınca uygulama tepside çalışmaya devam eder (oyun izleyici
    # için). Varsayılan: KAPALI. Tepsi simgesi Qt'nin kendi bileşeniyle çizilir.
    "tepsiye_kucult": False,
    # Arayüz dili (lang/<kod>.json). Boş: henüz seçilmedi; ilk açılışta dil seçme penceresi çıkar.
    "dil": "",
    # Kullanıcının fare/klavyelere verdiği adlar: {"VID:PID": "ad"}. Yalnızca bu bilgisayarda;
    # rapora girmez.
    "cihaz_adlari": {},
    # Uygulama açıkken istenen zamanlayıcı çözünürlüğü (100 ns birimi; 0: Windows'a bırak).
    "zamanlayici_cozunurlugu": 0,
    # Hareketi azalt: açıkken hover parlaması ve sayfa solması kapanır (erişilebilirlik).
    "hareket_azalt": False,
    # Ekran kartı algılanamadıysa Ekran Kartı sayfasında elle seçilen marka ("NVIDIA" / "AMD" / "Intel"; boş: yok).
    "gpu_markasi_elle": "",
    # Erişilebilirlik (docs/TASARIM_ESASLARI.md §3): Verdana, +1 px, geniş harf aralığı / daha yüksek karşıtlık.
    # İkisi de yeniden başlatınca uygulanır.
    "okunabilir_yazi": False,
    "yuksek_karsitlik": False,
    # Uygulama güncellemesi (app/core/guncelleme.py): KAPALI = hiç bağlanmaz; "Şimdi denetle" düğmesi yine çalışır.
    "guncelleme_denetle": False,
    "guncelleme_son_deneme": "",
    # Özet > Bulgular: kullanıcının daralttığı önem grupları ("sorun", "uyari", "bilgi", "iyi").
    "bulgu_daralt": ["iyi"],
}

_cache = None


def _path():
    return paths.user_data_dir() / "uygulama_ayarlari.json"


def load():
    global _cache
    if _cache is None:
        _cache = dict(DEFAULTS)
        try:
            stored = json.loads(_path().read_text(encoding="utf-8"))
            _cache.update({k: v for k, v in stored.items() if k in DEFAULTS})
        except (OSError, ValueError):
            pass
    return _cache


def get(key):
    return load().get(key, DEFAULTS.get(key))


def set(key, value):  # noqa: A001 - ayar sözlüğü arayüzü
    data = load()
    data[key] = value
    try:
        paths.atomic_write(_path(), json.dumps(data, ensure_ascii=False, indent=2))
    except OSError as exc:
        _log.warning("Uygulama ayarı kaydedilemedi: %s", exc)


def reset_cache():
    """Testler için."""
    global _cache
    _cache = None
