"""Gömülü kapağı kaldırır: resmi siler, data/oyun_kapaklari.json'dan girdisini çıkarır.
Kullanım: python tools/kapak_kaldir.py rust.jpg [diger.jpg ...]   |   python tools/kapak_kaldir.py --hepsi"""
import json
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
JSON = DATA / "oyun_kapaklari.json"


def main(args):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # PS 5.1 / cp1252 konsolunda Türkçe harf hata vermesin
    if not args:
        print(__doc__)
        return 1
    doc = json.loads(JSON.read_text(encoding="utf-8"))
    names = {e["dosya"] for e in doc["kapaklar"]} if args == ["--hepsi"] else set(args)
    unknown = names - {e["dosya"] for e in doc["kapaklar"]}
    if unknown:
        print("JSON'da yok:", ", ".join(sorted(unknown)))
        return 1
    doc["kapaklar"] = [e for e in doc["kapaklar"] if e["dosya"] not in names]
    JSON.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name in sorted(names):
        (DATA / "oyun_kapaklari" / name).unlink(missing_ok=True)
        print("kaldırıldı:", name)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
