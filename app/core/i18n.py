"""Arayüz metinleri ve dil seçimi.

Her dil bir dosyadır: lang/<kod>.json (ör. lang/en.json, lang/tr.json). Dosyada
anahtar → metin çiftleri ve bir "_meta" bölümü bulunur (dilin adı, yazı yönü,
sayı/tarih biçimi). Yeni dil eklemek için yeni bir dosya yeterlidir; kod
değişmez (ayrıntı: docs/DIL_EKLEME.md).

Bir anahtar seçili dilde yoksa İngilizcesi gösterilir; İngilizcede de yoksa
anahtarın kendisi görünür (eksik çeviri ekranda fark edilir).

Uygulamanın iç kimlikleri (kategori kimliği, risk/etki seviyesi, servis adı
vb.) dile bağlı değildir; yalnızca ekranda görünen metinler bu dosyalardan gelir.
"""

import datetime
import json
import locale

from app.core import log, paths

_log = log.get("i18n")

FALLBACK = "en"
DEFAULT_META = {
    "kod": "en", "ad": "English", "yerel_ad": "English", "yon": "ltr", "yerel": "en-US",
    "ondalik": ".", "binlik": ",", "tarih": "{yil}-{ay}-{gun}", "saat": "{saat}:{dakika}",
    "yuzde": "{n}%", "yazi_tipi": "",
}

_strings = {}
_meta = dict(DEFAULT_META)
_language = None


def _read(language):
    """(metinler, meta) döndürür; dosya yoksa veya bozuksa boş sözlükler."""
    try:
        data = json.loads((paths.lang_dir() / f"{language}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _log.warning("Dil dosyası okunamadı (%s): %s", language, exc)
        return {}, {}
    meta = data.pop("_meta", {})
    return {k: v for k, v in data.items() if isinstance(v, str)}, meta


def load(language=None):
    """Dili yükler. İngilizce her zaman alttaki yedek katmandır."""
    global _strings, _meta, _language
    language = language or FALLBACK
    strings, meta = _read(FALLBACK)
    if language != FALLBACK:
        own, own_meta = _read(language)
        if own:
            strings.update(own)
            meta = own_meta
        else:
            language = FALLBACK
    _strings = strings
    _meta = {**DEFAULT_META, **meta}
    _language = language


def _ensure():
    if _language is None:
        load(FALLBACK)


def current():
    _ensure()
    return _language


def meta():
    _ensure()
    return _meta


def direction():
    """"ltr" veya "rtl" (sağdan sola yazılan diller için)."""
    return "rtl" if meta().get("yon") == "rtl" else "ltr"


def available():
    """lang klasöründeki diller: [{kod, ad, yerel_ad}], yerel ada göre sıralı."""
    result = []
    for path in sorted(paths.lang_dir().glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        info = data.get("_meta") or {}
        code = path.stem
        result.append({"kod": code, "ad": info.get("ad", code), "yerel_ad": info.get("yerel_ad", code)})
    return sorted(result, key=lambda item: item["yerel_ad"].casefold())


def windows_language():
    """Windows arayüz dilinin kısa kodu (ör. "tr", "en", "de"); okunamazsa None."""
    try:
        import ctypes  # noqa: WPS433
        langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
    except (AttributeError, OSError):
        return None
    name = locale.windows_locale.get(langid)
    return name.split("_")[0].lower() if name else None


def suggest():
    """İlk açılışta önerilen dil: Windows'un dili mevcutsa o, değilse İngilizce."""
    code = windows_language()
    return code if code in {item["kod"] for item in available()} else FALLBACK


# ---------------------------------------------------------------- metin
def _localize(value):
    if isinstance(value, float):
        return fmt_number(value, None)
    return value


def t(key, **params):
    """Anahtarın metnini döndürür; {ad} yer tutucularını doldurur.

    Ondalıklı sayılar dilin ondalık ayracıyla yazılır.
    """
    _ensure()
    text = _strings.get(key, key)
    if params:
        try:
            text = text.format(**{k: _localize(v) for k, v in params.items()})
        except (KeyError, IndexError, ValueError):
            pass
    return text


def has(key):
    _ensure()
    return key in _strings


def value_label(family, value):
    """İç kimliğin (ör. etki seviyesi "yüksek") ekrandaki adı: "<family>.<value>" anahtarı;
    yoksa değerin kendisi."""
    key = f"{family}.{value}"
    return t(key) if has(key) else str(value)


# ---------------------------------------------------------------- biçimler
def fmt_number(value, decimals=0):
    """Sayıyı dilin ayraçlarıyla yazar. decimals=None: gereken kadar basamak."""
    if value is None:
        return "—"
    if decimals is None:
        text = f"{value:,.10f}".rstrip("0").rstrip(".") if isinstance(value, float) else f"{value:,}"
    else:
        text = f"{value:,.{decimals}f}"
    m = meta()
    return text.replace(",", "\0").replace(".", m["ondalik"]).replace("\0", m["binlik"])


def fmt_percent(value, decimals=0):
    return meta()["yuzde"].format(n=fmt_number(value, decimals))


def fmt_date(value, with_time=True):
    """ISO metni ("2026-10-23T14:05:00") veya datetime → dilin tarih biçimi."""
    if not value:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.datetime.fromisoformat(value)
        except ValueError:
            return value.replace("T", " ")
    m = meta()
    text = m["tarih"].format(yil=value.year, ay=f"{value.month:02d}", gun=f"{value.day:02d}")
    if with_time and isinstance(value, datetime.datetime):
        text += " " + m["saat"].format(saat=f"{value.hour:02d}", dakika=f"{value.minute:02d}")
    return text
