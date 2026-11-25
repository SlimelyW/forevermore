"""Katalog adayları (Grup A + C6): QOL-017, SYS-024, NET-010, SYS-025, SYS-026. Yaz / oku / geri al, yalnızca sahte sistemde.

Çalıştırma: py -3.12 -m unittest tests.test_katalog_adaylari -v
"""

import json
import unittest
from pathlib import Path

from tests.test_motor import BY_ID, EngineTestBase

ROOT = Path(__file__).resolve().parent.parent
TCPIP6 = (r"SYSTEM\CurrentControlSet\Services\Tcpip6\Parameters", "DisabledComponents")


class TestGrupA(EngineTestBase):
    def _apply(self, tweak_id):
        tweak = BY_ID[tweak_id]
        result = self.engine.set_enabled(tweak, True, confirmed=True)
        self.assertTrue(result.ok, result)
        self.assertEqual(self.engine.read_state(tweak).status, "acik")
        return tweak

    def test_baslat_onerilenler_ilkesi(self):
        path, name = r"Software\Policies\Microsoft\Windows\Explorer", "HideRecommendedSection"
        tweak = self._apply("QOL-017")
        self.assertEqual(self.sys.read_reg("HKCU", path, name), (1, "REG_DWORD"))
        self.assertTrue(self.engine.set_enabled(tweak, False).ok)
        self.assertIsNone(self.sys.read_reg("HKCU", path, name))  # değer yoktu: silinir
        self.assertEqual(self.engine.read_state(tweak).status, "kapali")

    def test_ayrintili_acilis_iletileri(self):
        path, name = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System", "VerboseStatus"
        tweak = self._apply("SYS-024")
        self.assertEqual(self.sys.read_reg("HKLM", path, name), (1, "REG_DWORD"))
        self.assertTrue(self.engine.revert(tweak["id"]).ok)
        self.assertIsNone(self.sys.read_reg("HKLM", path, name))

    def test_ipv4_tercih_eski_degeri_geri_getirir(self):
        """Önce başka bir araç IPv6'yı kapatmış olsun (255): ayar 0x20 yazar, geri alınca 255 döner."""
        self.sys.write_reg("HKLM", *TCPIP6, 255, "REG_DWORD")
        tweak = self._apply("NET-010")
        self.assertEqual(self.sys.read_reg("HKLM", *TCPIP6), (32, "REG_DWORD"))
        self.assertTrue(self.engine.revert(tweak["id"]).ok)
        self.assertEqual(self.sys.read_reg("HKLM", *TCPIP6), (255, "REG_DWORD"))

    def test_ipv4_tercih_ipv6_kapatmayla_karismaz(self):
        """İkisi aynı değeri yazar: 0x20 iken 'IPv6'yı kapat' açık görünmez, 0xFF iken 'IPv4'ü tercih et açık görünmez."""
        self._apply("NET-010")
        self.assertNotEqual(self.engine.read_state(BY_ID["PLC-015"]).status, "acik")
        self.sys.write_reg("HKLM", *TCPIP6, 255, "REG_DWORD")
        self.assertNotEqual(self.engine.read_state(BY_ID["NET-010"]).status, "acik")

    def test_kayit_yedegi_regback(self):
        path, name = r"System\CurrentControlSet\Control\Session Manager\Configuration Manager", "EnablePeriodicBackup"
        tweak = self._apply("SYS-026")  # Grup C6: kayıt yazdığı için Bakım kartında değil, motordan geçen ayar
        self.assertEqual(self.sys.read_reg("HKLM", path, name), (1, "REG_DWORD"))
        self.assertTrue(self.engine.revert(tweak["id"]).ok)
        self.assertIsNone(self.sys.read_reg("HKLM", path, name))

    def test_f8_menusu_bcd(self):
        self.sys.bcd["bootmenupolicy"] = "standard"
        tweak = self._apply("SYS-025")
        self.assertEqual(self.sys.bcd["bootmenupolicy"], "legacy")
        self.assertTrue(self.engine.revert(tweak["id"]).ok)
        self.assertEqual(self.sys.bcd["bootmenupolicy"], "standard")

    def test_f8_menusu_deger_yoksa_silinir(self):
        tweak = self._apply("SYS-025")
        self.assertTrue(self.engine.revert(tweak["id"]).ok)
        self.assertNotIn("bootmenupolicy", self.sys.bcd)


class TestGrupAVeri(unittest.TestCase):
    IDS = ("QOL-017", "SYS-024", "NET-010", "SYS-025", "SYS-026")

    def test_kaynak_yalnizca_microsoft_belgesi(self):
        for tweak_id in self.IDS:
            with self.subTest(tweak_id):
                sources = BY_ID[tweak_id]["kaynaklar"]
                self.assertTrue(sources)
                self.assertTrue(all(s.startswith("https://learn.microsoft.com/") for s in sources), sources)

    def test_sade_ad_aciklama_ve_ingilizce_var(self):
        en = json.loads((ROOT / "data" / "ceviriler" / "en.json").read_text(encoding="utf-8"))["ayarlar"]
        for tweak_id in self.IDS:
            with self.subTest(tweak_id):
                tweak = BY_ID[tweak_id]
                self.assertTrue(tweak.get("sade_ad"))
                self.assertTrue(tweak["ne_ise_yarar"])
                for key in ("ad", "sade_ad", "ne_ise_yarar"):
                    self.assertTrue(en[tweak_id].get(key), key)

    def test_ayarlar_winutil_atfi_gerektirmez(self):
        for tweak_id in self.IDS:
            self.assertNotIn("winutil", json.dumps(BY_ID[tweak_id]).lower(), tweak_id)


class TestKaynakDuzeltmeleri(unittest.TestCase):
    def test_fare_ve_tus_kaynaklari_dogru_sayfada(self):
        for tweak_id in ("INP-002", "INP-003"):
            self.assertEqual(BY_ID[tweak_id]["kaynaklar"], ["https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-mouse_event"])
        self.assertIn("ns-winuser-stickykeys", BY_ID["INP-007"]["kaynaklar"][0])
        self.assertIn("Manage_3D_Settings", BY_ID["GPU-005"]["kaynaklar"][0])

    def test_dogrulanamayan_cumleler_kalmadi(self):
        self.assertNotIn("rehberinde de geçer;", BY_ID["GPU-003"]["gerceklik"]["aciklama"].replace("kaldırıldı", ""))
        self.assertIn("belgede", BY_ID["GPU-001"]["gerceklik"]["aciklama"].replace("belgesinde", "belgede"))


if __name__ == "__main__":
    unittest.main()
