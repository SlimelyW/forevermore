"""Ayar motoru testleri. Gerçek bilgisayara DOKUNMAZ; tests/fake_system.py
içindeki sahte Windows üzerinde çalışır.

Çalıştırma (proje klasöründe):
    py -3.12 -m unittest tests.test_motor -v
"""

import copy
import datetime
import json
import tempfile
import unittest
from pathlib import Path

from app.engine import compat, handlers, profiles, resolvers, restore_point
from app.engine.backup import BackupStore
from app.engine.engine import Engine
from tests.fake_system import FakeResolver, FakeSystem

ROOT = Path(__file__).resolve().parent.parent
CATALOG = json.loads((ROOT / "data" / "tweaks_app.json").read_text(encoding="utf-8"))
BY_ID = {t["id"]: t for t in CATALOG["ayarlar"]}
DESKTOP = compat.SystemProfile("11", 26300, "masaustu", ["NVIDIA", "AMD", "Intel"], True)
LAPTOP = compat.SystemProfile("11", 26300, "laptop", ["NVIDIA", "AMD", "Intel"], True)


def make_tweak(steps, risk="güvenli", **extra):
    tweak = {
        "id": "TEST-001", "ad": "Test", "sinif": "SWITCH", "risk": risk, "onay_gerekli": risk == "dikkatli",
        "gerceklik": {"durum": "gerçek"}, "yeniden_baslatma_kodu": "yok",
        "uyumluluk": {"windows": {"surumler": ["10", "11"], "min_build": {}},
                      "form": {"masaustu": "goster", "laptop": "goster"}, "gpu": None, "kosullar": []},
        "islem": {"kontrol": "switch", "adimlar": steps},
    }
    tweak.update(extra)
    return tweak


def reg_step(name="Deger", on=1, off=None, missing=None, path=r"Software\Test", **extra):
    step = {"tur": "registry", "kok": "HKCU", "yol": path, "ad": name, "veri_turu": "REG_DWORD",
            "acik": on, "kapali": off, "yoksa": missing}
    step.update(extra)
    return step


class EngineTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sys = FakeSystem()
        self.engine = self.new_engine()
        self.engine.prepare()

    def tearDown(self):
        self.tmp.cleanup()

    def new_engine(self, profile=DESKTOP, admin=True):
        return Engine(system=self.sys, store=BackupStore(Path(self.tmp.name)), profile=profile,
                      resolver=FakeResolver(), is_admin=lambda: admin)


class TestApplyRevert(EngineTestBase):
    def test_apply_then_revert_restores_absent_value(self):
        tweak = make_tweak([reg_step()])
        before = self.sys.state_copy()
        result = self.engine.set_enabled(tweak, True)
        self.assertTrue(result.ok, result)
        self.assertEqual(self.sys.read_reg("HKCU", r"Software\Test", "Deger"), (1, "REG_DWORD"))
        self.assertEqual(self.engine.read_state(tweak).status, "acik")
        self.assertTrue(self.engine.set_enabled(tweak, False).ok)
        self.assertEqual(self.sys.reg, before[0])
        self.assertFalse(self.engine.store.has("TEST-001"))

    def test_wlan_autoconfig_apply_and_revert(self):
        guid = next(iter(self.sys.wlan))
        step = {"tur": "yerlesik", "eylem": "wlan_otomatik_yapilandirma", "parametreler": {},
                "acik": "Disabled", "kapali": "Enabled"}
        tweak = make_tweak([step])
        self.assertTrue(self.engine.set_enabled(tweak, True).ok)
        self.assertEqual(self.sys.wlan[guid], "Disabled")
        self.assertEqual(self.engine.read_state(tweak).status, "acik")
        self.assertTrue(self.engine.revert(tweak["id"]).ok)
        self.assertEqual(self.sys.wlan[guid], "Enabled")

    def test_first_backup_kept_across_toggles(self):
        self.sys.write_reg("HKCU", r"Software\Test", "Deger", 7, "REG_DWORD")
        tweak = make_tweak([reg_step(off=0)])
        self.engine.set_enabled(tweak, True)
        self.engine.store.remove  # yedek duruyor
        # Kullanıcı başka bir araçla değeri değiştirse bile yedek ilk hâli tutar
        self.sys.write_reg("HKCU", r"Software\Test", "Deger", 3, "REG_DWORD")
        self.engine.set_enabled(tweak, True)
        self.engine.revert("TEST-001")
        self.assertEqual(self.sys.read_reg("HKCU", r"Software\Test", "Deger"), (7, "REG_DWORD"))

    def test_already_on_writes_nothing(self):
        self.sys.write_reg("HKCU", r"Software\Test", "Deger", 1, "REG_DWORD")
        self.sys.calls.clear()
        result = self.engine.set_enabled(make_tweak([reg_step()]), True)
        self.assertEqual(result.key, "sonuc.zaten")
        self.assertNotIn("write_reg", self.sys.calls)

    def test_rollback_when_a_step_fails(self):
        tweak = make_tweak([reg_step("A"), {"tur": "servis", "ad": "Svc",
                                            "acik": {"baslangic": "Disabled", "calisiyor": False},
                                            "kapali": {"baslangic": "Automatic", "calisiyor": True}}])
        self.sys.fail_on.add("set_service")
        result = self.engine.set_enabled(tweak, True)
        self.assertFalse(result.ok)
        self.assertEqual(result.key, "hata.yetki")
        self.assertIsNone(self.sys.read_reg("HKCU", r"Software\Test", "A"))  # ilk adım geri alındı

    def test_failed_first_apply_leaves_no_backup(self):
        """Bu bilgisayarda görülen hata: yazma reddedilince yedek kaydı kalmamalı."""
        self.sys.fail_on.add("write_reg")
        result = self.engine.set_enabled(make_tweak([reg_step()]), True)
        self.assertEqual(result.key, "hata.yetki")
        self.assertFalse(self.engine.store.has("TEST-001"))
        self.assertEqual(self.engine.changed_ids(), [])

    def test_failed_reapply_keeps_original_backup(self):
        tweak = make_tweak([reg_step("A"), reg_step("B")])
        self.engine.set_enabled(make_tweak([reg_step("A")]), True)  # TEST-001 yedeği oluştu
        self.sys.fail_on.add("write_reg")
        self.engine.set_enabled(tweak, True)
        self.assertTrue(self.engine.store.has("TEST-001"))  # önceki gerçek yedek silinmemeli

    def test_backup_is_on_disk_before_write(self):
        self.engine.set_enabled(make_tweak([reg_step()]), True)
        reloaded = BackupStore(Path(self.tmp.name))
        self.assertTrue(reloaded.has("TEST-001"))

    def test_revert_all_newest_first(self):
        t1 = make_tweak([reg_step("A")], id="T1")
        t2 = make_tweak([reg_step("B")], id="T2")
        self.engine.set_enabled(t1, True)
        self.engine.set_enabled(t2, True)
        results = self.engine.revert_all()
        self.assertTrue(all(r.ok for _, r in results))
        self.assertEqual(self.sys.reg, {})

    def test_off_without_backup_uses_off_values_and_backs_up(self):
        self.sys.write_reg("HKCU", r"Software\Test", "Deger", 1, "REG_DWORD")
        tweak = make_tweak([reg_step(off=0)])
        self.assertTrue(self.engine.set_enabled(tweak, False).ok)
        self.assertEqual(self.sys.read_reg("HKCU", r"Software\Test", "Deger")[0], 0)
        self.engine.revert("TEST-001")
        self.assertEqual(self.sys.read_reg("HKCU", r"Software\Test", "Deger")[0], 1)


class TestSafetyRules(EngineTestBase):
    def test_careful_requires_confirmation(self):
        tweak = make_tweak([reg_step()], risk="dikkatli")
        self.assertEqual(self.engine.set_enabled(tweak, True).key, "hata.onay_gerekli")
        self.assertTrue(self.engine.set_enabled(tweak, True, confirmed=True).ok)

    def test_forbidden_and_info_never_applied(self):
        for tweak in (make_tweak([reg_step()], id="PLC-020"),  # yasaklı liste: veri ne derse desin
                      make_tweak([reg_step()], sinif="BILGI")):
            self.assertEqual(self.engine.set_enabled(tweak, True, confirmed=True).key, "hata.izin_yok")
        self.assertEqual(self.sys.reg, {})

    def test_placebo_switch_allowed(self):
        tweak = make_tweak([reg_step()], gerceklik={"durum": "placebo"})
        self.assertTrue(self.engine.set_enabled(tweak, True).ok)

    def test_risky_needs_confirmation_both_ways(self):
        tweak = make_tweak([reg_step()], risk="riskli", onay_seviyesi=2)
        self.assertEqual(self.engine.set_enabled(tweak, True).key, "hata.onay_gerekli")
        self.assertTrue(self.engine.set_enabled(tweak, True, confirmed=True).ok)
        self.assertEqual(self.engine.set_enabled(tweak, False).key, "hata.onay_gerekli")
        self.assertEqual(self.engine.revert("TEST-001").key, "hata.onay_gerekli")
        self.assertTrue(self.engine.set_enabled(tweak, False, confirmed=True).ok)
        self.assertEqual(self.sys.reg, {})

    def test_careful_needs_confirmation_only_when_enabling(self):
        tweak = make_tweak([reg_step()], risk="dikkatli", onay_seviyesi=1)
        self.engine.set_enabled(tweak, True, confirmed=True)
        self.assertTrue(self.engine.set_enabled(tweak, False).ok)

    def test_off_only_cannot_turn_on_but_can_turn_off(self):
        step = reg_step(on=None, off=100, acik_kosulu={"kucuk": 100})
        tweak = make_tweak([step])
        tweak["islem"]["yalnizca_kapat"] = True
        self.assertEqual(self.engine.read_state(tweak).status, "kapali")
        self.assertEqual(self.engine.set_enabled(tweak, True).key, "hata.yalnizca_kapatilabilir")
        self.sys.write_reg("HKCU", r"Software\Test", "Deger", 20, "REG_DWORD")  # zararlı ayar uygulanmış
        self.assertEqual(self.engine.read_state(tweak).status, "acik")
        self.assertTrue(self.engine.set_enabled(tweak, False).ok)
        self.assertEqual(self.sys.read_reg("HKCU", r"Software\Test", "Deger")[0], 100)
        self.engine.revert("TEST-001")
        self.assertEqual(self.sys.read_reg("HKCU", r"Software\Test", "Deger")[0], 20)

    def test_missing_service_is_skipped(self):
        steps = [{"tur": "servis", "ad": name, "yoksa_atla": True,
                  "acik": {"baslangic": "Disabled", "calisiyor": False},
                  "kapali": {"baslangic": "Manual", "calisiyor": None}} for name in ("Var", "Yok")]
        self.sys.services["Var"] = {"baslangic": "Manual", "calisiyor": False}
        self.sys.get_service = (lambda orig: lambda n: None if n == "Yok" else orig(n))(self.sys.get_service)
        tweak = make_tweak(steps)
        self.assertTrue(self.engine.set_enabled(tweak, True).ok)
        self.assertEqual(self.engine.read_state(tweak).status, "acik")
        self.assertEqual(self.sys.services["Var"]["baslangic"], "Disabled")

    def test_computed_ram_value(self):
        step = reg_step(on={"hesapla": "toplam_ram_kb"}, off=3670016, missing=3670016)
        tweak = make_tweak([step])
        self.engine.set_enabled(tweak, True)
        self.assertEqual(self.sys.read_reg("HKCU", r"Software\Test", "Deger")[0], self.sys.ram_kb)
        self.assertEqual(self.engine.read_state(tweak).status, "acik")

    def test_one_shot_action(self):
        tweak = BY_ID["PLC-023"]
        result = self.engine.run_action(tweak, "temp")
        self.assertTrue(result.ok)
        self.assertTrue(self.sys.temp_deleted)
        self.assertEqual(self.engine.changed_ids(), [])  # geri alınamaz; değişiklik kaydına girmez

    def test_dns_selection_and_revert(self):
        tweak = BY_ID["PLC-014"]
        self.assertEqual(self.engine.read_state(tweak).values, {"dns": "otomatik"})
        self.assertTrue(self.engine.set_selection(tweak, {"dns": "cloudflare"}).ok)
        self.assertEqual(self.sys.dns["TEST"]["sunucular"], ["1.1.1.1", "1.0.0.1"])
        self.assertEqual(self.engine.read_state(tweak).values, {"dns": "cloudflare"})
        self.engine.revert("PLC-014")
        self.assertTrue(self.sys.dns["TEST"]["otomatik"])

    def test_display_refresh_to_max_and_back(self):
        tweak = BY_ID["DISP-001"]
        self.assertEqual(self.engine.read_state(tweak).status, "kapali")
        self.assertTrue(self.engine.set_enabled(tweak, True).ok)
        self.assertEqual(self.sys.displays["TEST"]["hz"], 144)
        self.assertEqual(self.engine.read_state(tweak).status, "acik")
        self.assertTrue(self.engine.set_enabled(tweak, False).ok)  # yedekten önceki Hz'e döner
        self.assertEqual(self.sys.displays["TEST"]["hz"], 60)

    def test_display_refresh_has_no_off_target_without_backup(self):
        tweak = BY_ID["DISP-001"]
        self.sys.displays["TEST"] = {"hz": 144, "en_yuksek": 144, "hizlar": [60, 144]}
        self.assertFalse(self.engine.set_enabled(tweak, False).ok)
        self.assertEqual(self.sys.displays["TEST"]["hz"], 144)

    def test_custom_change_startup_item_and_revert(self):
        step = {"tur": "yerlesik", "eylem": "baslangic_onayi", "parametreler": {"kok": "HKCU", "yol": "A", "ad": "X"}}
        result = self.engine.apply_custom("BAS-1", "Başlangıç: X", [step], [False])
        self.assertTrue(result.ok)
        self.assertTrue(self.sys.approved[("HKCU", "A", "X")].startswith("03"))
        self.assertTrue(self.engine.store.has("BAS-1"))
        self.assertTrue(self.engine.revert("BAS-1").ok)
        self.assertNotIn(("HKCU", "A", "X"), self.sys.approved)  # değer hiç yoktu: silindi

    def test_custom_change_service_and_revert(self):
        self.sys.services["Foo"] = {"baslangic": "Automatic", "calisiyor": True}
        step = {"tur": "servis", "ad": "Foo"}
        self.assertTrue(self.engine.apply_custom("SRV-Foo", "Servis: Foo", [step],
                                                 [{"baslangic": "Disabled", "calisiyor": False}]).ok)
        self.assertEqual(self.sys.services["Foo"], {"baslangic": "Disabled", "calisiyor": False})
        self.engine.revert("SRV-Foo")
        self.assertEqual(self.sys.services["Foo"], {"baslangic": "Automatic", "calisiyor": True})

    def test_custom_risky_change_needs_confirmation(self):
        step = reg_step()
        self.assertEqual(self.engine.apply_custom("MSI-1", "MSI", [step], [1], level=2).key, "hata.onay_gerekli")
        self.assertTrue(self.engine.apply_custom("MSI-1", "MSI", [step], [1], level=2, confirmed=True,
                                                 related="GPU-018").ok)
        self.assertEqual(self.engine.stored_related("MSI-1"), "GPU-018")
        self.assertEqual(self.engine.revert("MSI-1").key, "hata.onay_gerekli")
        self.assertTrue(self.engine.revert("MSI-1", confirmed=True).ok)

    def test_custom_change_rolls_back_on_failure(self):
        self.sys.fail_on.add("set_device_power")
        step = {"tur": "yerlesik", "eylem": "cihaz_guc", "parametreler": {"ornek": "USB1"}}
        self.assertFalse(self.engine.apply_custom("GUC-1", "Güç", [step], [False]).ok)
        self.assertFalse(self.engine.store.has("GUC-1"))  # hiçbir şey değişmedi, yedek kaydı da kalmadı

    def test_power_setting_on_battery_is_separate(self):
        tweak = BY_ID["PWR-003"]
        variant = copy.deepcopy(tweak)
        variant["id"] = "PWR-003@pil"
        for step in variant["islem"]["adimlar"]:
            step["kaynak"] = "dc"
        engine = self.new_engine(LAPTOP)
        engine.prepare()
        self.assertTrue(engine.set_enabled(variant, True).ok)
        self.assertTrue(any(len(k) == 4 for k in self.sys.power))  # yalnızca pilde değeri yazıldı
        self.assertFalse(any(len(k) == 3 for k in self.sys.power))
        self.assertTrue(engine.revert("PWR-003@pil").ok)

    def test_nvidia_setting_and_revert_to_driver_default(self):
        step = {"tur": "yerlesik", "eylem": "nvidia_drs", "parametreler": {"ayar": "0x00CE2691"}}
        self.assertTrue(self.engine.apply_custom("GPU-004", "Doku", [step], [20]).ok)
        self.assertEqual(self.sys.nvidia[0x00CE2691], 20)
        self.assertTrue(self.engine.revert("GPU-004").ok)
        self.assertNotIn(0x00CE2691, self.sys.nvidia)  # özelleştirilmemişti: sürücü varsayılanına döndü

    def test_nvidia_setting_revert_keeps_previous_custom_value(self):
        self.sys.nvidia[0x00A879CF] = 138504007
        step = {"tur": "yerlesik", "eylem": "nvidia_drs", "parametreler": {"ayar": "0x00A879CF"}}
        self.engine.apply_custom("GPU-006", "VSync", [step], [1199655232])
        self.engine.revert("GPU-006")
        self.assertEqual(self.sys.nvidia[0x00A879CF], 138504007)

    def test_audio_format_and_revert(self):
        step = {"tur": "yerlesik", "eylem": "ses_bicimi", "parametreler": {"cihaz": "{abc}"}}
        self.assertTrue(self.engine.apply_custom("SESB-1", "Ses", [step], ["48000/24"]).ok)
        self.assertEqual(self.sys.audio_formats["{abc}"], "48000/24")
        self.engine.revert("SESB-1")
        self.assertEqual(self.sys.audio_formats["{abc}"], "48000/16")

    def test_custom_change_runs_after_actions(self):
        step = reg_step()
        result = self.engine.apply_custom("SESG-1", "Ses", [step], [1], after=["ses_servisini_yeniden_baslat"])
        self.assertTrue(result.ok)
        self.assertIn("audio_restart", self.sys.calls)

    def test_every_new_change_kind_is_listed_and_revert_all_restores(self):
        """Kapanış doğrulaması: revizyonda eklenen her değişiklik türü yedeklenir, listelenir ve geri alınır."""
        from app.engine import managers
        from app.games import profiles
        self.sys.services["Foo"] = {"baslangic": "Automatic", "calisiyor": True}
        self.sys.nvidia[0x00A879CF] = 138504007
        # Gerçek Windows'ta bu üst anahtarlar zaten vardır; geri alma boş anahtar silmez.
        self.sys._add_key("HKCU", profiles.GPU_KEY)
        self.sys._add_key("HKCU", profiles.LAYERS_KEY)
        before = self.sys.state_copy()
        reg = lambda root, path, name, kind="REG_DWORD": {"tur": "registry", "kok": root, "yol": path, "ad": name,
                                                          "veri_turu": kind, "acik": None, "kapali": None, "yoksa": None}
        changes = [
            ("BAS-1", {"tur": "yerlesik", "eylem": "baslangic_onayi",
                       "parametreler": {"kok": "HKCU", "yol": "A", "ad": "X"}}, False),
            ("GRV-1", {"tur": "yerlesik", "eylem": "zamanlanmis_gorev", "parametreler": {"yol": "/", "ad": "G"}},
             "Disabled"),
            ("SRV-Foo", {"tur": "servis", "ad": "Foo"}, {"baslangic": "Disabled", "calisiyor": False}),
            ("MSI-1", reg("HKLM", managers.msi_key("PCI/X"), "MSISupported"), 1),
            ("GUC-1", {"tur": "yerlesik", "eylem": "cihaz_guc", "parametreler": {"ornek": "USB1"}}, False),
            ("GPU-006", {"tur": "yerlesik", "eylem": "nvidia_drs", "parametreler": {"ayar": "0x00A879CF"}}, 1199655232),
            ("GPU-004", {"tur": "yerlesik", "eylem": "nvidia_drs", "parametreler": {"ayar": "0x00CE2691"}}, 20),
            ("SESB-1", {"tur": "yerlesik", "eylem": "ses_bicimi", "parametreler": {"cihaz": "C"}}, "48000/24"),
            ("DISP-001", {"tur": "yerlesik", "eylem": "ekran_yenileme", "parametreler": {"aygit": "TEST"}}, "144"),
            ("OYUN-1-oncelik", reg("HKLM", profiles.IFEO + r"\o.exe\PerfOptions", "CpuPriorityClass"), 6),
            ("OYUN-1-gpu", reg("HKCU", profiles.GPU_KEY, "C:/o.exe", "REG_SZ"), "GpuPreference=2;"),
            ("OYUN-1-fso", reg("HKCU", profiles.LAYERS_KEY, "C:/o.exe", "REG_SZ"), "~ " + profiles.FSO_FLAG),
        ]
        for change_id, step, value in changes:
            self.assertTrue(self.engine.apply_custom(change_id, change_id, [step], [value], confirmed=True).ok, change_id)
        for tweak_id in ("PERF-005", "PWR-002", "DISP-004"):
            self.assertTrue(self.engine.set_enabled(BY_ID[tweak_id], True, confirmed=True).ok, tweak_id)
        listed = set(self.engine.changed_ids())
        self.assertTrue({c[0] for c in changes} | {"PERF-005", "PWR-002", "DISP-004"} <= listed)
        self.assertNotEqual(self.sys.state_copy(), before)
        results = self.engine.revert_all()
        self.assertTrue(all(r.ok for _i, r in results), [(i, r.key) for i, r in results if not r.ok])
        self.assertEqual(self.engine.changed_ids(), [])
        self.assertEqual(self.sys.state_copy(), before)

    def test_requires_admin(self):
        engine = self.new_engine(admin=False)
        engine.prepare()
        self.assertEqual(engine.set_enabled(make_tweak([reg_step()]), True).key, "hata.yonetici_gerekli")

    def test_requires_prepare_and_restore_point_consent(self):
        self.sys = FakeSystem()  # henüz geri yükleme noktası olmayan bir bilgisayar
        engine = self.new_engine()
        self.assertEqual(engine.set_enabled(make_tweak([reg_step()]), True).key, "hata.hazirlik_gerekli")
        self.sys.restore_mode = "fail"
        self.assertFalse(engine.prepare().ok)
        self.assertEqual(engine.set_enabled(make_tweak([reg_step()]), True).key, "hata.geri_yukleme_noktasi_yok")
        engine.accept_without_restore_point()
        self.assertTrue(engine.set_enabled(make_tweak([reg_step()]), True).ok)
        strict = make_tweak([reg_step("Siki")], id="TEST-002", geri_yukleme_zorunlu=True)
        self.assertEqual(engine.set_enabled(strict, True).key, "hata.geri_yukleme_zorunlu")
        self.assertEqual(self.sys.read_reg("HKCU", r"Software\Test", "Siki"), None)

    def test_spectre_visible_but_needs_restore_point(self):
        self.assertTrue(BY_ID["CPU-004"]["geri_yukleme_zorunlu"])
        self.assertEqual(BY_ID["CPU-004"]["uyumluluk"]["kosullar"], [])

    def test_hidden_tweak_not_applied(self):
        tweak = make_tweak([reg_step()])
        tweak["uyumluluk"]["form"] = {"masaustu": "gizle", "laptop": "goster"}
        self.assertEqual(self.engine.set_enabled(tweak, True).key, "hata.uygun_degil")


class TestStepTypes(EngineTestBase):
    def test_flag_keeps_other_tokens(self):
        path = r"Software\Microsoft\DirectX\UserGpuPreferences"
        self.sys.write_reg("HKCU", path, "DirectXUserGlobalSettings", "SwapEffectUpgradeEnable=1;", "REG_SZ")
        tweak = make_tweak([{"tur": "registry_bayrak", "kok": "HKCU", "yol": path, "ad": "DirectXUserGlobalSettings",
                             "anahtar": "VRROptimizeEnable", "acik": "1", "kapali": "0", "yoksa": "0"}])
        self.engine.set_enabled(tweak, True)
        self.assertEqual(self.sys.read_reg("HKCU", path, "DirectXUserGlobalSettings")[0],
                         "SwapEffectUpgradeEnable=1;VRROptimizeEnable=1;")
        self.engine.revert("TEST-001")
        self.assertEqual(self.sys.read_reg("HKCU", path, "DirectXUserGlobalSettings")[0], "SwapEffectUpgradeEnable=1;")

    def test_bit_keeps_other_bits(self):
        path = r"Control Panel\Accessibility\StickyKeys"
        self.sys.write_reg("HKCU", path, "Flags", "510", "REG_SZ")
        tweak = make_tweak([{"tur": "registry_bit", "kok": "HKCU", "yol": path, "ad": "Flags",
                             "veri_turu": "REG_SZ", "maske": 4, "acik": 0, "kapali": 4}])
        self.engine.set_enabled(tweak, True)
        self.assertEqual(self.sys.read_reg("HKCU", path, "Flags")[0], "506")
        self.sys.write_reg("HKCU", path, "Flags", "498", "REG_SZ")  # başka bir bit sonradan değişti
        self.engine.revert("TEST-001")
        self.assertEqual(self.sys.read_reg("HKCU", path, "Flags")[0], "502")  # yalnızca bizim bit geri geldi

    def test_key_create_and_delete(self):
        clsid = r"Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}"
        tweak = make_tweak([{"tur": "registry_anahtar", "kok": "HKCU", "yol": clsid + r"\InprocServer32",
                             "silinecek_yol": clsid, "varsayilan_deger": "", "acik": "var", "kapali": "yok"}])
        self.engine.set_enabled(tweak, True)
        self.assertTrue(self.sys.get_key_exists("HKCU", clsid + r"\InprocServer32"))
        self.engine.revert("TEST-001")
        self.assertFalse(self.sys.get_key_exists("HKCU", clsid))

    def test_powercfg_plan_default_and_custom_plan(self):
        step = {"tur": "powercfg", "alt_grup": "54533251-82be-4824-96c1-47b60b740d00",
                "ayar": "893dee8e-2bef-41e0-89c6-b55d0929964c", "acik": 100, "kapali": "plan_varsayilani"}
        key = (self.sys.active_scheme, step["alt_grup"], step["ayar"])
        self.sys.power[key] = 100
        self.sys.power_defaults[key] = 5
        self.assertTrue(self.engine.set_enabled(make_tweak([step]), False).ok)
        self.assertEqual(self.sys.power[key], 5)
        self.sys.active_scheme = "11111111-2222-3333-4444-555555555555"  # özel plan
        self.sys.power[(self.sys.active_scheme, step["alt_grup"], step["ayar"])] = 100
        result = self.engine.set_enabled(make_tweak([step], id="T2"), False)
        self.assertEqual(result.key, "hata.plan_varsayilani_yok")

    def test_selection_validates_and_reverts(self):
        tweak = BY_ID["INP-006"]
        self.assertEqual(self.engine.set_selection(tweak, {"gecikme": "9"}).key, "hata.gecersiz_deger")
        self.sys.write_reg("HKCU", r"Control Panel\Keyboard", "KeyboardDelay", "1", "REG_SZ")
        self.assertTrue(self.engine.set_selection(tweak, {"gecikme": "0", "hiz": "31"}).ok)
        self.assertEqual(self.engine.read_state(tweak).values, {"gecikme": "0", "hiz": "31"})
        self.assertIn("refresh_keyboard", self.sys.calls)
        self.engine.revert("INP-006")
        self.assertEqual(self.sys.read_reg("HKCU", r"Control Panel\Keyboard", "KeyboardDelay"), ("1", "REG_SZ"))
        self.assertIsNone(self.sys.read_reg("HKCU", r"Control Panel\Keyboard", "KeyboardSpeed"))


class TestUnreadablePreviousValue(EngineTestBase):
    """Denetim A B1: önceki değer okunamazsa (None) yazılmaz; eski yedekte None varsa geri alma "başarılı" demez."""
    STEP = {"tur": "yerlesik", "eylem": "cihaz_guc", "parametreler": {"ornek": "USB1"}, "acik": False, "kapali": True}

    def setUp(self):
        super().setUp()
        self.sys.get_device_power = lambda instance: None  # ör. aygıt eşlenemedi, okuma boş döndü

    def test_switch_refuses_to_write(self):
        result = self.engine.set_enabled(make_tweak([dict(self.STEP)]), True)
        self.assertEqual(result.key, "hata.deger_yok")
        self.assertNotIn("USB1", self.sys.device_power)
        self.assertFalse(self.engine.store.has("TEST-001"))

    def test_custom_refuses_to_write(self):
        result = self.engine.apply_custom("GUC-1", "Güç", [dict(self.STEP)], [False])
        self.assertEqual(result.key, "hata.deger_yok")
        self.assertNotIn("USB1", self.sys.device_power)
        self.assertFalse(self.engine.store.has("GUC-1"))

    def test_revert_of_old_backup_with_none_keeps_backup(self):
        self.sys.device_power["USB1"] = False  # eski sürüm None ile yedekleyip yazmıştı
        self.engine.store.save_first("GUC-1", "Güç", [{"adim": dict(self.STEP), "anlik": {"deger": None}}])
        result = self.engine.revert("GUC-1")
        self.assertFalse(result.ok)
        self.assertEqual(result.key, "hata.geri_alma_kismen")
        self.assertTrue(self.engine.store.has("GUC-1"))


class TestAfterWriteFailures(EngineTestBase):
    """Denetim A B3: yazma bitti; doğrulama okuması ya da işlem geçmişi hata verirse sonuç yine 'uygulandı'."""

    def test_verify_read_failure_is_a_warning(self):
        tweak = make_tweak([reg_step()])
        real, calls = self.sys.read_reg, []

        def read_reg(*args):
            calls.append(args)
            if len(calls) > 1:  # ilk okuma anlık görüntü, sonraki doğrulama
                raise PermissionError("zaman aşımı")
            return real(*args)
        self.sys.read_reg = read_reg
        result = self.engine.set_enabled(tweak, True)
        self.assertTrue(result.ok, result)
        self.assertIn(("uyari.dogrulanamadi", {}), result.warnings)

    def test_history_write_failure_is_not_an_error(self):
        self.engine.store.history_path = Path(self.tmp.name)  # klasör: açılamaz
        self.assertTrue(self.engine.set_enabled(make_tweak([reg_step()]), True).ok)
        self.assertTrue(self.engine.revert("TEST-001").ok)


class TestWindowsServiceCheck(unittest.TestCase):
    def test_systemroot_env_is_not_trusted(self):
        """Denetim A S1 (managers.py): ezilmiş SystemRoot, yabancı servisi "Windows servisi" yapmamalı."""
        import os
        from unittest import mock
        from app.core import powershell
        from app.engine import managers
        windows = os.path.dirname(powershell.SYSTEM32)
        with mock.patch.dict(os.environ, {"SystemRoot": r"C:\Users\x\kotu"}):
            self.assertFalse(managers._is_windows_service(r"C:\Users\x\kotu\svc.exe"))
            self.assertTrue(managers._is_windows_service(os.path.join(windows, "svc.exe")))


class TestRealCatalogRoundTrip(EngineTestBase):
    """Veritabanındaki HER switch: aç → eski haline getir → sistem birebir aynı."""

    def test_every_switch_round_trips(self):
        for tweak in CATALOG["ayarlar"]:
            if tweak["sinif"] != "SWITCH" or tweak["islem"]["kontrol"] != "switch":
                continue
            with self.subTest(tweak=tweak["id"]):
                self.sys = FakeSystem()
                profile = LAPTOP if tweak["uyumluluk"]["form"]["masaustu"] == "gizle" else DESKTOP
                engine = self.new_engine(profile)
                engine.prepare()
                off_only = tweak["islem"].get("yalnizca_kapat")
                # Her ayarı "kapalı" durumdan başlat ki uygulama gerçekten bir şey yazsın.
                # Yalnızca kapatılabilenlerde tersine: zararlı ayar "uygulanmış" olarak başlar.
                for step in resolvers.expand_steps(tweak["islem"], FakeResolver().resolve(tweak["islem"])):
                    if step["tur"] == "registry_bit":  # bit işlemleri mevcut bir değer ister
                        self.sys.write_reg(step["kok"], step["yol"], step["ad"], "6", step["veri_turu"])
                    if step["tur"] == "registry_anahtar":  # gerçek Windows'ta üst anahtar (CLSID) hep vardır
                        self.sys._add_key(step["kok"], step["silinecek_yol"].rpartition("\\")[0])
                    if off_only:
                        if step["tur"] == "registry":
                            self.sys.write_reg(step["kok"], step["yol"], step["ad"], 20, step["veri_turu"])
                        else:
                            self.sys.bcd[step["parametreler"]["eleman"]] = "2"
                    elif step.get("kapali") is not None or step["tur"] != "yerlesik":
                        # (Kapalı hedefi olmayan yerleşik adımlarda sahte sistemin varsayılanı kullanılır.)
                        handlers.apply(self.sys, step, "kapali", handlers.snapshot(self.sys, step))
                before = self.sys.state_copy()
                result = engine.set_enabled(tweak, not off_only, confirmed=True)
                self.assertTrue(result.ok, f"{tweak['id']}: {result.key}")
                self.assertEqual(engine.read_state(tweak).status, "kapali" if off_only else "acik")
                self.assertTrue(engine.revert(tweak["id"], confirmed=True).ok)
                self.assertEqual(self.sys.state_copy(), before)


class TestCompat(unittest.TestCase):
    def test_windows_and_form_and_gpu(self):
        tweak = make_tweak([reg_step()])
        tweak["uyumluluk"]["windows"] = {"surumler": ["11"], "min_build": {"11": 22631}}
        old = compat.SystemProfile("11", 22621, "masaustu", ["AMD"], True)
        self.assertEqual(compat.check(tweak, old, FakeResolver()).reasons[0][0], "uyum.windows_build")
        tweak["uyumluluk"]["windows"]["min_build"] = {}
        tweak["uyumluluk"]["gpu"] = ["NVIDIA"]
        self.assertEqual(compat.check(tweak, old, FakeResolver()).reasons[0][0], "uyum.gpu")

    def test_smbios_chassis_parsing(self):
        """Kasa türü PowerShell'siz okunur (arayüz donmasın); tip 3'ün 5. baytı, üst bit (kilit) atılır."""
        import struct
        bios = bytes([0, 6, 0, 0, 1, 2]) + b"Ven\0\0"            # tip 0, metinler
        enclosure = bytes([3, 9, 1, 0, 1, 0x8A, 0, 0, 0]) + b"\0\0"  # tip 3, kasa 10 (+kilit biti)
        end = bytes([127, 4, 2, 0]) + b"\0\0"
        table = bios + enclosure + end
        raw = bytes([0, 3, 4, 0]) + struct.pack("<I", len(table)) + table
        self.assertEqual(compat.chassis_types(raw), [10])
        self.assertEqual(compat.chassis_types(bytes(8)), [])

    def test_other_admin_account_hides_user_settings(self):
        other = compat.SystemProfile("11", 26300, "masaustu", ["AMD"], same_account=False)
        self.assertFalse(compat.check(make_tweak([reg_step()]), other, FakeResolver()).visible)
        hklm = make_tweak([dict(reg_step(), kok="HKLM")])
        self.assertTrue(compat.check(hklm, other, FakeResolver()).visible)


class TestProfiles(unittest.TestCase):
    def test_real_profiles_valid(self):
        data = json.loads((ROOT / "data" / "profiller.json").read_text(encoding="utf-8"))
        self.assertEqual(profiles.validate(data, BY_ID), [])

    def test_careful_cannot_be_preselected(self):
        data = {"profiller": [{"id": "x", "ayarlar": [{"id": "SYS-001", "secili": True}]}]}
        self.assertTrue(profiles.validate(data, BY_ID))

    def test_inheritance(self):
        data = json.loads((ROOT / "data" / "profiller.json").read_text(encoding="utf-8"))["profiller"]
        ids = [i["id"] for i in profiles.expand(data, "dikkatli")]
        self.assertIn("PERF-001", ids)  # guvenli'den
        self.assertIn("DISP-002", ids)  # oyun'dan
        self.assertIn("SYS-001", ids)


class TestRestorePoint(unittest.TestCase):
    def test_statuses(self):
        system = FakeSystem()
        self.assertEqual(restore_point.ensure(system).status, "olusturuldu")
        system.restore_mode = "silent"  # Windows 24 saat sınırı: yeni nokta oluşmadı
        now = datetime.datetime.fromisoformat("2026-10-22T18:00:00")
        self.assertEqual(restore_point.ensure(system, now).status, "mevcut_24s")
        system.restore_mode = "fail"
        later = datetime.datetime.fromisoformat("2026-10-25T18:00:00")
        self.assertEqual(restore_point.ensure(system, later).status, "basarisiz")


if __name__ == "__main__":
    unittest.main()
