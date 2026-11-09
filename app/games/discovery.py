"""Bilgisayardaki oyunları bulur (SALT OKUNUR).

Kaynaklar: Steam (libraryfolders.vdf + appmanifest), Epic (Manifests\\*.item),
GOG (kayıt defteri), Ubisoft Connect (kayıt defteri), Riot (product_settings.yaml),
EA / Battle.net (Kaldır kayıtları, yayıncıya göre), Xbox (XboxGames klasörleri),
klasik konumlar (<sürücü>:\\Games\\*).

Oyun yolları yalnızca bu bilgisayarda gösterilir ve saklanır; rapora yazılmaz.
"""

import fnmatch
import glob
import json
import os
import re
import string
import time
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


def steam_root():
    """Steam'in kurulu olduğu klasör ya da None."""
    # Yönetici olarak başka hesapla çalışınca HKCU o hesabındır: Steam'in makine geneli kaydına da bakılır.
    root = (registry.read("HKCU", r"Software\Valve\Steam", "SteamPath")
            or registry.read("HKLM", r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath")
            or registry.read("HKLM", r"SOFTWARE\Valve\Steam", "InstallPath"))
    return root if root and os.path.isdir(root) else None


# Steam'in YEREL görsel önbelleği (appcache\librarycache\<appid>\...): yeni düzende dosya adı hash olabilir ve her
# oyunda farklı türler bulunur (library_600x900, library_capsule, library_hero, header, logo, küçük simge...). Bu yüzden tür
# adına değil, dosyanın BOYUTUNA bakılır: önce kapak oranına yakın (dikey) en çözünürlüklüsü, yoksa en yüksek (kırpılınca
# en az büyütülen) yatay görsel; kart her ikisini de kırparak doldurur. Küçük kare simge kapak diye şişirilmez.
# Ağdan hiçbir şey indirilmez.
PORTRAIT_MAX = 0.85    # genişlik/yükseklik bundan küçükse dikey kapak, değilse yatay/kare sayılır
MIN_PORTRAIT_W = 300   # dikey için en az genişlik (kart 156 px; 2x ekranda şişmesin)
MIN_FIT_LONG = 400     # yatay/kare için en uzun kenar en az; 184x184 topluluk simgesi gibi küçükler elenir
MIN_LANDSCAPE_H = 200  # yatay için en az yükseklik (kutu 208 px: daha alçak görsel kırpılınca fazla büyür)
SKIP_IMAGE = ("logo", "blur", "marker")  # saydam logo ve bulanık arka plan kapak yerine geçmez
USER_COVER_ID = re.compile(r"OYUN-[0-9a-f]{10}")


def image_size(path):
    """(genişlik, yükseklik) ya da None: yalnızca PNG ve JPEG başlığı okunur (görüntü çözülmez, Qt gerekmez)."""
    try:
        with open(path, "rb") as f:
            head = f.read(26)
            if head[:8] == b"\x89PNG\r\n\x1a\n" and head[12:16] == b"IHDR":
                return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")
            if head[:2] != b"\xff\xd8":
                return None
            f.seek(2)
            for _ in range(64):  # işaretçiler arasında gez: SOFn (C0-CF, C4/C8/CC hariç) boyutu taşır
                marker = f.read(2)
                if len(marker) < 2 or marker[0] != 0xFF:
                    return None
                while marker[1] == 0xFF:  # dolgu baytları
                    marker = b"\xff" + f.read(1)
                    if len(marker) < 2:
                        return None
                if marker[1] in (0xD8, 0x01) or 0xD0 <= marker[1] <= 0xD7:
                    continue
                length = int.from_bytes(f.read(2), "big")
                if 0xC0 <= marker[1] <= 0xCF and marker[1] not in (0xC4, 0xC8, 0xCC):
                    data = f.read(5)
                    height, width = int.from_bytes(data[1:3], "big"), int.from_bytes(data[3:5], "big")
                    return (width, height) if width and height else None
                f.seek(length - 2, 1)
    except OSError:
        pass
    return None


def steam_cover(appid, root=None):
    """Steam'in yerel önbelleğindeki en uygun görsel (bkz. yukarıdaki kural); yoksa None.
    appid yalnızca rakam olabilir (yol karıştırılamaz)."""
    appid = str(appid or "")
    root = root or steam_root()
    if not appid.isdigit() or not root:
        return None
    cache = os.path.join(root, "appcache", "librarycache")
    files = glob.glob(os.path.join(glob.escape(cache), f"{appid}_*"))  # eski düzen
    for folder, _dirs, names in os.walk(os.path.join(cache, appid)):  # yeni düzen: <appid>\<hash>\dosya
        files += [os.path.join(folder, n) for n in names]
    best = None
    for path in files:
        name = os.path.basename(path).lower()
        if not name.endswith((".jpg", ".jpeg", ".png")) or any(k in name for k in SKIP_IMAGE):
            continue
        size = image_size(path)
        if not size:
            continue
        width, height = size
        portrait = width / height <= PORTRAIT_MAX
        if width < MIN_PORTRAIT_W if portrait else (max(width, height) < MIN_FIT_LONG or height < MIN_LANDSCAPE_H):
            continue
        key = (portrait, 0 if portrait else height, width * height, name)
        if best is None or key > best[0]:
            best = (key, path)
    return best[1] if best else None


def user_cover_dir():
    """Kullanıcının seçtiği oyun resimlerinin klasörü (yalnızca yerel; OLUŞTURMAZ)."""
    return paths.user_data_path() / "kapaklar"


def user_cover(game_id):
    """Kullanıcının bu oyun için seçtiği (kopyalanıp ölçeklenmiş) resim ya da None."""
    if not USER_COVER_ID.fullmatch(str(game_id or "")):
        return None
    path = user_cover_dir() / f"{game_id}.jpg"
    return str(path) if path.is_file() else None


def remove_user_cover(game_id):
    """Kullanıcının seçtiği resmi siler (oyun kaydı ya da 'Resmi kaldır'); yoksa sessizce geçer."""
    path = user_cover(game_id)
    if path:
        try:
            os.remove(path)
        except OSError as exc:
            _log.warning("Oyun resmi silinemedi: %s", exc)


_cover_index = {}  # (json yolu, değişme zamanı) -> girdiler: her kart çizilişinde dosya yeniden okunup ayrıştırılmasın


def _cover_entries(path):
    try:
        key = (str(path), path.stat().st_mtime_ns)
    except OSError:
        return []
    if key not in _cover_index:
        try:
            entries = json.loads(path.read_text(encoding="utf-8")).get("kapaklar") or []
        except (OSError, ValueError):
            entries = []
        _cover_index.clear()
        _cover_index[key] = entries
    return _cover_index[key]


def embedded_cover(game, appid=None):
    """Pakete gömülü kapak (data/oyun_kapaklari/) ya da None. Eşleştirme sırası: exe adı -> Steam appid -> klasör/takma ad
    (harf-rakam dışı karakterler yok sayılır, TAM eşitlik; 'Rust' yalnızca 'Rust' olan oyunla eşleşir). Yalnızca oyun
    kaydındaki alanlara bakar (yeni tarama yok), ağa bağlanmaz."""
    base = paths.data_dir()
    entries = _cover_entries(base / "oyun_kapaklari.json")
    exe = os.path.basename(game.get("exe") or "").lower()
    names = {_compact(os.path.basename(os.path.normpath(game["klasor"]))) if game.get("klasor") else "",
             _compact(game.get("ad") or "")} - {""}

    def keys(entry):
        return {_compact(x) for x in [entry.get("ad")] + (entry.get("klasor") or []) + (entry.get("takma") or [])} - {""}

    for matches in (lambda e: exe and any(fnmatch.fnmatchcase(exe, p.lower()) for p in e.get("exe") or []),
                    lambda e: appid and str(appid) in (e.get("appid") or []),
                    lambda e: names & keys(e)):
        for entry in entries:
            if matches(entry):
                path = base / "oyun_kapaklari" / os.path.basename(entry.get("dosya") or "")
                return str(path) if path.is_file() else None
    return None


def cover_path(game, root=None):
    """Oyunun yerel görseli. Sıra: kullanıcının seçtiği resim -> (Steam kısayolu olan oyunlarda) Steam yerel önbelleği ->
    pakete gömülü kapak; yoksa None (arayüz exe simgesine, o da yoksa harfe düşer). Epic için yerel önbellekte
    kullanılabilir görsel bulunamadı; gömülü kapak bu boşluğu (ve Steam dışı kopyaları) doldurur."""
    own = user_cover(game.get("id"))
    if own:
        return own
    match = re.fullmatch(r"steam://rungameid/(\d+)", game.get("baslat") or "")
    appid = match.group(1) if match else steam_appid(game.get("klasor"))
    return (steam_cover(appid, root) if appid else None) or embedded_cover(game, appid)


_appids = {}  # (steamapps klasörü, installdir) -> appid (yalnızca bulunanlar; manifest her çizimde yeniden okunmasın)


def steam_appid(folder):
    """steamapps/common/<installdir> altındaki oyun klasöründen Steam appid'si (yerel appmanifest_*.acf okunur) ya da None.
    Listemdeki oyunun kaydında Steam kısayolu (baslat) yoksa kapak yine de bulunsun diye (eski/elle eklenen kayıtlar)."""
    parts = os.path.normpath(folder or "").split(os.sep)
    low = [p.lower() for p in parts]
    for i in range(len(parts) - 2, 0, -1):
        if low[i] == "common" and low[i - 1] == "steamapps":
            steamapps, installdir = os.sep.join(parts[:i]), parts[i + 1].lower()
            break
    else:
        return None
    if (steamapps, installdir) not in _appids:
        for manifest in glob.glob(os.path.join(glob.escape(steamapps), "appmanifest_*.acf")):
            try:
                with open(manifest, encoding="utf-8", errors="replace") as f:
                    state = _vdf(f.read()).get("AppState", {})
            except OSError:
                continue
            if str(state.get("installdir", "")).lower() == installdir and str(state.get("appid", "")).isdigit():
                _appids[(steamapps, installdir)] = state["appid"]
                break
    return _appids.get((steamapps, installdir))


def steam_libraries():
    """Steam kitaplık klasörleri (yerel libraryfolders.vdf; salt okunur). Steam yoksa []."""
    root = steam_root()
    if not root:
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
    return sorted(libraries)


def steam_downloading(window=120, now=None):
    """Steam şu an indirme/güncelleme yapıyor mu? YAKLAŞIK ve salt okunur: bir kitaplığın steamapps/downloading
    klasöründeki bir dosya son `window` saniyede değişmişse True (duraklatılmış indirme dosya yazmaz: False).
    Steam'e hiçbir şey yazılmaz, ağa bağlanılmaz. Gerçek bir indirmeyle DENENMEDİ."""
    now = time.time() if now is None else now
    for library in steam_libraries():
        folder = os.path.join(library, "steamapps", "downloading")
        try:
            for base, _dirs, files in os.walk(folder):
                if base[len(folder):].count(os.sep) >= 2:
                    continue
                for name in files:
                    if now - os.stat(os.path.join(base, name)).st_mtime <= window:
                        return True
        except OSError:
            continue
    return False


def _steam():
    libraries = steam_libraries()
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
    for letter in string.ascii_uppercase[2:]:  # A:/B: disket sürücüleri yoklanmaz (boşken yavaş yanıt verir)
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
