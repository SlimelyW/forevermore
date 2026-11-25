"""Oyunun kendi ayar dosyası: sakla (birebir kopya), geri yükle, sıfırla. Ayrıntı: docs/OYUN_ICI_AYAR.md, docs/GUVENLIK.md.

GÜVENLİK:
- Yollar yalnızca GAMES katalogundan gelir; arayüz yalnızca oyun kimliği ve kopya adı gönderir. Dosya içeriği okunmaz,
  yorumlanmaz, hiçbir ayar anahtarı yazılmaz: dosya bütün olarak kopyalanır ya da taşınır.
- Oyun VEYA başlatıcısı açıksa hiçbir işlem yapılmaz (açık oyun dosyayı yeniden yazar; Riot "ikisi de kapalı" diyor).
- Hedefler kökün içinde olmalı; yolda bağlantı/birleşim noktası (OneDrive yer tutucusu dahil) varsa atlanır.
- Silme yok: sıfırla ve geri yükle mevcut dosyayı kaldırıcının yedek klasörüne TAŞIR (uninstaller.remove_leftovers);
  "geri al" bunu yerine koyar. Kendi saklanan kopyalarımızdan yalnızca en eski olanlar (KEEP üstü) silinir.
- Sıfırla yalnızca yapımcının sıfırlamayı kendisinin anlattığı oyunlarda (Riot, Ubisoft); Fortnite'ta yok.
"""

import datetime
import fnmatch
import json
import os
import re
import shutil
from pathlib import Path

from app.core import paths
from app.engine import uninstaller
from app.engine.cleaners import REPARSE_POINT, _running

KEEP = 5
SNAPSHOT_NAME = re.compile(r"\d{8}-\d{6}")
ITEM_NAME = re.compile(r"k\d{1,3}")
RIOT = ("riotclientservices.exe", "riot client.exe", "riotclientux.exe")

# id -> eşleşen oyun adları, (ortam anahtarı, kökten klasörler), kök altındaki hedef kalıpları, sıfırla?, kapalı olması gereken süreçler
# Süreç adları yapımcı belgesi değil, bilinen exe adlarıdır (docs/OYUN_ICI_AYAR.md).
GAMES = {
    "valorant": (("VALORANT",), ("LOCALAPPDATA", ("VALORANT", "Saved")), ("Config",), True,
                 ("valorant.exe", "valorant-win64-shipping.exe") + RIOT),
    "lol": (("League of Legends",), ("SYSTEMDRIVE", ("Riot Games", "League of Legends")), ("Config",), True,
            ("league of legends.exe", "leagueclient.exe", "leagueclientux.exe") + RIOT),
    "fortnite": (("Fortnite",), ("LOCALAPPDATA", ("FortniteGame", "Saved", "Config", "WindowsClient")),
                 ("GameUserSettings.ini",), False,
                 ("fortniteclient-win64-shipping.exe", "fortnitelauncher.exe", "epicgameslauncher.exe")),
    "r6": (("Tom Clancy's Rainbow Six Siege", "Rainbow Six Siege"), ("DOCUMENTS", ("My Games", "Rainbow Six - Siege")),
           ("*/GameSettings.ini",), True,
           ("rainbowsix.exe", "rainbowsix_vulkan.exe", "rainbowsix_be.exe", "upc.exe", "ubisoftconnect.exe")),
}


def _key(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def find(game_name):
    """Oyun adı -> katalog kimliği ya da None (guides.find ile aynı önek eşleşmesi)."""
    key = _key(game_name or "")
    for game_id, spec in GAMES.items():
        for name in spec[0]:
            other = _key(name)
            if key and (other.startswith(key) or key.startswith(other)):
                return game_id
    return None


def _documents():
    """Belgeler klasörü (OneDrive'a yönlendirilmiş olabilir): SHGetFolderPathW(CSIDL_PERSONAL)."""
    try:
        import ctypes  # noqa: WPS433
        buffer = ctypes.create_unicode_buffer(260)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buffer) == 0:
            return buffer.value
    except (AttributeError, OSError):
        pass
    return None


def _env(env):
    if env is not None:
        return env
    return dict(os.environ, DOCUMENTS=_documents() or "")


def _root(game_id, env):
    var, parts = GAMES[game_id][1]
    if not env.get(var):
        return None
    return Path(env[var] + os.sep).joinpath(*parts)


def _safe(path, root):
    """Yol kökün içinde mi; kök ile hedef arasındaki hiçbir öğe bağlantı/birleşim noktası değil mi?"""
    try:
        relative = Path(path).relative_to(root)
    except ValueError:
        return False
    current = Path(root)
    for part in relative.parts:
        current = current / part
        try:
            if os.path.islink(current) or os.lstat(current).st_file_attributes & REPARSE_POINT:
                return False
        except (OSError, AttributeError):
            return False
    real_root = os.path.realpath(root).lower().rstrip("\\/") + os.sep
    return os.path.realpath(path).lower().startswith(real_root)


def _targets(game_id, env):
    root = _root(game_id, env)
    if root is None:
        return []
    found = []
    for pattern in GAMES[game_id][2]:
        for path in sorted(root.glob(pattern)):
            if _safe(path, root):
                found.append(str(path))
    return found


def _store(base, game_id):
    return Path(base) if base else paths.game_settings_dir() / game_id


def _manifest(folder):
    try:
        return json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def snapshots(game_id, base=None):
    """Saklanan kopyalar, yeni olan önce: [{"ad", "tarih"}]."""
    store = _store(base, game_id)
    if not store.is_dir():
        return []
    found = []
    for folder in store.iterdir():
        data = _manifest(folder) if SNAPSHOT_NAME.fullmatch(folder.name) else None
        if data and data.get("oyun") == game_id:
            found.append({"ad": folder.name, "tarih": data.get("tarih", "")})
    return sorted(found, key=lambda s: s["ad"], reverse=True)


def _label(game_id):
    return "Oyun ayarı: " + GAMES[game_id][0][0]


def resets(game_id, base=None):
    """Geri alınabilir taşımalar (sıfırla / geri yükle öncesi), yeni olan önce: uninstaller.list_sessions süzülmüş."""
    return [s for s in uninstaller.list_sessions(base) if s["program"] == _label(game_id)]


def status(game_id, env=None, processes=None, base=None, backup_base=None):
    """Salt okunur: {"var": hedef var mı, "calisiyor", "sifirla", "kopyalar", "geri_al": son taşıma oturumu ya da None}."""
    env = _env(env)
    running = _running(processes)
    undo = resets(game_id, backup_base)
    return {"var": bool(_targets(game_id, env)), "calisiyor": any(p in running for p in GAMES[game_id][4]),
            "sifirla": GAMES[game_id][3], "kopyalar": snapshots(game_id, base),
            "geri_al": undo[0]["oturum"] if undo else None}


def _guard(game_id, processes):
    if any(p in _running(processes) for p in GAMES[game_id][4]):
        raise RuntimeError("calisiyor")


def save(game_id, env=None, processes=None, base=None, now=None):
    """Hedeflerin birebir kopyasını tarihli klasöre alır; en yeni KEEP kopya kalır. Kopya adını döner."""
    _guard(game_id, processes)
    targets = _targets(game_id, _env(env))
    if not targets:
        raise FileNotFoundError(game_id)
    now = now or datetime.datetime.now()
    store = _store(base, game_id)
    folder = store / now.strftime("%Y%m%d-%H%M%S")
    folder.mkdir(parents=True, exist_ok=False)
    items = []
    try:
        for number, target in enumerate(targets, 1):
            copy = folder / f"k{number}"
            (shutil.copytree if os.path.isdir(target) else shutil.copy2)(target, copy)
            items.append({"yol": target, "yedek": copy.name})
    except (OSError, shutil.Error):
        shutil.rmtree(folder, ignore_errors=True)
        raise
    manifest = {"oyun": game_id, "tarih": now.isoformat(timespec="seconds"), "ogeler": items}
    (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    for old in snapshots(game_id, base)[KEEP:]:
        shutil.rmtree(store / old["ad"], ignore_errors=True)
    return folder.name


def _move_aside(game_id, env, backup_base, now):
    """Mevcut hedefleri kaldırıcının yedek klasörüne taşır (geri alınabilir). Oturum adı ya da None."""
    targets = _targets(game_id, env)
    if not targets:
        return None
    result = uninstaller.remove_leftovers(_label(game_id), [{"tur": "klasor", "yol": t} for t in targets],
                                          backup_base, None, now)
    if result["basarisiz"]:
        raise OSError(result["basarisiz"][0]["neden"])
    return result["oturum"]


def reset(game_id, env=None, processes=None, backup_base=None, now=None):
    """Resmi sıfırlama: ayar dosyası/klasörü silinmez, yedeğe taşınır; oyun açılınca yenisini kurar."""
    if not GAMES[game_id][3]:
        raise ValueError(game_id)
    _guard(game_id, processes)
    session = _move_aside(game_id, _env(env), backup_base, now)
    if session is None:
        raise FileNotFoundError(game_id)
    return session


def restore(game_id, name, env=None, processes=None, base=None, backup_base=None, now=None):
    """Saklanan kopyayı yerine koyar; mevcut dosya önce yedeğe taşınır. Manifestteki yol katalog kökünün dışındaysa reddedilir."""
    if not SNAPSHOT_NAME.fullmatch(name):
        raise ValueError(name)
    _guard(game_id, processes)
    env = _env(env)
    root = _root(game_id, env)
    folder = _store(base, game_id) / name
    data = _manifest(folder)
    if root is None or not data or data.get("oyun") != game_id:
        raise FileNotFoundError(name)
    items = data["ogeler"]
    for item in items:  # dosyalara dokunmadan önce: manifest elle değiştirilmiş olabilir
        if not _valid_target(game_id, root, item.get("yol", "")) or not ITEM_NAME.fullmatch(item.get("yedek", "")):
            raise ValueError(item.get("yol"))
    session = _move_aside(game_id, env, backup_base, now)
    for item in items:
        target, copy = Path(item["yol"]), folder / item["yedek"]
        target.parent.mkdir(parents=True, exist_ok=True)
        (shutil.copytree if copy.is_dir() else shutil.copy2)(copy, target)
    return session


def _valid_target(game_id, root, path):
    """Yol katalog kalıbına uyuyor, '..' içermiyor, var olan üst klasörü güvenli mi?"""
    try:
        relative = Path(path).relative_to(root)
    except ValueError:
        return False
    if ".." in relative.parts or not any(fnmatch.fnmatch(relative.as_posix().lower(), p.lower()) for p in GAMES[game_id][2]):
        return False
    parent = Path(path).parent
    return parent == root or not parent.exists() or _safe(parent, root)


def undo(game_id, session, env=None, processes=None, backup_base=None, now=None):
    """Son taşımayı geri alır: şu anki dosya yedeğe taşınır (o da geri alınabilir), taşınan eski dosya yerine konur."""
    if session not in {s["oturum"] for s in resets(game_id, backup_base)}:
        raise ValueError(session)
    _guard(game_id, processes)
    _move_aside(game_id, _env(env), backup_base, now)
    result = uninstaller.restore(session, backup_base)
    if result["basarisiz"]:
        raise OSError(result["basarisiz"][0]["neden"])
    return result["geri_yuklenen"]
