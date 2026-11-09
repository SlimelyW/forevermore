"""Oyun listesi ve oyun başına profil.

Yerel dosya: %LOCALAPPDATA%\\Forevermore\\oyunlar.json (hiçbir yere gönderilmez).

Ayarlar iki türdür:
- KALICI (uygulama kapalıyken de geçerli; "Kaydet" / "Önerilen ayarları uygula" ile motordan yazılır, Değişiklikler'den
  geri alınır): öncelik (IFEO PerfOptions), GPU tercihi (DirectX UserGpuPreferences), tam ekran optimizasyonları.
- OYUN SIRASINDA (RUNTIME_KEYS; yalnızca kullanıcı "Hazırla" / "Oyunu başlat"a basınca uygulanır, oyun kapanınca ya da
  "Geri al" ile geri alınır; arka planda izleyici YOK). Oyun izleyici 7 Kasım 2026'da kaldırılmıştı; bu seçenekler
  düğmeye bağlı olarak geri geldi (runtime.GameSession). Çekirdek seçimi, güç kısması muafiyeti, standby temizliği ve
  oyun içi Boost GERİ GELMEDİ (docs/KARAR_GUNLUGU.md).
"""

import copy
import json
import os
import re
import shutil

from app.core import log, paths
from app.engine.managers import item_id
from app.games import discovery

_log = log.get("games")

DEFAULT_PROFILE = {
    "otomatik": True,               # kapalıyken seçimler saklanır, sisteme Windows varsayılanı yazılır
    "oncelik": "Normal",            # Normal / AboveNormal / High (Realtime YOK)
    "gpu_tercihi": "varsayilan",    # varsayilan / guc_tasarrufu / yuksek_performans
    "fso_kapali": False,
    # oyun sırasında (hepsi varsayılan KAPALI; bkz. RUNTIME_KEYS)
    "hazirla_rahatsiz_etme": False,         # Windows Rahatsız etme açılır
    "hazirla_steam_uyari": False,    # Steam indirmesi sürüyorsa uyar (Steam'e dokunulmaz)
    "hazirla_guc_plani": False,     # Yüksek performans güç planı
    "hazirla_servisler": False,      # SysMain, DiagTrack, MapsBroker, WerSvc (anti-cheat'li oyunda gizli)
    "hazirla_search": False,          # (anti-cheat'li oyunda gizli)
    "hazirla_steam_oncelik": False,  # steamwebhelper önceliği düşer (anti-cheat'li oyunda gizli)
}
RUNTIME_KEYS = ("hazirla_rahatsiz_etme", "hazirla_steam_uyari", "hazirla_guc_plani", "hazirla_servisler", "hazirla_search",
                "hazirla_steam_oncelik")
# Oyun sürecine, oyunun hizmetlerine ya da başka süreçlere dokunmayanlar: anti-cheat'li oyunda da açılabilir.
RUNTIME_ANTI_CHEAT_OK = ("hazirla_rahatsiz_etme", "hazirla_steam_uyari", "hazirla_guc_plani")
PERSISTENT_DEFAULTS = {"oncelik": "Normal", "gpu_tercihi": "varsayilan", "fso_kapali": False}

# Anti-cheat ve başlatıcı süreçleri: oyun olarak eklenemez, hiçbir ayar uygulanmaz.
PROTECTED_EXES = {"vgc.exe", "vgk.exe", "vgtray.exe", "beservice.exe", "beservice_x64.exe", "easyanticheat.exe",
                  "easyanticheat_eos.exe", "easyanticheat_eos_setup.exe", "faceit.exe", "faceitservice.exe",
                  "eaanticheat.gameservice.exe", "eaanticheat.installer.exe", "gameguard.exe", "xigncode.exe",
                  "riotclientservices.exe", "leagueclient.exe", "leagueclientux.exe", "steam.exe",
                  "epicgameslauncher.exe", "battle.net.exe", "eadesktop.exe", "upc.exe", "galaxyclient.exe"}

PRIORITY_CLASS = {"Normal": None, "AboveNormal": 6, "High": 3}  # IFEO CpuPriorityClass (None = değer silinir)
GPU_PREF = {"varsayilan": None, "guc_tasarrufu": "GpuPreference=1;", "yuksek_performans": "GpuPreference=2;"}
FSO_FLAG = "DISABLEDXMAXIMIZEDWINDOWEDMODE"
IFEO = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options"
GPU_KEY = r"Software\Microsoft\DirectX\UserGpuPreferences"
LAYERS_KEY = r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"


# Oyun klasöründe aranan anti-cheat izleri (klasör veya dosya adında geçen ifade).
ANTI_CHEAT_MARKERS = (
    ("EasyAntiCheat", ("easyanticheat", "start_protected_game")),
    ("BattlEye", ("battleye", "beservice")),
    ("nProtect GameGuard", ("gameguard",)),
    ("XIGNCODE3", ("xigncode",)),
    ("EA Javelin", ("eaanticheat",)),
    ("Nexon BlackCipher", ("blackcipher",)),  # The First Descendant: canlı FPS açıkken oyunu kapattı (docs/CANLI_FPS_COKME.md)
    ("Anti-cheat", ("anticheat",)),  # genel iz (THE FINALS/ARC Raiders: AntiCheatInstaller.exe); adı bilinen varsa o yazılır
)
ANTI_CHEAT_VERSION = 3  # işaret listesi değişince artar: eski kayıtlar bir kez yeniden taranır


def detect_anti_cheat(game, max_depth=4):
    """Oyunda bulunan anti-cheat adları (salt okunur, klasörün ilk dört seviyesine bakılır).
    Gömülü veya sunucu tarafı korumalar (ör. VAC) klasörde görünmez; bulunamaması "yok" demek değildir."""
    found = set()
    folder = game.get("klasor") or ""
    if game.get("kaynak") == "Riot" or r"\riot games" + "\\" in folder.lower().replace("/", "\\") + "\\":
        found.add("Riot Vanguard")
    base = folder.rstrip("\\/").count(os.sep)
    try:
        for root, dirs, files in os.walk(folder):
            if root.count(os.sep) - base >= max_depth:
                dirs[:] = []
            for name in dirs + files:
                lowered = name.lower()
                for label, markers in ANTI_CHEAT_MARKERS:
                    if any(m in lowered for m in markers):
                        found.add(label)
    except OSError:
        pass
    if len(found) > 1:
        found.discard("Anti-cheat")  # adı bilinen koruma varsa genel etiket gereksiz
    return sorted(found)


def runtime_options(game):
    """Bu oyunda GÖRÜNEN oyun-sırası seçenekleri. Anti-cheat'li oyunda yalnızca oyun sürecine dokunmayanlar
    (Rahatsız etme, Steam indirme uyarısı, güç planı); servis durdurma ve süreç önceliği gizli."""
    return RUNTIME_ANTI_CHEAT_OK if game.get("anti_cheat") else RUNTIME_KEYS


def runtime_selected(game):
    """Kullanıcının bu oyunda açtığı VE bu oyunda izin verilen seçenekler (uygulama katmanı ayrıca süzer)."""
    return [k for k in runtime_options(game) if (game.get("profil") or {}).get(k)]


def is_protected(exe):
    return os.path.basename(exe or "").lower() in PROTECTED_EXES


_LAUNCH_URI = re.compile(r"steam://rungameid/\d+|com\.epicgames\.launcher://apps/[\w.-]+\?action=launch&silent=true")


def launch_target(game, rediscover=False):
    """Başlatma hedefi: bulunan Steam/Epic kısayolu (oyun listesi dosyası elle değişmiş olabilir: yalnızca bu iki kalıp
    kabul edilir), yoksa var olan exe, yoksa None. Anti-cheat'li oyunda da aynı normal başlatmadır.
    rediscover: kayıtlı kısayol yoksa Steam/Epic dosyalarından yeniden bulunur (yalnızca tıklayınca; disk okur)."""
    uri = game.get("baslat")
    if not (isinstance(uri, str) and _LAUNCH_URI.fullmatch(uri)) and rediscover:
        uri = discovery.launcher_uri(game.get("exe") or game.get("klasor"))
    if isinstance(uri, str) and _LAUNCH_URI.fullmatch(uri):
        return uri
    exe = game.get("exe")
    return exe if exe and os.path.isfile(exe) else None


class GameStore:
    def __init__(self, path=None):
        self.path = path or (paths.user_data_dir() / "oyunlar.json")
        self.games = []
        self.load_error = None  # "yedekten" (önceki kopyadan dönüldü) veya "bozuk" (okunamadı, kenara alındı)
        self.load()

    def _previous(self):
        return self.path.with_name(self.path.stem + ".onceki.json")

    def _read(self, path):
        games = json.loads(path.read_text(encoding="utf-8")).get("oyunlar", [])
        if not isinstance(games, list):
            raise ValueError("oyunlar listesi yok")
        return [g for g in games if isinstance(g, dict) and isinstance(g.get("id"), str) and isinstance(g.get("ad"), str)]

    def load(self):
        """Bozuk dosya sessizce boş liste sayılmaz (eskiden ilk kayıtta profiller kayboluyordu): bir önceki sağlam
        kopyadan dönülür; o da yoksa bozuk dosya kenara alınır ve sebep arayüzde gösterilir."""
        self.load_error = None
        try:
            self.games = self._read(self.path)
        except FileNotFoundError:
            self.games = []
        except (OSError, ValueError, AttributeError) as exc:
            _log.error("Oyun listesi okunamadı (%s): %s", self.path.name, exc)
            try:
                self.games, self.load_error = self._read(self._previous()), "yedekten"
            except (OSError, ValueError, AttributeError):
                self.games, self.load_error = [], "bozuk"
            try:
                os.replace(self.path, self.path.with_name(self.path.stem + ".bozuk.json"))
            except OSError:
                pass
        fixed = False
        for game in self.games:
            game["profil"] = dict(DEFAULT_PROFILE, **game.get("profil", {}))
            real = discovery.real_game_exe(game.get("exe"))
            if real != game.get("exe"):  # eski kayıt istemci exe'siyle yapılmış (ör. LeagueClientUxRender.exe)
                _log.info("Oyun exe'si düzeltildi: %s -> %s", game["exe"], real)
                game["exe"], fixed = real, True
        if fixed:
            self.save()

    def save(self):
        try:
            if self.path.exists():
                shutil.copyfile(self.path, self._previous())  # bir önceki sağlam hâl
            paths.atomic_write(self.path, json.dumps({"oyunlar": self.games}, ensure_ascii=False, indent=2))
        except OSError as exc:
            _log.warning("Oyun listesi kaydedilemedi: %s", exc)

    def get(self, game_id):
        return next((g for g in self.games if g["id"] == game_id), None)

    def add(self, name, folder, source, exe=None, baslat=None):
        exe = discovery.real_game_exe(exe)
        if exe and is_protected(exe):
            raise ValueError("korumali")
        game_id = item_id("OYUN", exe or folder)
        existing = self.get(game_id)
        if existing:
            return existing
        game = {"id": game_id, "ad": name, "klasor": folder, "kaynak": source, "exe": exe,
                "profil": copy.deepcopy(DEFAULT_PROFILE)}
        if baslat:
            game["baslat"] = baslat
        game["anti_cheat"], game["anti_cheat_surum"] = detect_anti_cheat(game), ANTI_CHEAT_VERSION
        self.games.append(game)
        self.games.sort(key=lambda g: g["ad"].lower())
        self.save()
        return game

    def set_exe(self, game_id, exe):
        exe = discovery.real_game_exe(exe)
        if is_protected(exe):
            raise ValueError("korumali")
        self.get(game_id)["exe"] = exe
        self.save()

    def update_profile(self, game_id, profile):
        self.get(game_id)["profil"] = dict(DEFAULT_PROFILE, **profile)
        self.save()

    def set_runtime(self, game_id, key, value):
        """Tek bir oyun-sırası anahtarını saklar (sisteme hiçbir şey yazılmaz)."""
        if key not in RUNTIME_KEYS:
            raise ValueError(key)
        self.get(game_id)["profil"][key] = bool(value)
        self.save()

    def ensure_anti_cheat(self):
        """Eski kayıtlarda (veya işaret listesi değişince) anti-cheat bilgisini bir kez hesaplar. Yalnızca EKLER: klasör o an
        erişilemezse (sürücü takılı değil) daha önce bulunan koruma silinmez."""
        changed = False
        for game in self.games:
            if game.get("anti_cheat_surum") != ANTI_CHEAT_VERSION:
                game["anti_cheat"] = sorted(set(game.get("anti_cheat") or []) | set(detect_anti_cheat(game)))
                game["anti_cheat_surum"] = ANTI_CHEAT_VERSION
                changed = True
        if changed:
            self.save()

    def remove(self, game_id):
        self.games = [g for g in self.games if g["id"] != game_id]
        self.save()
        discovery.remove_user_cover(game_id)  # kullanıcının seçtiği resim de gider


# ---------------------------------------------------------------------------
# Kalıcı ayarlar: adım ve değer üretimi (motorun apply_custom yolu kullanılır)
# ---------------------------------------------------------------------------

def _reg(root, path, name, kind):
    return {"tur": "registry", "kok": root, "yol": path, "ad": name, "veri_turu": kind,
            "acik": None, "kapali": None, "yoksa": None}


def _layers_value(current, disable_fso):
    """Uyumluluk bayraklarındaki diğer bayraklara dokunmadan FSO bayrağını ekler/çıkarır."""
    flags = [f for f in (current or "").replace("~", " ").split() if f.upper() != FSO_FLAG]
    if disable_fso:
        flags.append(FSO_FLAG)
    return ("~ " + " ".join(flags)) if flags else None


def persistent_changes(game, profile, read_reg):
    """[(değişiklik_kimliği, ad_anahtarı, adım, değer)] — yalnızca şu ankinden farklı olanlar.
    read_reg(kök, yol, ad) -> değer veya None."""
    exe = game["exe"]
    name = os.path.basename(exe)
    changes = []
    step = _reg("HKLM", f"{IFEO}\\{name}\\PerfOptions", "CpuPriorityClass", "REG_DWORD")
    want = PRIORITY_CLASS[profile["oncelik"]]
    if read_reg("HKLM", step["yol"], "CpuPriorityClass") != want:
        changes.append((game["id"] + "-oncelik", "oyun.degisiklik.oncelik", step, want))
    step = _reg("HKCU", GPU_KEY, exe, "REG_SZ")
    want = GPU_PREF[profile["gpu_tercihi"]]
    if read_reg("HKCU", GPU_KEY, exe) != want:
        changes.append((game["id"] + "-gpu", "oyun.degisiklik.gpu", step, want))
    step = _reg("HKCU", LAYERS_KEY, exe, "REG_SZ")
    current = read_reg("HKCU", LAYERS_KEY, exe)
    want = _layers_value(current, profile["fso_kapali"])
    if (current or None) != want:
        changes.append((game["id"] + "-fso", "oyun.degisiklik.fso", step, want))
    return changes


def read_persistent(game, read_reg):
    """Sistemdeki gerçek kalıcı durum (profil dosyasına değil sisteme güvenilir)."""
    exe = game["exe"]
    priority = read_reg("HKLM", f"{IFEO}\\{os.path.basename(exe)}\\PerfOptions", "CpuPriorityClass")
    gpu = read_reg("HKCU", GPU_KEY, exe)
    layers = (read_reg("HKCU", LAYERS_KEY, exe) or "").upper()
    return {"oncelik": {6: "AboveNormal", 3: "High"}.get(priority, "Normal"),
            "gpu_tercihi": {v: k for k, v in GPU_PREF.items() if v}.get(gpu, "varsayilan"),
            "fso_kapali": FSO_FLAG in layers}
