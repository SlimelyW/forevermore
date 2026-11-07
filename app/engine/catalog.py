"""data/tweaks_app.json dosyasını yükler.

Uygulama açılırken her ayar şema doğrulamasından geçer; hatalı tanımlanmış
bir ayar listeden çıkarılır ve log'a yazılır.

Ayar metinlerinin asıl dili Türkçedir. Başka dil seçiliyse metinler
data/ceviriler/<dil>.json dosyasından değiştirilir (çeviri katmanı). Çevirisi
olmayan metin önce İngilizce katmandan, o da yoksa Türkçe asıldan gelir.
Çeviri katmanı YALNIZCA ekranda görünen metinleri değiştirebilir (TRANSLATABLE);
kimlikler, risk/etki seviyeleri, registry yolları ve değerler asla değişmez.

Katman biçimi (anahtarlar noktalı yol, liste öğeleri sıra numarasıyla):
    {"ayarlar": {"DISP-001": {"ad": "...", "artilar": ["...", "..."],
                              "islem.alanlar.0.secenekler.1.etiket": "..."}},
     "genel": {"meta.anti_cheat_uyarisi": "...", "kategoriler.0.aciklama": "..."}}
"""

import functools
import hashlib
import json
import re

from app.core import i18n, log, paths
from app.engine.schema import validate_tweak

_log = log.get("catalog")

SOURCE_LANGUAGE = "tr"

# Ayar içinde çevrilebilen (ekranda görünen) alanlar. Liste sıra numaraları "*" ile yazılır;
# metin listeleri (artilar vb.) bütün olarak da verilebilir.
TRANSLATABLE_WHOLE = (
    "ad", "sade_ad", "ne_ise_yarar", "artilar", "eksiler", "dokunmamali", "notlar", "varsayilan", "bilgi.neden",
    "bilgi.yapilamaz_nedeni", "gerceklik.aciklama", "gerceklik.celiski", "performans_etkisi.gerekce",
    "rehber.adimlar", "rehber.geri_alma", "rehber.kontrol", "tespit.mesaj", "uyumluluk.kaynak_metin.windows",
    "islem.alanlar.*.etiket", "islem.alanlar.*.secenekler.*.etiket", "islem.eylemler.*.etiket",
    "nvidia.secenekler.*.etiket",
)
TRANSLATABLE = set(TRANSLATABLE_WHOLE) | {"artilar.*", "eksiler.*", "dokunmamali.*", "notlar.*",
                                          "rehber.adimlar.*"}
# Ayarlar dışındaki genel metinler (bu öneklerle başlayan metin yaprakları).
TRANSLATABLE_GENERAL = ("meta.anti_cheat_uyarisi", "meta.genel_uyarilar", "kategoriler.*.aciklama",
                        "placebo_menusu", "arastirma_notlari")


def _pattern(path):
    return re.sub(r"\.\d+(?=\.|$)", ".*", path)


def _set(root, path, value):
    """Noktalı yoldaki metni değiştirir. Yol yoksa veya tür uymuyorsa False (hiçbir şey değişmez)."""
    parts = path.split(".")
    node = root
    for part in parts[:-1]:
        node = node[int(part)] if isinstance(node, list) and part.isdigit() else (
            node.get(part) if isinstance(node, dict) else None)
        if node is None:
            return False
    last = parts[-1]
    if isinstance(node, list) and last.isdigit() and int(last) < len(node):
        index = int(last)
        if isinstance(node[index], str) and isinstance(value, str):
            node[index] = value
            return True
        return False
    if not isinstance(node, dict) or last not in node:
        return False
    old = node[last]
    if isinstance(old, str) and isinstance(value, str):
        node[last] = value
        return True
    if isinstance(old, list) and isinstance(value, list) and all(isinstance(v, str) for v in old + value):
        node[last] = list(value)
        return True
    return False


def _general_allowed(path):
    pattern = _pattern(path)
    return any(pattern == p or pattern.startswith(p + ".") for p in TRANSLATABLE_GENERAL)


def source_texts(tweak):
    """Ayarın çevrilecek Türkçe metinleri: {noktalı yol: metin veya metin listesi} (boşlar hariç)."""
    found = {}

    def walk(node, path):
        if path and _pattern(path) in TRANSLATABLE_WHOLE:
            if node and (isinstance(node, str) or (isinstance(node, list) and all(isinstance(v, str) for v in node))):
                found[path] = node
            return
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}.{key}" if path else key)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}.{index}")

    walk(tweak, "")
    return found


def source_digest(tweak):
    """Çevrilecek metinlerin kısa özeti; çeviri katmanı Türkçe metin değişince eskidiğini bununla anlar."""
    text = json.dumps(source_texts(tweak), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def apply_translation(data, layer):
    """Bir çeviri katmanını veriye uygular; uygulanamayan girdi sayısını döndürür."""
    rejected = 0
    tweaks = {t["id"]: t for t in data["ayarlar"]}
    for tweak_id, fields in (layer.get("ayarlar") or {}).items():
        tweak = tweaks.get(tweak_id)
        for path, value in (fields or {}).items():
            if tweak is None or _pattern(path) not in TRANSLATABLE or not _set(tweak, path, value):
                rejected += 1
    for path, value in (layer.get("genel") or {}).items():
        if not _general_allowed(path) or not _set(data, path, value):
            rejected += 1
    return rejected


def _layers(language):
    """Uygulanacak katman dilleri (sırayla): İngilizce yedek, sonra seçili dil."""
    if language == SOURCE_LANGUAGE:
        return []
    return [i18n.FALLBACK] + ([language] if language != i18n.FALLBACK else [])


@functools.lru_cache(maxsize=None)
def load():
    roots = [paths.data_dir()]
    base = paths.data_dir()
    data = json.loads((base / "tweaks_app.json").read_text(encoding="utf-8"))
    for code in _layers(i18n.current()):
        path = next((r / "ceviriler" / f"{code}.json" for r in roots if (r / "ceviriler" / f"{code}.json").is_file()), None)
        if path is None:
            continue
        try:
            rejected = apply_translation(data, json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError) as exc:
            _log.warning("Çeviri dosyası okunamadı (%s): %s", path.name, exc)
            continue
        if rejected:
            _log.warning("Çeviri dosyasında uygulanamayan %d girdi var (%s)", rejected, path.name)
    valid = []
    for tweak in data["ayarlar"]:
        errors = validate_tweak(tweak)
        if errors:
            _log.error("Ayar yüklenmedi (%s): %s", tweak.get("id"), "; ".join(errors))
            continue
        valid.append(tweak)
    data["ayarlar"] = valid
    return data


def tweaks():
    return load()["ayarlar"]


def by_id():
    return {t["id"]: t for t in tweaks()}
