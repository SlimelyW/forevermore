"""B1: Store ve Windows uygulamalarını geri yükleme (sahte PowerShell; sistemde hiçbir şey değişmez)."""

import unittest

from app.core import powershell
from app.engine import store_restore


def status_with(installed, manifest=None):
    return lambda: {"paketler": [{"ad": "Microsoft.WindowsStore", "kurulu": installed, "manifest": manifest}]}


class TestRestore(unittest.TestCase):
    def test_register_then_verify(self):
        calls, state = [], {"kurulu": False}

        def run(command, timeout):
            calls.append(command)
            state["kurulu"] = True

        info = {"manifest": r"C:\Program Files\WindowsApps\Store\AppxManifest.xml", "saglanmis": True}
        result = store_restore.restore("Microsoft.WindowsStore", info, 19045, run=run,
                                       read=lambda: {"paketler": [{"ad": "Microsoft.WindowsStore", **state}]})
        self.assertTrue(result["basarili"])
        self.assertEqual(result["yontemler"], ["Add-AppxPackage -Register"])  # Windows 10: wsreset -i yok
        self.assertIn("-DisableDevelopmentMode -Register 'C:\\Program Files", calls[0])

    def test_windows11_tries_wsreset_first(self):
        calls = []
        result = store_restore.restore("Microsoft.WindowsStore", {"manifest": None, "saglanmis": False}, 26100,
                                       run=lambda c, _t: calls.append(c), read=status_with(False),
                                       sleep=lambda _s: None, wait_seconds=20)
        self.assertIn("wsreset.exe", calls[0])
        self.assertFalse(result["basarili"])
        self.assertEqual(result["neden"], "dosya_yok")  # dosyalar silinmiş: sahte başarı yok

    def test_registration_error_is_reported(self):
        def run(_command, _timeout):
            raise powershell.PowerShellError("0x80073CF9 AppX Deployment hatası")
        result = store_restore.restore("Microsoft.WindowsCalculator", {"manifest": "C:\\x\\AppxManifest.xml"},
                                       19045, run=run, read=lambda: {"paketler": []})
        self.assertEqual((result["basarili"], result["neden"]), (False, "kayit_hatasi"))
        self.assertIn("0x80073CF9", result["hata"])

    def test_problems_detect_disabled_services(self):
        data = {"servisler": [{"ad": "wuauserv", "durum": "Stopped", "baslangic": "Disabled"},
                              {"ad": "AppXSvc", "durum": "yok", "baslangic": None}], "dagitim_hatasi_24s": 3}
        keys = [k for k, _p in store_restore.problems(data)]
        self.assertEqual(keys, ["store_geri.uyari.wu_kapali", "store_geri.uyari.appx_yok"])
        self.assertIn("store_geri.uyari.appx_hata", [k for k, _p in store_restore.problems(data, failed=True)])

    def test_problems_detect_failing_appx_service(self):
        """3.3: hizmet var ve El ile ama başlatılamıyor (test sistemi): geri yüklemeden önce gösterilir."""
        data = {"servisler": [{"ad": "AppXSvc", "durum": "Stopped", "baslangic": "Manual"}], "appx_hizmet_hatasi_7g": 4}
        self.assertEqual(store_restore.problems(data), [("store_geri.uyari.appx_hizmet_hata", {"adet": 4})])
        self.assertEqual(store_restore.problems(dict(data, appx_hizmet_hatasi_7g=0)), [])

    def test_status_script_lists_every_package(self):
        seen = {}

        def run(script, timeout):
            seen["script"] = script
            return {"derleme": 19045, "paketler": {"ad": "Microsoft.WindowsStore", "kurulu": True},
                    "servisler": [], "dagitim_hatasi_24s": 0}
        data = store_restore.status(run=run)
        for name in store_restore.NAMES:
            self.assertIn(f"'{name}'", seen["script"])
        self.assertEqual(data["paketler"][0]["anahtar"], "store")  # tek nesne listeye çevrildi


if __name__ == "__main__":
    unittest.main()
