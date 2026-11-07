"""Tek tuş Boost'un mantığı (arayüzsüz): kimler kapanacak, kapatma, ÖLÇÜLMÜŞ sonuç.

Kapatılacaklar iki kaynaktan gelir: bilinen arka plan kategorilerinden hazır, güvenli bir küme (DEFAULT_CATEGORIES)
ve kullanıcının kendi Boost listesi. Korumalı süreçler (closer.is_protected) hiçbir yoldan girmez. Tarayıcı, oyun
başlatıcıları (Steam/Epic), iletişim (Discord/Teams/Zoom) ve kayıt programları varsayılanda YOK: tarayıcıda kaydedilmemiş iş olabilir, başlatıcı oyunun
kendisi için gerekir, kayıt programı kullanıcı o anda kayıtta olabilir.

Bellek "temizleme" yoktur (çalışma kümesi küçültme, standby boşaltma: katalogda PLC-001, zararlı). Sonuçtaki "boşalan
bellek" yalnızca kapatmadan ÖNCE ve SONRA ölçülen boş fiziksel bellek farkıdır; o sırada başka programlar da bellek
kullanmış olabilir, bu yüzden tahmin değil ama kesin de değildir (arayüzde not olarak yazılır). Zorla sonlandırma bu
modülde yalnızca `force` ile ve arayüz kullanıcıdan ayrı onay aldıktan sonra çağrılır.
"""

import time

from app.engine import closer
from app.scan import hardware

# bilinen_surecler.json kategorileri: bulut eşitleme (OneDrive...), güncelleyiciler. İletişim (Discord, Teams, Zoom) YOK:
# oyuncu oyun sırasında sesli sohbette olabilir; isteyen Gelişmiş'te listeye ekler (Kubilay, TEST_FAZI A16-A17).
DEFAULT_CATEGORIES = ("bulut", "guncelleyici")


def targets(known_rows, listed_names=(), ops=None):
    """[{ad, adet, bellek_mb}] (ada göre sıralı): şu an çalışan, korumasız hedefler.
    known_rows: scan.software.collect_processes()["bilinen_arka_plan"]; listed_names: kullanıcının Boost listesi."""
    chosen = {}
    known = {row["ad"].lower(): {"ad": row["ad"], "adet": row["adet"], "bellek_mb": row["bellek_mb"]}
             for row in known_rows or [] if not closer.is_protected(row["ad"])}
    for row in known_rows or []:
        if row.get("kategori") in DEFAULT_CATEGORIES and row["ad"].lower() in known:
            chosen[row["ad"].lower()] = known[row["ad"].lower()]
    listed = list(listed_names or [])
    if listed:
        ops = ops or closer.WindowsOps()
        for name in closer.running(listed, ops):  # çalışmayan ve korumalı olanlar elenir
            # listeye eklenen bilinen program (ör. Discord) taramadaki adı/adedi/belleğiyle görünür
            chosen.setdefault(name.lower(), known.get(name.lower())
                              or {"ad": name, "adet": len(closer.pids_of(name, ops)), "bellek_mb": 0})
    return sorted(chosen.values(), key=lambda r: r["ad"].lower())


class Run:
    """Bir Boost çalıştırması: kurulumda önce-ölçüm alınır; close → (isteğe bağlı force) → result."""

    def __init__(self, names, ops=None, free=None, timeout=6.0):
        self.timeout = timeout
        self.ops = ops or closer.WindowsOps()
        self.free = free or hardware.free_mb
        self.names = [n for n in dict.fromkeys(names) if not closer.is_protected(n)]
        self.count_before = {n: len(closer.pids_of(n, self.ops)) for n in self.names}
        self.free_before = self.free()

    def close(self):
        """Nazikçe kapatma isteği; kapanmayan program adlarını döner (zorla sonlandırma YAPMAZ)."""
        results = closer.close_many(self.names, self.ops, self.timeout)
        return [name for name, result in results.items() if result == "calisiyor"]

    def force(self, names):
        """Yalnızca kullanıcının ayrı onayından sonra: sonlandırılan süreç sayısı."""
        return sum(closer.kill(name, self.ops) for name in names)

    def result(self, settle=1.5, sleep=time.sleep):
        """{kapanan: [ad], acik: [ad], surec: int, bosalan_mb: int | None}. bosalan_mb: önce/sonra boş bellek farkı;
        fark sıfır ya da negatifse None (uydurma sayı yok)."""
        sleep(settle)  # Windows kapanan sürecin belleğini hemen iade etmez
        left = {n: len(closer.pids_of(n, self.ops)) for n in self.names}
        closed = [n for n in self.names if self.count_before[n] and not left[n]]
        still_open = [n for n in self.names if left[n]]
        processes = sum(max(0, self.count_before[n] - left[n]) for n in self.names)
        gained = self.free() - self.free_before
        return {"kapanan": closed, "acik": still_open, "surec": processes, "bosalan_mb": gained if gained > 0 else None}
