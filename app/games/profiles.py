"""Oyun listesi ve oyun başına profil.

Yerel dosya: %LOCALAPPDATA%\\Forevermore\\oyunlar.json (hiçbir yere gönderilmez).

Ayarlar iki türdür:
- KALICI (uygulama kapalıyken de geçerli; kaydedince yazılır, Değişiklikler'den geri alınır):
  öncelik (IFEO PerfOptions), GPU tercihi (DirectX UserGpuPreferences),
  tam ekran optimizasyonları (AppCompatFlags\\Layers).
- OYUN SIRASINDA (uygulama açıkken; oyun açılınca uygulanır, kapanınca geri alınır):
  çekirdek seçimi (CPU Sets), güç kısmasından muafiyet, servis duraklatma,
  Windows Search, Steam önceliği, oyun güç planı, bildirimler, standby temizliği,
  pencereyi küçültme. Bkz. runtime.py.
"""

import copy
import json
import os
import shutil

from app.core import log, paths
from app.engine.managers import item_id
from app.games import discovery

_log = log.get("games")

DEFAULT_PROFILE = {
    "otomatik": True,               # oyun açılınca otomatik uygula (kapalıyken seçimler saklanır, uygulanmaz)
    "oncelik": "Normal",            # Normal / AboveNormal / High (Realtime YOK)
    "gpu_tercihi": "varsayilan",    # varsayilan / guc_tasarrufu / yuksek_performans
    "fso_kapali": False,
    "cekirdek_secimi": "tum",       # tum / performans / fiziksel / vcache / ozel
    "cekirdekler": None,            # özel seçimde CPU numaraları
    "guc_kismasi_muaf": False,
    "servisleri_duraklat": False,
    "windows_search_durdur": False,
    "steam_dusuk_oncelik": False,
    "guc_plani": False,
    "bildirimleri_kapat": False,
    "standby_temizle": False,       # durumsal: ölçerek kullanın
    "pencereyi_kucult": False,
    "boost": False,                 # oyun açılınca Boost listesindeki açık programları nazikçe kapat (geri alınmaz)
}
PERSISTENT_DEFAULTS = {"oncelik": "Normal", "gpu_tercihi": "varsayilan", "fso_kapali": False}
RUNTIME_KEYS = ("guc_kismasi_muaf", "servisleri_duraklat", "windows_search_durdur", "steam_dusuk_oncelik",
                "guc_plani", "bildirimleri_kapat", "standby_temizle", "pencereyi_kucult", "boost")

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
)


def detect_anti_cheat(game, max_depth=4):
    """Oyunda bulunan anti-cheat adları (salt okunur, klasörün ilk dört seviyesine bakılır).
    Gömülü veya sunucu tarafı korumalar (ör. VAC) klasörde görünmez; bulunamaması "yok" demek değildir."""
    found = set()
    if game.get("kaynak") == "Riot":
        found.add("Riot Vanguard")
    folder = game.get("klasor") or ""
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
    return sorted(found)


def is_protected(exe):
    return os.path.basename(exe or "").lower() in PROTECTED_EXES


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
        return games

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

    def add(self, name, folder, source, exe=None):
        exe = discovery.real_game_exe(exe)
        if exe and is_protected(exe):
            raise ValueError("korumali")
        game_id = item_id("OYUN", exe or folder)
        existing = self.get(game_id)
        if existing:
            return existing
        game = {"id": game_id, "ad": name, "klasor": folder, "kaynak": source, "exe": exe,
                "profil": copy.deepcopy(DEFAULT_PROFILE)}
        game["anti_cheat"] = detect_anti_cheat(game)
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

    def ensure_anti_cheat(self):
        """Eski kayıtlarda anti-cheat bilgisi yoksa bir kez hesaplar."""
        changed = False
        for game in self.games:
            if "anti_cheat" not in game:
                game["anti_cheat"] = detect_anti_cheat(game)
                changed = True
        if changed:
            self.save()

    def remove(self, game_id):
        self.games = [g for g in self.games if g["id"] != game_id]
        self.save()

    def runtime_games(self):
        """Oyun sırasında uygulanacak ayarı olan oyunlar (izleyici yalnızca bunlar için çalışır)."""
        return [g for g in self.games if g.get("exe") and g["profil"].get("otomatik", True) and (
            any(g["profil"].get(k) for k in RUNTIME_KEYS) or g["profil"].get("cekirdek_secimi") != "tum")]


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
