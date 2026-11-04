"""Teknik hataları kullanıcıya anlaşılır Türkçe mesaj anahtarına çevirir.

Teknik ayrıntı her zaman log dosyasına yazılır; kullanıcıya yalnızca ne
olduğu ve ne yapabileceği gösterilir. Metinler lang/tr.json "hata.*".
"""

import subprocess

from app.core import powershell
from app.engine.handlers import UserFacingError
from app.engine.system import SystemError_


def friendly(exc):
    """(mesaj_anahtarı, parametreler)"""
    if isinstance(exc, UserFacingError):
        return exc.key, exc.params
    if isinstance(exc, PermissionError):
        return "hata.yetki", {}
    if isinstance(exc, FileNotFoundError):
        return "hata.bulunamadi", {}
    if isinstance(exc, (subprocess.TimeoutExpired,)) or "Zaman aşımı" in str(exc):
        return "hata.zaman_asimi", {}
    if isinstance(exc, (powershell.PowerShellError, SystemError_)):
        return "hata.sistem", {}
    return "hata.beklenmeyen", {}
