"""3.1: Sistem Koruması durumu ve açılması (sahte PowerShell; sistemde hiçbir şey değişmez)."""

import unittest

from app.core import powershell
from app.engine import restore_point, system_protection as sp

GB = sp.GB


def data(**over):
    base = {"surucu": "C:", "ilke_kapali": False, "ilke_ayar_kapali": False, "acik": False, "siklik_dk": 1440,
            "boyut": 512 * GB, "bos": 200 * GB, "golge_sinir": None,
            "servisler": [{"ad": "VSS", "durum": "Stopped", "baslangic": "Manual"},
                          {"ad": "swprv", "durum": "Stopped", "baslangic": "Manual"}]}
    base.update(over)
    return base


def point(status):
    return lambda _system: restore_point.RestorePointResult(status, "2026-10-31T12:00")


class TestLimit(unittest.TestCase):
    def test_limit_follows_disk_and_free_space(self):
        self.assertEqual(sp.limit_gb(512 * GB, 200 * GB), 15)    # %5 = 25.6 -> 15 GB tavan
        self.assertEqual(sp.limit_gb(128 * GB, 100 * GB), 6)     # %5 = 6.4
        self.assertEqual(sp.limit_gb(512 * GB, 20 * GB), 4)      # boş alanın %20'si
        self.assertIsNone(sp.limit_gb(512 * GB, 5 * GB))         # 1 GB: yer yok, açılmaz
        self.assertIsNone(sp.limit_gb(None, None))


class TestBlocker(unittest.TestCase):
    def test_group_policy_is_never_forced(self):
        self.assertEqual(sp.blocker(data(ilke_kapali=True)), "ilke")
        self.assertEqual(sp.blocker(data(ilke_ayar_kapali=True)), "ilke_ayar")

    def test_missing_service_and_full_disk(self):
        self.assertEqual(sp.blocker(data(servisler=[{"ad": "VSS", "durum": "yok", "baslangic": None}])), "servis_yok")
        self.assertEqual(sp.blocker(data(bos=GB)), "disk")
        self.assertIsNone(sp.blocker(data()))


class TestEnable(unittest.TestCase):
    def test_enable_sets_limit_and_verifies_point(self):
        calls = []
        res = sp.enable(None, data(servisler=[{"ad": "VSS", "durum": "Stopped", "baslangic": "Disabled"},
                                              {"ad": "swprv", "durum": "Stopped", "baslangic": "Manual"}]),
                        run=lambda c, _t: calls.append(c), read=lambda: data(acik=True, golge_sinir=15 * GB),
                        ensure=point(restore_point.RestorePointResult.CREATED))
        self.assertTrue(res["basarili"])
        self.assertTrue(res["nokta"].ok)
        self.assertIn("Set-Service -Name VSS -StartupType Manual", calls[0])   # yalnızca devre dışı olan
        self.assertIn("Enable-ComputerRestore -Drive 'C:\\'", calls[1])
        self.assertIn("/maxsize=15GB", calls[2])
        self.assertIn(("sinir", True, "15.0 GB"), res["adimlar"])

    def test_not_counted_when_readback_still_off(self):
        res = sp.enable(None, data(), run=lambda c, _t: None, read=lambda: data(acik=False),
                        ensure=point(restore_point.RestorePointResult.CREATED))
        self.assertFalse(res["basarili"])
        self.assertEqual(res["neden"], "dogrulanamadi")
        self.assertIsNone(res["nokta"])  # açık görünmüyorsa nokta da denenmez

    def test_enable_error_is_reported(self):
        def run(command, _t):
            if "Enable-ComputerRestore" in command:
                raise powershell.PowerShellError("0x80070422")
        res = sp.enable(None, data(), run=run, read=lambda: data(acik=True), ensure=point("olusturuldu"))
        self.assertFalse(res["basarili"])
        self.assertEqual(res["neden"], "ac")
        self.assertIn(("ac", False, "0x80070422"), res["adimlar"])

    def test_frequency_limit_skip_is_explained(self):
        """Windows sıklık sınırı noktayı hatasız atlar: liste değişmez -> 'siklik' (0 dk ise başka sebep)."""
        failed = point(restore_point.RestorePointResult.FAILED)
        res = sp.enable(None, data(), run=lambda c, _t: None, read=lambda: data(acik=True, golge_sinir=15 * GB),
                        ensure=failed)
        self.assertTrue(res["basarili"])
        self.assertEqual(res["neden"], "siklik")
        res = sp.enable(None, data(), run=lambda c, _t: None,
                        read=lambda: data(acik=True, golge_sinir=15 * GB, siklik_dk=0), ensure=failed)
        self.assertEqual(res["neden"], "nokta")

    def test_limit_failure_does_not_block(self):
        def run(command, _t):
            if "vssadmin" in command:
                raise powershell.PowerShellError("vssadmin 2")
        res = sp.enable(None, data(), run=run, read=lambda: data(acik=True), ensure=point("olusturuldu"))
        self.assertTrue(res["basarili"])
        self.assertIn(("sinir", False, "vssadmin 2"), res["adimlar"])


class TestStatus(unittest.TestCase):
    def test_missing_frequency_means_windows_default(self):
        got = sp.status(run=lambda _s, _t: {"servisler": {"ad": "VSS"}, "siklik_dk": None})
        self.assertEqual(got["siklik_dk"], 1440)
        self.assertEqual(got["servisler"], [{"ad": "VSS"}])


if __name__ == "__main__":
    unittest.main()
