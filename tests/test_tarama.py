"""Tarama modülünün sistemden bağımsız (saf) fonksiyonlarının kontrolleri.

Sistemde hiçbir şey okumaz veya değiştirmez; örnek verilerle çalışır.

Çalıştırma (proje klasöründe):
    py -3.12 -m unittest tests.test_tarama -v
"""

import json
import re
import unittest
from pathlib import Path

from app.scan import findings
from app.scan.hardware import analyze_ram
from app.scan.peripherals import parse_wave_format

ROOT = Path(__file__).resolve().parent.parent
TR = json.loads((ROOT / "lang" / "tr.json").read_text(encoding="utf-8"))


class TestWaveFormat(unittest.TestCase):
    def test_extensible_96k_24bit(self):
        # Bu bilgisayardaki gerçek bir kulaklıktan alınan değerin başı
        blob = bytes.fromhex("4100000001000000" "feff0200" "00770100" "00b80b00" "0800" "2000" "1600" "1800" "03000000")
        self.assertEqual(parse_wave_format(blob), {"hz": 96000, "bit": 24, "kanal": 2})

    def test_48k_16bit(self):
        blob = bytes.fromhex("4100000001000000feff020080bb000000ee02000400100016001000030000000000")
        self.assertEqual(parse_wave_format(blob), {"hz": 48000, "bit": 16, "kanal": 2})

    def test_garbage(self):
        self.assertIsNone(parse_wave_format(b"\x00" * 10))
        self.assertIsNone(parse_wave_format(None))


class TestInputDeviceIds(unittest.TestCase):
    def test_vid_pid_usb_and_bluetooth(self):
        from app.scan.input_devices import vid_pid
        self.assertEqual(vid_pid(r"HID\VID_19F5&PID_6120&MI_00\7&abc&0&0000"), ("19F5", "6120"))
        self.assertEqual(vid_pid(r"HID\{00001124-0000-1000-8000-00805f9b34fb}_VID&0002046d_PID&b023\9&1"),
                         ("046D", "B023"))
        self.assertEqual(vid_pid(r"ACPI\PNP0303\4&1"), (None, None))

    def test_generic_names_are_not_real_names(self):
        from app.scan.input_devices import _is_generic
        self.assertTrue(_is_generic("USB Input Device"))
        self.assertTrue(_is_generic("HID-compliant mouse"))
        self.assertFalse(_is_generic("NuPhy Air75 HE"))


class TestDisplayLabel(unittest.TestCase):
    def test_edid_name_or_honest_fallback(self):
        from app.core import i18n
        from app.scan.displays import edid_code, label
        i18n.load("tr")
        self.assertEqual(label({"monitor": "VG27WQ1B", "uretici_adi": "ASUS"}, 2), "ASUS VG27WQ1B")
        self.assertEqual(label({"monitor": "", "dahili": True, "uretici_adi": "AU Optronics", "uretici_kodu": "AUO",
                                "urun_kodu": "56AD"}, 1), "Dahili ekran (AU Optronics, AUO 56AD)")
        self.assertEqual(label({"monitor": "Generic PnP Monitor"}, 3), "Ekran 3")
        # EDID üretici kodu: "AUS" = 0x06B3 (EDID'de büyük sonlu: B3 06 olarak okunur)
        self.assertEqual(edid_code(0xB306, 0x27E0), ("AUS", "27E0"))


class TestGpuLinking(unittest.TestCase):
    """Windows'un yüksek performans / güç tasarrufu rolü ve sürülen ekranlar kartlara doğru bağlanır."""

    def test_two_gpus(self):
        from app.scan.hardware import link_gpus
        gpus = [{"ad": "AMD Radeon(TM) 880M Graphics"}, {"ad": "NVIDIA GeForce RTX 5070 Laptop GPU"}]
        adapters = [
            {"ad": "NVIDIA GeForce RTX 5070 Laptop GPU", "vram_mb": 7891, "ekranlar": [r"\\.\DISPLAY6"],
             "yuksek_performans": True, "guc_tasarrufu": False},
            {"ad": "AMD Radeon(TM) 880M Graphics", "vram_mb": 512, "ekranlar": [r"\\.\DISPLAY1"],
             "yuksek_performans": False, "guc_tasarrufu": True}]
        displays = [{"aygit": r"\\.\DISPLAY1", "birincil": False}, {"aygit": r"\\.\DISPLAY6", "birincil": True}]
        link_gpus(gpus, adapters, displays)
        amd, nvidia = gpus
        self.assertEqual(nvidia["rol"], "yuksek_performans")
        self.assertTrue(nvidia["birincil_ekran"])
        self.assertEqual(amd["rol"], "guc_tasarrufu")
        self.assertEqual(amd["ekran_suruyor"], [r"\\.\DISPLAY1"])
        self.assertEqual([d["gpu_rol"] for d in displays], ["guc_tasarrufu", "yuksek_performans"])

    def test_hybrid_dxgi_reports_internal_panel_under_dgpu(self):
        """A7 (HP Victus): DXGI DISPLAY1'i NVIDIA altında gösterse de ekranı AMD sürüyor (EnumDisplayDevices)."""
        from app.scan.hardware import link_gpus
        gpus = [{"ad": "AMD Radeon(TM) Graphics"}, {"ad": "NVIDIA GeForce RTX 4060 Laptop GPU"}]
        adapters = [
            {"ad": "NVIDIA GeForce RTX 4060 Laptop GPU", "vram_mb": 8188, "ekranlar": [r"\\.\DISPLAY1"],
             "yuksek_performans": True, "guc_tasarrufu": False},
            {"ad": "AMD Radeon(TM) Graphics", "vram_mb": 512, "ekranlar": [r"\\.\DISPLAY1"],
             "yuksek_performans": False, "guc_tasarrufu": True}]
        displays = [{"aygit": r"\\.\DISPLAY1", "birincil": True, "ekran_karti": "AMD Radeon(TM) Graphics"}]
        link_gpus(gpus, adapters, displays)
        amd, nvidia = gpus
        self.assertEqual(amd["ekran_suruyor"], [r"\\.\DISPLAY1"])
        self.assertEqual(nvidia["ekran_suruyor"], [])
        self.assertEqual(nvidia["rol"], "yuksek_performans")  # oyunları çizen kart
        self.assertEqual(displays[0]["gpu_rol"], "guc_tasarrufu")

    def test_hybrid_report_and_scaling_agree_with_driving_card(self):
        """2.8: rapor NVIDIA'yı 'oyunları çizer, ekran sürmüyor' diye yazar; AMD'nin sürdüğü ekranda NVAPI sorulmaz."""
        from unittest import mock

        from app.core.i18n import t
        from app.engine import nvidia
        from app.engine.system import WindowsSystem
        from app.scan.report import _hardware
        gpu = {"ad": "NVIDIA GeForce RTX 4060 Laptop GPU", "surucu_surumu": "1", "surucu_tarihi": "-",
               "uretici": "NVIDIA", "rol": "yuksek_performans", "ekran_suruyor": []}
        hw = {"bilgisayar": {"uretici": "HP", "model": "Victus", "tur": "dizustu"},
              "cpu": {"ad": "R5", "cekirdek": 6, "is_parcacigi": 12}, "gpu": [gpu], "ram": {},
              "anakart": {"uretici": "-", "model": "-", "bios_surumu": "-", "bios_tarihi": "-"}, "ekranlar": []}
        lines = []
        _hardware(lines, hw)
        self.assertIn(t("rapor.gpu_rol_ekran_yok"), "\n".join(lines))
        amd_panel = [{"aygit": r"\\.\DISPLAY1", "ekran_karti": "AMD Radeon(TM) Graphics"}]
        with mock.patch("app.scan.hardware.collect_displays", return_value=amd_panel), \
                mock.patch.object(nvidia, "get_scaling", return_value=7) as nv, \
                mock.patch.object(WindowsSystem, "nvidia_available", return_value=True), \
                mock.patch.object(WindowsSystem, "_amd_display", return_value=None):
            self.assertIsNone(WindowsSystem.__new__(WindowsSystem).get_display_scaling(r"\\.\DISPLAY1"))
            nv.assert_not_called()

    def test_single_and_unknown(self):
        from app.scan.hardware import link_gpus
        gpus = [{"ad": "Intel UHD"}, {"ad": "Bilinmeyen"}]
        link_gpus(gpus, [{"ad": "Intel UHD", "vram_mb": 128, "ekranlar": [], "yuksek_performans": True,
                          "guc_tasarrufu": True}], [])
        self.assertEqual(gpus[0]["rol"], "tek")
        self.assertIsNone(gpus[1]["rol"])
        self.assertEqual(link_gpus([], [], []), None)


class TestRam(unittest.TestCase):
    def module(self, **kw):
        base = {"Capacity": 16 * 1024 ** 3, "Speed": 3600, "ConfiguredClockSpeed": 2133,
                "SMBIOSMemoryType": 26, "FormFactor": 8, "DeviceLocator": "DIMM_A1", "BankLabel": "BANK 0"}
        base.update(kw)
        return base

    def test_single_module_single_channel(self):
        self.assertEqual(analyze_ram([self.module()])["kanal"], "tek")

    def test_dual_channel_from_labels(self):
        r = analyze_ram([self.module(BankLabel="P0 CHANNEL A"), self.module(BankLabel="P0 CHANNEL B")])
        self.assertEqual(r["kanal"], "cift_veya_fazla")

    def test_desktop_ddr4_at_jedec_flags_xmp(self):
        r = analyze_ram([self.module(), self.module(DeviceLocator="DIMM_B1")])
        self.assertEqual(r["xmp_expo"], "kapali_olabilir")
        self.assertTrue(r["modul_hizinin_altinda"])

    def test_laptop_memory_no_xmp_claim(self):
        r = analyze_ram([self.module(FormFactor=12, SMBIOSMemoryType=34, Speed=5600, ConfiguredClockSpeed=5600)])
        self.assertEqual(r["xmp_expo"], "laptop_uygulanmaz")


class TestFindings(unittest.TestCase):
    def test_low_refresh_and_full_disk(self):
        scan = {"bolumler": {
            "sistem": {"yonetici": True, "windows": {"surum": "11"}, "bellek": {}},
            "donanim": {"ekranlar": [{"monitor": "M", "ekran_karti": "G", "yenileme_hz": 60,
                                      "bu_cozunurlukte_en_yuksek_hz": 144}]},
            "depolama": {"birimler": [{"surucu": "C:", "doluluk_yuzde": 95, "bos_gb": 5.0, "boyut_gb": 100}]},
        }, "tespitler": []}
        result = findings.build(scan)
        codes = [f["kod"] for f in result]
        self.assertIn("ekran_hz_dusuk", codes)
        self.assertIn("disk_dolu", codes)
        self.assertEqual(result[0]["seviye"], "sorun")
        disk = next(f for f in result if f["kod"] == "disk_dolu")
        TR["bulgu.disk_dolu.aciklama"].format(**disk["params"])  # tüm yer tutucular dolu olmalı

    def test_every_finding_code_has_text(self):
        source = (ROOT / "app" / "scan" / "findings.py").read_text(encoding="utf-8")
        codes = set(re.findall(r'_f\("([a-z0-9_]+)"', source))
        codes |= set(re.findall(r'\("[a-z_]+", "([a-z0-9_]+)", "(?:sorun|uyari|bilgi)"', source))
        missing = [c for c in sorted(codes)
                   if f"bulgu.{c}.baslik" not in TR or f"bulgu.{c}.aciklama" not in TR]
        self.assertEqual(missing, [])


class TestNvidiaBar1(unittest.TestCase):
    def test_parses_bar1_total_per_gpu(self):
        from unittest import mock
        from app.scan import hardware
        out = "\n".join(["GPU 0", "    FB Memory Usage", "        Total : 8151 MiB", "    BAR1 Memory Usage",
                         "        Total : 8192 MiB", "        Used : 1 MiB", "GPU 1", "    BAR1 Memory Usage",
                         "        Total : 256 MiB"])
        proc = mock.Mock(returncode=0, stdout=out.encode())
        with mock.patch.object(hardware.subprocess, "run", return_value=proc):
            self.assertEqual(hardware._nvidia_bar1(), [8192, 256])
        with mock.patch.object(hardware.subprocess, "run", return_value=mock.Mock(returncode=1, stdout=b"")):
            self.assertEqual(hardware._nvidia_bar1(), [])


if __name__ == "__main__":
    unittest.main()
