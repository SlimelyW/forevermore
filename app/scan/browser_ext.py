"""Yüklü tarayıcı eklentileri (salt okunur, yalnızca yerel dosyalar).

Chromium tabanlı tarayıcılar (Chrome, Edge, Brave, Vivaldi, Opera, Chromium): her profilin Extensions
klasöründeki manifest.json. Firefox: profilin extensions.json dosyası. Hiçbir şey değiştirilmez,
hiçbir yere gönderilmez; eklentiyi kapatmak kullanıcıya bırakılır (tarayıcının eklenti sayfası).
Yalnızca Chrome gerçek bir bilgisayarda denendi; diğer tarayıcıların biçimi belgelere ve bilgiye dayanır.
"""

import json
import os
from pathlib import Path

_ALL_SITES = ("<all_urls>", "*://*/*", "http://*/*", "https://*/*")


def _chromium_roots():
    local, roaming = os.environ.get("LOCALAPPDATA", ""), os.environ.get("APPDATA", "")
    # (ad, kök klasör, profiller kökün altında "Default"/"Profile N" mi yoksa kökün kendisi mi)
    return [
        ("Chrome", Path(local, "Google", "Chrome", "User Data"), True),
        ("Edge", Path(local, "Microsoft", "Edge", "User Data"), True),
        ("Brave", Path(local, "BraveSoftware", "Brave-Browser", "User Data"), True),
        ("Vivaldi", Path(local, "Vivaldi", "User Data"), True),
        ("Chromium", Path(local, "Chromium", "User Data"), True),
        ("Opera", Path(roaming, "Opera Software", "Opera Stable"), False),
        ("Opera GX", Path(roaming, "Opera Software", "Opera GX Stable"), False),
    ]


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _localized(folder, manifest, text):
    """'__MSG_ad__' biçimindeki adı _locales altından çözer; çözülemezse metni olduğu gibi döndürür."""
    if not (isinstance(text, str) and text.startswith("__MSG_") and text.endswith("__")):
        return text
    key = text[6:-2].lower()
    default = manifest.get("default_locale") or "en"
    for code in (default, "en", "en_US", "en_GB"):
        messages = _read_json(Path(folder, "_locales", code, "messages.json"))
        if isinstance(messages, dict):
            for name, value in messages.items():
                if name.lower() == key and isinstance(value, dict) and value.get("message"):
                    return value["message"]
    return text


def _wide_access(manifest):
    patterns = list(manifest.get("host_permissions") or []) + [p for p in manifest.get("permissions") or []
                                                               if isinstance(p, str)]
    for script in manifest.get("content_scripts") or []:
        patterns += script.get("matches") or []
    return any(p in _ALL_SITES for p in patterns)


def _chromium_profile(profile):
    """Bir profildeki eklentiler (tema ve boş klasörler atlanır). Etkin/devre dışı bilgisi Secure Preferences'tan."""
    folder = Path(profile, "Extensions")
    if not folder.is_dir():
        return []
    prefs = _read_json(Path(profile, "Secure Preferences")) or _read_json(Path(profile, "Preferences")) or {}
    settings = ((prefs.get("extensions") or {}).get("settings")) or {}
    found = []
    for ext in sorted(p for p in folder.iterdir() if p.is_dir()):
        versions = sorted(v for v in ext.iterdir() if v.is_dir())
        manifest = _read_json(Path(versions[-1], "manifest.json")) if versions else None
        if not isinstance(manifest, dict) or "theme" in manifest:
            continue
        entry = settings.get(ext.name) or {}
        if entry.get("location") in (5, 10):  # Chrome'un kendi bileşenleri (PDF görüntüleyici vb.), kullanıcının eklentisi değil
            continue
        found.append({"id": ext.name, "ad": _localized(versions[-1], manifest, manifest.get("name")) or ext.name,
                      "surum": manifest.get("version"),
                      "etkin": entry.get("state") != 0 and not entry.get("disable_reasons"),
                      "tum_siteler": _wide_access(manifest), "arka_plan": bool(manifest.get("background")),
                      "manifest": manifest.get("manifest_version")})
    return found


def _chromium(name, root, nested):
    if not root.is_dir():
        return []
    profiles = ([p for p in sorted(root.iterdir()) if p.is_dir() and (p.name == "Default" or p.name.startswith("Profile "))]
                if nested else [root])
    return [{"tarayici": name, "profil": p.name if nested else "", "eklentiler": exts}
            for p in profiles if (exts := _chromium_profile(p))]


def _firefox():
    base = Path(os.environ.get("APPDATA", ""), "Mozilla", "Firefox", "Profiles")
    if not base.is_dir():
        return []
    result = []
    for profile in sorted(p for p in base.iterdir() if p.is_dir()):
        data = _read_json(profile / "extensions.json")
        exts = []
        for addon in (data or {}).get("addons") or []:
            # yalnızca kullanıcının kurduğu eklentiler (sistem/yerleşik olanlar "app-profile" değildir)
            if addon.get("type") != "extension" or addon.get("location") != "app-profile":
                continue
            origins = ((addon.get("userPermissions") or {}).get("origins")) or []
            exts.append({"id": addon.get("id"), "ad": (addon.get("defaultLocale") or {}).get("name") or addon.get("id"),
                         "surum": addon.get("version"), "etkin": bool(addon.get("active")) and not addon.get("userDisabled"),
                         "tum_siteler": any(o in _ALL_SITES for o in origins), "arka_plan": None, "manifest": None})
        if exts:
            result.append({"tarayici": "Firefox", "profil": profile.name.split(".", 1)[-1], "eklentiler": exts})
    return result


def collect():
    """[{tarayici, profil, eklentiler: [{id, ad, surum, etkin, tum_siteler, arka_plan, manifest}]}]"""
    result = []
    for name, root, nested in _chromium_roots():
        result += _chromium(name, root, nested)
    return result + _firefox()
