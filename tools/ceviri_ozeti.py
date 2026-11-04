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
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
