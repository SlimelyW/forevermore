"""Önce / Sonra ölçümü: sistem ölçümleri, oyun FPS ölçümü (PresentMon), saklama ve karşılaştırma.

DÜRÜSTLÜK: Tek ölçüm kanıt değildir. Aynı koşullarda (aynı sahne, aynı arka plan
uygulamaları, bilgisayar soğukken veya ısınmışken aynı) birkaç kez ölçüp ortalamaya
bakılmalıdır. Arayüz bunu her ölçümde hatırlatır.

Sonuçlar yalnızca bu bilgisayarda saklanır: %LOCALAPPDATA%\\Forevermore\\olcumler.json
"""

import datetime
import json
import uuid

from app.core import log, paths

_log = log.get("measure")

# metrik -> (daha düşük mü iyi, birim)
METRICS = {
    "acilis_sn": (True, "sn"),
    "baslangic_uygulama": (True, ""),
    "baslangic_gorev": (True, ""),
    "otomatik_servis": (True, ""),
    "calisan_servis": (True, ""),
    "bosta_cpu": (True, "%"),
    "bosta_ram_gb": (True, "GB"),
    "surec_sayisi": (True, ""),
    "uyku_1ms": (True, "ms"),
    "fps_ort": (False, "FPS"),
    "fps_1": (False, "FPS"),
    "fps_01": (False, "FPS"),
    "kare_suresi_ms": (True, "ms"),
    "kare_suresi_p99_ms": (True, "ms"),
}
SYSTEM_METRICS = ("acilis_sn", "baslangic_uygulama", "baslangic_gorev", "otomatik_servis", "calisan_servis",
                  "bosta_cpu", "bosta_ram_gb", "surec_sayisi", "uyku_1ms")
GAME_METRICS = ("fps_ort", "fps_1", "fps_01", "kare_suresi_ms", "kare_suresi_p99_ms")


class MeasurementStore:
    def __init__(self, path=None):
        self.path = path or (paths.user_data_dir() / "olcumler.json")
        try:
            items = json.loads(self.path.read_text(encoding="utf-8")).get("olcumler", [])
            self.items = [m for m in items if isinstance(m, dict)]
        except (OSError, ValueError, AttributeError, TypeError):  # null / [] / bozuk şekil: boş liste
            self.items = []

    def save(self):
        try:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"olcumler": self.items}, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.path)
        except OSError as exc:
            _log.warning("Ölçümler kaydedilemedi: %s", exc)

    def add(self, kind, label, values, details=None, note=""):
        item = {"id": uuid.uuid4().hex[:10], "zaman": datetime.datetime.now().isoformat(timespec="seconds"),
                "tur": kind, "etiket": label, "not": note, "degerler": values, "ayrinti": details or {}}
        self.items.insert(0, item)
        self.save()
        return item

    def remove(self, item_id):
        self.items = [m for m in self.items if m["id"] != item_id]
        self.save()

    def get(self, item_id):
        return next((m for m in self.items if m["id"] == item_id), None)


def compare(before, after):
    """[(metrik, önce, sonra, fark, yüzde, iyileşti_mi)] — yalnızca iki ölçümde de olan metrikler."""
    rows = []
    for metric, (lower_better, _unit) in METRICS.items():
        a, b = before["degerler"].get(metric), after["degerler"].get(metric)
        if a is None or b is None:
            continue
        diff = b - a
        pct = (diff / a * 100) if a else None
        better = None if abs(diff) < 1e-9 else (diff < 0) == lower_better
        rows.append((metric, a, b, diff, pct, better))
    return rows
