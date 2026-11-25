"""Ayar çeviri katmanlarının (data/ceviriler/<dil>.json) güncelliğini denetler.

Türkçe ayar metni değiştiğinde ilgili çeviri eskir. Bu betik eskiyen ve eksik
ayarları listeler; çeviriyi düzelttikten sonra özetleri yenilemek için:

    py -3.12 tools\\ceviri_ozeti.py            -> rapor
    py -3.12 tools\\ceviri_ozeti.py --yenile en -> en.json'daki özetleri günceller
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.engine import catalog  # noqa: E402


def main():
    sys.stdout.reconfigure(encoding="utf-8")  # boruya/dosyaya yönlenince cp1252 ile düşmesin
    parser = argparse.ArgumentParser()
    parser.add_argument("--yenile", metavar="DIL", help="bu dilin özetlerini mevcut Türkçe metne göre yeniler")
    args = parser.parse_args()
    tweaks = json.loads((ROOT / "data" / "tweaks_app.json").read_text(encoding="utf-8"))["ayarlar"]
    ok = True
    for path in sorted((ROOT / "data" / "ceviriler").glob("*.json")):
        layer = json.loads(path.read_text(encoding="utf-8"))
        digests = layer.setdefault("_kaynak_ozeti", {})
        stale = [t["id"] for t in tweaks if t["id"] in layer.get("ayarlar", {})
                 and digests.get(t["id"]) != catalog.source_digest(t)]
        missing = [t["id"] for t in tweaks if t["id"] not in layer.get("ayarlar", {})]
        print(f"{path.name}: {len(stale)} eskimiş, {len(missing)} eksik")
        for tweak_id in stale:
            print(f"  eskimiş: {tweak_id}")
        for tweak_id in missing:
            print(f"  eksik:   {tweak_id}")
        if args.yenile == path.stem:
            for tweak in tweaks:
                if tweak["id"] in layer.get("ayarlar", {}):
                    digests[tweak["id"]] = catalog.source_digest(tweak)
            path.write_text(json.dumps(layer, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            print(f"  özetler yenilendi: {path.name}")
        elif stale or missing:
            ok = False
    ok = arayuz_raporu() and ok
    return 0 if ok else 1


def arayuz_raporu():
    """lang/<kod>.json: tr'ye göre eksik/fazla anahtar; otomatik çevrilen dillerde İngilizceyle aynı kalan metin sayısı
    (çevrilmemiş olabilir; kısa/ortak sözcükler ve yer tutucu-yalnız metinler sayılmaz) ve anadil kontrolü uyarısı."""
    lang = ROOT / "lang"
    load = lambda p: json.loads(p.read_text(encoding="utf-8"))
    tr, en = load(lang / "tr.json"), load(lang / "en.json")
    ok = True
    for path in sorted(lang.glob("*.json")):
        if path.stem in ("tr", "en"):
            continue
        data = load(path)
        missing = [k for k in tr if k != "_meta" and k not in data]
        extra = [k for k in data if k != "_meta" and k not in tr]
        same = [k for k, v in data.items() if k != "_meta" and v == en.get(k) and len(v) > 12 and "{" not in v[:1]]
        auto = "otomatik_not" in data.get("_meta", {})
        print(f"lang/{path.name}: {len(missing)} eksik, {len(extra)} fazla anahtar; İngilizceyle aynı kalan metin: {len(same)}"
              + ("; OTOMATİK ÇEVİRİ, anadil kontrolü YOK" if auto else ""))
        for key in missing[:20]:
            print(f"  eksik:   {key}")
        if missing or extra:
            ok = False
    return ok


if __name__ == "__main__":
    sys.exit(main())
