"""Başlangıç onayı (sorumluluk uyarısı).

İlk açılışta, sürüm değiştiğinde veya onay metni değiştiğinde gösterilir.
Kullanıcı kabul etmezse uygulama açılmaz. Kabul tarihi, sürüm ve metnin
özeti yalnızca bu bilgisayarda saklanır (%LOCALAPPDATA%\\Forevermore\\onay.json).

Metin seçili dilde gösterilir: lang/baslangic_onayi.<dil>.txt (yoksa İngilizce,
o da yoksa Türkçe). Kodu değiştirmeden düzenlenebilir. Dil değişince metin de
değiştiği için onay yeni dilde bir kez daha istenir.

Bu bir sorumluluk uyarısıdır (sistem ayarları değişir; yedek sorumluluğu kullanıcıdadır); lisans
koşulları değil: lisans MIT'tir (LICENSE). Bu kod yalnızca teknik altyapıdır, hukuki geçerlilik garantisi vermez.
GEÇERLİ METİN: Türkçe metin (baslangic_onayi.tr.txt) asıl metindir; diğer diller
çeviridir ve sonlarında bunu belirtir.
"""

import datetime
import hashlib
import json

from app import __version__
from app.core import i18n, log, paths

_log = log.get("consent")


ORIGINAL_LANGUAGE = "tr"


def text(language=None):
    for code in (language or i18n.current(), i18n.FALLBACK, ORIGINAL_LANGUAGE):
        path = paths.lang_dir() / f"baslangic_onayi.{code}.txt"
        if path.is_file():
            return path.read_text(encoding="utf-8").strip()
    raise FileNotFoundError("baslangic_onayi")


def _digest(content):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _path():
    return paths.user_data_dir() / "onay.json"


def is_accepted(language=None):
    try:
        stored = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return stored.get("surum") == __version__ and stored.get("metin") == _digest(text(language))


def accept(language=None):
    record = {"surum": __version__, "metin": _digest(text(language)), "dil": language or i18n.current(),
              "kabul_tarihi": datetime.datetime.now().isoformat(timespec="seconds")}
    paths.atomic_write(_path(), json.dumps(record, ensure_ascii=False, indent=2))
    _log.info("Başlangıç onayı kabul edildi (sürüm %s)", __version__)
