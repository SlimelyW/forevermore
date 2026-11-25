"""Otomatik çevrilen bir dilin metinlerinde İngilizce karşılığındaki sayıların (ve kodla yazılmış değerlerin) korunup
korunmadığını denetler: anlam taşıyan çeviride yanlış rakam en tehlikeli hatadır. Dil bilgisi/anlam denetlemez.

    py -3.12 tools/ceviri_sayi_denetimi.py es
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def numbers(text):
    """Metindeki sayılar; 0.5 ile 0,5 aynı sayılır, binlik ayraç (1.234 / 1,234) sayı sayılmaz diye atılmaz."""
    return Counter(n.replace(",", ".") for n in NUMBER.findall(text))


def pairs(language):
    lang = ROOT / "lang"
    en, own = (json.loads((lang / f"{c}.json").read_text(encoding="utf-8")) for c in ("en", language))
    for key, text in own.items():
        if key != "_meta":
            yield f"lang/{key}", en.get(key, ""), text
    layers = ROOT / "data" / "ceviriler"
    en_l, own_l = (json.loads((layers / f"{c}.json").read_text(encoding="utf-8")) for c in ("en", language))
    for scope in ("genel", "ayarlar"):
        for tid, fields in own_l[scope].items():
            en_fields = en_l[scope][tid]
            for name, value in (fields.items() if scope == "ayarlar" else [(None, fields)]):
                ev = en_fields[name] if scope == "ayarlar" else en_l[scope][tid]
                values = zip(ev, value) if isinstance(value, list) else [(ev, value)]
                for a, b in values:
                    yield f"{tid}.{name}" if name else f"genel.{tid}", a, b


def main():
    language = sys.argv[1]
    sys.stdout.reconfigure(encoding="utf-8")
    bad = [(key, a, b) for key, a, b in pairs(language) if numbers(a) != numbers(b)]
    for key, a, b in bad:
        print(f"{key}: {sorted((numbers(a) - numbers(b)).elements())} eksik, {sorted((numbers(b) - numbers(a)).elements())} fazla")
    total = sum(1 for _ in pairs(language))
    print(f"{language}: {total} metin tarandı, {len(bad)} sayı farkı")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
