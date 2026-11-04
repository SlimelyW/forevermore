"""Ayar motoru: oku, önizle, uygula, geri al.

Güvenlik kuralları bu sınıfın içinde uygulanır (arayüz atlasa bile geçerlidir):
1. Yalnızca SWITCH sınıfındaki ayarlar değiştirilebilir; riskli, placebo veya
   zararlı ayarlar asla.
2. Bu bilgisayara uymayan (gizli) ayarlar değiştirilemez.
3. "dikkatli" ayarlar açılırken `onaylandi=True` zorunludur.
4. Değişiklikten önce oturumda bir kez geri yükleme noktası denenir
   (`hazirla`). Oluşturulamazsa kullanıcı açıkça kabul etmedikçe devam edilmez.
5. Dokunulacak her değer, yazmadan ÖNCE diske yedeklenir.
6. Bir adım başarısız olursa o ana kadar yazılan adımlar geri alınır.
7. Her işlem log'a ve işlem geçmişine yazılır.
"""

import os

from app.core import admin, log, powershell
from app.core.i18n import fmt_date, t
from app.engine import compat, handlers, resolvers, restore_point
from app.engine.backup import BackupStore
from app.engine.errors import friendly
from app.engine.handlers import UserFacingError
from app.engine.schema import FORBIDDEN_IDS, validate_stored_step
from app.engine.system import WindowsSystem

_log = log.get("engine")

REGISTRY_TYPES = {"registry", "registry_bayrak", "registry_bit", "registry_anahtar"}


class Result:
    def __init__(self, ok, key, params=None, restart=None, explorer=False, warnings=None):
        self.ok = ok
        self.key = key  # lang/tr.json anahtarı
        self.params = params or {}
        self.restart = restart  # yeniden_baslatma_kodu (yok, uygulama, oturum, bilgisayar...)
        self.explorer = explorer  # Gezgin'i yeniden başlatmak önerilsin mi
        self.warnings = warnings or []

    def __repr__(self):
        return f"Result(ok={self.ok}, key={self.key!r}, warnings={self.warnings})"


class TweakState:
    def __init__(self, status, step_states=None, values=None, error=None):
        self.status = status  # acik | kapali | kismen | bilinmiyor
        self.step_states = step_states or []
        self.values = values or {}  # secim: {alan_id: değer}
        self.error = error

    @property
    def is_on(self):
        return self.status == "acik"

    def __repr__(self):
        return f"TweakState({self.status!r}, {self.values or ''})"


class Engine:
    def __init__(self, system=None, store=None, profile=None, resolver=resolvers, is_admin=admin.is_admin):
        self.system = system or WindowsSystem()
        self.store = store or BackupStore()
        self._profile = profile
        self.resolver = resolver
        self.is_admin = is_admin
        self.restore_point = None
        self.accepted_without_restore_point = False
        self._availability = {}

    # ------------------------------------------------------------------ uygunluk
    @property
    def profile(self):
        if self._profile is None:
            self._profile = compat.SystemProfile.detect()
        return self._profile

    def availability(self, tweak, refresh=False):
        if refresh or tweak["id"] not in self._availability:
            self._availability[tweak["id"]] = compat.check(tweak, self.profile, self.resolver)
        return self._availability[tweak["id"]]

    def _steps(self, tweak):
        avail = self.availability(tweak)
        if not avail.visible:
            key, params = avail.reasons[0]
            raise UserFacingError("hata.uygun_degil", neden=key, **params)
        return self.resolver.expand_steps(tweak["islem"], avail.resolution)

    # ------------------------------------------------------------------ okuma
    def read_state(self, tweak):
        """Ayarın şu anki durumu. Hiçbir şey değiştirmez."""
        islem = tweak.get("islem")
        if not islem:
            return TweakState("bilinmiyor")
        if islem["kontrol"] == "eylem":
            return TweakState("eylem")
        try:
            if islem["kontrol"] == "secim":
                values = {}
                for field_id, step in self._selection_steps(tweak):
                    if field_id not in values:  # birden çok ağ kartında ilkinin değeri gösterilir
                        values[field_id] = handlers.selection_value(step, handlers.snapshot(self.system, step))
                return TweakState("secim", values=values)
            all_states = [handlers.state(step, handlers.snapshot(self.system, step)) for step in self._steps(tweak)]
        except Exception as exc:
            _log.warning("Durum okunamadı (%s): %s", tweak["id"], exc)
            return TweakState("bilinmiyor", error=friendly(exc))
        states = [s for s in all_states if s != "yok"]  # bu bilgisayarda olmayan servisler sayılmaz
        if not states:
            status = "bilinmiyor"
        elif all(s == "acik" for s in states):
            status = "acik"
        elif any(s == "acik" for s in states):
            status = "kismen"
        else:
            status = "kapali"
        return TweakState(status, all_states)

    def _selection_steps(self, tweak):
        """[(alan_id, somut_adım)] — çözümleyicisi olan seçimlerde (ör. DNS) her ağ kartı için."""
        islem = tweak["islem"]
        if not islem.get("cozumleyici"):
            return [(f["id"], f["adim"]) for f in islem["alanlar"]]
        avail = self.availability(tweak)
        if not avail.visible:
            key, params = avail.reasons[0]
            raise UserFacingError("hata.uygun_degil", neden=key, **params)
        return [(f["id"], resolvers.substitute(f["adim"], context))
                for context in avail.resolution.contexts for f in islem["alanlar"]]

    def preview(self, tweak, on):
        """Bu ayar uygulanınca nelerin değişeceği (okunabilir satırlar)."""
        which = "acik" if on else "kapali"
        if self.store.has(tweak["id"]) and not on:
            entry = self.store.get(tweak["id"])
            return [t("onizleme.yedekten_geri", zaman=fmt_date(entry["zaman"]))]
        lines = []
        for step in self._steps(tweak):
            try:
                current = handlers.state(step, handlers.snapshot(self.system, step))
            except Exception:
                current = None  # okunamadıysa değişecekmiş gibi göster
            if current != which:
                lines.append(handlers.describe(step, which))
        return lines or [t("onizleme.degisiklik_yok")]

    def changed_ids(self):
        """Uygulamanın değiştirdiği (yedeği olan) ayarlar, en yeni önce."""
        return self.store.ids_newest_first()

    # ------------------------------------------------------------------ hazırlık
    def prepare(self):
        """Oturumdaki ilk değişiklikten önce geri yükleme noktası dener. Bir kez çalışır."""
        if self.restore_point is None:
            self.restore_point = restore_point.ensure(self.system)
        return self.restore_point

    def skip_restore_point(self):
        """Kullanıcı bu oturumda geri yükleme noktası oluşturulmasını istemedi."""
        self.restore_point = restore_point.RestorePointResult(restore_point.RestorePointResult.FAILED, detail="atlandi")
        self.accept_without_restore_point()

    def accept_without_restore_point(self):
        """Kullanıcı geri yükleme noktası olmadan devam etmeyi açıkça kabul etti."""
        _log.warning("Kullanıcı geri yükleme noktası olmadan devam etmeyi kabul etti")
        self.accepted_without_restore_point = True

    @staticmethod
    def confirm_level(tweak):
        """0: onaysız, 1: dikkatli (açarken tek onay), 2: riskli (açarken ve kapatırken iki aşama)."""
        if "onay_seviyesi" in tweak:
            return tweak["onay_seviyesi"]
        return 1 if tweak.get("onay_gerekli") else 0

    def stored_related(self, change_id):
        """Katalog dışı değişikliğin bağlı olduğu ayar (onay ekranları için), ör. MSI -> GPU-018."""
        entry = self.store.get(change_id) or {}
        meta = next((e["meta"] for e in entry.get("adimlar", []) if "meta" in e), {})
        return meta.get("ilgili")

    def stored_confirm_level(self, tweak_id):
        """Yedek alınırken kaydedilen onay seviyesi (veri dosyası sonradan değişse de geçerli)."""
        entry = self.store.get(tweak_id)
        if entry is None:
            return 0
        meta = next((e["meta"] for e in entry["adimlar"] if "meta" in e), {})
        return meta.get("onay_seviyesi", 0)

    def _guard(self, tweak, enabling, confirmed):
        if tweak["sinif"] != "SWITCH" or tweak["id"] in FORBIDDEN_IDS:
            raise UserFacingError("hata.izin_yok")
        if not self.is_admin():
            raise UserFacingError("hata.yonetici_gerekli")
        level = self.confirm_level(tweak)
        if not confirmed and (level == 2 or (level == 1 and enabling)):
            raise UserFacingError("hata.onay_gerekli")
        if self.restore_point is None:
            raise UserFacingError("hata.hazirlik_gerekli")
        if not self.restore_point.ok and not self.accepted_without_restore_point:
            raise UserFacingError("hata.geri_yukleme_noktasi_yok")
        if enabling and tweak.get("geri_yukleme_zorunlu") and not self.restore_point.ok:
            raise UserFacingError("hata.geri_yukleme_zorunlu")

    # ------------------------------------------------------------------ değiştirme
    def _backup(self, tweak, steps, snaps):
        entries = [{"adim": step, "anlik": snap} for step, snap in zip(steps, snaps)]
        entries_meta = {"sonrasinda": tweak["islem"].get("sonrasinda", []),
                        "yeniden_baslatma_kodu": tweak["yeniden_baslatma_kodu"],
                        "onay_seviyesi": self.confirm_level(tweak)}
        if not self.store.has(tweak["id"]) and any(s.get("eylem") == "bcdedit" for s in steps):
            # Önyükleme değişikliğinden önce tüm BCD yedeklenir; yedek alınamazsa hiçbir şey yazılmaz.
            self.system.export_bcd(self.store.bcd_export_path(tweak["id"]))
        created = self.store.save_first(tweak["id"], tweak["ad"], entries + [{"meta": entries_meta}])
        if created:
            for i, step in enumerate(steps):
                if step["tur"] in REGISTRY_TYPES:
                    path = step.get("silinecek_yol") or step["yol"]
                    if self.system.get_key_exists(step["kok"], path):
                        self.system.export_reg_key(step["kok"], path, self.store.reg_export_path(tweak["id"], i))
        return created

    def _drop_unused_backup(self, tweak_id, created):
        """İşlem başarısız olup her şey geri alındıysa, bu işlemde açılan yedek
        kaydı silinir; aksi hâlde hiçbir şey değişmediği hâlde ayar
        'değiştirildi' görünür."""
        if created:
            self.store.remove(tweak_id)

    def _post_actions(self, actions):
        warnings, explorer = [], False
        for action in actions:
            try:
                if action == "fare_ayarlarini_yenile":
                    self.system.refresh_mouse()
                elif action == "klavye_ayarlarini_yenile":
                    self.system.refresh_keyboard()
                elif action == "ses_servisini_yeniden_baslat":
                    self.system.set_audio_service_restart()
                elif action == "gezgin_yeniden_baslat_oner":
                    explorer = True
            except Exception as exc:
                _log.warning("Sonrasında eylemi başarısız (%s): %s", action, exc)
                warnings.append(("uyari.sonrasinda", {"eylem": action}))
        return warnings, explorer

    def _write(self, steps, snaps, which, written):
        for step, snap in zip(steps, snaps):
            if handlers.state(step, snap) in (which, "yok"):
                continue  # zaten istenen durumda veya bu bilgisayarda yok
            written.append((step, snap))  # önce: yarıda kalan adım da geri alınmalı (sc config tamam, Stop-Service hata)
            handlers.apply(self.system, step, which, snap)

    def _fail(self, change_id, created, written):
        """İşlem yarıda kaldı: yazılan adımlar ters sırayla geri alınır. Yedek kaydı yalnızca HEPSİ geri alındıysa
        silinir; biri geri alınamadıysa sistemde değişiklik kalmıştır ve "Eski haline getir" için yedek gerekir."""
        if written:
            _log.error("Uygulama yarıda kaldı (%s); yazılan %d adım geri alınıyor", change_id, len(written))
        restored = True
        for step, snap in reversed(written):
            try:
                handlers.restore(self.system, step, snap)
            except Exception as exc:
                if not self._unchanged(step, snap):  # hiç değişmemiş adımın geri alınamaması sorun değil
                    restored = False
                    _log.error("Geri alma da başarısız (%s): %s", change_id, exc)
        if restored:
            self._drop_unused_backup(change_id, created)

    def _unchanged(self, step, snap):
        try:
            return handlers.snapshot(self.system, step) == snap
        except Exception:
            return False

    def set_enabled(self, tweak, on, confirmed=False):
        """Switch'i açar (on=True) veya kapatır. Kapatırken yedek varsa yedeğe döner."""
        if not on and self.store.has(tweak["id"]):
            if self.confirm_level(tweak) == 2 and not confirmed:
                return Result(False, "hata.onay_gerekli")
            return self.revert(tweak["id"], confirmed=True)
        action = "uygula" if on else "kapat"
        which = "acik" if on else "kapali"
        created, written = False, []
        try:
            self._guard(tweak, on, confirmed)
            if tweak["islem"]["kontrol"] != "switch":
                raise UserFacingError("hata.izin_yok")
            if on and tweak["islem"].get("yalnizca_kapat"):
                raise UserFacingError("hata.yalnizca_kapatilabilir")
            steps = self._steps(tweak)
            snaps = [handlers.snapshot(self.system, step) for step in steps]
            if all(handlers.state(s, n) in (which, "yok") for s, n in zip(steps, snaps)):
                return Result(True, "sonuc.zaten")
            _log.info("%s: %s (%s), %d adım", action, tweak["id"], tweak["ad"], len(steps))
            created = self._backup(tweak, steps, snaps)
            self._write(steps, snaps, which, written)
        except Exception as exc:
            key, params = friendly(exc)
            _log.error("%s başarısız (%s): %s", action, tweak["id"], exc)
            self._fail(tweak["id"], created, written)
            self.store.history(action, tweak["id"], False, str(exc))
            return Result(False, key, params)

        warnings, explorer = self._post_actions(tweak["islem"].get("sonrasinda", []))
        after = [handlers.state(s, handlers.snapshot(self.system, s)) for s in steps]
        if any(state not in (which, "yok") for state in after):
            warnings.append(("uyari.dogrulanamadi", {}))
        self.store.history(action, tweak["id"], True)
        return Result(True, "sonuc.uygulandi" if on else "sonuc.kapatildi",
                      restart=tweak["yeniden_baslatma_kodu"], explorer=explorer, warnings=warnings)

    def set_selection(self, tweak, values, confirmed=False):
        """Seçim ayarı: values = {alan_id: değer (metin)}."""
        created, written = False, []
        try:
            self._guard(tweak, True, confirmed)
            islem = tweak["islem"]
            if islem["kontrol"] != "secim":
                raise UserFacingError("hata.izin_yok")
            fields = {f["id"]: f for f in islem["alanlar"]}
            for field_id, value in values.items():
                field = fields.get(field_id)
                if field is None:
                    raise UserFacingError("hata.gecersiz_deger")
                allowed = ({o["deger"] for o in field["secenekler"]} if field.get("secenekler")
                           else {str(v) for v in range(field["aralik"]["min"], field["aralik"]["max"] + 1)})
                if str(value) not in allowed:
                    raise UserFacingError("hata.gecersiz_deger")
            pairs = [(fid, step) for fid, step in self._selection_steps(tweak) if fid in values]
            steps = [step for _, step in pairs]
            snaps = [handlers.snapshot(self.system, s) for s in steps]
            _log.info("Seçim: %s %s", tweak["id"], values)
            created = self._backup(tweak, steps, snaps)
            for (field_id, step), snap in zip(pairs, snaps):
                written.append((step, snap))
                handlers.write_value(self.system, step, str(values[field_id]))
        except Exception as exc:
            key, params = friendly(exc)
            _log.error("Seçim başarısız (%s): %s", tweak["id"], exc)
            self._fail(tweak["id"], created, written)
            self.store.history("secim", tweak["id"], False, str(exc))
            return Result(False, key, params)
        warnings, explorer = self._post_actions(tweak["islem"].get("sonrasinda", []))
        self.store.history("secim", tweak["id"], True, str(values))
        return Result(True, "sonuc.uygulandi", restart=tweak["yeniden_baslatma_kodu"],
                      explorer=explorer, warnings=warnings)

    def apply_custom(self, change_id, name, steps, values, level=0, restart="yok", confirmed=False, related=None,
                     after=()):
        """Katalog dışı değişiklik: başlangıç öğesi, servis, MSI, aygıt güç yönetimi,
        tek bir monitörün yenileme hızı.

        steps: somut adımlar; values: her adım için yazılacak değer (None = bu adıma
        yazma, yalnızca yedekle). İlk yedek `change_id` altında tutulur; böylece
        Değişiklikler sayfasında görünür ve "Eski haline getir" ile geri alınır.
        """
        created, written = False, []
        try:
            if not self.is_admin():
                raise UserFacingError("hata.yonetici_gerekli")
            if level == 2 and not confirmed:
                raise UserFacingError("hata.onay_gerekli")
            if self.restore_point is None:
                raise UserFacingError("hata.hazirlik_gerekli")
            if not self.restore_point.ok and not self.accepted_without_restore_point:
                raise UserFacingError("hata.geri_yukleme_noktasi_yok")
            snaps = [handlers.snapshot(self.system, s) for s in steps]
            entries = [{"adim": s, "anlik": n} for s, n in zip(steps, snaps)]
            meta = {"sonrasinda": list(after), "yeniden_baslatma_kodu": restart, "onay_seviyesi": level,
                    "ilgili": related}
            created = self.store.save_first(change_id, name, entries + [{"meta": meta}])
            if created:
                for i, step in enumerate(steps):
                    if step["tur"] in REGISTRY_TYPES and self.system.get_key_exists(step["kok"], step["yol"]):
                        self.system.export_reg_key(step["kok"], step["yol"], self.store.reg_export_path(change_id, i))
            _log.info("Özel değişiklik: %s (%s)", change_id, name)
            for step, snap, value in zip(steps, snaps, values):
                if value is None:
                    continue
                written.append((step, snap))
                handlers.write_value(self.system, step, value, snap)
        except Exception as exc:
            key, params = friendly(exc)
            _log.error("Özel değişiklik başarısız (%s): %s", change_id, exc)
            self._fail(change_id, created, written)
            self.store.history("ozel", change_id, False, str(exc))
            return Result(False, key, params)
        warnings, explorer = self._post_actions(after)
        self.store.history("ozel", change_id, True)
        return Result(True, "sonuc.uygulandi", restart=restart, explorer=explorer, warnings=warnings)

    def revert(self, tweak_id, confirmed=False):
        """Ayarı uygulamanın ilk değiştirdiği andaki hâline döndürür.

        Yalnızca yedek dosyasındaki bilgiyi kullanır; veri dosyası sonradan
        değişse veya ayar kaldırılsa bile geri alma çalışır. Geri yükleme
        noktası gerektirmez (eski hâle dönmek her zaman serbesttir).
        Riskli ayarlarda kapatırken de iki aşamalı onay gerekir (`confirmed`).
        """
        entry = self.store.get(tweak_id)
        if entry is None:
            return Result(False, "hata.yedek_yok")
        if not self.is_admin():
            return Result(False, "hata.yonetici_gerekli")
        steps = [e for e in entry["adimlar"] if "adim" in e]
        meta = next((e["meta"] for e in entry["adimlar"] if "meta" in e), {})
        if meta.get("onay_seviyesi") == 2 and not confirmed:
            return Result(False, "hata.onay_gerekli")
        _log.info("Geri al: %s (%s)", tweak_id, entry.get("ad"))
        failures = []
        for item in reversed(steps):
            try:
                # Yedek kullanıcı klasöründe durur ve geri alma yönetici olarak yazar: şemaya uymayan adım uygulanmaz.
                problems = validate_stored_step(item["adim"])
                if problems:
                    raise ValueError("yedekteki adım geçersiz: " + "; ".join(problems))
                handlers.restore(self.system, item["adim"], item["anlik"])
            except Exception as exc:
                _log.error("Geri alma adımı başarısız (%s): %s", tweak_id, exc)
                failures.append(friendly(exc))
        warnings, explorer = self._post_actions(meta.get("sonrasinda", []))
        if failures:
            self.store.history("geri_al", tweak_id, False, str(failures))
            return Result(False, "hata.geri_alma_kismen", {"adet": len(failures)}, warnings=warnings)
        self.store.remove(tweak_id)
        self.store.history("geri_al", tweak_id, True)
        return Result(True, "sonuc.geri_alindi", restart=meta.get("yeniden_baslatma_kodu"),
                      explorer=explorer, warnings=warnings)

    def revert_all(self):
        """Uygulamanın yaptığı tüm değişiklikleri en yeniden eskiye geri alır.
        (Arayüz bunun için tek, toplu bir onay alır.)"""
        return [(tweak_id, self.revert(tweak_id, confirmed=True)) for tweak_id in self.store.ids_newest_first()]

    def run_action(self, tweak, action_id):
        """Tek seferlik, GERİ ALINAMAZ eylem (ör. geçici dosyaları temizlemek).
        Değişiklik kaydına değil işlem geçmişine yazılır."""
        try:
            if tweak["sinif"] != "SWITCH" or tweak["islem"]["kontrol"] != "eylem" or tweak["id"] in FORBIDDEN_IDS:
                raise UserFacingError("hata.izin_yok")
            if not self.is_admin():
                raise UserFacingError("hata.yonetici_gerekli")
            action = next((a for a in tweak["islem"]["eylemler"] if a["id"] == action_id), None)
            if action is None:
                raise UserFacingError("hata.bilinmeyen_islem")
            windows = os.path.dirname(powershell.SYSTEM32)
            # TEMP'i HKCU\Environment belirler (yönetici gerekmez): yönetici olarak başka klasör silinmesin
            user_temp = os.environ.get("TEMP") or ""
            if os.path.basename(os.path.realpath(user_temp)).lower() != "temp":
                user_temp = None
            folders = {"gecici_dosyalari_temizle": [user_temp, os.path.join(windows, "Temp")],
                       "prefetch_temizle": [os.path.join(windows, "Prefetch")]}[action["eylem"]]
            count = size = 0
            for folder in folders:
                if folder and os.path.isdir(folder):
                    c, s = self.system.delete_temp_files(folder)
                    count, size = count + c, size + s
        except Exception as exc:
            key, params = friendly(exc)
            _log.error("Eylem başarısız (%s/%s): %s", tweak["id"], action_id, exc)
            self.store.history("eylem", tweak["id"], False, f"{action_id}: {exc}")
            return Result(False, key, params)
        self.store.history("eylem", tweak["id"], True, f"{action_id}: {count} dosya, {size} bayt")
        return Result(True, "sonuc.eylem", {"adet": count, "mb": round(size / 1024 ** 2, 1)})
