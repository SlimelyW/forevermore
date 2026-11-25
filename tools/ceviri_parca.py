"""Yeni dili parça parça çevirmek için: İngilizce metinleri ~200'er anahtarlık / ~15 KB'lık parçalara böler, çevrilen
parçaları tr sırasında lang/<kod>.json ve data/ceviriler/<kod>.json olarak birleştirir ve doğrular.

    py -3.12 tools/ceviri_parca.py bol <kod> <klasör>        # c01.en.json… (arayüz), a01.en.json… (ayarlar)
    # her parçayı çevirip <klasör>/c01.<kod>.json, a01.<kod>.json olarak kaydet (anahtarlar/kimlikler/alan adları AYNEN)
    py -3.12 tools/ceviri_parca.py birlestir <kod> <klasör> [--cikti <klasör>]

Birleştirme: eksik/fazla anahtar, yer tutucu, ayar kimliği/alan/liste uzunluğu ve komut simgesi farklarını yazar; arayüz
dosyası hatasızsa yazılır. Sonra: tools/ceviri_ozeti.py --yenile <kod>, tools/ceviri_sayi_denetimi.py <kod>,
tools/ceviri_ikinci_gecis.py <kod>, testler. Süreç ve durum: docs/CEVIRI_KONTROL.md, docs/DIL_EKLEME.md.
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLACEHOLDER = re.compile(r"\{(\w+)\}")
COMMAND_TOKEN = re.compile(r"HK(?:CU|LM):[^ ')\"]*|[A-Z][a-z]+-[A-Z]\w+|\s-[A-Za-z]\w+|\b0x[0-9A-Fa-f]+\b|\b[A-Za-z]+\.exe\b|\{[0-9a-f-]{36}\}")
LAYER_CHUNK_CHARS = 15000
UI_CHUNK_KEYS = 200
META_ORDER = ("kod", "ad", "yerel_ad", "yon", "yerel", "ondalik", "binlik", "tarih", "saat", "yuzde", "yazi_tipi", "otomatik_not")

# kod -> _meta (ad İngilizce adı, yerel_ad kendi adı; otomatik_not o dilin kendi dilinde olmalı)
DIL_META = {
    "es": {"ad": "Spanish", "yerel_ad": "Español", "yerel": "es-ES", "ondalik": ",", "binlik": ".", "tarih": "{gun}/{ay}/{yil}",
           "yuzde": "{n} %", "yazi_tipi": "", "otomatik_not": "traducción automática, puede contener errores"},
    "de": {"ad": "German", "yerel_ad": "Deutsch", "yerel": "de-DE", "ondalik": ",", "binlik": ".", "tarih": "{gun}.{ay}.{yil}",
           "yuzde": "{n} %", "yazi_tipi": "", "otomatik_not": "automatische Übersetzung, kann Fehler enthalten"},
    "ru": {"ad": "Russian", "yerel_ad": "Русский", "yerel": "ru-RU", "ondalik": ",", "binlik": " ", "tarih": "{gun}.{ay}.{yil}",
           "yuzde": "{n} %", "yazi_tipi": "", "otomatik_not": "автоматический перевод, возможны ошибки"},
    "zh": {"ad": "Chinese (Simplified)", "yerel_ad": "简体中文", "yerel": "zh-CN", "ondalik": ".", "binlik": ",", "tarih": "{yil}-{ay}-{gun}",
           "yuzde": "{n}%", "yazi_tipi": "Microsoft YaHei UI", "otomatik_not": "自动翻译，可能有错误"},
    "ja": {"ad": "Japanese", "yerel_ad": "日本語", "yerel": "ja-JP", "ondalik": ".", "binlik": ",", "tarih": "{yil}/{ay}/{gun}",
           "yuzde": "{n}%", "yazi_tipi": "Yu Gothic UI", "otomatik_not": "自動翻訳のため、誤りがある可能性があります"},
}


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def bol(code, folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    en = _load(ROOT / "lang/en.json")
    keys = [k for k in en if k != "_meta"]
    for i in range(0, len(keys), UI_CHUNK_KEYS):
        chunk = {k: en[k] for k in keys[i:i + UI_CHUNK_KEYS]}
        (folder / f"c{i // UI_CHUNK_KEYS + 1:02d}.en.json").write_text(json.dumps(chunk, ensure_ascii=False, indent=0), encoding="utf-8")
    layer = _load(ROOT / "data/ceviriler/en.json")
    items = [("genel", layer["genel"])] + list(layer["ayarlar"].items())
    chunks, current, size = [], {}, 0
    for key, value in items:
        length = len(json.dumps(value, ensure_ascii=False))
        if current and size + length > LAYER_CHUNK_CHARS:
            chunks.append(current)
            current, size = {}, 0
        current[key] = value
        size += length
    chunks.append(current)
    for i, chunk in enumerate(chunks, 1):
        (folder / f"a{i:02d}.en.json").write_text(json.dumps(chunk, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{code}: {len(keys) // UI_CHUNK_KEYS + 1} arayüz parçası, {len(chunks)} ayar parçası -> {folder}")


def _tokens(text):
    return Counter(COMMAND_TOKEN.findall(text))


def _pairs(english, own):
    """(İngilizce, çeviri) çiftleri; liste uzunlukları farklıysa None."""
    if isinstance(english, list):
        return list(zip(english, own)) if isinstance(own, list) and len(own) == len(english) else None
    return [(english, own)]


def birlestir(code, folder, out=None):
    folder, out = Path(folder), Path(out) if out else ROOT
    tr = _load(ROOT / "lang/tr.json")
    own = {}
    for path in sorted(folder.glob(f"c*.{code}.json")):
        own.update(_load(path))
    keys = [k for k in tr if k != "_meta"]
    missing, extra = [k for k in keys if k not in own], [k for k in own if k not in tr]
    bad = [k for k in keys if k in own and sorted(set(PLACEHOLDER.findall(own[k]))) != sorted(set(PLACEHOLDER.findall(tr[k])))]
    print(f"arayüz: {len(own)} metin; eksik {len(missing)} {missing[:5]}; fazla {len(extra)}; yer tutucu uyumsuz {bad}")
    meta = {"kod": code, "yon": "ltr", "saat": "{saat}:{dakika}", **DIL_META[code]}
    meta = {k: meta[k] for k in META_ORDER}
    if not (missing or extra or bad):
        lines = ["{", "  " + json.dumps("_meta", ensure_ascii=False) + ": " + json.dumps(meta, ensure_ascii=False) + ","]
        lines += [f"  {json.dumps(k, ensure_ascii=False)}: {json.dumps(own[k], ensure_ascii=False)}" + ("," if i < len(keys) - 1 else "")
                  for i, k in enumerate(keys)]
        lines.append("}")
        (out / "lang").mkdir(parents=True, exist_ok=True)
        (out / "lang" / f"{code}.json").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"yazıldı: lang/{code}.json")
    layer = _load(ROOT / "data/ceviriler/en.json")
    settings = {}
    for path in sorted(folder.glob(f"a*.{code}.json")):
        settings.update(_load(path))
    general = settings.pop("genel", {})
    problems = []
    if list(general) != list(layer["genel"]):
        problems.append(("genel", sorted(set(general) ^ set(layer["genel"]))))
    if list(settings) != list(layer["ayarlar"]):
        problems.append(("kimlikler", sorted(set(settings) ^ set(layer["ayarlar"]))))
    for tid, fields in layer["ayarlar"].items():
        mine = settings.get(tid, {})
        if set(fields) != set(mine):
            problems.append((tid, "alanlar", sorted(set(fields) ^ set(mine))))
            continue
        for name, value in fields.items():
            pairs = _pairs(value, mine[name])
            if pairs is None:
                problems.append((tid, name, "liste uzunluğu"))
            elif name.startswith("rehber."):
                for a, b in pairs:
                    if _tokens(a) != _tokens(b):
                        problems.append((tid, name, "komut simgesi", sorted((_tokens(a) - _tokens(b)).elements()),
                                         sorted((_tokens(b) - _tokens(a)).elements())))
    for problem in problems:
        print("ayar uyarısı:", problem)
    print(f"ayarlar: {len(settings)} ayar, {len(problems)} uyarı (komut simgesi uyarıları çoğu zaman 'Wi-Fi' gibi çevrilmiş sözcüktür; gözle bak)")
    if not [p for p in problems if not (len(p) > 2 and p[2] == "komut simgesi")]:
        text = {"_aciklama": [f"Ayar metinlerinin '{code}' çeviri katmanı. Asıl metin Türkçedir (data/tweaks_app.json).",
                              "OTOMATİK ÇEVİRİ: yapay zekâ tarafından İngilizce katmandan çevrildi; ana dili o dil olan biri kontrol etmedi, hatalar olabilir.",
                              "_kaynak_ozeti: tools/ceviri_ozeti.py --yenile ile yazılır.",
                              "Biçim ve çevrilebilen alanlar: docs/DIL_EKLEME.md, app/engine/catalog.py (TRANSLATABLE)."],
                "_kaynak_ozeti": {}, "genel": general, "ayarlar": settings}
        (out / "data" / "ceviriler").mkdir(parents=True, exist_ok=True)
        (out / "data" / "ceviriler" / f"{code}.json").write_text(json.dumps(text, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"yazıldı: data/ceviriler/{code}.json")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 4 or sys.argv[1] not in ("bol", "birlestir"):
        sys.exit(__doc__)
    command, code, folder = sys.argv[1:4]
    if code not in DIL_META:
        sys.exit(f"{code}: DIL_META'da yok (önce meta ekle)")
    if command == "bol":
        bol(code, folder)
    else:
        birlestir(code, folder, sys.argv[5] if len(sys.argv) > 5 and sys.argv[4] == "--cikti" else None)


if __name__ == "__main__":
    main()
