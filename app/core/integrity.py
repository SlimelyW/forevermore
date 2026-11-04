"""Paket imzası: güncelleme paketinin yapımcının yayımladığı paket olup olmadığını doğrular (guncelleme.py).

Derlemede (tools/imzala.py) program klasöründeki her dosyanın SHA-256 özeti bir listeye yazılır ve liste
yapımcının ÖZEL anahtarıyla Ed25519 ile imzalanır (_internal/imza.json). Özel anahtar yalnızca yapımcının
bilgisayarında durur; depoda ve pakette yoktur. İndirilen güncelleme bu GENEL anahtarla doğrulanır.

Çalışan uygulama kendi dosyalarını denetlemez: kaynak açıktır, kodu herkes değiştirip derleyebilir.
"""

import hashlib
import json
from pathlib import Path

from app.core import ed25519

PUBLIC_KEY_HEX = "b5f2355dc9fc4b71b91497b2641476d3e2c143caa65f68406b266a9d5abf7628"  # tools/imzala.py anahtar-olustur yazar
MANIFEST = "imza.json"
BUNDLE = "_internal"
# .exe'nin yanında kullanıcının koyabileceği klasörler (DDU vb. araçlar); denetlenmez.
USER_FOLDERS = {"tools"}
# Gezginin kendiliğinden yazdığı dosyalar: yanlış "eklenen" alarmı vermesin.
OS_FILES = {"desktop.ini", "thumbs.db"}


def fingerprint(public_hex=None):
    """Genel anahtarın kısa parmak izi: AB12-CD34-EF56-7890 (kullanıcının karşılaştırması için)."""
    key = bytes.fromhex(public_hex if public_hex is not None else PUBLIC_KEY_HEX)
    digest = hashlib.sha256(key).hexdigest()[:16].upper()
    return "-".join(digest[i:i + 4] for i in range(0, 16, 4))


def canonical(manifest):
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_file(path):
    with open(path, "rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def collect(root):
    """Denetlenen dosyalar: {göreli yol: sha256}. İmza dosyası ve kullanıcı klasörleri hariç."""
    root = Path(root)
    files = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if (not path.is_file() or rel == f"{BUNDLE}/{MANIFEST}" or rel.split("/")[0].lower() in USER_FOLDERS
                or path.name.lower() in OS_FILES):
            continue
        files[rel] = sha256_file(path)
    return files


def build_manifest(root, version):
    return {"uygulama": "Forevermore", "surum": version, "dosyalar": collect(root)}


def check_folder(root, public_hex=None):
    """Bir program klasörünü denetler. Dönüş: {"durum", "degisen", "eksik", "eklenen", "surum"}."""
    root = Path(root)
    result = {"durum": "imzasiz", "degisen": [], "eksik": [], "eklenen": [], "surum": None}
    public_hex = PUBLIC_KEY_HEX if public_hex is None else public_hex
    try:
        signed = json.loads((root / BUNDLE / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return result
    manifest = signed.get("manifest") if isinstance(signed, dict) else None
    try:
        valid = bool(public_hex) and isinstance(manifest, dict) and ed25519.verify(
            bytes.fromhex(public_hex), canonical(manifest), bytes.fromhex(signed.get("imza", "")))
    except ValueError:
        valid = False
    result["durum"] = "degistirilmis"
    if not valid:
        result["degisen"] = [MANIFEST]
        return result
    result["surum"] = manifest.get("surum")
    expected, actual = manifest.get("dosyalar") or {}, collect(root)
    result["degisen"] = sorted(k for k in expected if k in actual and actual[k] != expected[k])
    result["eksik"] = sorted(k for k in expected if k not in actual)
    result["eklenen"] = sorted(k for k in actual if k not in expected)
    if not (result["degisen"] or result["eksik"] or result["eklenen"]):
        result["durum"] = "orijinal"
    elif not result["eklenen"]:
        result["durum"] = "bozuk"
    return result
