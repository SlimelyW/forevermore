"""Windows'la başlatma (varsayılan KAPALI).

Uygulama yönetici izniyle çalıştığı için Run anahtarı her oturum açılışında UAC
penceresi çıkarırdı. Bunun yerine oturum açılışında "en yüksek yetkiyle" çalışan bir
zamanlanmış görev oluşturulur (Görev Zamanlayıcı'da görünür, oradan da silinebilir).
Görev uygulamayı `--tepside` ile başlatır: pencere açılmaz, simge tepside durur.

Kullanıcı adı uygulama tarafından okunmaz; PowerShell'e $env:USERNAME olarak
Windows'un kendisi verir.
"""

import sys

from app.core import log, paths, powershell

_log = log.get("autostart")

TASK_NAME = "Forevermore - oturum acilisi"
# Uygulamanın eski adıyla (PC Optimizer) oluşturulmuş görev: varsa tanınır ve silinir.
LEGACY_TASK_NAMES = ("PC Optimizer - oturum acilisi",)


class ProfileFolderError(Exception):
    """Program kullanıcı profilinde: en yüksek yetkiyle başlayan görev UAC sorusuz yönetici yetkisi verirdi."""


def _command():
    if getattr(sys, "frozen", False):
        return sys.executable, "--tepside"
    return sys.executable, "-m app --tepside"


def _all_names():
    return ", ".join(powershell.quote(name) for name in (TASK_NAME, *LEGACY_TASK_NAMES))


def is_enabled():
    rows = powershell.run_json(
        f"Get-ScheduledTask -TaskName {_all_names()} -ErrorAction SilentlyContinue | Select-Object TaskName")
    return bool(rows)


def enable():
    exe, args = _command()
    # Profildeki exe'yi (İndirilenler, Masaüstü) yönetici olmayan bir program değiştirebilir; görev onu oturum
    # açılışında sorusuz yönetici olarak çalıştırırdı.
    if any(paths.in_user_profile(p) for p in (paths.app_dir(), exe)):
        raise ProfileFolderError(str(paths.app_dir()))
    _log.info("Windows'la başlatma açılıyor")
    powershell.run(
        f"Unregister-ScheduledTask -TaskName {_all_names()} -Confirm:$false -ErrorAction SilentlyContinue; "
        f"$a = New-ScheduledTaskAction -Execute {powershell.quote(exe)} -Argument {powershell.quote(args)} "
        f"-WorkingDirectory {powershell.quote(str(paths.app_dir()))}; "
        "$t = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME; "
        "$p = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest; "
        "$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries "
        "-ExecutionTimeLimit ([TimeSpan]::Zero); "
        f"Register-ScheduledTask -TaskName {powershell.quote(TASK_NAME)} -Action $a -Trigger $t -Principal $p "
        "-Settings $s -Force | Out-Null", timeout=60)


def disable():
    _log.info("Windows'la başlatma kapatılıyor")
    powershell.run(f"Unregister-ScheduledTask -TaskName {_all_names()} -Confirm:$false -ErrorAction SilentlyContinue",
                   timeout=60)
