"""Başka bir programın daha önce uyguladığı zararlı/placebo ayarı "Windows varsayılanına döndür".

Düğme yalnızca Windows varsayılanı KESİN bilinen ayarlarda çıkar (PLC-018, PLC-021). Diğer tespitlerde
arayüz tek satır elle düzeltme yönergesi gösterir (lang: ui.varsayilan.elle.<kimlik>); güvenilir yazma yolu
olmayan ayara (sayfa dosyası) uygulama yazmaz. Toplu düzeltme yoktur.
Her döndürme motorun apply_custom yolundan geçer: yedek, Değişiklikler kaydı, tek tıkla geri alma.
"""

PREFIX = "VARSAYILAN-"
CSRSS_PERF = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\csrss.exe\PerfOptions"
# IFEO PerfOptions'ın belgeli değerleri. Başka değer ya da alt anahtar varsa düğme yok:
# yedek yalnızca tanıdığımız değerleri geri getirebilir.
PERF_VALUES = {"cpupriorityclass", "iopriority", "pagepriority"}
# PLC-018: Windows'ta csrss.exe için PerfOptions anahtarı hiç yoktur.
# PLC-021: wuauserv Windows'ta "El ile (tetikleyiciyle başlar)". Kubilay onayı (7 Kasım): servis yöneticisinde
# korumalı (kilitli) olsa da yalnızca Devre dışı → El ile geri dönüşü yazılır; başka değer/servis/ilke yok.
SUPPORTED = ("PLC-018", "PLC-021")
MANUAL = ("PLC-008", "PLC-020")  # yalnızca elle yönerge


def change_id(tweak_id):
    return PREFIX + tweak_id


def plan(system, tweak_id):
    """{'adimlar', 'degerler', 'onizleme': (dil anahtarı, parametreler)} veya None (kesin varsayılan yok ya da
    beklenmeyen içerik). Yalnızca okur."""
    if tweak_id == "PLC-021":
        return _update_service(system)
    if tweak_id != "PLC-018" or not system.get_key_exists("HKLM", CSRSS_PERF):
        return None
    names, children = system.list_reg("HKLM", CSRSS_PERF)
    if children or any(n.lower() not in PERF_VALUES for n in names):
        return None
    steps, found = [], []
    for name in names:
        current = system.read_reg("HKLM", CSRSS_PERF, name)
        if current is None or current[1] not in ("REG_DWORD", "REG_SZ"):
            return None
        found.append((name, current[0]))
        # değer None: yazılmaz, yalnızca yedeklenir (geri almada geri gelir)
        steps.append({"tur": "registry", "kok": "HKLM", "yol": CSRSS_PERF, "ad": name, "veri_turu": current[1],
                      "acik": None, "kapali": None, "yoksa": None})
    steps.append({"tur": "registry_anahtar", "kok": "HKLM", "yol": CSRSS_PERF, "silinecek_yol": CSRSS_PERF,
                  "acik": "var", "kapali": "yok"})
    shown = ", ".join(f"{name} = {value}" for name, value in found) or "-"
    return {"adimlar": steps, "degerler": [None] * len(found) + ["kapali"],
            "onizleme": ("ui.varsayilan.onizleme", {"yol": "HKLM\\" + CSRSS_PERF, "degerler": shown})}


def _update_service(system):
    """Yalnızca wuauserv Devre dışı ise: başlangıç türü El ile; servis başlatılmaz, durdurulmaz (calisiyor None)."""
    info = system.get_service("wuauserv")
    if info is None or info["baslangic"] != "Disabled":
        return None
    step = {"tur": "servis", "ad": "wuauserv"}  # anlık görüntü eski başlangıç türünü saklar (geri alma)
    return {"adimlar": [step], "degerler": [{"baslangic": "Manual", "calisiyor": None}],
            "onizleme": ("ui.varsayilan.onizleme_servis", {})}
