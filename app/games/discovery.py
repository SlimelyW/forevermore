"""Bilgisayardaki oyunları bulur (SALT OKUNUR).

Kaynaklar: Steam (libraryfolders.vdf + appmanifest), Epic (Manifests\\*.item),
GOG (kayıt defteri), Ubisoft Connect (kayıt defteri), Riot (product_settings.yaml),
EA / Battle.net (Kaldır kayıtları, yayıncıya göre), Xbox (XboxGames klasörleri),
klasik konumlar (<sürücü>:\\Games\\*).

Oyun yolları yalnızca bu bilgisayarda gösterilir ve saklanır; rapora yazılmaz.
"""

import glob
import json
import os
import re
import string
import datetime
import json

from app.core import log, paths, registry

_log = log.get("games")

SKIP_EXE = re.compile(r"(unins|setup|install|crash|report|redist|vc_redist|vcredist|dxsetup|prereq|updater|"
                      r"easyanticheat|battleye|beservice|helper|cef|launcher|uploader|benchmark|dotnet|directx|"
                      r"unitycrashhandler|ue4prereq|ueprereq|epicwebhelper|overlay|touchup|cleanup|vconsole|ffmpeg|dbg|"
                      r"diagnose|capture|record|browser)", re.I)
# Başlatıcı / istemci / yardımcı süreçler: aday listesinde en sona itilir (oyun değil, oyunu başlatan program).
CLIENT_EXE = re.compile(r"(client|uxrender|launcher|crashhandler|webhelper|bootstrap|socialclub|redprelauncher|"
                        r"eadesktop|eaapp|ubisoftconnect|upc\.exe|galaxy|battle\.net|riotclient)", re.I)
# Bilinen istemci exe -> aynı klasöre göre gerçek oyun exe'si (A6: League profili istemciyle kaydedilmişti)
CLIENT_TO_GAME = {"leagueclient.exe": r"Game\League of Legends.exe",
                  "leagueclientux.exe": r"Game\League of Legends.exe",
                  "leagueclientuxrender.exe": r"Game\League of Legends.exe"}
# Steam araçları (oyun değil)
STEAM_TOOLS = {"228980", "1070560", "1391110", "1628350", "1493710", "1826330", "250820"}


def _vdf(text):
    """Steam KeyValues metnini sözlüğe çevirir (yalnızca okuma için yeterli basit ayrıştırıcı)."""
    tokens = re.findall(r'"((?:[^"\\]|\\.)*)"|([{}])', text)
    stack, current, key = [], {}, None
    for quoted, brace in tokens:
        if brace == "{":
            new = {}
            current[key] = new
            stack.append(current)
            current, key = new, None
        elif brace == "}":
            current = stack.pop() if stack else current
        elif key is None:
            key = quoted.replace("\\\\", "\\")
        else:
            current[key] = quoted.replace("\\\\", "\\")
            key = None
    return current


def _game(name, folder, source, exe=None, baslat=None):
    game = {"ad": name, "klasor": os.path.normpath(folder), "kaynak": source,
            "exe": os.path.normpath(exe) if exe else None}
    if baslat:
        game["baslat"] = baslat  # başlatıcının kendi kısayolu (steam:// vb.); profiles.launch_target doğrular
    return game


def real_game_exe(path):
    """İstemci/başlatıcı exe'si seçildiyse ve gerçek oyun exe'si yanında varsa onu döndürür; yoksa yolu aynen."""
    if not path:
        return path
    relative = CLIENT_TO_GAME.get(os.path.basename(path).lower())
    if relative:
        candidate = os.path.join(os.path.dirname(path), relative)
        if os.path.isfile(candidate):
            return os.path.normpath(candidate)
    # Unreal Engine: kökteki exe yalnızca başlatıcıdır; kareleri <Proje>\Binaries\Win64\*-Shipping.exe üretir.
    if not os.path.basename(path).lower().endswith("-shipping.exe"):
        shipping = glob.glob(os.path.join(glob.escape(os.path.dirname(path)), "*", "Binaries", "Win64", "*-Shipping.exe"))
        if len(shipping) == 1:
            return os.path.normpath(shipping[0])
    return path


def _steam():
    # Yönetici olarak başka hesapla çalışınca HKCU o hesabındır: Steam'in makine geneli kaydına da bakılır.
    root = (registry.read("HKCU", r"Software\Valve\Steam", "SteamPath")
            or registry.read("HKLM", r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath")
            or registry.read("HKLM", r"SOFTWARE\Valve\Steam", "InstallPath"))
    if not root or not os.path.isdir(root):
        return []
    libraries = {os.path.normpath(root)}
    try:
        with open(os.path.join(root, "steamapps", "libraryfolders.vdf"), encoding="utf-8", errors="replace") as f:
            data = _vdf(f.read()).get("libraryfolders", {})
        for entry in data.values():
            if isinstance(entry, dict) and entry.get("path"):
                libraries.add(os.path.normpath(entry["path"]))
    except OSError:
        pass
    games = []
    for library in libraries:
        for manifest in glob.glob(os.path.join(library, "steamapps", "appmanifest_*.acf")):
            try:
                with open(manifest, encoding="utf-8", errors="replace") as f:
                    state = _vdf(f.read()).get("AppState", {})
            except OSError:
                continue
            if state.get("appid") in STEAM_TOOLS or not state.get("installdir"):
                continue
            folder = os.path.join(library, "steamapps", "common", state["installdir"])
            if os.path.isdir(folder):
                appid = state.get("appid", "")
                games.append(_game(state.get("name") or state["installdir"], folder, "Steam",
                                   baslat=f"steam://rungameid/{appid}" if str(appid).isdigit() else None))
    return games


def _epic():
    folder = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), r"Epic\EpicGamesLauncher\Data\Manifests")
    games = []
    for item in glob.glob(os.path.join(folder, "*.item")):
        try:
            with open(item, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        location = data.get("InstallLocation")
        if not location or not os.path.isdir(location) or "games" not in [c.lower() for c in
                                                                          data.get("AppCategories", ["games"])]:
            continue
        exe = data.get("LaunchExecutable")
        games.append(_game(data.get("DisplayName") or os.path.basename(location), location, "Epic",
                           os.path.join(location, exe) if exe else None,
                           baslat=(f"com.epicgames.launcher://apps/{data['AppName']}?action=launch&silent=true"
                                   if re.fullmatch(r"[\w.-]+", str(data.get("AppName", ""))) else None)))
    return games


def launcher_uri(path):
    """Kısayolu kaydedilmemiş (eski/elle eklenmiş) oyun için: yolun içinde kaldığı Steam/Epic oyununun kısayolu,
    yoksa None. Yalnızca yerel appmanifest / .item dosyalarını okur; ağ yok."""
    if not path:
        return None
    target = os.path.normcase(os.path.normpath(path))
    try:
        found = _steam() + _epic()
    except Exception:  # okunamayan başlatıcı dosyası başlatmayı engellemesin: exe ile açılır
        _log.exception("Başlatıcı kısayolu aranamadı")
        return None
    for game in found:
        folder = os.path.normcase(game["klasor"])
        if game.get("baslat") and (target == folder or target.startswith(folder.rstrip(os.sep) + os.sep)):
            return game["baslat"]
    return None


def _gog():
    key = r"SOFTWARE\WOW6432Node\GOG.com\Games"
    games = []
    for sub in registry.subkeys("HKLM", key):
        path = registry.read("HKLM", key + "\\" + sub, "path")
        if path and os.path.isdir(path):
            games.append(_game(registry.read("HKLM", key + "\\" + sub, "gameName") or os.path.basename(path), path,
                               "GOG", registry.read("HKLM", key + "\\" + sub, "exe")))
    return games


def _ubisoft():
    key = r"SOFTWARE\WOW6432Node\Ubisoft\Launcher\Installs"
    games = []
    for sub in registry.subkeys("HKLM", key):
        path = registry.read("HKLM", key + "\\" + sub, "InstallDir")
        if path and os.path.isdir(path):
            games.append(_game(os.path.basename(os.path.normpath(path)), path, "Ubisoft Connect"))
    return games


RIOT_EXE = {"league_of_legends": r"Game\League of Legends.exe",
            "valorant": r"ShooterGame\Binaries\Win64\VALORANT-Win64-Shipping.exe"}


def _riot():
    folder = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), r"Riot Games\Metadata")
    games = []
    for settings in glob.glob(os.path.join(folder, "*", "*.product_settings.yaml")):
        try:
            with open(settings, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            continue
        match = re.search(r'product_install_full_path:\s*"?([^"\r\n]+)"?', text)
        if not match or not os.path.isdir(match.group(1).strip()):
            continue
        path = match.group(1).strip()
        product = os.path.basename(settings).split(".")[0]
        if product == "riot_client":
            continue
        exe = RIOT_EXE.get(product)
        games.append(_game(product.replace("_", " ").title(), path, "Riot",
                           os.path.join(path, exe) if exe else None))
    return games


def _uninstall_by_publisher(publishers, source):
    games = []
    for root, key in (("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                      ("HKLM", r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                      ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Uninstall")):
        for sub in registry.subkeys(root, key):
            path = key + "\\" + sub
            publisher = (registry.read(root, path, "Publisher") or "").lower()
            if not any(p in publisher for p in publishers):
                continue
            name = registry.read(root, path, "DisplayName") or sub
            location = registry.read(root, path, "InstallLocation")
            if not location or not os.path.isdir(location) or re.search(r"(launcher|app|desktop|battle\.net$)",
                                                                         name, re.I):
                continue
            games.append(_game(name, location, source))
    return games


def _xbox():
    games = []
    for letter in string.ascii_uppercase[2:]:  # A: ve B: disket sürücüsü: boşken yavaş yanıt verebilir
        root = f"{letter}:\\XboxGames"
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            folder = os.path.join(root, name, "Content")
            if os.path.isdir(folder):
                games.append(_game(name, folder, "Xbox"))
    return games


def _classic():
    games = []
    for letter in string.ascii_uppercase:
        root = f"{letter}:\\Games"
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            folder = os.path.join(root, name)
            if os.path.isdir(folder):
                games.append(_game(name, folder, "Klasör"))
    return games


SOURCES = [("Steam", _steam), ("Epic", _epic), ("GOG", _gog), ("Ubisoft Connect", _ubisoft), ("Riot", _riot),
           ("EA", lambda: _uninstall_by_publisher(["electronic arts"], "EA")),
           ("Battle.net", lambda: _uninstall_by_publisher(["blizzard"], "Battle.net")),
           ("Xbox", _xbox), ("Klasör", _classic)]


def discover(errors=None):
    """Tüm kaynaklardan oyun listesi (aynı klasör bir kez). errors: {kaynak: hata metni} doldurulur."""
    found, seen = [], set()
    for name, func in SOURCES:
        try:
            games = func()
        except Exception as exc:  # bir kaynağın hatası diğerlerini durdurmasın
            _log.warning("Oyun kaynağı okunamadı (%s): %s", name, exc)
            if errors is not None:
                errors[name] = str(exc) or type(exc).__name__
            continue
        for game in games:
            key = game["klasor"].lower()
            if key not in seen:
                seen.add(key)
                found.append(game)
    return sorted(found, key=lambda g: g["ad"].lower())


def cache_path():
    return paths.user_data_dir() / "oyun_taramasi.json"


def load_cache():
    """Son taramanın sonucu (yalnızca bu bilgisayarda): {zaman, oyunlar, hatalar} veya None."""
    try:
        data = json.loads(cache_path().read_text(encoding="utf-8"))
        return data if isinstance(data.get("oyunlar"), list) else None
    except (OSError, ValueError, AttributeError):
        return None


def save_cache(found, errors):
    data = {"zaman": datetime.datetime.now().isoformat(timespec="seconds"), "oyunlar": found, "hatalar": errors}
    try:
        paths.atomic_write(cache_path(), json.dumps(data, ensure_ascii=False, indent=1))
    except OSError as exc:
        _log.warning("Oyun taraması önbelleğe yazılamadı: %s", exc)
    return data


def exe_candidates(folder, limit=8, max_depth=4):
    """Oyun klasöründeki olası ana .exe dosyaları (büyükten küçüğe)."""
    candidates = []
    base_depth = folder.rstrip("\\/").count(os.sep)
    for root, dirs, files in os.walk(folder):
        if root.count(os.sep) - base_depth >= max_depth:
            dirs[:] = []
        dirs[:] = [d for d in dirs if not SKIP_EXE.search(d) and d.lower() not in ("_commonredist", "redist",
                                                                                 "support", "engine")]
        for name in files:
            if name.lower().endswith(".exe") and not SKIP_EXE.search(name):
                path = os.path.join(root, name)
                try:
                    size = os.path.getsize(path)
                except OSError:
                    continue
                bonus = 4 if "shipping" in name.lower() or "win64" in root.lower() else 1
                if _compact(os.path.basename(folder.rstrip("\\/"))) in _compact(name):
                    bonus *= 4  # exe adı oyun klasörünün adına benziyor
                if CLIENT_EXE.search(name):
                    bonus /= 1000  # başlatıcı/istemci: listede kalır ama en sonda
                candidates.append((size * bonus, path))
    return [p for _s, p in sorted(candidates, reverse=True)[:limit]]


def _compact(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())
