"""Hazır profiller (data/profiller.json): Güvenli, Oyun, Dikkatli kullanıcı."""

import json

from app.core import log, paths

_log = log.get("profiles")


def validate(data, tweaks_by_id):
    errors = []
    ids = {p["id"] for p in data["profiller"]}
    for profile in data["profiller"]:
        if profile.get("temel") and profile["temel"] not in ids:
            errors.append(f"{profile['id']}: bilinmeyen temel profil {profile['temel']!r}")
        for item in profile["ayarlar"]:
            tweak = tweaks_by_id.get(item["id"])
            if tweak is None:
                errors.append(f"{profile['id']}: bilinmeyen ayar {item['id']}")
            elif tweak["sinif"] != "SWITCH" or tweak["islem"]["kontrol"] != "switch":
                errors.append(f"{profile['id']}: {item['id']} bir switch değil")
            elif tweak["onay_gerekli"] and item.get("secili"):
                errors.append(f"{profile['id']}: dikkatli ayar {item['id']} varsayılan seçili olamaz")
    return errors


def load(tweaks_by_id):
    data = json.loads((paths.data_dir() / "profiller.json").read_text(encoding="utf-8"))
    errors = validate(data, tweaks_by_id)
    if errors:
        for error in errors:
            _log.error("Profil hatası: %s", error)
        bad = {e.split(" ")[-1] for e in errors}
        for profile in data["profiller"]:
            profile["ayarlar"] = [i for i in profile["ayarlar"] if i["id"] not in bad]
    return data["profiller"]


def expand(profiles, profile_id):
    """Temel profiller dahil, sıralı ve tekrarsız ayar listesi: [{"id", "secili"}]."""
    by_id = {p["id"]: p for p in profiles}
    chain, current = [], by_id[profile_id]
    while current:
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
