"""Temizleyiciler: bilinen önbellek/döküm klasörlerini SİLMEZ, yedek klasörüne TAŞIR (geri yüklenebilir).

GÜVENLİK:
- Yollar yalnızca bu dosyadaki katalogdan gelir (kullanıcıdan ya da dosyadan yol alınmaz); arayüz yalnızca kimlik gönderir
  ve taşınacak öğeler her seferinde yeniden taranır.
- Her öğe, katalogdaki kök klasörün DOĞRUDAN çocuğudur (özyineleme yok), gerçek yolu kökün içinde kalmalı; sembolik bağ ve
  birleşim noktası (reparse point) olan öğeler atlanır.
- Programı çalışan temizleyici atlanır (program kendiliğinden kapatılmaz); kilitli dosya zorlanmaz, hata olarak raporlanır.
- Taşıma ve geri yükleme uninstaller.remove_leftovers / restore ile yapılır (korumalı yedek klasörü, manifest, ACL sıfırlama).
Ayrıntı: docs/GUVENLIK.md "Temizleyiciler".
"""

import fnmatch
import os
import time
from pathlib import Path

from app.engine import uninstaller

REPARSE_POINT = 0x400  # FILE_ATTRIBUTE_REPARSE_POINT

# id -> (ortam değişkeni, kökten klasör yolu, ad kalıpları, çalışırsa temizlenmeyecek süreçler, en az kaç günlük [0: süzgeç yok])
# eski_log: yalnızca kullanıcının Temp kökündeki eski .log/.etl DOSYALARI (Windows günlükleri ve Olay Günlüğü değil).
# son_belgeler: yalnızca Recent kökündeki .lnk KISAYOLLARI (belgelerin kendisi ve görev çubuğu sabitleri
# [AutomaticDestinations/CustomDestinations] kalıp dışı).
CLEANERS = {
    "discord": ("APPDATA", ("discord",), ("Cache", "Code Cache", "GPUCache"), ("discord.exe",), 0),
    "steam": ("LOCALAPPDATA", ("Steam",), ("htmlcache",), ("steam.exe", "steamwebhelper.exe"), 0),
    "kucuk_resim": ("LOCALAPPDATA", ("Microsoft", "Windows", "Explorer"), ("thumbcache_*.db",), (), 0),
    "cokme_dokumu": ("LOCALAPPDATA", ("CrashDumps",), ("*.dmp",), (), 0),
    "eski_log": ("LOCALAPPDATA", ("Temp",), ("*.log", "*.etl"), (), 14),
    "son_belgeler": ("APPDATA", ("Microsoft", "Windows", "Recent"), ("*.lnk",), (), 0),
}
OWN_PREFIX = "forevermore"  # kendi dosyalarımız hiçbir temizleyiciye girmez


def _running(processes):
    return {exe.lower() for _pid, exe in (processes() if processes else _default_processes())}


def _default_processes():
    from app.games.runtime import ProcessOps  # noqa: WPS433 (yalnızca gerçek Windows'ta)
    return ProcessOps().list_processes()


def _safe_child(path, root):
    """path kökün doğrudan çocuğu mu, gerçek yolu kök içinde mi, bağlantı/birleşim noktası değil mi?"""
    try:
        attributes = os.lstat(path).st_file_attributes
    except (OSError, AttributeError):  # durum okunamadı: güvenli sayılmaz
        return False
    if os.path.islink(path) or attributes & REPARSE_POINT:
        return False
    real_root, real = os.path.realpath(root).lower(), os.path.realpath(path).lower()
    return os.path.dirname(real) == real_root


def _old_enough(path, min_days, now_ts):
    """Süzgeç yoksa True. Süzgeç varsa yalnızca DOSYA ve son değişikliği en az min_days gün önce olmalı (okunamazsa hayır)."""
    if not min_days:
        return True
    try:
        return path.is_file() and (now_ts or time.time()) - os.stat(path).st_mtime >= min_days * 86400
    except OSError:
        return False


def _items(cleaner_id, env, now_ts=None):
    var, parts, patterns, _procs, min_days = CLEANERS[cleaner_id]
    if not env.get(var):
        return []
    root = Path(env[var]).joinpath(*parts)
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return []
    found = []
    for name in names:
        if name.lower().startswith(OWN_PREFIX):
            continue
        if any(fnmatch.fnmatch(name.lower(), pattern.lower()) for pattern in patterns):
            path = root / name
            if _safe_child(path, root) and _old_enough(path, min_days, now_ts):
                size = os.path.getsize(path) if path.is_file() else uninstaller._size(path)  # noqa: SLF001
                found.append({"tur": "klasor", "yol": str(path), "boyut": size})
    return found


def scan(env=None, processes=None):
    """[{"id", "boyut", "adet", "calisiyor"}] her temizleyici için (boş olanın boyutu 0). Salt okunur: hiçbir şey değişmez."""
    env = os.environ if env is None else env
    running = _running(processes)
    result = []
    for cleaner_id, spec in CLEANERS.items():
        items = _items(cleaner_id, env)
        result.append({"id": cleaner_id, "boyut": sum(i["boyut"] for i in items), "adet": len(items),
                       "calisiyor": any(p in running for p in spec[3])})
    return result


def clean(ids, name, env=None, processes=None, base=None, ops=None, now=None):
    """Seçilen temizleyicilerin öğelerini yedek klasörüne taşır. Bilinmeyen kimlik yok sayılır; programı çalışan atlanır.
    {"oturum", "kaldirilan", "basarisiz", "atlanan": [kimlikler], "boyut"}"""
    env = os.environ if env is None else env
    running = _running(processes)
    items, skipped = [], []
    for cleaner_id in dict.fromkeys(ids):
        if cleaner_id not in CLEANERS:
            continue
        if any(p in running for p in CLEANERS[cleaner_id][3]):
            skipped.append(cleaner_id)
            continue
        items += _items(cleaner_id, env)
    if not items:
        return {"oturum": None, "kaldirilan": 0, "basarisiz": [], "atlanan": skipped, "boyut": 0}
    result = uninstaller.remove_leftovers(name, [{"tur": i["tur"], "yol": i["yol"], "boyut": i["boyut"]} for i in items],
                                          base, ops, now, tur="temizlik")
    failed = {f["yol"] for f in result["basarisiz"]}
    return dict(result, atlanan=skipped, boyut=sum(i["boyut"] for i in items if i["yol"] not in failed))
