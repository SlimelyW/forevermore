"""Paket imzalama (yalnızca yapımcının bilgisayarında).

    py -3.12 tools\\imzala.py anahtar-olustur        -> özel anahtarı oluşturur, genel anahtarı koda yazar
    py -3.12 tools\\imzala.py imzala dist\\Forevermore -> dosya listesini imzalar (_internal\\imza.json)
    py -3.12 tools\\imzala.py denetle dist\\Forevermore

Özel anahtar: %USERPROFILE%\\.forevermore-imza\\ozel_anahtar.txt (PCOPT_IMZA_ANAHTARI ile değiştirilebilir).
Bu dosya DEPOYA KONMAZ, kimseyle paylaşılmaz; yedeğini USB/şifreli bir yerde saklayın. Kaybolursa yeni anahtar
oluşturup genel anahtarı (ve parmak izini) yeniden yayımlamak gerekir; çalınırsa başkası "orijinal" görünen
paket imzalayabilir.
"""

import os
import re
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import __version__  # noqa: E402
from app.core import ed25519, integrity  # noqa: E402

KEY_FILE = Path(os.environ.get("PCOPT_IMZA_ANAHTARI") or Path.home() / ".forevermore-imza" / "ozel_anahtar.txt")
CODE = ROOT / "app" / "core" / "integrity.py"


def load_secret():
    try:
        return bytes.fromhex(KEY_FILE.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return None


def create_key():
    if KEY_FILE.exists():
        raise SystemExit(f"Anahtar zaten var: {KEY_FILE} (üzerine yazılmaz)")
    secret = secrets.token_bytes(32)
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    KEY_FILE.write_text(secret.hex() + "\n", encoding="ascii")
    public = ed25519.public_key(secret).hex()
    text = CODE.read_text(encoding="utf-8")
    text, count = re.subn(r'^PUBLIC_KEY_HEX = "[0-9a-f]*"', f'PUBLIC_KEY_HEX = "{public}"', text, flags=re.MULTILINE)
    if count != 1:
        raise SystemExit("integrity.py içinde PUBLIC_KEY_HEX satırı bulunamadı")
    CODE.write_text(text, encoding="utf-8")
    print(f"Özel anahtar: {KEY_FILE}  (YEDEKLEYİN, PAYLAŞMAYIN)")
    print(f"Genel anahtar koda yazıldı. Parmak izi: {integrity.fingerprint(public)}")


def sign_folder(folder):
    secret = load_secret()
    if secret is None:
        print(f"UYARI: imza anahtarı yok ({KEY_FILE}); paket İMZASIZ kalır.")
        return 2
    public = ed25519.public_key(secret).hex()
    if public != integrity.PUBLIC_KEY_HEX:
        raise SystemExit("Özel anahtar koddaki genel anahtarla eşleşmiyor; paket imzalanmadı.")
    folder = Path(folder)
    manifest = integrity.build_manifest(folder, __version__)
    signature = ed25519.sign(secret, integrity.canonical(manifest)).hex()
    target = folder / integrity.BUNDLE / integrity.MANIFEST
    import json  # noqa: WPS433
    target.write_text(json.dumps({"manifest": manifest, "imza": signature}, ensure_ascii=False, indent=1),
                      encoding="utf-8")
    result = integrity.check_folder(folder)
    print(f"İmzalandı: {len(manifest['dosyalar'])} dosya, denetim: {result['durum']}, "
          f"parmak izi: {integrity.fingerprint()}")
    return 0 if result["durum"] == "orijinal" else 1


def check(folder):
    result = integrity.check_folder(folder)
    print(result["durum"], {k: v[:10] for k, v in result.items() if isinstance(v, list) and v})
    return 0 if result["durum"] == "orijinal" else 1


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "anahtar-olustur":
        create_key()
        return 0
    if len(sys.argv) >= 3 and sys.argv[1] == "imzala":
        return sign_folder(sys.argv[2])
    if len(sys.argv) >= 3 and sys.argv[1] == "denetle":
        return check(sys.argv[2])
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
