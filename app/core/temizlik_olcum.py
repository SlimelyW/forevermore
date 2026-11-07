"""Haftalık temizlik BOYUT ölçümü (varsayılan KAPALI).

Görev Zamanlayıcı'da yönetici OLMAYAN (RunLevel Limited), haftada bir çalışan bir görev oluşturur. Görev uygulamayı
`--temizlik-olc` ile açar: pencere yok, hiçbir şey taşınmaz/silinmez, yalnızca temizleyicilerin toplam boyutu hesaplanıp
kullanıcı klasörüne küçük bir dosyaya (tarih, toplam bayt, öğe sayısı; yol yok) yazılır. Temizlik sayfası bunu "Son ölçüm"
olarak gösterir. Bildirim/açılır pencere yok. Taşıma her zaman kullanıcının onayıyla, Temizlik sayfasından yapılır.
"""

import datetime
import json
import sys

from app.core import log, paths, powershell

_log = log.get("temizlik_olcum")

TASK_NAME = "Forevermore - temizlik olcumu"
FILE_NAME = "temizlik_olcum.json"


def _command():
    if getattr(sys, "frozen", False):
        return sys.executable, "--temizlik-olc"
    return sys.executable, "-m app --temizlik-olc"


def is_enabled():
    return bool(powershell.run_json(
        f"Get-ScheduledTask -TaskName {powershell.quote(TASK_NAME)} -ErrorAction SilentlyContinue | Select-Object TaskName"))


def enable():
    exe, args = _command()
    _log.info("Haftalık temizlik ölçümü açılıyor")
    powershell.run(
        f"Unregister-ScheduledTask -TaskName {powershell.quote(TASK_NAME)} -Confirm:$false -ErrorAction SilentlyContinue; "
        f"$a = New-ScheduledTaskAction -Execute {powershell.quote(exe)} -Argument {powershell.quote(args)} "
        f"-WorkingDirectory {powershell.quote(str(paths.app_dir()))}; "
        "$t = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 20:00; "
        "$p = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited; "
        "$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries "
        "-ExecutionTimeLimit (New-TimeSpan -Minutes 5); "
        f"Register-ScheduledTask -TaskName {powershell.quote(TASK_NAME)} -Action $a -Trigger $t -Principal $p "
        "-Settings $s -Force | Out-Null", timeout=60)


def disable():
    _log.info("Haftalık temizlik ölçümü kapatılıyor")
    powershell.run(f"Unregister-ScheduledTask -TaskName {powershell.quote(TASK_NAME)} -Confirm:$false "
                   "-ErrorAction SilentlyContinue", timeout=60)


def measure_and_save(path=None, scan=None, now=None):
    """Salt okunur ölçüm. Çalışan program bilgisi gerekmez (boş süreç listesi). Sonuç: yazılan sözlük."""
    from app.engine import cleaners  # noqa: WPS433 (çekirdek katman motoru yalnızca burada kullanır)
    found = (scan or (lambda: cleaners.scan(processes=lambda: [])))()
    snapshot = {"tarih": (now or datetime.datetime.now()).isoformat(timespec="minutes"),
                "boyut": sum(f["boyut"] for f in found), "adet": sum(f["adet"] for f in found)}
    paths.atomic_write(path or paths.user_data_dir() / FILE_NAME, json.dumps(snapshot))
    return snapshot


def last(path=None):
    """Son ölçüm ({"tarih", "boyut", "adet"}) ya da None (hiç yok / bozuk)."""
    try:
        data = json.loads((path or paths.user_data_dir() / FILE_NAME).read_text(encoding="utf-8"))
        datetime.datetime.fromisoformat(data["tarih"])
        if isinstance(data["boyut"], int) and isinstance(data["adet"], int):
            return {"tarih": data["tarih"], "boyut": data["boyut"], "adet": data["adet"]}
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None
