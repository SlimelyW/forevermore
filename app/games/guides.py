"""Oyun başına dış ayar rehberi bağlantıları (data/oyun_rehberi.json).

Yalnızca bağlantı ve kısa tanım; sitelerin içeriği kopyalanmaz ve uygulama bu sitelere kendisi bağlanmaz
(bağlantı kullanıcının tarayıcısında açılır). Adresler elle ziyaret edilerek doğrulanmıştır (docs/D2B_REHBER_KAYNAKLARI.md).
"""

import json
import re

from app.core import paths

ALLOWED_HOSTS = {"prosettings.net", "www.prosettings.net", "prosettings.gg", "www.prosettings.gg",
                 "pcgamecheck.com", "www.pcgamecheck.com", "www.systemrequirementslab.com",
                 "systemrequirementslab.com", "smoothfps.com", "www.smoothfps.com"}


def _key(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _load():
    try:
        return json.loads((paths.data_dir() / "oyun_rehberi.json").read_text(encoding="utf-8")).get("oyunlar") or []
    except (OSError, ValueError):
        return []


def _entry(game_name):
    key = _key(game_name)
    if not key:
        return None
    for entry in _load():
        other = _key(entry.get("ad", ""))
        if other and (other.startswith(key) or key.startswith(other)):
            return entry
    return None


def find(game_name):
    """Oyunun bağlantıları: [{site, url, icerik}]. Ad eşleşmesi harf/rakama indirgenmiş önek eşleşmesidir
    ("Overwatch®" -> "Overwatch 2"). Yalnızca izin verilen sitelerin https adresleri döner."""
    entry = _entry(game_name) or {}
    return [s for s in entry.get("kaynaklar") or [] if _allowed(s.get("url", ""))]


def support(game_name):
    """Oyunun doğrulanmış özellik desteği: {"reflex": True/False/None}. None: bilinmiyor (listede yok ya da doğrulanmadı)."""
    entry = _entry(game_name) or {}
    return {"reflex": entry.get("reflex")}


def ingame_items(language="tr"):
    """Her oyunda aranacak genel oyun içi ayar maddeleri (data/oyun_ici_ayarlar.json): [{id, kanit, kaynak, baslik, metin}]."""
    try:
        items = json.loads((paths.data_dir() / "oyun_ici_ayarlar.json").read_text(encoding="utf-8")).get("maddeler") or []
    except (OSError, ValueError):
        return []
    pick = lambda value: value.get(language) or value.get("tr") or ""  # noqa: E731
    return [{"id": i["id"], "kanit": i["kanit"], "kaynak": i.get("kaynak", ""), "baslik": pick(i["baslik"]), "metin": pick(i["metin"])}
            for i in items]


def _allowed(url):
    match = re.match(r"https://([^/]+)/", url)
    return bool(match) and match.group(1) in ALLOWED_HOSTS
