"""Yedek deposu.

Bir ayar uygulama tarafından ilk kez değiştirilmeden ÖNCE, dokunulacak her
değerin o anki hâli %ProgramData%\\Forevermore\\<SID>\\backups\\yedekler.json
dosyasına yazılır (paths: yalnızca Yöneticiler/SYSTEM yazabilir). "Eski haline getir" bu ilk hâle döner; aynı ayar birkaç
kez açılıp kapatılsa bile ilk yedek korunur.

Dosya her yazımda önce geçici dosyaya yazılıp sonra yerine konur; yazma
sırasında elektrik kesilse bile eski yedek bozulmaz.

Dosya, bu Windows kullanıcısına bağlı (DPAPI) bir anahtarla HMAC-SHA256 ile imzalanır; değiştirilmiş bir dosya
yüklenmez, `yedekler.bozuk.json` olarak kenara alınır ve `tampered` işaretlenir (arayüz uyarır). Dosya okunabiliyorsa
içeriği `recoverable`da tutulur: kullanıcı "Yedekleri kurtar" (recover) veya "Sıfırla ve devam et" (dismiss_broken)
seçer; uygulama hiçbir durumda kilitlenmez. Ani kapanmada en olası neden anahtar dosyasının yarım kalmasıdır
(eskiden atomik yazılmıyordu): bozuk anahtar kenara alınıp yenisi oluşturulur. Sınır: aynı
hesapta çalışan bir program anahtarı da okuyabilir; bu önlem rastgele/dikkatsiz değişikliği yakalar. Asıl koruma,
geri almadan önce adımların şemadan geçirilmesidir (engine.revert).

Ayrıca registry anahtarları ilk değişiklikten önce .reg dosyası olarak
backups\\reg klasörüne aktarılır (uygulama açılamazsa elle geri yükleme için).

Salt okunur depo (`readonly`, yönetici izni yokken) klasöre hiç yazmaz: korumalı klasöre zaten yazamaz.
"""

import datetime
import hashlib
import hmac
import json
import os
import secrets
import threading

from app.core import dpapi, log, paths

_log = log.get("backup")


class BackupStore:
    def __init__(self, folder=None, readonly=False):
        self.folder = folder or paths.backups_dir()
        self.readonly = readonly
        if not readonly:
            self.folder.mkdir(parents=True, exist_ok=True)
        self.path = self.folder / "yedekler.json"
        self.history_path = self.folder / "islem_gecmisi.jsonl"
        self.key_path = self.folder / paths.BACKUP_KEY
        self._lock = threading.Lock()
        self.tampered = False   # dosya imzası tutmadı / anahtar okunamadı: yedekler yüklenmedi
        self.recoverable = None  # yüklenmeyen ama okunabilen yedek verisi (kullanıcı onayıyla kurtarılır)
        self._data = self._load()

    def _key(self, create):
        """İmza anahtarı: DPAPI ile saklanan 32 rastgele bayt. create ise yoksa oluşturulur; okunamazsa None."""
        try:
            if self.key_path.exists():
                return dpapi.unprotect(self.key_path.read_bytes())
        except OSError as exc:
            _log.error("Yedek imza anahtarı okunamadı: %s", exc)
            if not create:
                return None
            self._set_aside(self.key_path)  # yarım/bozuk anahtar: kenara alınır, yenisiyle devam edilir
        if not create:
            return None
        key = secrets.token_bytes(32)
        try:
            paths.atomic_write(self.key_path, dpapi.protect(key))
        except OSError as exc:
            _log.error("Yedek imza anahtarı yazılamadı: %s", exc)
            return None
        return key

    @staticmethod
    def _mac(key, data):
        body = json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hmac.new(key, body, hashlib.sha256).hexdigest()

    @staticmethod
    def _set_aside(path):
        """Dosyayı silmeden yanına alır (önceki bozuk kopyanın üzerine yazmaz)."""
        broken = path.with_name(f"{path.stem}.bozuk{path.suffix}")
        if broken.exists():
            broken = path.with_name(f"{path.stem}.bozuk_{datetime.datetime.now():%Y%m%d_%H%M%S}{path.suffix}")
        try:
            os.replace(path, broken)
        except OSError:
            pass
        return broken

    def _quarantine(self, reason, readable=None):
        # Dosyayı silme; yanına al ki elle kurtarılabilsin.
        if not self.readonly:
            broken = self._set_aside(self.path)
            _log.error("Yedek dosyası yüklenmedi (%s); %s olarak saklandı", reason, broken.name)
        if isinstance(readable, dict):
            self.recoverable = readable

    def _load(self):
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            self._quarantine(exc)
            return {}
        if isinstance(raw, dict) and raw.get("surum") == 2:
            key = self._key(create=False)
            if key is None or not hmac.compare_digest(str(raw.get("hmac", "")), self._mac(key, raw.get("veri"))):
                self.tampered = True
                self._quarantine("anahtar okunamadı" if key is None else "imza tutmadı", raw.get("veri"))
                return {}
            return raw["veri"]
        if self.key_path.exists():  # anahtar varken imzasız dosya olmamalı (imza silinmiş olabilir)
            self.tampered = True
            self._quarantine("imza yok", raw)
            return {}
        self._data = raw  # eski (imzasız) sürüm: bir kez kabul edilip imzalanır
        self._save()
        return raw

    def _save(self, data=None):
        """data diske yazıldıktan SONRA bellekteki kayıt olur: yazılamazsa bellek de değişmez (Denetim A B2)."""
        data = self._data if data is None else data
        if not self.readonly:
            key = self._key(create=True)
            # anahtar yoksa imzasız (eski biçim) yazılır; sonraki açılışta eski sürüm gibi ele alınır
            document = {"surum": 2, "veri": data, "hmac": self._mac(key, data)} if key else data
            paths.atomic_write(self.path, json.dumps(document, ensure_ascii=False, indent=2))
        self._data = data

    def recover(self):
        """Kullanıcı onayıyla imzası doğrulanamayan yedekleri yükler ve yeniden imzalar. Güvenlik: geri alma her
        adımı yine şemadan geçirir (engine.revert); biçimi bozuk kayıtlar alınmaz. Kurtarılan kayıt sayısını döndürür."""
        with self._lock:
            entries = {k: v for k, v in (self.recoverable or {}).items()
                       if isinstance(v, dict) and isinstance(v.get("adimlar"), list) and isinstance(v.get("zaman"), str)
                       and k not in self._data}
            self._data.update(entries)
            self.recoverable, self.tampered = None, False
            self._save()
        _log.warning("Kullanıcı onayıyla %d yedek kaydı kurtarıldı", len(entries))
        return len(entries)

    def dismiss_broken(self):
        """'Sıfırla ve devam et': bozuk dosya kenarda kalır, uyarı kapanır."""
        self.recoverable, self.tampered = None, False
        _log.warning("Kullanıcı bozuk yedek dosyasını kurtarmadan devam etti")

    def has(self, tweak_id):
        return tweak_id in self._data

    def get(self, tweak_id):
        return self._data.get(tweak_id)

    def save_first(self, tweak_id, name, entries):
        """İlk yedeği kaydeder; zaten varsa dokunmaz. entries: [{"adim":..., "anlik":...}]."""
        with self._lock:
            if tweak_id in self._data:
                return False
            self._save({**self._data, tweak_id: {
                "ad": name,
                "zaman": datetime.datetime.now().isoformat(timespec="seconds"),
                "adimlar": entries,
            }})
            _log.info("Yedek alındı: %s (%d adım)", tweak_id, len(entries))
            return True

    def stamp_rev(self, tweak_id, rev, entries=()):
        """Kayda hangi katalog sürümüyle uygulandığını yazar. entries: yedekte henüz olmayan yeni adımlar
        ({"adim","anlik"}); eklenir ki geri alma onları da kapsasın. Kayıt yoksa bir şey yapmaz."""
        with self._lock:
            if tweak_id not in self._data:
                return
            entry = dict(self._data[tweak_id])  # kopya: diske yazılamazsa bellekteki kayıt değişmesin
            have = [e["adim"] for e in entry["adimlar"] if "adim" in e]
            new = [e for e in entries if e["adim"] not in have]
            if new:
                meta = [e for e in entry["adimlar"] if "meta" in e]
                entry["adimlar"] = [e for e in entry["adimlar"] if "meta" not in e] + new + meta
            entry["rev"] = rev
            self._save({**self._data, tweak_id: entry})

    def remove(self, tweak_id):
        with self._lock:
            if tweak_id in self._data:
                self._save({k: v for k, v in self._data.items() if k != tweak_id})

    def ids_newest_first(self):
        with self._lock:  # işçi iş parçacığı aynı anda kayıt ekleyebilir (Denetim A O5)
            return sorted(self._data, key=lambda k: self._data[k]["zaman"], reverse=True)

    def history(self, action, tweak_id, success, detail=""):
        record = {"zaman": datetime.datetime.now().isoformat(timespec="seconds"),
                  "islem": action, "id": tweak_id, "basarili": success, "ayrinti": detail}
        if self.readonly:
            return
        try:  # geçmiş yalnızca bilgi: yazılamaması işlemi başarısız göstermesin (Denetim A B3)
            with self._lock, open(self.history_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as exc:
            _log.warning("İşlem geçmişi yazılamadı: %s", exc)

    def read_history(self, action=None, limit=20):
        """İşlem geçmişinden en yeni kayıtlar (ör. geri alınamaz eylemler için action="eylem")."""
        try:
            lines = self.history_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        records = []
        for line in reversed(lines):
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if action is None or record.get("islem") == action:
                records.append(record)
                if len(records) >= limit:
                    break
        return records

    def bcd_export_path(self, tweak_id):
        folder = self.folder / "bcd"
        folder.mkdir(exist_ok=True)
        return folder / f"{tweak_id}_{datetime.datetime.now():%Y%m%d_%H%M%S}.bcd"

    def reg_export_path(self, tweak_id, index):
        folder = self.folder / "reg"
        folder.mkdir(exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        return folder / f"{tweak_id}_{index}_{stamp}.reg"
