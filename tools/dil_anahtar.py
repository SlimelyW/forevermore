"""lang/*.json dosyalarına aynı sırayla anahtar ekler veya siler (geliştirme aracı).

    py -3.12 tools\\dil_anahtar.py ekle eklemeler.json
    py -3.12 tools\\dil_anahtar.py sil anahtar1 anahtar2 ...

eklemeler.json: [{"sonra": "<var olan anahtar>", "anahtarlar": [[anahtar, tr, en], ...]}, ...]
Yeni dil dosyaları (ör. de.json) varsa eklenen anahtar onlara İngilizce metinle yazılır.
"""

import json
import sys
from pathlib import Path

LANG = Path(__file__).resolve().parent.parent / "lang"


def _line(key, value):
    return f"  {json.dumps(key, ensure_ascii=False)}: {json.dumps(value, ensure_ascii=False)},"


def add(spec_path):
    additions = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    for path in sorted(LANG.glob("*.json")):
        code = path.stem
        lines = path.read_text(encoding="utf-8").splitlines()
        existing = json.loads("\n".join(lines))
        for block in additions:
            anchor = "  " + json.dumps(block["sonra"], ensure_ascii=False) + ":"
            pos = next(i for i, line in enumerate(lines) if line.startswith(anchor))
            new = []
            for key, tr, en in block["anahtarlar"]:
                if key in existing:
                    raise SystemExit(f"{path.name}: {key} zaten var")
                new.append(_line(key, tr if code == "tr" else en))
            if not lines[pos].endswith(","):
                lines[pos] += ","
                new[-1] = new[-1].rstrip(",")
            lines[pos + 1:pos + 1] = new
        text = "\n".join(lines) + "\n"
        json.loads(text)
        path.write_text(text, encoding="utf-8")
    _check_order()


def remove(keys):
    for path in sorted(LANG.glob("*.json")):
        lines = path.read_text(encoding="utf-8").splitlines()
        kept = [line for line in lines
                if not any(line.startswith("  " + json.dumps(k, ensure_ascii=False) + ":") for k in keys)]
        if kept and kept[-2].endswith(","):  # silinen son anahtarsa kalan son satırdaki virgülü kaldır
            kept[-2] = kept[-2].rstrip(",")
        text = "\n".join(kept) + "\n"
        json.loads(text)
        path.write_text(text, encoding="utf-8")
        print(path.name, len(lines) - len(kept), "silindi")
    _check_order()


def _check_order():
    files = {p.stem: list(json.loads(p.read_text(encoding="utf-8"))) for p in LANG.glob("*.json")}
    reference = files.get("tr")
    for code, keys in files.items():
        if keys != reference:
            raise SystemExit(f"{code}.json anahtar sırası tr.json ile aynı değil")
    print("tamam:", ", ".join(sorted(files)))


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "ekle":
        add(sys.argv[2])
    elif len(sys.argv) >= 3 and sys.argv[1] == "sil":
        remove(sys.argv[2:])
    else:
        print(__doc__)
        sys.exit(1)
