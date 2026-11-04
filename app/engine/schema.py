"""`islem` şemasının doğrulayıcısı.

Hem dönüştürücü (tools/convert_tweaks.py) hem de uygulama açılırken ayar
motoru bu doğrulamayı kullanır. Hatalı tanımlanmış bir ayar uygulamada
gösterilmez; böylece veri dosyasındaki bir yazım hatası bilgisayara yanlış
değer yazılmasına yol açmaz.

Şemanın Türkçe açıklaması: docs/islem_semasi.md
"""

import re

from app.engine.resolvers import CONDITIONS, RESOLVERS, find_placeholders

GUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

REGISTRY_ROOTS = {"HKCU", "HKLM"}
REGISTRY_TYPES = {"REG_DWORD", "REG_SZ"}
SERVICE_START_TYPES = {"Disabled", "Manual", "Automatic", "AutomaticDelayed"}
CONTROL_TYPES = {"switch", "secim", "eylem"}

# Bu beş ayar ASLA uygulamadan yapılamaz; veri dosyası değiştirilse bile kod
# reddeder (Windows Defender'ı kapatma, Windows Update'i kalıcı kapatma,
# sayfa dosyasını kapatma, Realtime öncelik, agresif debloat).
FORBIDDEN_IDS = frozenset({"PLC-008", "PLC-018", "PLC-020", "PLC-021", "PLC-022"})

# Hesaplanan değerler: veri dosyası sabit sayı yerine bunlardan birini isteyebilir.
COMPUTED_VALUES = {"toplam_ram_kb"}
# Yalnızca kapatılabilen ayarlarda "açık" sayılma koşulu.
STATE_CONDITIONS = {"var", "kucuk"}
POST_ACTIONS = {
    "fare_ayarlarini_yenile",
    "klavye_ayarlarini_yenile",
    "gezgin_yeniden_baslat_oner",
    "ses_servisini_yeniden_baslat",
}
# Yerleşik eylemler: kodun içinde tanımlı, veri dosyasından keyfi komut
# çalıştırılamaz. Her eylemin beklediği parametreler.
BUILTIN_ACTIONS = {
    "hazirda_bekletme": set(),
    "bellek_sikistirma": set(),
    "windows_ozelligi": {"ozellikler"},
    "ag_gelismis_ozellik": {"bagdastirici", "anahtar"},
    "bcdedit": {"eleman"},
    "tcp_otomatik_ayar": set(),
    "wlan_otomatik_yapilandirma": set(),
    "zamanlanmis_gorev": {"yol", "ad"},
    "pnp_cihaz": {"donanim_kimligi"},
    "nihai_performans_plani": set(),
    "dns": {"bagdastirici"},
    "ekran_yenileme": {"aygit"},
    "ekran_modu": {"aygit", "monitor"},
    "ekran_olcek": {"aygit", "monitor"},
    "ekran_yon": {"aygit", "monitor"},
    "ekran_konum": {"aygit", "monitor"},
    "gorsel_efekt": {"ad"},
    "guc_modu": {"kaynak"},
    "nvidia_drs": {"ayar"},
    "amd_adlx": {"gpu", "ozellik"},
    "ekran_olcekleme": {"aygit", "monitor"},
    "aygit_etkin": {"ornek"},
    "defender_gercek_zamanli": set(),
}
# Tek seferlik, geri alınamaz eylemler (kontrol: "eylem").
ONE_SHOT_ACTIONS = {"gecici_dosyalari_temizle", "prefetch_temizle"}
BCD_ELEMENT_RE = re.compile(r"^[a-z]+$")
BUILTIN_CHECKS = {
    "bcdedit_deger_var",
    "sayfa_dosyasi_yok",
    "tcp_otomatik_ayar_kapali",
    "defender_gercek_zamanli_kapali",
}
OPENER_TYPES = {"ms-settings", "uri", "program", "denetim_masasi"}
# "Ayarı aç" düğmesinin çalıştırabileceği programlar (beyaz liste).
ALLOWED_PROGRAMS = {
    "SystemPropertiesPerformance.exe",
    "devmgmt.msc",
    "powercfg.cpl",
    "main.cpl",
    "msconfig.exe",
    "UserAccountControlSettings.exe",
}
ALLOWED_CONTROL_PANEL = {"mmsys.cpl", "keyboard", "printers"}
ALLOWED_URI_PREFIXES = ("windowsdefender://",)
FORM_VALUES = {"goster", "uyar", "gizle"}
COMPARE_OPS = {"esit", "esit_degil", "kucuk", "icinde"}


def _check_registry_value(value, reg_type, where, errors, allow_none=True):
    if value is None:
        if not allow_none:
            errors.append(f"{where}: değer boş olamaz")
        return
    if reg_type == "REG_DWORD" and not (isinstance(value, int) and 0 <= value <= 0xFFFFFFFF):
        errors.append(f"{where}: REG_DWORD için 0..4294967295 arası tam sayı gerekir, gelen {value!r}")
    if reg_type == "REG_SZ" and not isinstance(value, str):
        errors.append(f"{where}: REG_SZ için metin gerekir, gelen {value!r}")


def _check_registry_location(step, where, errors):
    if step.get("kok") not in REGISTRY_ROOTS:
        errors.append(f"{where}: 'kok' HKCU veya HKLM olmalı")
    path = step.get("yol")
    if not isinstance(path, str) or not path or path.startswith(("HK", "\\")) or ":" in path:
        errors.append(f"{where}: 'yol' kök olmadan yazılmalı (ör. 'Software\\\\Microsoft\\\\...')")


def validate_stored_step(step):
    """Yedekteki (kullanıcı klasöründe duran) bir adımın konumu/parametreleri geri almadan önce denetlenir.
    shortcut: yalnızca kayıt defteri konumu ve şemada tanımlı yerleşik eylemlerin parametre kümesi bakılır;
    yönetici kartlarının (servis, başlangıç, ses...) kendi adım biçimleri bu şemada yok, onlara güvence HMAC'tir."""
    errors = []
    kind = step.get("tur")
    if kind in ("registry", "registry_bayrak"):
        _check_registry_location(step, "yedek", errors)
    elif kind == "yerlesik" and step.get("eylem") in BUILTIN_ACTIONS:
        if set(step.get("parametreler", {})) != BUILTIN_ACTIONS[step["eylem"]]:
            errors.append(f"yedek: '{step['eylem']}' parametreleri uymuyor")
    return errors


def validate_step(step, where, for_selection=False, off_only=False):
    """Tek bir adımı doğrular. `for_selection` ise acik/kapali beklenmez.
    `off_only` (yalnızca kapatılabilen ayar) ise 'acik' yerine 'acik_kosulu' kullanılabilir."""
    errors = []
    kind = step.get("tur")

    if kind == "registry":
        _check_registry_location(step, where, errors)
        if not step.get("ad"):
            errors.append(f"{where}: 'ad' gerekli")
        reg_type = step.get("veri_turu")
        if reg_type not in REGISTRY_TYPES:
            errors.append(f"{where}: 'veri_turu' {sorted(REGISTRY_TYPES)} olmalı")
        if not for_selection:
            for key in ("acik", "kapali", "yoksa"):
                if key not in step:
                    errors.append(f"{where}: '{key}' alanı yazılmalı (boşsa null)")
            on = step.get("acik")
            condition = step.get("acik_kosulu")
            if condition is not None:
                if not off_only:
                    errors.append(f"{where}: 'acik_kosulu' yalnızca 'yalnizca_kapat' ayarlarda kullanılabilir")
                if not (condition == "var" or (isinstance(condition, dict) and set(condition) == {"kucuk"}
                                                and isinstance(condition["kucuk"], int))):
                    errors.append(f"{where}: 'acik_kosulu' \"var\" veya {{\"kucuk\": sayı}} olmalı")
            elif isinstance(on, dict):
                if set(on) != {"hesapla"} or on["hesapla"] not in COMPUTED_VALUES or reg_type != "REG_DWORD":
                    errors.append(f"{where}: hesaplanan değer {sorted(COMPUTED_VALUES)} (REG_DWORD) olmalı")
            else:
                _check_registry_value(on, reg_type, where + ".acik", errors, allow_none=False)
            _check_registry_value(step.get("kapali"), reg_type, where + ".kapali", errors)
            if on is not None and on == step.get("kapali"):
                errors.append(f"{where}: açık ve kapalı değer aynı")
        _check_registry_value(step.get("yoksa"), reg_type, where + ".yoksa", errors)

    elif kind == "registry_bayrak":
        _check_registry_location(step, where, errors)
        for key in ("ad", "anahtar", "acik", "kapali"):
            if not isinstance(step.get(key), str) or step.get(key) == "":
                errors.append(f"{where}: '{key}' metin olmalı")
        if ";" in step.get("anahtar", "") or "=" in step.get("anahtar", ""):
            errors.append(f"{where}: 'anahtar' ';' veya '=' içeremez")

    elif kind == "registry_bit":
        _check_registry_location(step, where, errors)
        mask = step.get("maske")
        if not isinstance(mask, int) or mask <= 0:
            errors.append(f"{where}: 'maske' pozitif tam sayı olmalı")
        else:
            for key in ("acik", "kapali"):
                if step.get(key) not in (0, mask):
                    errors.append(f"{where}: '{key}' 0 veya maske ({mask}) olmalı")
        if step.get("veri_turu") not in REGISTRY_TYPES:
            errors.append(f"{where}: 'veri_turu' {sorted(REGISTRY_TYPES)} olmalı")

    elif kind == "registry_anahtar":
        _check_registry_location(step, where, errors)
        delete_path = step.get("silinecek_yol", "")
        if not step.get("yol", "").startswith(delete_path) or not delete_path:
            errors.append(f"{where}: 'silinecek_yol', 'yol'un üst anahtarı olmalı")
        if delete_path.count("\\") < 2:
            errors.append(f"{where}: 'silinecek_yol' çok üst seviyede; güvenlik için reddedildi")
        if step.get("acik") != "var" or step.get("kapali") != "yok":
            errors.append(f"{where}: registry_anahtar için acik='var', kapali='yok' olmalı")

    elif kind == "servis":
        if not re.fullmatch(r"[A-Za-z0-9_.]+", step.get("ad", "")):
            errors.append(f"{where}: servis adı geçersiz")
        for key in ("acik", "kapali"):
            state = step.get(key)
            if not isinstance(state, dict):
                errors.append(f"{where}: '{key}' sözlük olmalı")
                continue
            if state.get("baslangic") not in SERVICE_START_TYPES:
                errors.append(f"{where}.{key}: 'baslangic' {sorted(SERVICE_START_TYPES)} olmalı")
            if state.get("calisiyor") not in (True, False, None):
                errors.append(f"{where}.{key}: 'calisiyor' true/false/null olmalı (null = dokunma)")

    elif kind == "powercfg":
        for key in ("alt_grup", "ayar"):
            if not GUID_RE.match(str(step.get(key, ""))):
                errors.append(f"{where}: '{key}' GUID olmalı")
        if not isinstance(step.get("acik"), int):
            errors.append(f"{where}: 'acik' tam sayı olmalı")
        off = step.get("kapali")
        if not (isinstance(off, int) or off == "plan_varsayilani"):
            errors.append(f"{where}: 'kapali' tam sayı veya 'plan_varsayilani' olmalı")

    elif kind == "guc_plani":
        for key in ("acik", "kapali"):
            if not GUID_RE.match(str(step.get(key, ""))):
                errors.append(f"{where}: '{key}' GUID olmalı")

    elif kind == "yerlesik":
        action = step.get("eylem")
        if action not in BUILTIN_ACTIONS:
            errors.append(f"{where}: bilinmeyen yerleşik eylem {action!r}")
        else:
            params = set(step.get("parametreler", {}))
            if params != BUILTIN_ACTIONS[action]:
                errors.append(f"{where}: '{action}' parametreleri {sorted(BUILTIN_ACTIONS[action])} olmalı, gelen {sorted(params)}")
            if action == "bcdedit" and not BCD_ELEMENT_RE.match(str(step["parametreler"].get("eleman", ""))):
                errors.append(f"{where}: bcdedit 'eleman' yalnızca küçük harf olmalı")
        if not for_selection:
            if "acik" not in step or "kapali" not in step:
                errors.append(f"{where}: 'acik' ve 'kapali' alanları yazılmalı")
            elif step.get("acik") == step.get("kapali") and not off_only:
                errors.append(f"{where}: 'acik' ve 'kapali' farklı değerler olmalı")

    else:
        errors.append(f"{where}: bilinmeyen adım türü {kind!r}")
    return errors


def validate_islem(islem, where="islem"):
    errors = []
    control = islem.get("kontrol")
    if control not in CONTROL_TYPES:
        return [f"{where}: 'kontrol' {sorted(CONTROL_TYPES)} olmalı"]

    off_only = bool(islem.get("yalnizca_kapat"))
    if off_only and control != "switch":
        errors.append(f"{where}: 'yalnizca_kapat' yalnızca switch'lerde kullanılabilir")
    if control == "switch":
        steps = islem.get("adimlar")
        if not isinstance(steps, list) or not steps:
            errors.append(f"{where}: switch için en az bir adım gerekir")
            steps = []
        for i, step in enumerate(steps):
            errors += validate_step(step, f"{where}.adimlar[{i}]", off_only=off_only)
    elif control == "eylem":
        actions = islem.get("eylemler")
        if not isinstance(actions, list) or not actions:
            errors.append(f"{where}: eylem için en az bir eylem gerekir")
            actions = []
        for i, action in enumerate(actions):
            if action.get("eylem") not in ONE_SHOT_ACTIONS:
                errors.append(f"{where}.eylemler[{i}]: bilinmeyen eylem {action.get('eylem')!r}")
            if not action.get("id") or not action.get("etiket"):
                errors.append(f"{where}.eylemler[{i}]: 'id' ve 'etiket' gerekli")
    else:
        fields = islem.get("alanlar")
        if not isinstance(fields, list) or not fields:
            errors.append(f"{where}: secim için en az bir alan gerekir")
            fields = []
        for i, field in enumerate(fields):
            fw = f"{where}.alanlar[{i}]"
            step = field.get("adim", {})
            if step.get("tur") not in ("registry", "yerlesik") or (
                    step.get("tur") == "yerlesik" and step.get("eylem") != "dns"):
                errors.append(f"{fw}: secim alanları registry veya yerleşik 'dns' olmalı")
            errors += validate_step(step, fw + ".adim", for_selection=True)
            options, rng = field.get("secenekler"), field.get("aralik")
            if bool(options) == bool(rng):
                errors.append(f"{fw}: 'secenekler' veya 'aralik' alanlarından tam olarak biri olmalı")
            allowed = None
            if options:
                allowed = {o["deger"] for o in options}
            elif rng:
                if not (isinstance(rng.get("min"), int) and isinstance(rng.get("max"), int) and rng["min"] < rng["max"]):
                    errors.append(f"{fw}: 'aralik' min < max tam sayılar olmalı")
                else:
                    allowed = {str(v) for v in range(rng["min"], rng["max"] + 1)}
            if allowed is not None and field.get("onerilen") not in allowed:
                errors.append(f"{fw}: 'onerilen' izin verilen değerlerden biri olmalı")

    for action in islem.get("sonrasinda", []):
        if action not in POST_ACTIONS:
            errors.append(f"{where}: bilinmeyen 'sonrasinda' eylemi {action!r}")

    resolver = islem.get("cozumleyici")
    if resolver and resolver.get("ad") not in RESOLVERS:
        errors.append(f"{where}: bilinmeyen çözümleyici {resolver.get('ad')!r}")
    if find_placeholders(islem) and not resolver:
        errors.append(f"{where}: yer tutucu var ama 'cozumleyici' tanımlı değil")
    return errors


def validate_conditions(conditions, where):
    errors = []
    for i, cond in enumerate(conditions or []):
        if cond.get("ad") not in CONDITIONS:
            errors.append(f"{where}[{i}]: bilinmeyen koşul {cond.get('ad')!r}")
    return errors


def validate_uyumluluk(uyum, where="uyumluluk"):
    errors = []
    form = uyum.get("form", {})
    for key in ("masaustu", "laptop"):
        if form.get(key) not in FORM_VALUES:
            errors.append(f"{where}.form.{key}: {sorted(FORM_VALUES)} olmalı")
    gpu = uyum.get("gpu")
    if gpu is not None and not (isinstance(gpu, list) and set(gpu) <= {"NVIDIA", "AMD", "Intel"}):
        errors.append(f"{where}.gpu: null veya NVIDIA/AMD/Intel listesi olmalı")
    win = uyum.get("windows", {})
    if not set(win.get("surumler", [])) or not set(win.get("surumler", [])) <= {"10", "11"}:
        errors.append(f"{where}.windows.surumler: '10' ve/veya '11' olmalı")
    errors += validate_conditions(uyum.get("kosullar"), where + ".kosullar")
    return errors


def validate_opener(opener, where="rehber.ac"):
    kind, target = opener.get("tur"), opener.get("hedef", "")
    if kind not in OPENER_TYPES:
        return [f"{where}: bilinmeyen tür {kind!r}"]
    if kind == "ms-settings" and not target.startswith("ms-settings:"):
        return [f"{where}: hedef 'ms-settings:' ile başlamalı"]
    if kind == "uri" and not target.startswith(ALLOWED_URI_PREFIXES):
        return [f"{where}: izin verilmeyen adres {target!r}"]
    if kind == "program" and target not in ALLOWED_PROGRAMS:
        return [f"{where}: beyaz listede olmayan program {target!r}"]
    if kind == "denetim_masasi" and target not in ALLOWED_CONTROL_PANEL:
        return [f"{where}: beyaz listede olmayan denetim masası öğesi {target!r}"]
    return []


def validate_tespit(tespit, where="tespit"):
    errors = []
    checks = tespit.get("herhangi")
    if not isinstance(checks, list) or not checks:
        errors.append(f"{where}: 'herhangi' listesi gerekli")
        checks = []
    if not tespit.get("mesaj"):
        errors.append(f"{where}: 'mesaj' gerekli")
    for i, check in enumerate(checks):
        cw = f"{where}.herhangi[{i}]"
        kind = check.get("tur")
        if kind == "registry":
            _check_registry_location(check, cw, errors)
            if check.get("karsilastir") not in COMPARE_OPS:
                errors.append(f"{cw}: 'karsilastir' {sorted(COMPARE_OPS)} olmalı")
        elif kind == "registry_anahtar_var":
            _check_registry_location(check, cw, errors)
        elif kind == "servis":
            if check.get("baslangic") not in SERVICE_START_TYPES:
                errors.append(f"{cw}: 'baslangic' geçersiz")
        elif kind == "yerlesik":
            if check.get("kontrol") not in BUILTIN_CHECKS:
                errors.append(f"{cw}: bilinmeyen yerleşik kontrol {check.get('kontrol')!r}")
        else:
            errors.append(f"{cw}: bilinmeyen tespit türü {kind!r}")
    return errors


def validate_tweak(tweak):
    """Dönüştürülmüş tek bir ayarı (tweaks_app.json girdisi) doğrular."""
    tid = tweak.get("id", "?")
    errors = []
    sinif = tweak.get("sinif")
    if sinif not in {"SWITCH", "REHBER", "BILGI"}:
        errors.append(f"{tid}: geçersiz sınıf {sinif!r}")
    if sinif == "SWITCH":
        if tid in FORBIDDEN_IDS:
            errors.append(f"{tid}: bu ayar hiçbir zaman uygulamadan yapılamaz (yasaklı liste)")
        if tweak.get("risk") == "riskli" and tweak.get("onay_seviyesi") != 2:
            errors.append(f"{tid}: riskli ayar iki aşamalı onay (onay_seviyesi=2) gerektirir")
        if "islem" not in tweak:
            errors.append(f"{tid}: switch için 'islem' gerekli")
        else:
            errors += validate_islem(tweak["islem"], f"{tid}.islem")
    elif "islem" in tweak:
        errors.append(f"{tid}: yalnızca SWITCH sınıfında 'islem' olabilir")
    errors += validate_uyumluluk(tweak.get("uyumluluk", {}), f"{tid}.uyumluluk")
    opener = tweak.get("rehber", {}).get("ac")
    if opener:
        errors += validate_opener(opener, f"{tid}.rehber.ac")
    if "tespit" in tweak:
        errors += validate_tespit(tweak["tespit"], f"{tid}.tespit")
    return errors
