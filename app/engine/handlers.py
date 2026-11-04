"""Adım türlerine göre oku / uygula / geri yükle.

Her adım türü için dört işlem vardır:
- snapshot(sys, step): mevcut durumu yedeklenebilir bir sözlük olarak okur
- state(step, snap): "acik" | "kapali" | "diger"
- apply(sys, step, which, snap): "acik" veya "kapali" hedefini yazar
- restore(sys, step, snap): yedekteki duruma geri döner

Geri yükleme mümkün olduğunca yalnızca bu ayarın dokunduğu kısmı geri alır;
örneğin DirectX ayar satırındaki diğer parçalara veya erişilebilirlik
bayraklarının diğer bitlerine dokunmaz.
"""

from app.core.i18n import t, value_label


class UserFacingError(Exception):
    """Kullanıcıya lang/tr.json'daki bir anahtarla anlatılabilecek hata."""

    def __init__(self, key, **params):
        super().__init__(key)
        self.key = key
        self.params = params


def _same(a, b):
    return a is not None and b is not None and str(a) == str(b)


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------

def _existing_ancestor(sys, root, path):
    """Yolun var olan en derin üst anahtarı. Geri alırken bizim oluşturduğumuz
    boş anahtarları temizlemek için kullanılır."""
    parts = path.split("\\")
    for i in range(len(parts), 0, -1):
        candidate = "\\".join(parts[:i])
        if sys.get_key_exists(root, candidate):
            return candidate
    return ""


def _computed(sys, spec):
    if spec == "toplam_ram_kb":
        return sys.get_total_ram_kb()
    raise UserFacingError("hata.bilinmeyen_islem")


def _reg_target(sys, step, which):
    value = step[which]
    return _computed(sys, value["hesapla"]) if isinstance(value, dict) else value


def _reg_snapshot(sys, step):
    found = sys.read_reg(step["kok"], step["yol"], step["ad"])
    snap = {"var": found is not None, "deger": found[0] if found else None,
            "veri_turu": found[1] if found else step.get("veri_turu"),
            "var_olan_ust": _existing_ancestor(sys, step["kok"], step["yol"])}
    if isinstance(step.get("acik"), dict):
        snap["hesaplanan"] = _computed(sys, step["acik"]["hesapla"])
    return snap


def _cleanup_created_keys(sys, step, snap):
    """Değer silindikten sonra, uygulamanın oluşturduğu ve artık boş kalan anahtarları siler."""
    stop = snap.get("var_olan_ust")
    if stop is not None and stop.lower() != step["yol"].lower():
        sys.delete_empty_keys(step["kok"], step["yol"], stop)


def _reg_state(step, snap):
    condition = step.get("acik_kosulu")
    if condition is not None:  # yalnızca kapatılabilen ayar: "uygulanmış mı?"
        if not snap["var"]:
            return "kapali"
        if condition == "var":
            return "acik"
        try:
            return "acik" if int(str(snap["deger"])) < condition["kucuk"] else "kapali"
        except ValueError:
            return "diger"
    effective = snap["deger"] if snap["var"] else step.get("yoksa")
    on = snap.get("hesaplanan") if isinstance(step["acik"], dict) else step["acik"]
    if _same(effective, on):
        return "acik"
    if (not snap["var"] and step["kapali"] is None) or _same(effective, step["kapali"]):
        return "kapali"
    return "diger"


def _reg_write_value(sys, step, value):
    if value is None:
        sys.delete_reg_value(step["kok"], step["yol"], step["ad"])
    else:
        sys.write_reg(step["kok"], step["yol"], step["ad"], value, step["veri_turu"])


def _reg_apply(sys, step, which, _snap):
    _reg_write_value(sys, step, _reg_target(sys, step, which))


def _reg_restore(sys, step, snap):
    if snap["var"]:
        sys.write_reg(step["kok"], step["yol"], step["ad"], snap["deger"], snap["veri_turu"])
    else:
        sys.delete_reg_value(step["kok"], step["yol"], step["ad"])
        _cleanup_created_keys(sys, step, snap)


# ---------------------------------------------------------------------------
# registry_bayrak: "Ad=Değer;Ad2=Değer2;" satırındaki tek parça
# ---------------------------------------------------------------------------

def parse_flags(text):
    pairs = []
    for part in (text or "").split(";"):
        if "=" in part:
            key, _, value = part.partition("=")
            pairs.append((key.strip(), value.strip()))
    return pairs


def format_flags(pairs):
    return "".join(f"{k}={v};" for k, v in pairs)


def _set_flag(pairs, key, value):
    """value None ise parça silinir."""
    result = [(k, v) for k, v in pairs if k != key]
    if value is not None:
        existing = [i for i, (k, _) in enumerate(pairs) if k == key]
        if existing:
            result.insert(min(existing[0], len(result)), (key, value))
        else:
            result.append((key, value))
    return result


def _flag_snapshot(sys, step):
    found = sys.read_reg(step["kok"], step["yol"], step["ad"])
    text = found[0] if found else None
    token = dict(parse_flags(text)).get(step["anahtar"])
    return {"var": found is not None, "deger": text, "parca": token,
            "var_olan_ust": _existing_ancestor(sys, step["kok"], step["yol"])}


def _flag_state(step, snap):
    value = snap["parca"] if snap["parca"] is not None else step.get("yoksa")
    if _same(value, step["acik"]):
        return "acik"
    if _same(value, step["kapali"]):
        return "kapali"
    return "diger"


def _flag_write(sys, step, token_value):
    current = sys.read_reg(step["kok"], step["yol"], step["ad"])
    pairs = _set_flag(parse_flags(current[0] if current else ""), step["anahtar"], token_value)
    if pairs:
        sys.write_reg(step["kok"], step["yol"], step["ad"], format_flags(pairs), "REG_SZ")
    else:
        sys.delete_reg_value(step["kok"], step["yol"], step["ad"])


def _flag_apply(sys, step, which, _snap):
    _flag_write(sys, step, step[which])


def _flag_restore(sys, step, snap):
    _flag_write(sys, step, snap["parca"])
    if not snap["var"] and sys.read_reg(step["kok"], step["yol"], step["ad"]) is None:
        _cleanup_created_keys(sys, step, snap)


# ---------------------------------------------------------------------------
# registry_bit
# ---------------------------------------------------------------------------

def _bit_snapshot(sys, step):
    return _reg_snapshot(sys, step)


def _bit_state(step, snap):
    if not snap["var"]:
        return "diger"
    try:
        bit = int(str(snap["deger"])) & step["maske"]
    except ValueError:
        return "diger"
    return "acik" if bit == step["acik"] else "kapali"


def _bit_write(sys, step, bit_value):
    current = sys.read_reg(step["kok"], step["yol"], step["ad"])
    if current is None:
        raise UserFacingError("hata.deger_yok")
    number = (int(str(current[0])) & ~step["maske"]) | (bit_value & step["maske"])
    value = str(number) if current[1] in ("REG_SZ", "REG_EXPAND_SZ") else number
    sys.write_reg(step["kok"], step["yol"], step["ad"], value, current[1])


def _bit_apply(sys, step, which, _snap):
    _bit_write(sys, step, step[which])


def _bit_restore(sys, step, snap):
    if snap["var"]:
        _bit_write(sys, step, int(str(snap["deger"])))


# ---------------------------------------------------------------------------
# registry_anahtar
# ---------------------------------------------------------------------------

def _key_snapshot(sys, step):
    return {"var": sys.get_key_exists(step["kok"], step["yol"]),
            "ust_var": sys.get_key_exists(step["kok"], step["silinecek_yol"])}


def _key_state(_step, snap):
    return "acik" if snap["var"] else "kapali"


def _key_apply(sys, step, which, _snap):
    if which == "acik":
        sys.create_reg_key(step["kok"], step["yol"], step.get("varsayilan_deger"))
    else:
        sys.delete_reg_tree(step["kok"], step["silinecek_yol"])


def _key_restore(sys, step, snap):
    if snap["var"]:
        sys.create_reg_key(step["kok"], step["yol"], step.get("varsayilan_deger"))
    elif snap["ust_var"]:
        sys.delete_reg_tree(step["kok"], step["yol"])  # üst anahtar zaten vardı; yalnızca bizimkini sil
    else:
        sys.delete_reg_tree(step["kok"], step["silinecek_yol"])


# ---------------------------------------------------------------------------
# servis
# ---------------------------------------------------------------------------

def _norm_start(kind):
    return "Automatic" if kind == "AutomaticDelayed" else kind


def _svc_snapshot(sys, step):
    info = sys.get_service(step["ad"])
    if info is None:
        return {"var": False}
    return {"var": True, "baslangic": info["baslangic"], "calisiyor": info["calisiyor"]}


def _svc_state(step, snap):
    if not snap["var"]:
        # Birden çok servisli ayarlarda bu bilgisayarda olmayan servis yok sayılır.
        return "yok" if step.get("yoksa_atla") else "diger"
    start = _norm_start(snap["baslangic"])
    if start == _norm_start(step["acik"]["baslangic"]):
        return "acik"
    if start == _norm_start(step["kapali"]["baslangic"]):
        return "kapali"
    return "diger"


def _svc_apply(sys, step, which, snap):
    if not snap["var"]:
        if step.get("yoksa_atla"):
            return
        raise UserFacingError("hata.servis_yok", ad=step["ad"])
    target = step[which]
    sys.set_service(step["ad"], target["baslangic"], target["calisiyor"])


def _svc_restore(sys, step, snap):
    if snap["var"]:
        sys.set_service(step["ad"], snap["baslangic"], snap["calisiyor"])


# ---------------------------------------------------------------------------
# powercfg (etkin plandaki bir ayar, prizde/AC)
# ---------------------------------------------------------------------------

def _pwr_snapshot(sys, step):
    scheme = sys.get_active_scheme()
    source = step.get("kaynak", "ac")
    return {"plan": scheme, "deger": sys.read_power_ac(scheme, step["alt_grup"], step["ayar"], source=source)}


def _pwr_state(step, snap):
    if snap["deger"] == step["acik"]:
        return "acik"
    return "kapali"


def _pwr_apply(sys, step, which, snap):
    value = step[which]
    if value == "plan_varsayilani":
        value = sys.read_power_ac_default(snap["plan"], step["alt_grup"], step["ayar"], source=step.get("kaynak", "ac"))
        if value is None:
            raise UserFacingError("hata.plan_varsayilani_yok")
    sys.write_power_ac(snap["plan"], step["alt_grup"], step["ayar"], value, source=step.get("kaynak", "ac"))


def _pwr_restore(sys, step, snap):
    sys.write_power_ac(snap["plan"], step["alt_grup"], step["ayar"], snap["deger"], source=step.get("kaynak", "ac"))


# ---------------------------------------------------------------------------
# guc_plani
# ---------------------------------------------------------------------------

def _plan_snapshot(sys, _step):
    return {"plan": sys.get_active_scheme()}


def _plan_state(step, snap):
    if snap["plan"].lower() == step["acik"].lower():
        return "acik"
    if snap["plan"].lower() == step["kapali"].lower():
        return "kapali"
    return "diger"


def _plan_apply(sys, step, which, _snap):
    sys.set_active_scheme(step[which])


def _plan_restore(sys, _step, snap):
    sys.set_active_scheme(snap["plan"])


# ---------------------------------------------------------------------------
# yerleşik eylemler
# ---------------------------------------------------------------------------

DNS_PROVIDERS = {
    "cloudflare": ["1.1.1.1", "1.0.0.1"],
    "google": ["8.8.8.8", "8.8.4.4"],
    "quad9": ["9.9.9.9", "149.112.112.112"],
}


def dns_choice(info):
    """DNS durumunu seçim değerine çevirir: otomatik / cloudflare / google / quad9 / ozel."""
    if info["otomatik"]:
        return "otomatik"
    servers = set(info["sunucular"])
    for name, addresses in DNS_PROVIDERS.items():
        if servers and servers <= set(addresses):
            return name
    return "ozel"


def _builtin_snapshot(sys, step):
    action, params = step["eylem"], step["parametreler"]
    if action == "hazirda_bekletme":
        return {"deger": sys.get_hibernate()}
    if action == "bellek_sikistirma":
        return {"deger": sys.get_memory_compression()}
    if action == "windows_ozelligi":
        return {"durumlar": sys.get_features(params["ozellikler"])}
    if action == "wlan_otomatik_yapilandirma":
        return {"durumlar": sys.get_wlan_autoconfig()}
    if action == "ag_gelismis_ozellik":
        return {"deger": sys.get_nic_property(params["bagdastirici"], params["anahtar"])}
    if action == "bcdedit":
        value = sys.get_bcd().get(params["eleman"])
        return {"deger": value.lower() if isinstance(value, str) else None}
    if action == "tcp_otomatik_ayar":
        return {"deger": sys.get_tcp_autotuning()}
    if action == "zamanlanmis_gorev":
        return {"deger": sys.get_task_state(params["yol"], params["ad"])}
    if action == "pnp_cihaz":
        devices = sys.get_pnp_devices(params["donanim_kimligi"])
        return {"cihazlar": devices}
    if action == "nihai_performans_plani":
        plan = sys.get_active_scheme().lower()
        return {"plan": plan, "kopyalar": sys.list_ultimate_schemes(), "nihai": sys.is_ultimate_scheme(plan)}
    if action == "dns":
        info = sys.get_dns(params["bagdastirici"])
        return {"deger": dns_choice(info), "dns": info}
    if action == "gorsel_efekt":
        return {"deger": sys.get_ui_effect(params["ad"])}
    if action == "nvidia_drs":
        info = sys.get_nvidia_settings([int(params["ayar"], 16)])[int(params["ayar"], 16)]
        return {"deger": info["deger"], "ozel": info["ozel"]}
    if action == "amd_adlx":
        info = (sys.get_amd_settings().get(params["gpu"]) or {}).get(params["ozellik"])
        if not info or info.get("acik") is None:
            raise UserFacingError("hata.amd_okunamadi")
        return {"deger": info["acik"]}
    if action == "ses_bicimi":
        info = sys.get_audio_format(params["cihaz"])
        return {"deger": info["deger"], "ham": info["ham"]}
    if action == "guc_modu":
        return {"deger": sys.get_power_overlay(params["kaynak"])}
    if action == "defender_gercek_zamanli":
        status = sys.get_defender_status()
        if not status or status.get("gercek_zamanli") is None:
            raise UserFacingError("hata.defender_okunamadi")
        return {"deger": bool(status["gercek_zamanli"])}
    if action == "baslangic_onayi":
        raw = sys.get_startup_approved(params["kok"], params["yol"], params["ad"])
        return {"ham": raw, "deger": raw is None or int(raw[:2], 16) % 2 == 0}
    if action == "cihaz_guc":
        return {"deger": sys.get_device_power(params["ornek"])}
    if action == "aygit_etkin":
        return {"deger": sys.get_device_enabled(params["ornek"])}
    if action == "ekran_yenileme":
        info = sys.get_display_refresh(params["aygit"])
        top = "en_yuksek" if info["hz"] >= info["en_yuksek"] else str(info["hz"])
        return {"deger": top, "hz": info["hz"], "en_yuksek": info["en_yuksek"]}
    if action in DISPLAY_ACTIONS:
        device = sys.find_display(params["monitor"], params["aygit"])
        if action == "ekran_modu":
            info = sys.get_display_mode(device)
            return {"deger": f"{info['cozunurluk']}@{info['hz']}"}
        if action in ("ekran_yon", "ekran_konum"):
            info = sys.get_display_layout(device)
            if info is None:
                raise UserFacingError("hata.ekran_yerlesim_okunamadi")
            return {"deger": info["yon"] if action == "ekran_yon" else f"{info['x']},{info['y']}"}
        if action == "ekran_olcekleme":
            info = sys.get_display_scaling(device)
            if info is None:
                raise UserFacingError("hata.olcekleme_okunamadi")
            return {"deger": info["deger"]}
        info = sys.get_display_scale(device)
        if info is None:
            raise UserFacingError("hata.ekran_olcek_okunamadi")
        return {"deger": str(info["yuzde"])}
    raise UserFacingError("hata.bilinmeyen_islem")


# Monitör başına ekran ayarları. Ekran numarası (\\.\DISPLAYn) yeniden başlatınca değişebildiği için
# her işlem önce kalıcı monitör yolundan şu anki ekranı bulur.
DISPLAY_ACTIONS = ("ekran_modu", "ekran_olcek", "ekran_olcekleme", "ekran_yon", "ekran_konum")


def parse_mode(value):
    """"2560x1440@144" -> (2560, 1440, 144)."""
    size, hz = str(value).split("@")
    width, height = size.lower().split("x")
    return int(width), int(height), int(hz)


def _match(value, target):
    if target == "*":  # yalnızca kapatılabilen ayarda: "herhangi bir değer tanımlı"
        return value is not None
    if target is None:
        return value is None
    return _same(value, target)


def _builtin_state(step, snap):
    action = step["eylem"]
    if action in ("windows_ozelligi", "wlan_otomatik_yapilandirma"):
        states = set(snap["durumlar"].values())
        if not states:
            return "diger"
        if states == {step["acik"]}:
            return "acik"
        if states == {step["kapali"]}:
            return "kapali"
        return "diger"
    if action == "pnp_cihaz":
        if not snap["cihazlar"]:
            return "diger"
        disabled = {d["kapali"] for d in snap["cihazlar"]}
        target_disabled = step["acik"] == "Disabled"
        if disabled == {target_disabled}:
            return "acik"
        return "kapali" if disabled == {not target_disabled} else "diger"
    if action == "nihai_performans_plani":
        return "acik" if snap["plan"] in snap["kopyalar"] or snap.get("nihai") else "kapali"
    if action == "ekran_yenileme":
        # "Kapalı" hedefi yok: en yüksekte değilse kapalı sayılır.
        return "acik" if snap["deger"] == "en_yuksek" else "kapali"
    if action == "bcdedit":
        value = snap["deger"] if snap["deger"] is not None else step.get("yoksa")
        if _match(value, step["acik"]):
            return "acik"
        return "kapali" if _match(value, step["kapali"]) else "diger"
    if snap.get("deger") is None:
        return "diger"
    if _same(snap["deger"], step["acik"]):
        return "acik"
    if _same(snap["deger"], step["kapali"]):
        return "kapali"
    return "diger"


def _builtin_set(sys, step, value, snap):
    action, params = step["eylem"], step["parametreler"]
    if action == "hazirda_bekletme":
        sys.set_hibernate(bool(value))
    elif action == "bellek_sikistirma":
        sys.set_memory_compression(bool(value))
    elif action == "windows_ozelligi":
        targets = value if isinstance(value, dict) else {name: value for name in snap["durumlar"]}
        for name, state in targets.items():
            if snap["durumlar"].get(name) != state:
                sys.set_feature(name, state == "Enabled")
    elif action == "wlan_otomatik_yapilandirma":
        targets = value if isinstance(value, dict) else {name: value for name in snap["durumlar"]}
        for name, state in targets.items():
            if snap["durumlar"].get(name) != state:
                sys.set_wlan_autoconfig(name, state == "Enabled")
    elif action == "ag_gelismis_ozellik":
        sys.set_nic_property(params["bagdastirici"], params["anahtar"], str(value))
    elif action == "bcdedit":
        sys.set_bcd(params["eleman"], None if value in (None, "*") else value)
    elif action == "tcp_otomatik_ayar":
        sys.set_tcp_autotuning(value)
    elif action == "zamanlanmis_gorev":
        sys.set_task_enabled(params["yol"], params["ad"], value == "Enabled")
    elif action == "pnp_cihaz":
        targets = value if isinstance(value, dict) else {d["id"]: value == "Disabled" for d in snap["cihazlar"]}
        for device in snap["cihazlar"]:
            if device["id"] in targets and device["kapali"] != targets[device["id"]]:
                sys.set_pnp_enabled(device["id"], not targets[device["id"]])
    elif action == "dns":
        if value == "otomatik":
            sys.set_dns(params["bagdastirici"], None)
        elif value in DNS_PROVIDERS:
            sys.set_dns(params["bagdastirici"], DNS_PROVIDERS[value])
        else:
            raise UserFacingError("hata.gecersiz_deger")
    elif action == "gorsel_efekt":
        sys.set_ui_effect(params["ad"], bool(value))
    elif action == "nvidia_drs":
        sys.set_nvidia_setting(int(params["ayar"], 16), None if value is None else int(value))
    elif action == "amd_adlx":
        sys.set_amd_feature(params["gpu"], params["ozellik"], bool(value))
    elif action == "ses_bicimi":
        sys.set_audio_format(params["cihaz"], value=value)
    elif action == "guc_modu":
        sys.set_power_overlay(params["kaynak"], value)
    elif action == "defender_gercek_zamanli":
        sys.set_defender_realtime(bool(value))
        status = sys.get_defender_status() or {}
        if status.get("gercek_zamanli") is None or bool(status["gercek_zamanli"]) != bool(value):
            raise UserFacingError("hata.defender_kurcalama")
    elif action == "baslangic_onayi":
        sys.set_startup_approved(params["kok"], params["yol"], params["ad"], bool(value))
    elif action == "cihaz_guc":
        sys.set_device_power(params["ornek"], bool(value))
    elif action == "aygit_etkin":
        sys.set_device_enabled(params["ornek"], bool(value))
    elif action == "ekran_yenileme":
        if value is None:
            raise UserFacingError("hata.kapatma_hedefi_yok")
        info = sys.get_display_refresh(params["aygit"])
        target = info["en_yuksek"] if value == "en_yuksek" else int(value)
        if target != info["hz"]:
            sys.set_display_refresh(params["aygit"], target)
    elif action in DISPLAY_ACTIONS:
        if value is None:
            raise UserFacingError("hata.kapatma_hedefi_yok")
        device = sys.find_display(params["monitor"], params["aygit"])
        if action == "ekran_modu":
            sys.set_display_mode(device, *parse_mode(value))
        elif action in ("ekran_yon", "ekran_konum"):
            now = sys.get_display_layout(device)
            if now is None:
                raise UserFacingError("hata.ekran_yerlesim_okunamadi")
            if action == "ekran_yon":
                sys.set_display_layout(device, now["x"], now["y"], value)
            else:
                x, y = (int(part) for part in str(value).split(","))
                sys.set_display_layout(device, x, y, now["yon"])
        elif action == "ekran_olcekleme":
            sys.set_display_scaling(device, value)
        else:
            sys.set_display_scale(device, int(value))


def _builtin_apply(sys, step, which, snap):
    if step["eylem"] == "nihai_performans_plani":
        if which == "acik":
            copies = sys.list_ultimate_schemes()
            sys.set_active_scheme(copies[0] if copies else sys.create_ultimate_scheme())
        else:
            sys.set_active_scheme(step["kapali"])
        return
    _builtin_set(sys, step, step[which], snap)


def _builtin_restore(sys, step, snap):
    action = step["eylem"]
    if action == "windows_ozelligi":
        current = sys.get_features(list(snap["durumlar"]))
        _builtin_set(sys, step, snap["durumlar"], {"durumlar": current})
    elif action == "wlan_otomatik_yapilandirma":
        _builtin_set(sys, step, snap["durumlar"], {"durumlar": sys.get_wlan_autoconfig()})
    elif action == "pnp_cihaz":
        current = {"cihazlar": sys.get_pnp_devices(step["parametreler"]["donanim_kimligi"])}
        _builtin_set(sys, step, {d["id"]: d["kapali"] for d in snap["cihazlar"]}, current)
    elif action == "nihai_performans_plani":
        sys.set_active_scheme(snap["plan"])
        for guid in sys.list_ultimate_schemes():  # yalnızca uygulamanın oluşturduğu kopyalar silinir
            if guid not in snap["kopyalar"]:
                sys.delete_scheme(guid)
    elif action == "bcdedit":
        sys.set_bcd(step["parametreler"]["eleman"], snap["deger"])
    elif action == "dns":
        info = snap["dns"]
        sys.set_dns(step["parametreler"]["bagdastirici"], None if info["otomatik"] else info["sunucular"])
    elif action == "ekran_yenileme":
        _builtin_set(sys, step, snap["hz"], snap)
    elif action == "baslangic_onayi":
        params = step["parametreler"]
        sys.set_startup_approved_raw(params["kok"], params["yol"], params["ad"], snap["ham"])
    elif action == "nvidia_drs":
        # Profil bu ayarı özelleştirmemişse sürücü varsayılanına döner.
        sys.set_nvidia_setting(int(step["parametreler"]["ayar"], 16), snap["deger"] if snap["ozel"] else None)
    elif action == "ses_bicimi":
        sys.set_audio_format(step["parametreler"]["cihaz"], raw_hex=snap["ham"])
    elif snap["deger"] is not None:
        _builtin_set(sys, step, snap["deger"], snap)


HANDLERS = {
    "registry": (_reg_snapshot, _reg_state, _reg_apply, _reg_restore),
    "registry_bayrak": (_flag_snapshot, _flag_state, _flag_apply, _flag_restore),
    "registry_bit": (_bit_snapshot, _bit_state, _bit_apply, _bit_restore),
    "registry_anahtar": (_key_snapshot, _key_state, _key_apply, _key_restore),
    "servis": (_svc_snapshot, _svc_state, _svc_apply, _svc_restore),
    "powercfg": (_pwr_snapshot, _pwr_state, _pwr_apply, _pwr_restore),
    "guc_plani": (_plan_snapshot, _plan_state, _plan_apply, _plan_restore),
    "yerlesik": (_builtin_snapshot, _builtin_state, _builtin_apply, _builtin_restore),
}


def snapshot(sys, step):
    return HANDLERS[step["tur"]][0](sys, step)


def state(step, snap):
    return HANDLERS[step["tur"]][1](step, snap)


def apply(sys, step, which, snap):
    HANDLERS[step["tur"]][2](sys, step, which, snap)


def restore(sys, step, snap):
    HANDLERS[step["tur"]][3](sys, step, snap)


def write_value(sys, step, value, snap=None):
    """Adıma doğrudan değer yazar: seçim alanları ve yöneticiler (başlangıç, servis, aygıt)."""
    if step["tur"] == "yerlesik":
        _builtin_set(sys, step, value, snap)
    elif step["tur"] == "servis":
        sys.set_service(step["ad"], value["baslangic"], value.get("calisiyor"))
    else:
        _reg_write_value(sys, step, value)


def selection_value(step, snap):
    """Seçim alanının şu anki değeri (metin)."""
    if step["tur"] == "yerlesik":
        return snap.get("deger")
    return str(snap["deger"]) if snap["var"] else step.get("yoksa")


# ---------------------------------------------------------------------------
# Önizleme: "bu ayar şunları değiştirecek"
# ---------------------------------------------------------------------------

def describe(step, which):
    kind = step["tur"]
    value = step.get(which) if which else None
    if kind == "registry":
        if isinstance(value, dict):
            value = t(f"onizleme.hesapla.{value['hesapla']}")
        if value is None:
            return t("onizleme.registry_sil", yol=f"{step['kok']}\\{step['yol']}", ad=step["ad"])
        return t("onizleme.registry_yaz", yol=f"{step['kok']}\\{step['yol']}", ad=step["ad"], deger=value)
    if kind == "registry_bayrak":
        return t("onizleme.registry_bayrak", ad=step["ad"], anahtar=step["anahtar"], deger=value)
    if kind == "registry_bit":
        return t("onizleme.registry_bit", yol=f"{step['kok']}\\{step['yol']}", ad=step["ad"],
                 deger=t("deger.acik") if value else t("deger.kapali"))
    if kind == "registry_anahtar":
        key = "onizleme.anahtar_olustur" if which == "acik" else "onizleme.anahtar_sil"
        return t(key, yol=f"{step['kok']}\\{step['yol' if which == 'acik' else 'silinecek_yol']}")
    if kind == "servis":
        running = {True: t("onizleme.calisir"), False: t("onizleme.durur"), None: t("onizleme.dokunulmaz")}
        return t("onizleme.servis", ad=step["ad"], baslangic=value_label("ui.baslangic_turu", value["baslangic"]),
                 durum=running[value["calisiyor"]])
    if kind == "powercfg":
        shown = t("onizleme.plan_varsayilani") if value == "plan_varsayilani" else value
        return t("onizleme.powercfg", ayar=step["ayar"], deger=shown)
    if kind == "guc_plani":
        return t("onizleme.guc_plani", plan=value)
    if kind == "yerlesik":
        shown = t("onizleme.silinir") if value in (None, "*") else value
        if value == "en_yuksek":
            shown = t("onizleme.en_yuksek_hz")
        return t(f"onizleme.{step['eylem']}", deger=shown, **step["parametreler"])
    return kind
