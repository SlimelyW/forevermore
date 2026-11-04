"""Arayüzün beyni: tarama, ayar motoru ve veri arasındaki bağlantı.

Bu dosya arayüz kütüphanesi kullanmaz; böylece pencere olmadan test edilebilir.
Uzun süren her metot arka plan iş parçacığında çağrılmak içindir.

Hız için:
- Ayar durumları paralel okunur (her ayar ayrı iş parçacığında).
- Son tarama ve durumlar diske önbelleklenir; uygulama açılınca önce bunlar
  gösterilir, gerçek durum arka planda okunup yerine konur. Önbellekteki bir
  durumla HİÇBİR değişiklik yapılmaz: bir ayarın düğmesi, o oturumda sistemden
  yeniden okunana kadar kilitli kalır.
"""

import copy
import hashlib
import json
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from app import __version__
from app.core import admin, log, paths, privacy
from app.core.i18n import fmt_date, t
from app.engine import catalog, compat, profiles, recommend, resolvers
from app.engine.backup import BackupStore
from app.engine.engine import Engine, TweakState
from app.engine.system import ReadOnlySystem, WindowsSystem
from app.scan import checks, run_scan

_log = log.get("ui")

MODE_NORMAL = "normal"          # yönetici, ayarlar değiştirilebilir
MODE_READ_ONLY = "salt_okunur"  # yönetici izni verilmedi
MODE_PREVIEW = "onizleme"       # deneme modu: hiçbir şey değiştirilmez, yedek geçici klasörde
MODE_BACKUPS_NOT_MOVED = "yedek_tasinamadi"  # yönetici ama yedekler korumalı klasöre geçirilemedi: yazma yok

RESTART_PRIORITY = ["bilgisayar", "oturum", "gezgin", "uygulama", "ses_servisi", "durumsal", "yok"]
STATE_WORKERS = 8
# Bu yöneticilerin ayarları kategori sayfalarında değil, kendi menülerinde yapılır.
OWN_PAGE = {"baslangic": "baslangic", "oyunlar": "oyunlar"}
# Uygulamanın yapamadığı ayarlar kategori sayfalarında değil, "Elle yapılacaklar" sayfasında nedenine göre
# toplanır (Placebo bilgi kartları kendi sayfasında kalır).
MANUAL_REASONS = ("bios", "ag", "oyun_ici", "surucu", "donanim", "uretici", "windows", "kullanici", "teshis",
                  "ucuncu_parti")


def is_manual(tweak):
    return (tweak["sinif"] in ("REHBER", "BILGI") and not tweak.get("liste_yoneticisi")
            and tweak["kategori"] != "Placebo")


def _catalog_fingerprint():
    data = (paths.data_dir() / "tweaks_app.json").read_bytes()
    return hashlib.sha256(data).hexdigest()[:16]


class Controller:
    def __init__(self, mode, engine=None, cache_file=None):
        self.mode = mode
        data = catalog.load()
        self.meta = data["meta"]
        self.categories = data["kategoriler"]
        self.research = data["arastirma_notlari"]
        self.placebo_menu = data["placebo_menusu"]
        self.tweaks = data["ayarlar"]
        self.by_id = {tw["id"]: tw for tw in self.tweaks}
        self.dc_variants = {}    # laptopta güç ayarlarının "pilde" kopyaları: asıl id -> kopya
        if engine is None:
            if mode == MODE_PREVIEW:
                self._tmp = tempfile.TemporaryDirectory()
                store = BackupStore(Path(self._tmp.name))
            else:
                store = BackupStore(readonly=mode != MODE_NORMAL)
            system = WindowsSystem() if mode == MODE_NORMAL else ReadOnlySystem(WindowsSystem())
            is_admin = admin.is_admin if mode == MODE_NORMAL else (lambda: False)
            engine = Engine(system=system, store=store, is_admin=is_admin)
        self.engine = engine
        self.profiles = profiles.load(self.by_id)
        self.scan = None
        self.scan_is_cached = False
        self.states = {}         # id -> TweakState
        self.availability = {}   # id -> Availability
        self.fresh = set()       # bu oturumda sistemden okunmuş ayarlar
        self.restart_codes = set()
        self.explorer_restart = False
        self._lock = threading.Lock()
        self.cache_file = cache_file or (paths.user_data_dir() / "onbellek.json")

    # ------------------------------------------------------------------ önbellek
    def load_cache(self):
        """Son oturumun tarama ve durumlarını yükler (yalnızca göstermek için)."""
        try:
            data = json.loads(self.cache_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        if data.get("surum") != __version__ or data.get("veri") != _catalog_fingerprint():
            return False
        self.scan = data.get("tarama")
        self.scan_is_cached = self.scan is not None
        for tweak_id, item in data.get("durumlar", {}).items():
            if tweak_id in self.by_id:
                self.states[tweak_id] = TweakState(item["durum"], values=item.get("degerler") or {})
        for tweak_id, item in data.get("uygunluk", {}).items():
            if tweak_id in self.by_id:
                self.availability[tweak_id] = compat.Availability(
                    item["gorunur"], [tuple(r) for r in item["nedenler"]], [tuple(w) for w in item["uyarilar"]])
        return True

    def save_cache(self):
        with self._lock:
            data = {
                "surum": __version__,
                "veri": _catalog_fingerprint(),
                # Önbellek de gizlilik filtresinden geçer ("_yerel" alanlar diske yazılmaz).
                "tarama": privacy.scrub(self.scan, export=True) if self.scan else None,
                "durumlar": {k: {"durum": s.status, "degerler": s.values} for k, s in self.states.items()
                             if k in self.fresh},
                "uygunluk": {k: {"gorunur": a.visible, "nedenler": a.reasons, "uyarilar": a.warnings}
                             for k, a in self.availability.items()},
            }
        try:
            tmp = self.cache_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.cache_file)
        except OSError as exc:
            _log.warning("Önbellek yazılamadı: %s", exc)

    # ------------------------------------------------------------------ okuma
    @property
    def can_modify(self):
        return self.mode == MODE_NORMAL

    def is_fresh(self, tweak_id):
        return tweak_id in self.fresh

    def run_scan(self, progress=None):
        scan = run_scan(progress=progress)
        resolvers.prime_from_scan(scan)
        with self._lock:
            self.scan = scan
            self.scan_is_cached = False
        self.engine._profile = compat.SystemProfile.from_scan(scan)
        return scan

    def recheck(self, tweak_id):
        """Çözümden sonra yalnız bu maddeyi yeniden okur (tam tarama 15-25 sn sürer ve tüm sayfaları yeniden kurar).
        Sorunlu ayar tespiti artık yoksa ilgili bulgu listeden çıkar (True döner). Arka plan iş parçacığında çağrılır."""
        checks.clear_cache()
        tweak = self.by_id.get(tweak_id)
        if tweak is not None:
            self.refresh_one(tweak_id)
        if self.scan is None or tweak is None or not tweak.get("tespit"):
            return False
        if checks.evaluate([tweak], self.scan.get("bolumler") or {}):
            return False
        with self._lock:
            self.scan["tespitler"] = [d for d in self.scan.get("tespitler") or [] if d["id"] != tweak_id]
            self.scan["bulgular"] = [f for f in self.scan.get("bulgular") or []
                                     if not (f["kod"] == "tespit" and f["ilgili"] == [tweak_id])]
        return True  # bulgu listesi değişti

    def recommendations(self, limit=recommend.LIMIT):
        """Bu bilgisayar için öneriler (bkz. app/engine/recommend.py); tarama yoksa boş."""
        hw = ((self.scan or {}).get("bolumler") or {}).get("donanim") or {}
        vendors = sorted({g["uretici"] for g in hw.get("gpu") or [] if g.get("uretici")})
        form = (hw.get("bilgisayar") or {}).get("tur", "masaustu")
        return recommend.recommend(self.tweaks, self.availability, self.states, vendors, form, limit)

    def refresh_all(self, on_each=None, reread=True):
        """Tüm ayarların uygunluğunu ve durumunu paralel okur.

        on_each(ayar_id) her ayar bitince (arka plan iş parçacığından) çağrılır. reread=False: bu oturumda zaten
        okunmuş ve görünür kalan ayarın durumu yeniden okunmaz (tarama sonrası tazeleme; 2.9: açılışta ikinci tur
        7-8 PowerShell daha açıyordu).
        """
        self.engine._availability.clear()
        _ = self.engine.profile  # profil bir kez, paralel okumalardan önce belirlensin
        self._ensure_dc_variants()
        targets = self.tweaks + list(self.dc_variants.values())
        with ThreadPoolExecutor(max_workers=STATE_WORKERS, thread_name_prefix="durum") as pool:
            futures = {pool.submit(self.refresh_one, tw["id"], reread): tw["id"] for tw in targets}
            for future in as_completed(futures):
                tweak_id = futures[future]
                try:
                    future.result()
                except Exception as exc:  # tek ayar hatası diğerlerini durdurmasın
                    _log.warning("Durum okunamadı (%s): %s", tweak_id, exc)
                if on_each:
                    on_each(tweak_id)

    def _ensure_dc_variants(self):
        """Laptopta yalnızca güç planı değeri yazan her switch için ayrı bir "Pilde" kopyası.
        Kopya kendi kimliğiyle (ör. PWR-003@pil) yedeklenir ve geri alınır."""
        if self.engine.profile.form != "laptop" or self.dc_variants:
            return
        for tweak in self.tweaks:
            if tweak["sinif"] != "SWITCH" or tweak["islem"]["kontrol"] != "switch":
                continue
            steps = tweak["islem"]["adimlar"]
            if not steps or not all(s["tur"] == "powercfg" or (s["tur"] == "yerlesik" and s["eylem"] == "guc_modu")
                                    for s in steps):
                continue
            variant = copy.deepcopy(tweak)
            variant["id"] = tweak["id"] + "@pil"
            variant["ad"] = f"{tweak['ad']} — {t('ui.pilde')}"
            variant["pilde_kopyasi"] = tweak["id"]
            for step in variant["islem"]["adimlar"]:
                if step["tur"] == "powercfg":
                    step["kaynak"] = "dc"
                else:
                    step["parametreler"]["kaynak"] = "dc"
            with self._lock:
                self.dc_variants[tweak["id"]] = variant
                self.by_id[variant["id"]] = variant

    def refresh_one(self, tweak_id, reread=True):
        tweak = self.by_id[tweak_id]
        if tweak["sinif"] == "BILGI":
            avail, state = compat.Availability(True), None
        elif tweak["sinif"] == "SWITCH":
            was_visible = tweak_id in self.fresh and getattr(self.availability.get(tweak_id), "visible", False)
            avail = self.engine.availability(tweak, refresh=True)
            keep = not reread and was_visible and tweak_id in self.states
            state = self.engine.read_state(tweak) if avail.visible and not keep else None
        else:
            avail, state = compat.check(tweak, self.engine.profile, resolve=False), None
        with self._lock:
            self.availability[tweak_id] = avail
            if state is not None:
                self.states[tweak_id] = state
            self.fresh.add(tweak_id)

    # ------------------------------------------------------------------ gösterim yardımcıları
    def category_items(self, category_name, include_hidden=False):
        """{"switch": [...], "rehber": [...], "bilgi": [...], "gizli": [...]} — ayar sözlükleri."""
        groups = {"switch": [], "rehber": [], "bilgi": [], "gizli": []}
        for tweak in self.tweaks:
            if tweak["kategori"] != category_name:
                continue
            avail = self.availability.get(tweak["id"])
            if avail is not None and not avail.visible:
                if include_hidden:
                    groups["gizli"].append(tweak)
                continue
            if tweak.get("liste_yoneticisi") in OWN_PAGE:  # kendi menüsünde yapılır (Oyunlar, Başlangıç)
                continue
            if is_manual(tweak):  # uygulamanın yapamadığı ayar: "Elle yapılacaklar" sayfasında
                continue
            if tweak.get("liste_yoneticisi"):  # uygulamanın kendi listesiyle yapılır: ayarlar bölümünde
                groups["switch"].append(tweak)
                continue
            groups[{"SWITCH": "switch", "REHBER": "rehber", "BILGI": "bilgi"}[tweak["sinif"]]].append(tweak)
        return groups

    def manual_items(self):
        """Elle yapılacaklar: {neden: [ayar, ...]} — bu bilgisayarda görünenler, MANUAL_REASONS sırasıyla."""
        groups = {reason: [] for reason in MANUAL_REASONS}
        for tweak in self.tweaks:
            avail = self.availability.get(tweak["id"])
            if is_manual(tweak) and (avail is None or avail.visible):
                groups[tweak.get("elle_nedeni") or "windows"].append(tweak)
        return {reason: items for reason, items in groups.items() if items}

    def category_counts(self, category_name):
        """Kenar menü için (açık, toplam) — yalnızca bu bilgisayarda görünen switch'ler."""
        on = total = 0
        for tweak in self.tweaks:
            if tweak["kategori"] != category_name or tweak["sinif"] != "SWITCH":
                continue
            avail = self.availability.get(tweak["id"])
            if avail is None or not avail.visible or tweak["islem"]["kontrol"] != "switch":
                continue
            total += 1
            state = self.states.get(tweak["id"])
            if state and state.is_on:
                on += 1
        return on, total

    def detected_ids(self):
        """Taramada 'daha önce uygulanmış' bulunan zararlı/placebo ayarlar."""
        return {d["id"] for d in (self.scan or {}).get("tespitler", [])}

    def changed(self):
        """Uygulamanın değiştirdiği ayarlar: [(id, ad, zaman)]."""
        rows = []
        for tweak_id in self.engine.changed_ids():
            entry = self.engine.store.get(tweak_id)
            rows.append((tweak_id, entry.get("ad", tweak_id), fmt_date(entry["zaman"])))
        return rows

    def note_result(self, result):
        if result.ok and result.restart and result.restart != "yok":
            self.restart_codes.add(result.restart)
        if result.explorer:
            self.explorer_restart = True

    def restart_message_key(self):
        for code in RESTART_PRIORITY:
            if code in self.restart_codes and code not in ("yok", "ses_servisi"):
                return f"yeniden.{code}"
        return None

    def category_of(self, tweak_id):
        tweak = self.by_id.get(tweak_id)
        return tweak["kategori"] if tweak else None
