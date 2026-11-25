"""Gizlilik filtresi.

Kural: kişisel veri hiç toplanmaz. Bu modül ikinci savunma hattıdır; rapor ve
log dosyalarına yazılan her metinden kullanıcı adı, bilgisayar adı, kullanıcı
klasörü yolu, IP adresi, MAC adresi, e-posta ve ürün anahtarı benzeri dizgeleri
temizler.

Anahtarı "_yerel" ile başlayan alanlar (ör. Bluetooth kulaklığın kullanıcının
verdiği adı) yalnızca uygulama ekranında gösterilir; dışa aktarılan rapordan
tamamen çıkarılır.
"""

import functools
import os
import re

LOCAL_ONLY_PREFIX = "_yerel"

IPV4_RE = re.compile(r"(?<![\d.])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?![\d.])")
# Tam biçim (8 grup) veya "::" içeren kısaltılmış biçim. Saat (12:34:56)
# gibi metinlerle karışmaması için "::" zorunlu tutulur.
IPV6_RE = re.compile(
    r"(?<![0-9A-Fa-f:])(?:(?:[0-9A-Fa-f]{1,4}:){7}[0-9A-Fa-f]{1,4}"
    r"|(?:[0-9A-Fa-f]{1,4}(?::[0-9A-Fa-f]{1,4}){0,6})?::(?:[0-9A-Fa-f]{1,4}(?::[0-9A-Fa-f]{1,4}){0,6})?)"
    r"(?:%\w+)?(?![0-9A-Fa-f:])"
)
MAC_RE = re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b")
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
PRODUCT_KEY_RE = re.compile(r"\b(?:[A-Z0-9]{5}-){4}[A-Z0-9]{5}\b")
USER_PATH_RE = re.compile(r"([A-Za-z]:\\Users\\)[^\\/:*?\"<>|\r\n]+", re.IGNORECASE)


@functools.lru_cache(maxsize=None)
def _sensitive_words():
    words = set()
    for var in ("USERNAME", "COMPUTERNAME", "USERDOMAIN", "LOGONSERVER"):
        value = (os.environ.get(var) or "").strip("\\ ")
        if len(value) >= 3:
            words.add(value)
    profile = os.environ.get("USERPROFILE") or ""
    if profile:
        last = os.path.basename(profile.rstrip("\\"))
        if len(last) >= 3:
            words.add(last)
    # 1-2 harfli adlar her metinde geçebileceği için atlanır.
    return tuple(sorted(words, key=len, reverse=True))


@functools.lru_cache(maxsize=None)
def _word_re(word):
    # Tam kelime eşleşmesi: kullanıcı adı "Ali" ise "Kalite" bozulmaz,
    # ama "Ali's AirPods" temizlenir.
    return re.compile(r"(?<!\w)" + re.escape(word) + r"(?!\w)", re.IGNORECASE)


def scrub_text(text):
    if not isinstance(text, str) or not text:
        return text
    text = USER_PATH_RE.sub(r"\1<KULLANICI>", text)
    for word in _sensitive_words():
        text = _word_re(word).sub("<GIZLI>", text)
    text = EMAIL_RE.sub("<E-POSTA>", text)
    text = MAC_RE.sub("<MAC>", text)
    text = PRODUCT_KEY_RE.sub("<ANAHTAR>", text)
    text = IPV4_RE.sub("<IP>", text)
    text = IPV6_RE.sub("<IP>", text)
    return text


def scrub(obj, export=True):
    """Veri yapısının temizlenmiş kopyasını döndürür.

    export=True ise "_yerel" ile başlayan alanlar tamamen çıkarılır.
    """
    if isinstance(obj, str):
        return scrub_text(obj)
    if isinstance(obj, dict):
        return {
            key: scrub(value, export)
            for key, value in obj.items()
            if not (export and str(key).startswith(LOCAL_ONLY_PREFIX))
        }
    if isinstance(obj, (list, tuple)):
        return [scrub(value, export) for value in obj]
    return obj


def find_leaks(obj):
    """Temizlenmemiş kişisel veri kalıntılarını bulur (testler için)."""
    leaks = []

    def walk(value, where):
        if isinstance(value, dict):
            for key, sub in value.items():
                walk(sub, f"{where}.{key}")
        elif isinstance(value, (list, tuple)):
            for i, sub in enumerate(value):
                walk(sub, f"{where}[{i}]")
        elif isinstance(value, str):
            for word in _sensitive_words():
                if _word_re(word).search(value):
                    leaks.append((where, "kullanıcı/bilgisayar adı"))
            for name, regex in (("IP", IPV4_RE), ("IPv6", IPV6_RE), ("MAC", MAC_RE), ("e-posta", EMAIL_RE),
                                ("ürün anahtarı", PRODUCT_KEY_RE)):
                if regex.search(value):
                    leaks.append((where, name))

    walk(obj, "rapor")
    return leaks
