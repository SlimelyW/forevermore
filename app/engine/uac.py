"""Kullanıcı Hesabı Denetimi (UAC) seviyesi: Windows'un "Kullanıcı Hesabı Denetimi Ayarları" penceresindeki
dört kaydırıcı konumu.

Değerler HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System altındadır (Microsoft Learn:
"User Account Control settings and configuration"). Kaydırıcı yalnızca iki değeri değiştirir:
ConsentPromptBehaviorAdmin (2 = her zaman sor, 5 = yalnızca uygulamalar değişiklik yapınca, 0 = sormadan yükselt)
ve PromptOnSecureDesktop (1 = ekranı karart). EnableLUA'ya dokunulmaz: 0 yapmak UAC'yi tamamen kapatır,
Microsoft Store uygulamalarını bozar ve yeniden başlatma ister.
"""

PATH = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
CHANGE_ID = "UAC-SEVIYE"
NAMES = ("ConsentPromptBehaviorAdmin", "PromptOnSecureDesktop")
DEFAULTS = (5, 1)
LEVELS = ("her_zaman", "varsayilan", "karartmasiz", "hic")
VALUES = {"her_zaman": (2, 1), "varsayilan": (5, 1), "karartmasiz": (5, 0), "hic": (0, 0)}
RISK = {"her_zaman": "güvenli", "varsayilan": "güvenli", "karartmasiz": "dikkatli", "hic": "riskli"}


def steps():
    return [{"tur": "registry", "kok": "HKLM", "yol": PATH, "ad": name, "veri_turu": "REG_DWORD",
             "acik": None, "kapali": None, "yoksa": default} for name, default in zip(NAMES, DEFAULTS)]


def values(level):
    return list(VALUES[level])


def detect(system):
    """Şu anki seviye; UAC tamamen kapalıysa "kapali", kaydırıcıya uymayan değerlerde "ozel"."""
    lua = system.read_reg("HKLM", PATH, "EnableLUA")
    if lua is not None and lua[0] == 0:
        return "kapali"
    current = []
    for name, default in zip(NAMES, DEFAULTS):
        found = system.read_reg("HKLM", PATH, name)
        current.append(default if found is None else found[0])
    return next((level for level, pair in VALUES.items() if tuple(current) == pair), "ozel")
