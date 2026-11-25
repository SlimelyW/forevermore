"""Hazır profiller (data/profiller.json): Güvenli, Oyun, Dikkatli kullanıcı."""

import json

from app.core import log, paths

_log = log.get("profiles")


def _errors(data, tweaks_by_id):
    """[(ayar kimliği | None, ileti)]: hangi maddenin atılacağı iletiden değil kimlikten bilinir (Denetim A2 O5)."""
    errors = []
    ids = {p["id"] for p in data["profiller"]}
    for profile in data["profiller"]:
        if profile.get("temel") and profile["temel"] not in ids:
            errors.append((None, f"{profile['id']}: bilinmeyen temel profil {profile['temel']!r}"))
        for item in profile["ayarlar"]:
            tweak = tweaks_by_id.get(item["id"])
            if tweak is None:
                errors.append((item["id"], f"{profile['id']}: bilinmeyen ayar {item['id']}"))
            elif tweak["sinif"] != "SWITCH" or tweak["islem"]["kontrol"] != "switch":
                errors.append((item["id"], f"{profile['id']}: {item['id']} bir switch değil"))
            elif tweak["onay_gerekli"] and item.get("secili"):
                errors.append((item["id"], f"{profile['id']}: dikkatli ayar {item['id']} varsayılan seçili olamaz"))
    return errors


def validate(data, tweaks_by_id):
    return [message for _id, message in _errors(data, tweaks_by_id)]


def clean(data, tweaks_by_id):
    """Hatalı maddeleri günlüğe yazıp atar; profil listesini döndürür."""
    errors = _errors(data, tweaks_by_id)
    for _id, message in errors:
        _log.error("Profil hatası: %s", message)
    bad = {i for i, _m in errors if i}
    for profile in data["profiller"]:
        profile["ayarlar"] = [i for i in profile["ayarlar"] if i["id"] not in bad]
    return data["profiller"]


def load(tweaks_by_id):
    return clean(json.loads((paths.data_dir() / "profiller.json").read_text(encoding="utf-8")), tweaks_by_id)


def expand(profiles, profile_id):
    """Temel profiller dahil, sıralı ve tekrarsız ayar listesi: [{"id", "secili"}]."""
    by_id = {p["id"]: p for p in profiles}
    chain, current = [], by_id[profile_id]
    while current and current not in chain:  # iki profil birbirini temel gösterirse sonsuz dönmesin
        chain.insert(0, current)
        current = by_id.get(current.get("temel"))
    items = {}
    for profile in chain:
        for item in profile["ayarlar"]:
            items[item["id"]] = dict(item)
    return list(items.values())


def plan(engine, profiles, profile_id, tweaks_by_id):
    """Profil ekranı için: bu bilgisayarda uygun olan ayarlar ve mevcut durumları."""
    rows = []
    for item in expand(profiles, profile_id):
        tweak = tweaks_by_id[item["id"]]
        avail = engine.availability(tweak)
        if not avail.visible:
            continue
        state = engine.read_state(tweak)
        rows.append({
            "id": tweak["id"],
            "ad": tweak["ad"],
            "secili": item["secili"] and not state.is_on,
            "zaten_acik": state.is_on,
            "onay_gerekli": tweak["onay_gerekli"],
            "uyarilar": avail.warnings,
        })
    return rows


def apply(engine, tweaks_by_id, choices):
    """choices: [(ayar_id, onaylandi)]. Her biri ayrı uygulanır; biri başarısız
    olursa diğerleri devam eder. Sonuç: [(ayar_id, Result)]."""
    results = []
    for tweak_id, confirmed in choices:
        results.append((tweak_id, engine.set_enabled(tweaks_by_id[tweak_id], True, confirmed=confirmed)))
    return results
