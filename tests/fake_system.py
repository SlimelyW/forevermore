"""Bellekte çalışan sahte Windows. Ayar motoru testleri gerçek bilgisayara
dokunmadan bunu kullanır. WindowsSystem ile aynı metot adlarına sahiptir."""

import copy

from app.engine import resolvers


class FakeSystem:
    def __init__(self):
        self.reg = {}          # (kök, yol_küçük, ad_küçük) -> (değer, tür)
        self.keys = set()      # (kök, yol_küçük)
        self.services = {}     # ad -> {"baslangic", "calisiyor"}
        self.active_scheme = "381b4222-f694-41f0-9685-ff5bb260df2e"
        self.power = {}        # (plan, alt, ayar) -> değer
        self.power_defaults = {}
        self.hibernate = True
        self.memory_compression = True
        self.defender = {"gercek_zamanli": True, "kurcalama": False, "mod": "Normal"}
        self.features = {}
        self.wlan = {"F7F590A3-398E-4369-BC69-A1A7CA02A3EE": "Enabled"}
        self.nic = {}
        self.bcd = {}           # öğe -> değer (küçük harf)
        self.autotuning = "normal"
        self.tasks = {}         # (yol, ad) -> "Enabled"/"Disabled"
        self.pnp = {}           # donanım kimliği -> {örnek: kapalı_mı}
        self.ultimate = []      # nihai performans plan kopyaları
        self.deleted_schemes = []
        self.dns = {}           # bağdaştırıcı -> {"otomatik", "sunucular"}
        self.ram_kb = 33554432
        self.displays = {}      # aygıt -> {"hz", "en_yuksek", "hizlar"}
        self.monitors = {"TEST": {"ad": "Test Monitör", "monitor_yolu": "MON-TEST", "baglanti": "HDMI",
                                  "dahili": False, "birincil": True, "gpu": "Test GPU",
                                  "mod": {"cozunurluk": "1920x1080", "hz": 60,
                                          "modlar": {"1920x1080": [144, 120, 60], "1280x720": [60]}},
                                  "olcek": {"yuzde": 100, "onerilen": 100, "secenekler": [100, 125, 150]},
                                  "olcekleme": "oran", "surucu_olcekleme": {"surucu": "nvidia", "deger": "nvidia:6"},
                                  "yerlesim": {"x": 0, "y": 0, "genislik": 1920, "yukseklik": 1080, "yon": "yatay"}}}
        self.amd = {"Test Radeon": {"anti_lag": {"destek": True, "acik": False},
                                    "enhanced_sync": {"destek": False, "acik": None}}}
        self.restarts = []      # restart_computer çağrıları (saniye)
        self.opened = []        # open_path ile açılanlar
        self.approved = {}      # (kök, yol, ad) -> onaltılık değer
        self.nvidia = {}        # ayar kimliği -> değer (yoksa sürücü varsayılanı)
        self.nvidia_ok = True
        self.npi_imports = []
        self.npi_hashes = []
        self.npi_signed = True
        self.audio_formats = {}  # cihaz -> "48000/24"
        self.device_power = {}  # örnek -> bool
        self.audio_pnp = [{"id": "SESA-hoparlor", "ornek": "SWD\\MMDEVAPI\\HOPARLOR", "ad": "Speaker", "sinif": "AudioEndpoint",
                           "etkin": True},
                          {"id": "SESA-hfp", "ornek": "BTHENUM\\{0000111E}_HFP", "ad": "Kulaklık Hands-Free",
                           "sinif": "Bluetooth", "etkin": True}]
        self.ui_effects = {}    # ad -> bool (varsayılan True)
        self.overlay = {"ac": "00000000-0000-0000-0000-000000000000", "dc": "00000000-0000-0000-0000-000000000000"}
        self.startup_items = [{"id": "BAS-test", "ad": "Uygulama", "komut": "uygulama.exe", "konum": "kayit_kullanici",
                               "etkin": True, "onay": {"kok": "HKCU", "yol": "Approved", "ad": "Uygulama"}}]
        self.logon_tasks = [{"id": "GRV-test", "ad": "Gorev", "yol": "/", "komut": "gorev.exe", "etkin": True}]
        self.pci_devices = [{"id": "MSI-test", "ornek": "PCI/VEN_TEST/1", "ad": "Test GPU", "sinif": "Display",
                             "msi": None, "anahtar_var": True}]
        self.power_devices = [{"id": "GUC-test", "ornek": "USB/ROOT_HUB/1_0", "ad": "USB Kök Hub", "sinif": "USB",
                               "etkin": True}]
        self.temp_deleted = []
        self.restore_points = []
        self.restore_mode = "ok"  # ok | fail | silent
        self.fail_on = set()   # bu metot adları çağrılınca hata ver
        self.calls = []
        self.exports = []

    # yardımcılar ------------------------------------------------------------
    def _maybe_fail(self, name):
        self.calls.append(name)
        if name in self.fail_on:
            raise PermissionError(f"sahte hata: {name}")

    def state_copy(self):
        """Karşılaştırma için durum. Varsayılana eşit açık kayıtlar yok sayılır
        (ör. 'servis Automatic' hiç yazılmamış olmakla aynı şeydir)."""
        default_service = {"baslangic": "Automatic", "calisiyor": True}
        return copy.deepcopy((
            self.reg, self.keys,
            {k: v for k, v in self.services.items() if v != default_service},
            self.active_scheme,
            {k: v for k, v in self.power.items() if v != 50},
            self.hibernate, self.memory_compression,
            {k: v for k, v in self.features.items() if v != "Enabled"},
            {k: v for k, v in self.nic.items() if v != "1"},
            self.bcd, self.autotuning,
            {k: v for k, v in self.tasks.items() if v != "Enabled"},
            {k: v for k, v in self.pnp.items() if any(v.values())},
            sorted(self.ultimate),
            {k: v for k, v in self.dns.items() if not v["otomatik"]},
            {k: v["hz"] for k, v in self.displays.items() if v["hz"] != 60},
            {k: (v["mod"]["cozunurluk"], v["mod"]["hz"], v["olcek"]["yuzde"], v["olcekleme"])
             for k, v in self.monitors.items()
             if (v["mod"]["cozunurluk"], v["mod"]["hz"], v["olcek"]["yuzde"], v["olcekleme"])
             != ("1920x1080", 60, 100, "oran")},
            {k: v["yerlesim"] for k, v in self.monitors.items()
             if v["yerlesim"] != {"x": 0, "y": 0, "genislik": 1920, "yukseklik": 1080, "yon": "yatay"}},
            self.approved, {k: v for k, v in self.device_power.items() if not v}, self.nvidia,
            {k: v for k, v in self.audio_formats.items() if v != "48000/16"},
            {k: v for k, v in self.ui_effects.items() if not v}, self.overlay,
            self.defender["gercek_zamanli"],
        ))

    def _add_key(self, root, path):
        parts = path.split("\\")
        for i in range(1, len(parts) + 1):
            self.keys.add((root, "\\".join(parts[:i]).lower()))

    # registry ----------------------------------------------------------------
    def read_reg(self, root, path, name):
        return self.reg.get((root, path.lower(), name.lower()))

    def get_key_exists(self, root, path):
        return (root, path.lower()) in self.keys

    def write_reg(self, root, path, name, value, reg_type):
        self._maybe_fail("write_reg")
        self._add_key(root, path)
        self.reg[(root, path.lower(), name.lower())] = (value, reg_type)

    def delete_reg_value(self, root, path, name):
        self._maybe_fail("delete_reg_value")
        self.reg.pop((root, path.lower(), name.lower()), None)

    def list_reg(self, root, path):
        low = path.lower()
        names = [k[2] for k in self.reg if k[0] == root and k[1] == low]
        children = {k[1][len(low) + 1:].split("\\")[0] for k in self.keys if k[0] == root and k[1].startswith(low + "\\")}
        return names, sorted(children)

    def create_reg_key(self, root, path, default_value=None):
        self._maybe_fail("create_reg_key")
        self._add_key(root, path)
        if default_value is not None:
            self.reg[(root, path.lower(), "")] = (default_value, "REG_SZ")

    def delete_reg_tree(self, root, path):
        self._maybe_fail("delete_reg_tree")
        prefix = path.lower()
        self.keys = {k for k in self.keys if not (k[0] == root and (k[1] == prefix or k[1].startswith(prefix + "\\")))}
        self.reg = {k: v for k, v in self.reg.items()
                    if not (k[0] == root and (k[1] == prefix or k[1].startswith(prefix + "\\")))}

    def delete_empty_keys(self, root, path, stop_at):
        self._maybe_fail("delete_empty_keys")
        current = path
        while current and len(current) > len(stop_at) and current.lower().startswith(stop_at.lower()):
            low = current.lower()
            has_children = any(k[0] == root and k[1].startswith(low + "\\") for k in self.keys)
            has_values = any(k[0] == root and k[1] == low for k in self.reg)
            if has_children or has_values:
                return
            self.keys.discard((root, low))
            current = current.rpartition("\\")[0]

    def export_bcd(self, file_path):
        self.bcd_exports = getattr(self, "bcd_exports", []) + [str(file_path)]

    def export_reg_key(self, root, path, file_path):
        self.exports.append((root, path))
        return True

    # servis ------------------------------------------------------------------
    def get_service(self, name):
        return copy.deepcopy(self.services.get(name, {"baslangic": "Automatic", "calisiyor": True}))

    def set_service(self, name, start_type, running):
        self._maybe_fail("set_service")
        if running is None:  # gerçek sistemde olduğu gibi: çalışma durumuna dokunma
            running = self.services.get(name, {"calisiyor": True})["calisiyor"]
        self.services[name] = {"baslangic": start_type, "calisiyor": running}

    # güç -----------------------------------------------------------------------
    def get_active_scheme(self):
        return self.active_scheme

    def set_active_scheme(self, scheme):
        self._maybe_fail("set_active_scheme")
        self.active_scheme = scheme

    @staticmethod
    def _pkey(scheme, sub, setting, source):
        return (scheme, sub, setting) if source == "ac" else (scheme, sub, setting, "dc")

    def read_power_ac(self, scheme, sub, setting, source="ac"):
        return self.power.get(self._pkey(scheme, sub, setting, source), 50)

    def read_power_ac_default(self, scheme, sub, setting, source="ac"):
        default = 50 if scheme.startswith("381b") else None
        return self.power_defaults.get(self._pkey(scheme, sub, setting, source), default)

    def write_power_ac(self, scheme, sub, setting, value, source="ac"):
        self._maybe_fail("write_power_ac")
        self.power[self._pkey(scheme, sub, setting, source)] = value

    # yerleşik ----------------------------------------------------------------
    def get_hibernate(self):
        return self.hibernate

    def set_hibernate(self, enabled):
        self._maybe_fail("set_hibernate")
        self.hibernate = enabled

    def get_memory_compression(self):
        return self.memory_compression

    def set_memory_compression(self, enabled):
        self._maybe_fail("set_memory_compression")
        self.memory_compression = enabled

    def get_defender_status(self):
        return dict(self.defender)

    def set_defender_realtime(self, enabled):
        self._maybe_fail("set_defender_realtime")
        if not self.defender["kurcalama"]:  # Windows gibi: Kurcalama koruması açıksa sessizce yok sayılır
            self.defender["gercek_zamanli"] = enabled
        return dict(self.defender)

    def get_features(self, names):
        return {n: self.features.get(n, "Enabled") for n in names}

    def set_feature(self, name, enabled):
        self._maybe_fail("set_feature")
        self.features[name] = "Enabled" if enabled else "Disabled"

    def get_wlan_autoconfig(self):
        return dict(self.wlan)

    def set_wlan_autoconfig(self, name, enabled):
        self._maybe_fail("set_wlan_autoconfig")
        self.wlan[name] = "Enabled" if enabled else "Disabled"

    def get_nic_property(self, adapter, keyword):
        return self.nic.get((adapter, keyword), "1")

    def set_nic_property(self, adapter, keyword, value):
        self._maybe_fail("set_nic_property")
        self.nic[(adapter, keyword)] = value

    def get_bcd(self):
        return dict(self.bcd)

    def set_bcd(self, element, value):
        self._maybe_fail("set_bcd")
        if value is None:
            self.bcd.pop(element, None)
        else:
            self.bcd[element] = str(value).lower()

    def get_tcp_autotuning(self):
        return self.autotuning

    def set_tcp_autotuning(self, level):
        self._maybe_fail("set_tcp_autotuning")
        self.autotuning = level

    def get_task_state(self, path, name):
        return self.tasks.get((path, name), "Enabled")

    def set_task_enabled(self, path, name, enabled):
        self._maybe_fail("set_task_enabled")
        self.tasks[(path, name)] = "Enabled" if enabled else "Disabled"

    def get_pnp_devices(self, hardware_id):
        devices = self.pnp.setdefault(hardware_id, {f"{hardware_id}\\0": False})
        return [{"id": k, "kapali": v} for k, v in devices.items()]

    def set_pnp_enabled(self, instance_id, enabled):
        self._maybe_fail("set_pnp_enabled")
        for devices in self.pnp.values():
            if instance_id in devices:
                devices[instance_id] = not enabled

    def list_ultimate_schemes(self):
        return list(self.ultimate)

    def is_ultimate_scheme(self, guid):
        return guid.lower() == "e9a42b02-d5df-448d-aa00-03f14749eb61" or guid in self.ultimate

    def create_ultimate_scheme(self):
        self._maybe_fail("create_ultimate_scheme")
        guid = f"aaaaaaaa-0000-0000-0000-00000000000{len(self.ultimate)}"
        self.ultimate.append(guid)
        return guid

    def delete_scheme(self, guid):
        self.deleted_schemes.append(guid)
        self.ultimate = [g for g in self.ultimate if g != guid]

    def get_dns(self, adapter):
        return copy.deepcopy(self.dns.get(adapter, {"otomatik": True, "sunucular": ["192.168.1.1"]}))

    def set_dns(self, adapter, servers):
        self._maybe_fail("set_dns")
        self.dns[adapter] = {"otomatik": not servers, "sunucular": list(servers) if servers else ["192.168.1.1"]}

    def get_total_ram_kb(self):
        return self.ram_kb

    def list_startup_items(self):
        items = copy.deepcopy(self.startup_items)
        for item in items:
            o = item["onay"]
            raw = self.approved.get((o["kok"], o["yol"], o["ad"]))
            item["etkin"] = raw is None or int(raw[:2], 16) % 2 == 0
        return items

    def list_logon_tasks(self):
        tasks = copy.deepcopy(self.logon_tasks)
        for task in tasks:
            task["etkin"] = self.tasks.get((task["yol"], task["ad"]), "Enabled") == "Enabled"
        return tasks

    def list_services(self):
        return [{"id": "SRV-" + name, "ad": name, "servis": name, "baslangic": info["baslangic"],
                 "calisiyor": info["calisiyor"], "windows": False, "kilit": None}
                for name, info in sorted(self.services.items())]

    def list_pci_devices(self):
        return copy.deepcopy(self.pci_devices)

    def list_power_managed_devices(self):
        devices = copy.deepcopy(self.power_devices)
        for d in devices:
            d["etkin"] = self.device_power.get(d["ornek"], True)
        return devices

    def get_startup_approved(self, root, path, name):
        return self.approved.get((root, path, name))

    def set_startup_approved(self, root, path, name, enabled):
        self._maybe_fail("set_startup_approved")
        self.approved[(root, path, name)] = ("02" if enabled else "03") + "00" * 11

    def set_startup_approved_raw(self, root, path, name, hex_value):
        if hex_value is None:
            self.approved.pop((root, path, name), None)
        else:
            self.approved[(root, path, name)] = hex_value

    def get_device_power(self, instance):
        return self.device_power.get(instance, True)

    def set_device_power(self, instance, enabled):
        self._maybe_fail("set_device_power")
        self.device_power[instance] = enabled

    def get_ui_effect(self, name):
        return self.ui_effects.get(name, True)

    def set_ui_effect(self, name, enabled):
        self._maybe_fail("set_ui_effect")
        self.ui_effects[name] = enabled

    def get_power_overlay(self, source):
        return self.overlay[source]

    def set_power_overlay(self, source, guid):
        self._maybe_fail("set_power_overlay")
        self.overlay[source] = guid

    def nvidia_available(self):
        return self.nvidia_ok

    def get_nvidia_settings(self, setting_ids):
        return {i: {"deger": self.nvidia.get(i), "ozel": i in self.nvidia} for i in setting_ids}

    def set_nvidia_setting(self, setting_id, value):
        self._maybe_fail("set_nvidia_setting")
        if value is None:
            self.nvidia.pop(setting_id, None)
        else:
            self.nvidia[setting_id] = value

    def npi_available(self):
        return True

    def get_amd_settings(self):
        return copy.deepcopy(self.amd)

    def set_amd_feature(self, gpu, feature, enabled):
        self._maybe_fail("set_amd_feature")
        info = self.amd[gpu][feature]
        if not info["destek"]:
            raise OSError("desteklenmiyor")
        info["acik"] = bool(enabled)

    def get_display_scaling(self, device):
        return copy.deepcopy(self.monitors[device].get("surucu_olcekleme"))

    def set_display_scaling(self, device, value):
        self._maybe_fail("set_display_scaling")
        info = self.monitors[device]["surucu_olcekleme"]
        if not str(value).startswith(info["surucu"] + ":"):
            raise ValueError("başka sürücü")
        info["deger"] = str(value)

    def restart_computer(self, seconds=10):
        self.restarts.append(seconds)

    def open_path(self, target):
        self.opened.append(str(target))

    def npi_check(self):
        return {"sha256": "ab" * 32, "imza_gecerli": self.npi_signed, "imzalayan": "Test" if self.npi_signed else ""}

    def run_npi_import(self, settings, sha256=None):
        self.npi_hashes.append(sha256)
        self.npi_imports.append(list(settings))

    def get_audio_format(self, device):
        value = self.audio_formats.get(device, "48000/16")
        return {"deger": value, "ham": "ham:" + value, "desteklenen": ["44100/16", "48000/16", "48000/24", "96000/24"]}

    def set_audio_format(self, device, value=None, raw_hex=None):
        self._maybe_fail("set_audio_format")
        self.audio_formats[device] = value if value is not None else raw_hex.split(":", 1)[1]

    def list_audio_pnp_devices(self):
        return copy.deepcopy(self.audio_pnp)

    def get_device_enabled(self, instance):
        return next((d["etkin"] for d in self.audio_pnp if d["ornek"] == instance), None)

    def set_device_enabled(self, instance, enabled):
        self._maybe_fail("set_device_enabled")
        next(d for d in self.audio_pnp if d["ornek"] == instance)["etkin"] = bool(enabled)

    def get_sleep_precision(self):
        return {"ortalama": 1.12, "p99": 1.9}

    def get_boot_info(self):
        return {"sure_sn": 24.5, "kaynak": "oturum_acma", "tur": "soguk"}

    def list_monitors(self):
        return [dict(copy.deepcopy(v), aygit=k) for k, v in self.monitors.items()]

    def find_display(self, monitor_path, fallback):
        return next((k for k, v in self.monitors.items() if v["monitor_yolu"] == monitor_path), fallback)

    def get_display_mode(self, device):
        return copy.deepcopy(self.monitors[device]["mod"])

    def set_display_mode(self, device, width, height, hz):
        self._maybe_fail("set_display_mode")
        mode = self.monitors[device]["mod"]
        if hz not in mode["modlar"].get(f"{width}x{height}", []):
            raise ValueError("desteklenmiyor")
        mode["cozunurluk"], mode["hz"] = f"{width}x{height}", hz

    def get_display_layout(self, device):
        return dict(self.monitors[device]["yerlesim"], aygit=device, birincil=self.monitors[device]["birincil"])

    def set_display_layout(self, device, x, y, orientation):
        from app.scan.hardware import layout_overlaps  # noqa: WPS433
        self._maybe_fail("set_display_layout")
        mon = self.monitors[device]
        me = mon["yerlesim"]
        if mon["birincil"]:
            x, y = me["x"], me["y"]
        width, height = me["genislik"], me["yukseklik"]
        if (me["yon"].startswith("dikey")) != orientation.startswith("dikey"):
            width, height = height, width
        others = [(o["yerlesim"]["x"], o["yerlesim"]["y"], o["yerlesim"]["genislik"], o["yerlesim"]["yukseklik"])
                  for k, o in self.monitors.items() if k != device]
        if layout_overlaps(others, (x, y, width, height)):
            raise ValueError("Ekranlar üst üste binemez")
        me.update(x=x, y=y, genislik=width, yukseklik=height, yon=orientation)

    def get_display_scale(self, device):
        return copy.deepcopy(self.monitors[device]["olcek"])

    def set_display_scale(self, device, percent):
        self._maybe_fail("set_display_scale")
        scale = self.monitors[device]["olcek"]
        if int(percent) not in scale["secenekler"]:
            raise ValueError("desteklenmiyor")
        scale["yuzde"] = int(percent)

    def get_display_refresh(self, device):
        return copy.deepcopy(self.displays.setdefault(device, {"hz": 60, "en_yuksek": 144, "hizlar": [60, 120, 144]}))

    def set_display_refresh(self, device, hz):
        self._maybe_fail("set_display_refresh")
        info = self.displays.setdefault(device, {"hz": 60, "en_yuksek": 144, "hizlar": [60, 120, 144]})
        if int(hz) not in info["hizlar"]:
            raise ValueError("desteklenmiyor")
        info["hz"] = int(hz)

    def delete_temp_files(self, folder):
        self._maybe_fail("delete_temp_files")
        self.temp_deleted.append(folder)
        return 3, 3 * 1024 * 1024

    def set_audio_service_restart(self):
        self.calls.append("audio_restart")

    def refresh_mouse(self):
        self.calls.append("refresh_mouse")

    def refresh_keyboard(self):
        self.calls.append("refresh_keyboard")

    # geri yükleme noktası --------------------------------------------------------
    def list_restore_points(self):
        return list(self.restore_points)

    def create_restore_point(self, description):
        if self.restore_mode == "fail":
            raise RuntimeError("Sistem Koruması kapalı")
        if self.restore_mode == "ok":
            self.restore_points.append({"Aciklama": description, "Zaman": "2026-10-22T12:00:00"})


class FakeResolver:
    """Koşulları hep doğru sayar; yer tutucuları 'TEST' değeriyle doldurur."""

    def check_condition(self, cond):
        return True

    def resolve(self, islem):
        names = resolvers.find_placeholders(islem)
        return resolvers.Resolution(True, [{n: "TEST" for n in names}])

    def expand_steps(self, islem, resolution):
        return resolvers.expand_steps(islem, resolution)
