"""Kullanıcı presetleri: ad + yalnızca bilinen ayar KİMLİKLERİ.

Preset değer, kayıt defteri yolu ya da komut TAŞIMAZ: dosyayı kim hazırlamış olursa olsun, içinden çıkabilecek tek
şey katalogdaki güvenli bir ayarın listede işaretlenmesidir. Uygulama her zamanki yoldan geçer (app.apply_profile:
geri yükleme noktası, onay pencereleri, yedek, geri alma); içe aktarılan preset hiçbir zaman kendiliğinden
uygulanmaz. Ayrıntı: docs/GUVENLIK.md "Preset içe aktarma".
"""

import json
import re
import secrets

from app.core import log, paths
from app.engine.schema import FORBIDDEN_IDS

_log = log.get("presets")

MARKER = "Forevermore preset"
VERSION = 1
MAX_PRESETS = 20
MAX_IDS = 100
MAX_BYTES = 64 * 1024
MAX_NAME = 40
REJECTED_REALITY = ("placebo", "zararlı")  # işe yaramayan ya da zararlı ayarlar preset'e girmez

_ID = re.compile(r"[A-Z]{2,6}-\d{3}")
_BAD_NAME_CHARS = re.compile(r"[\x00-\x1f\x7f\u202a-\u202e\u2066-\u2069<>]")  # denetim, yön değiştiren ve HTML karakterleri


class PresetError(Exception):
    """kod: gecersiz | buyuk | bos | cok_fazla | ad_bos"""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def usable(tweak):
    """Preset'e girebilen ayar: açma/kapama anahtarı, yasaklı değil, placebo/zararlı değil."""
    return (tweak["sinif"] == "SWITCH" and tweak["islem"]["kontrol"] == "switch" and tweak["id"] not in FORBIDDEN_IDS
            and tweak["gerceklik"]["durum"] not in REJECTED_REALITY)


def clean_name(name):
    name = _BAD_NAME_CHARS.sub("", str(name or ""))
    return re.sub(r"\s+", " ", name).strip()[:MAX_NAME].strip()


def clean_ids(ids, by_id):
    """(sırası korunmuş tekrarsız geçerli kimlikler, atılan sayısı). Liste değilse ya da çok büyükse hata."""
    if not isinstance(ids, list) or len(ids) > MAX_IDS * 5:
        raise PresetError("gecersiz")
    kept = []
    for item in ids:
        if isinstance(item, str) and _ID.fullmatch(item) and item in by_id and usable(by_id[item]) and item not in kept:
            kept.append(item)
    if len(kept) > MAX_IDS:
        raise PresetError("gecersiz")
    return kept, len(ids) - len(kept)


def _unique_name(name, taken):
    if name not in taken:
        return name
    n = 2
    while True:
        suffix = f" ({n})"
        candidate = name[:MAX_NAME - len(suffix)] + suffix
        if candidate not in taken:
            return candidate
        n += 1


class PresetStore:
    def __init__(self, path=None):
        self.path = path or (paths.user_data_dir() / "kullanici_presetleri.json")
        self.presets = []
        self.load_error = None
        self._load()

    def _load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            items = data["presetler"]
            ok = isinstance(items, list)
        except FileNotFoundError:
            return
        except (OSError, ValueError, KeyError, TypeError):
            ok = False
        if not ok:
            self.load_error = "bozuk"
            _log.warning("Preset dosyası okunamadı, boş liste kullanılıyor")
            return
        for item in items[:MAX_PRESETS]:
            if (isinstance(item, dict) and isinstance(item.get("id"), str) and isinstance(item.get("ayarlar"), list)
                    and clean_name(item.get("ad"))):
                self.presets.append({"id": item["id"], "ad": clean_name(item["ad"]),
                                     "ayarlar": [i for i in item["ayarlar"] if isinstance(i, str) and _ID.fullmatch(i)][:MAX_IDS]})

    def _save(self):
        paths.atomic_write(self.path, json.dumps({"surum": VERSION, "presetler": self.presets}, ensure_ascii=False, indent=2))

    def get(self, preset_id):
        return next((p for p in self.presets if p["id"] == preset_id), None)

    def add(self, name, ids, by_id):
        """Yeni preset; aynı ad varsa " (2)" eklenir. (preset, atılan sayısı)."""
        name = clean_name(name)
        if not name:
            raise PresetError("ad_bos")
        if len(self.presets) >= MAX_PRESETS:
            raise PresetError("cok_fazla")
        kept, dropped = clean_ids(ids, by_id)
        if not kept:
            raise PresetError("bos")
        preset = {"id": "kul-" + secrets.token_hex(4), "ad": _unique_name(name, {p["ad"] for p in self.presets}),
                  "ayarlar": kept}
        self.presets.append(preset)
        self._save()
        return preset, dropped

    def rename(self, preset_id, name):
        preset, name = self.get(preset_id), clean_name(name)
        if preset is None:
            raise PresetError("gecersiz")
        if not name:
            raise PresetError("ad_bos")
        preset["ad"] = _unique_name(name, {p["ad"] for p in self.presets if p is not preset})
        self._save()

    def remove(self, preset_id):
        self.presets = [p for p in self.presets if p["id"] != preset_id]
        self._save()

    def export_text(self, preset_id):
        preset = self.get(preset_id)
        if preset is None:
            raise PresetError("gecersiz")
        return json.dumps({"uygulama": MARKER, "surum": VERSION, "ad": preset["ad"], "ayarlar": preset["ayarlar"]},
                          ensure_ascii=False, indent=2)

    def import_bytes(self, raw, by_id):
        """Dosya içeriğinden preset ekler (uygulamaz). (preset, atılan sayısı). Güvenilmeyen girdi: boyut, tür ve
        kimlik denetimi; bilinmeyen/uygun olmayan kimlikler atılır."""
        if len(raw) > MAX_BYTES:
            raise PresetError("buyuk")
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError, RecursionError):
            raise PresetError("gecersiz") from None
        if (not isinstance(data, dict) or data.get("uygulama") != MARKER or data.get("surum") != VERSION
                or not isinstance(data.get("ad"), str)):
            raise PresetError("gecersiz")
        return self.add(data["ad"], data.get("ayarlar"), by_id)
