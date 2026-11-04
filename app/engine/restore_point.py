"""Sistem Geri Yükleme Noktası.

Bir oturumda ilk değişiklikten önce bir kez oluşturulur.

Bilinen Windows davranışları (dürüst not):
- Windows varsayılan olarak 24 saat içinde ikinci bir geri yükleme noktası
  oluşturmaz; Checkpoint-Computer hata vermeden yalnızca uyarı yazar. Bu durumda
  son 24 saatteki mevcut nokta kullanılır ve kullanıcıya tarihi gösterilir.
  Bu sınırı kaldırmak bir sistem ayarı değiştirmek demek olduğu için yapılmaz.
- "Sistem Koruması" C: sürücüsünde kapalıysa nokta oluşturulamaz. Uygulama
  bunu kendiliğinden açmaz; kullanıcıya nasıl açılacağı anlatılır ve yalnızca
  açık onayıyla geri yükleme noktası olmadan devam edilir (değerler yine de
  uygulamanın kendi yedeğine alınır).
"""

import datetime

from app.core import log

_log = log.get("restore_point")

DESCRIPTION = "Forevermore - degisiklik oncesi"


class RestorePointResult:
    CREATED = "olusturuldu"
    RECENT = "mevcut_24s"
    FAILED = "basarisiz"

    def __init__(self, status, when=None, detail=""):
        self.status = status
        self.when = when
        self.detail = detail

    @property
    def ok(self):
        return self.status in (self.CREATED, self.RECENT)

    def __repr__(self):
        return f"RestorePointResult({self.status!r}, {self.when!r})"


def _latest(points):
    times = []
    for p in points or []:
        try:
            times.append(datetime.datetime.fromisoformat(p["Zaman"]))
        except (KeyError, TypeError, ValueError):
            continue
    return max(times) if times else None


def ensure(system, now=None):
    now = now or datetime.datetime.now()
    before = system.list_restore_points()
    try:
        system.create_restore_point(DESCRIPTION)
    except Exception as exc:
        _log.error("Geri yükleme noktası oluşturulamadı: %s", exc)
        latest = _latest(before)
        if latest and now - latest < datetime.timedelta(hours=24):
            return RestorePointResult(RestorePointResult.RECENT, latest.isoformat(timespec="minutes"))
        return RestorePointResult(RestorePointResult.FAILED, detail=str(exc))

    after = system.list_restore_points()
    if after is not None and before is not None and len(after) > len(before):
        latest = _latest(after)
        _log.info("Geri yükleme noktası oluşturuldu")
        return RestorePointResult(RestorePointResult.CREATED, latest and latest.isoformat(timespec="minutes"))
    latest = _latest(after if after is not None else before)
    if latest and now - latest < datetime.timedelta(hours=24):
        _log.info("Son 24 saatte geri yükleme noktası zaten var: %s", latest)
        return RestorePointResult(RestorePointResult.RECENT, latest.isoformat(timespec="minutes"))
    _log.error("Geri yükleme noktası oluşturulamadı (liste değişmedi)")
    return RestorePointResult(RestorePointResult.FAILED, detail="liste_degismedi")
