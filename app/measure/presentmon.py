"""Oyun FPS ölçümü: Intel PresentMon (MIT lisansı, github.com/GameTechDev/PresentMon).

PresentMon uygulamaya kaynak olarak gömülmez; derlemede tools klasöründeki
PresentMon*.exe dosyası programın yanına kopyalanır (lisans metniyle birlikte).
Windows'un ETW kayıtlarından her karenin süresini okur; oyuna enjekte OLMAZ.

Yakalama SÜREÇ adına göredir (--process_name), ekran kartına veya ekranı süren karta göre DEĞİL:
hibrit laptopta oyun NVIDIA'da çizilip ekrana AMD/Intel üzerinden gönderilse de kareler sayılır.
Kıyas için dwm.exe de kaydedilir: dwm'den kare gelip oyundan gelmiyorsa yakalama çalışıyordur,
sorun süreçtedir; ikisinden de gelmiyorsa yakalama/sistem sorunudur.

Süreç adı eşleşmesi PresentMon'da büyük/küçük harf ve uzantı duyarsızdır (2.6.0 kaynak: CommandLine.cpp ve
OutputThread.cpp IsTargetProcess -> CanonicalizeProcessName: klasör ve uzantı atılır, küçük harfe çevrilir).

Akış: geri sayım (kullanıcı oyuna döner) -> PresentMon başlar -> seçilen süreç ön plandayken geçen
süre sayılır, değilse sayaç durur -> süre dolunca oturum kapatılır -> yalnızca ön plan aralıklarındaki
kareler kullanılır. Alt-tab'da PID değişirse exe adıyla yeni sürece bağlanılır.

Hesaplar (kare süreleri, ms; "MsBetweenPresents"):
- Ortalama FPS = 1000 / ortalama kare süresi
- %1 düşük FPS = en yavaş %1 karenin ortalama süresinden hesaplanan FPS
- %0,1 düşük FPS = en yavaş %0,1 karenin ortalama süresinden hesaplanan FPS
- Kare süresi p99 = karelerin %99'unun altında kaldığı süre
"""

import collections
import csv
import ctypes
import datetime
import glob
import os
import shutil
import subprocess
import tempfile
import time
from ctypes import wintypes

from app.core import log, paths, powershell

_log = log.get("measure")

MIN_FRAMES = 300  # bundan az kareyle sonuç anlamlı değil
SESSION = "ForevermoreOlcum"
COUNTDOWN_SN = 8
NOT_RUNNING_SN = 90  # süreç bu kadar sürede hiç açılmazsa beklemeyi bırak (yanlış süreç seçilmiş olabilir)
REFERENCE = "dwm.exe"
FRAME_COLUMNS = ("msbetweenpresents", "frametime")
TIME_COLUMNS = ("cpustartdatetime", "cpustarttime", "timeinseconds")


class MeasureError(Exception):
    """Ölçüm tamamlanamadı. code: az_kare / presentmon_kapandi / iptal; diag: ekranda ve logda gösterilen teşhis."""

    def __init__(self, code, diag=None):
        super().__init__(code)
        self.code, self.diag = code, diag or {}

    def __str__(self):
        return self.code


def find_presentmon():
    """Programın yanındaki veya tools klasöründeki PresentMon .exe dosyası."""
    for folder in (paths.app_dir(), paths.tools_dir()):
        found = sorted(glob.glob(str(folder / "PresentMon*.exe")), reverse=True)
        if found:
            return found[0]
    return None


def frame_stats(frame_times):
    """Kare sürelerinden (ms) istatistikler. En az MIN_FRAMES kare gerekir."""
    times = [t for t in frame_times if t and t > 0]
    if len(times) < MIN_FRAMES:
        raise ValueError("az_kare")
    ordered = sorted(times, reverse=True)  # en yavaş önce

    def low(fraction):
        count = max(1, int(len(ordered) * fraction))
        return round(1000 / (sum(ordered[:count]) / count), 1)

    mean = sum(times) / len(times)
    p99 = sorted(times)[min(len(times) - 1, int(len(times) * 0.99))]
    return {"fps_ort": round(1000 / mean, 1), "fps_1": low(0.01), "fps_01": low(0.001),
            "kare_suresi_ms": round(mean, 2), "kare_suresi_p99_ms": round(p99, 2)}, {"kare_sayisi": len(times)}


def _parse_time(text):
    """Zaman hücresi: sayı (oturum başından saniye/ms) veya tarih-saat. (tür, değer) ya da None."""
    text = (text or "").strip()
    try:
        return "sayi", float(text)
    except ValueError:
        pass
    head, _dot, frac = text.replace("T", " ").partition(".")
    try:
        moment = datetime.datetime.strptime(head, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    digits = "".join(ch for ch in frac if ch.isdigit())[:6].ljust(6, "0")
    return "tarih", moment + datetime.timedelta(microseconds=int(digits))


def read_rows(path):
    """PresentMon CSV'si -> [(uygulama küçük harf, pid, zaman (tür, değer) | None, kare süresi ms, sunum modu)].
    Sütun adları büyük/küçük harf duyarsız okunur: 2.x'in --v1_metrics çıktısı 'msBetweenPresents',
    varsayılan çıktısı 'MsBetweenPresents' yazar (ilk sürüm yalnızca birini arıyordu: her satır atlanıyordu)."""
    rows = []
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        header = [h.strip().lower() for h in next(reader, [])]
        index = {name: i for i, name in enumerate(header)}
        frame = next((index[c] for c in FRAME_COLUMNS if c in index), None)
        when = next((index[c] for c in TIME_COLUMNS if c in index), None)
        app, pid, mode = index.get("application"), index.get("processid"), index.get("presentmode")
        if frame is None or app is None:
            raise ValueError(f"PresentMon CSV sütunları tanınmadı: {header[:12]}")
        for row in reader:
            try:
                ms = float(row[frame])
            except (IndexError, ValueError):
                continue
            rows.append(((row[app] if app < len(row) else "").strip().lower(),
                         row[pid] if pid is not None and pid < len(row) else "",
                         _parse_time(row[when]) if when is not None and when < len(row) else None, ms,
                         row[mode].strip() if mode is not None and mode < len(row) else ""))
    return rows


def read_csv(path, process_name):
    """PresentMon CSV'sinden bir sürecin kare süreleri."""
    wanted = process_name.lower()
    return [row[3] for row in read_rows(path) if row[0] == wanted]


def to_epoch(rows, started, ended):
    """Satır zamanlarını Unix saniyesine çevirir (aynı sırada liste; okunamayanlar None).
    Sayı: oturum başından (started) saniye, oturum süresinden çok büyükse ms.
    Tarih: saat dilimine güvenilmez. PresentMon 2.6.0 bu bilgisayarda yerel saatten 3 saat ileri yazdı
    ("2026-10-30 4:04:10.46" / yerel 01:04:10); ilk kare oturum başına hizalanır ve fark 15 dakikanın
    katına yuvarlanır (saat dilimleri 15 dakikanın katıdır), saniye altı doğruluk korunur."""
    times = [r[2] for r in rows]
    numbers = [v[1] for v in times if v and v[0] == "sayi"]
    scale = 1000.0 if numbers and max(numbers) > (ended - started) * 2 + 10 else 1.0
    dates = [v[1].timestamp() for v in times if v and v[0] == "tarih"]
    shift = round((min(dates) - started) / 900) * 900 if dates else 0
    result = []
    for value in times:
        if value is None:
            result.append(None)
        elif value[0] == "sayi":
            result.append(started + value[1] / scale)
        else:
            result.append(value[1].timestamp() - shift)
    return result


class Desktop:
    """Gerçek Windows: süreçler, görünür pencereler ve ön plandaki pencerenin süreci (testlerde sahtesi)."""

    def __init__(self):
        from app.games.runtime import ProcessOps  # noqa: WPS433
        self.ops = ProcessOps()
        self.u = ctypes.WinDLL("user32", use_last_error=True)
        self.u.GetForegroundWindow.restype = wintypes.HWND
        self.u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.u.GetWindow.restype = wintypes.HWND
        self.u.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]

    def processes(self):
        return self.ops.list_processes()

    def _pid(self, hwnd):
        pid = wintypes.DWORD()
        self.u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value

    def foreground(self):
        hwnd = self.u.GetForegroundWindow()
        return self._pid(hwnd) if hwnd else 0

    def windows(self):
        """{pid: başlık} — görünür, sahipsiz, başlıklı, gizlenmemiş (cloaked) üst düzey pencereler."""
        found = {}
        callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        dwm = ctypes.WinDLL("dwmapi")

        def visit(hwnd, _):
            if not self.u.IsWindowVisible(hwnd) or self.u.GetWindow(hwnd, 4):  # 4: GW_OWNER
                return True
            cloaked = wintypes.DWORD()
            dwm.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked))  # 14: DWMWA_CLOAKED
            length = self.u.GetWindowTextLengthW(hwnd)
            if cloaked.value or not length:
                return True
            title = ctypes.create_unicode_buffer(length + 1)
            self.u.GetWindowTextW(hwnd, title, length + 1)
            found.setdefault(self._pid(hwnd), title.value)
            return True

        self.u.EnumWindows(callback(visit), 0)
        return found


def candidates(games, desktop=None):
    """Ölçülebilecek süreçler: [{exe, pid, baslik, oyun, on_planda, calisiyor}].
    Sıra: ön plandaki pencere, çalışan kayıtlı oyunlar, diğer pencereli süreçler, çalışmayan kayıtlı oyunlar.
    Bu uygulama ve korumalı sistem süreçleri (explorer, dwm...) listelenmez."""
    from app.engine import closer  # noqa: WPS433
    desktop = desktop or Desktop()
    names = {pid: exe for pid, exe in desktop.processes()}
    windows = desktop.windows()
    foreground = desktop.foreground()
    own = os.getpid()
    by_exe = {os.path.basename(g["exe"]).lower(): g["ad"] for g in games if g.get("exe")}
    items, seen = [], set()
    for pid, title in windows.items():
        exe = names.get(pid)
        if not exe or pid == own or closer.is_protected(exe) or exe in seen:
            continue
        seen.add(exe)
        items.append({"exe": exe, "pid": pid, "baslik": title, "oyun": by_exe.get(exe),
                      "on_planda": pid == foreground, "calisiyor": True})
    for exe, name in by_exe.items():
        if exe not in seen:
            running = next((pid for pid, e in names.items() if e == exe), None)
            items.append({"exe": exe, "pid": running, "baslik": "", "oyun": name, "on_planda": False,
                          "calisiyor": running is not None})
    rank = lambda i: (not i["on_planda"], not (i["oyun"] and i["calisiyor"]), not i["calisiyor"],  # noqa: E731
                      (i["oyun"] or i["baslik"] or i["exe"]).lower())
    return sorted(items, key=rank)


def _stop_session(exe, diag):
    """Aynı adla açık kalmış bir ETW oturumu varsa kapatır (önceki ölçüm çökerse kalabilir)."""
    try:
        proc = subprocess.run([exe, "--terminate_existing_session", "--session_name", SESSION], capture_output=True,
                              timeout=20, creationflags=powershell.CREATE_NO_WINDOW)
        diag["log"].append(f"oturum kapatma: kod {proc.returncode}")
    except (OSError, subprocess.TimeoutExpired) as exc:
        diag["log"].append(f"oturum kapatılamadı: {exc}")


def capture(process_name, seconds=60, exe=None, expected_sha256=None, countdown=COUNTDOWN_SN, progress=None,
            cancel=None, desktop=None, launch=None, sleep=time.sleep, clock=time.time):
    """Ölçer ve (istatistikler, ayrıntılar) döndürür; olmazsa MeasureError (diag ile).

    progress(aşama, bilgi): "geri_sayim" {kalan} / "olcum" {sayilan, toplam, on_planda, calisiyor, pid}.
    cancel(): True dönerse ölçüm durur. launch/desktop/sleep/clock testler içindir."""
    exe = exe or find_presentmon()
    if not exe:
        raise FileNotFoundError("presentmon_yok")
    if expected_sha256:  # kullanıcının onayladığı dosya çalıştırmadan önce değiştirilmiş olamaz
        from app.engine import driver_tools  # noqa: WPS433
        if driver_tools.sha256_file(exe) != expected_sha256:
            raise OSError("PresentMon onaydan sonra değişti")
    desktop = desktop or Desktop()
    progress = progress or (lambda *_a: None)
    cancel = cancel or (lambda: False)
    name = process_name.lower()
    diag = {"surec": name, "yontem": f"{os.path.basename(exe)} (ETW, süreç adına göre; kart filtresi yok)",
            "istenen_sn": seconds, "baslangic": datetime.datetime.now().isoformat(timespec="seconds"), "log": []}

    def note(text):
        diag["log"].append(f"{datetime.datetime.now():%H:%M:%S} {text}")
        _log.info("Ölçüm: %s", text)

    note(f"hedef {name}, {seconds} sn, geri sayım {countdown} sn, yöntem {diag['yontem']}")
    _stop_session(exe, diag)
    for left in range(countdown, 0, -1):
        if cancel():
            raise MeasureError("iptal", diag)
        progress("geri_sayim", {"kalan": left})
        sleep(1)

    folder = tempfile.mkdtemp(prefix="pcopt_pm_")
    output, console = os.path.join(folder, "olcum.csv"), os.path.join(folder, "presentmon.txt")
    args = [exe, "--process_name", name, "--process_name", REFERENCE, "--output_file", output,
            "--stop_existing_session", "--session_name", SESSION, "--no_console_stats", "--date_time"]
    with open(console, "wb") as out:
        launch = launch or (lambda a: subprocess.Popen(a, stdout=out, stderr=subprocess.STDOUT,
                                                         creationflags=powershell.CREATE_NO_WINDOW))
        proc = launch(args)
    started = clock()
    note("PresentMon başladı: " + " ".join(os.path.basename(a) if a == exe else a for a in args[1:]))
    intervals, open_since, counted, last_pids, last_fg, seen = [], None, 0.0, None, None, set()
    deadline = started + seconds * 3 + 120  # oyun hiç ön plana gelmezse sonsuza kadar beklenmez
    code = None
    tick = 0
    while True:
        now = clock()
        if proc.poll() is not None:
            code = "presentmon_kapandi"
            note(f"PresentMon erken kapandı (kod {proc.poll()})")
            break
        if tick % 4 == 0:  # süreç listesi saniyede bir (ucuz); ön plan her 250 ms
            pids = {pid for pid, e in desktop.processes() if e == name}
            if pids != last_pids:
                note(f"{name} PID: {sorted(pids) or 'çalışmıyor'}")
                last_pids = pids
                seen |= pids
        tick += 1
        fg_pid = desktop.foreground()
        fg = fg_pid in (last_pids or ())
        if fg != last_fg:
            if fg:
                note(f"ön planda (PID {fg_pid})")
            else:  # alt-tab'da hangi pencerenin öne geçtiği teşhiste işe yarar
                other = next((e for p, e in desktop.processes() if p == fg_pid), "?")
                note(f"ön planda değil: sayaç durdu (ön planda {other}, PID {fg_pid})")
            last_fg = fg
        if fg and open_since is None:
            open_since = now
        elif not fg and open_since is not None:
            intervals.append((open_since, now))
            open_since = None
        counted = sum(b - a for a, b in intervals) + (now - open_since if open_since is not None else 0)
        progress("olcum", {"sayilan": min(counted, seconds), "toplam": seconds, "on_planda": fg,
                           "calisiyor": bool(last_pids), "pid": min(last_pids) if last_pids else None})
        never = not seen and now - started > NOT_RUNNING_SN
        if counted >= seconds or now > deadline or never or cancel():
            if cancel():
                code = "iptal"
            elif never:
                note(f"{name} {NOT_RUNNING_SN} sn içinde hiç çalışmadı")
            elif counted < seconds:
                note("en uzun bekleme süresi doldu")
            break
        sleep(0.25)
    ended = clock()
    if open_since is not None:
        intervals.append((open_since, ended))
    _stop_session(exe, diag)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        note("PresentMon zorla kapatıldı")
    diag["on_plan_sn"] = round(sum(b - a for a, b in intervals), 1)
    diag["pidler"] = sorted(seen)
    diag["bitis"] = datetime.datetime.now().isoformat(timespec="seconds")
    try:
        with open(console, "rb") as f:
            raw = f.read()
        tail = raw.decode("utf-16-le" if b"\x00" in raw else "utf-8", errors="replace").strip()[-600:]
        if tail:
            diag["log"].append("PresentMon çıktısı: " + tail.lstrip("\ufeff"))
    except OSError:
        pass
    rows, csv_lines = [], 0
    if os.path.exists(output):
        try:
            with open(output, "rb") as f:
                csv_lines = max(0, sum(1 for _ in f) - 1)  # başlık hariç: dosyada kare satırı var mı
            rows = read_rows(output)
        except (OSError, ValueError) as exc:
            note(f"CSV okunamadı: {exc}")
    else:
        note("PresentMon çıktı dosyası oluşmadı")
    shutil.rmtree(folder, ignore_errors=True)  # kare listesi saklanmaz; yalnızca özet sonuç kaydedilir
    if code == "iptal":
        raise MeasureError("iptal", diag)
    epochs = to_epoch(rows, started, ended)
    target = [(when, row) for row, when in zip(rows, epochs) if row[0] == name]
    timed = all(when is not None for when, _row in target)
    inside = [row[3] for when, row in target if not timed or any(a <= when <= b for a, b in intervals)]
    modes = collections.Counter(row[4] for _when, row in target if row[4])
    diag.update(kare_csv_satir=csv_lines, kare_toplam=len(rows), kare_dwm=sum(1 for r in rows if r[0] == REFERENCE),
                kare_hedef=len(target), kare_on_planda=len(inside), kare_elenen_on_plan=len(target) - len(inside),
                kare_pid=dict(collections.Counter(row[1] for _when, row in target)), zaman_suzgeci=timed,
                sunum_modu=", ".join(f"{m} ({n})" for m, n in modes.most_common(3)),
                ozel_tam_ekran=any("legacy" in m.lower() for m in modes))  # Hardware: Legacy Flip = exclusive
    note(f"kareler: CSV satırı {csv_lines}, okunan {len(rows)}, dwm {diag['kare_dwm']}, hedef {len(target)} "
         f"(PID'e göre {diag['kare_pid']}), ön planda {len(inside)}, ön plan süzgeciyle elenen "
         f"{diag['kare_elenen_on_plan']}, sunum modu {diag['sunum_modu'] or '—'}"
         + ("" if timed else " (zaman sütunu okunamadı: ön plan süzgeci uygulanmadı)"))
    # istenen sürenin %90'ı ön planda geçmediyse (bekleme süresi doldu) sonuç kısa ve yanıltıcı: kaydedilmez
    if code is None and (len(inside) < MIN_FRAMES or diag["on_plan_sn"] < seconds * 0.9):
        code = "az_kare"
    if code:
        # 0 satır = yakalama sorunu; satır var ama okunamadı = ayrıştırma sorunu (eski sürümde sütun adı hatası buydu)
        diag["neden"] = ("ayristirma" if csv_lines and not rows else "yakalama" if not rows else
                         "surec" if not target else "on_plan")
        raise MeasureError(code, diag)
    stats, details = frame_stats(inside)
    details.update(sure_sn=diag["on_plan_sn"], surec=name, yontem=diag["yontem"])
    return stats, details


def diagnosis_text(diag):
    """Logu kopyala için düz metin."""
    keys = ("surec", "pidler", "yontem", "baslangic", "bitis", "istenen_sn", "on_plan_sn", "kare_csv_satir",
            "kare_toplam", "kare_dwm", "kare_hedef", "kare_pid", "kare_on_planda", "kare_elenen_on_plan",
            "zaman_suzgeci", "sunum_modu", "ozel_tam_ekran", "neden")
    lines = [f"{k}: {diag[k]}" for k in keys if k in diag]
    return "\n".join(lines + [""] + diag.get("log", []))
