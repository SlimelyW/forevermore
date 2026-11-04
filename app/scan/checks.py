"""Daha önce uygulanmış zararlı/placebo ayarların tespiti (BİLGİ kartlarındaki
`tespit` alanı). Yalnızca okur; hiçbir şeyi düzeltmez."""

import functools
import re
import subprocess

from app.core import log, powershell, registry

_log = log.get("checks")

SERVICE_START = {"Automatic": 2, "Manual": 3, "Disabled": 4}


@functools.lru_cache(maxsize=None)
def _bcd_elements():
    """Etkin önyükleme girdisindeki öğeler {ad: değer} (küçük harf). Yönetici izni gerekir; yoksa None.

    bcdedit çıktısında başlıklar Windows diline göre çevrilir ama öğe adları
    (numproc, useplatformclock...) İngilizce kalır.
    """
    try:
        proc = subprocess.run(["bcdedit", "/enum", "{current}"], capture_output=True, timeout=15,
                              creationflags=powershell.CREATE_NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    text = proc.stdout.decode("mbcs", errors="replace")
    return {m.group(1).lower(): m.group(2).strip().lower()
            for m in re.finditer(r"^([A-Za-z]+)\s+(.*)$", text, re.MULTILINE)}


# msconfig > Önyükleme > Gelişmiş seçenekler'in diğer kutuları: uygulama değiştirmez, uyarır.
BOOT_OPTIONS = {"usefirmwarepcisettings": "pci_kilidi", "debug": "hata_ayiklama", "bootdebug": "hata_ayiklama"}


def boot_warnings():
    """Açık olan diğer önyükleme seçenekleri (ör. PCI kilidi, hata ayıklama). Okunamazsa None."""
    elements = _bcd_elements()
    if elements is None:
        return None
    return sorted({key for name, key in BOOT_OPTIONS.items() if elements.get(name) == "yes"})


def clear_cache():
    """Çözümden sonra yeniden okumak için (bcdedit sonucu önbellekte kalmasın)."""
    _bcd_elements.cache_clear()


def _builtin(check, scan):
    name, params = check["kontrol"], check.get("parametreler", {})
    if name == "bcdedit_deger_var":
        elements = _bcd_elements()
        if elements is None:
            return None
        return any(v.lower() in elements for v in params["degerler"])
    if name == "sayfa_dosyasi_yok":
        vm = (scan.get("depolama") or {}).get("sanal_bellek")
        if vm is None:
            return None
        return not vm.get("otomatik") and not vm.get("dosyalar")
    if name == "tcp_otomatik_ayar_kapali":
        level = ((scan.get("ag") or {}).get("tcp") or {}).get("otomatik_ayar")
        return None if level is None else level.lower() == "disabled"
    if name == "defender_gercek_zamanli_kapali":
        sec = scan.get("guvenlik") or {}
        if sec.get("defender_gercek_zamanli") is None:
            return None
        return sec["defender_gercek_zamanli"] is False and not sec.get("diger_antivirusler")
    return None


def _compare(value, op, expected):
    if value is None:
        return False
    if op == "esit":
        return value == expected
    if op == "esit_degil":
        return value != expected
    if op == "kucuk":
        return isinstance(value, int) and value < expected
    if op == "icinde":
        return value in expected
    return False


def _check(check, scan):
    kind = check["tur"]
    if kind == "registry":
        value = registry.read(check["kok"], check["yol"], check["ad"])
        return _compare(value, check["karsilastir"], check["deger"])
    if kind == "registry_anahtar_var":
        return registry.key_exists(check["kok"], check["yol"])
    if kind == "servis":
        start = registry.read("HKLM", rf"SYSTEM\CurrentControlSet\Services\{check['ad']}", "Start")
        return start == SERVICE_START[check["baslangic"]]
    if kind == "yerlesik":
        return _builtin(check, scan)
    return None


def evaluate(tweaks, scan):
    """Tespit edilen sorunlu ayarların listesi: [{id, ad, mesaj, durum}]."""
    found = []
    for tweak in tweaks:
        tespit = tweak.get("tespit")
        if not tespit:
            continue
        results = []
        for check in tespit["herhangi"]:
            try:
                results.append(_check(check, scan))
            except Exception as exc:  # tek kontrol hatası taramayı durdurmasın
                _log.warning("Tespit kontrolü hatası (%s): %s", tweak["id"], exc)
                results.append(None)
        if any(r is True for r in results):
            found.append({"id": tweak["id"], "ad": tweak["ad"], "mesaj": tespit["mesaj"],
                          "durum": tweak["gerceklik"]["durum"]})
    return found
