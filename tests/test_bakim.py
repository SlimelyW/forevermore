"""Bakım araçları testleri (sfc/DISM/Optimize-Volume). GERÇEK sfc, DISM ya da Optimize-Volume ÇALIŞMAZ:
süreç çalıştırıcı sahtedir ve Popen sahte tutulur. Gerçek çalıştırma: docs/EL_TESTLERI.md son bölüm.

Çalıştırma: py -3.12 -m unittest tests.test_bakim -v
"""

import os
import sys
import threading
import time
import unittest
from unittest import mock

from app.core import powershell
from app.engine import bakim

SFC_TEMIZ = "Windows Resource Protection did not find any integrity violations."
SFC_ONARILDI = "Windows Resource Protection found corrupt files and successfully repaired them."
SFC_ONARILAMADI = "Windows Resource Protection found corrupt files but was unable to fix some of them."
SFC_TR_TEMIZ = "Windows Kaynak Koruması herhangi bir bütünlük ihlali bulamadı."


def _utf16(text):
    return text.encode("utf-16-le")


class Fake:
    """Sahte süreç çalıştırıcı: komut -> (çıkış kodu, bayt); çağrılan komutları kaydeder."""

    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def __call__(self, command, iptal, ilerleme=None):
        self.calls.append(command)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


class NoRealProcess(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(bakim.subprocess, "Popen", side_effect=AssertionError("gerçek süreç başlatılamaz"))
        patcher.start()
        self.addCleanup(patcher.stop)


class TestCikti(NoRealProcess):
    def test_decode_utf16_and_utf8(self):
        self.assertEqual(bakim.decode(_utf16("Doğrulama %5 tamamlandı")), "Doğrulama %5 tamamlandı")
        self.assertEqual(bakim.decode("Doğrulama".encode("utf-8")), "Doğrulama")
        self.assertEqual(bakim.decode(b""), "")
        self.assertEqual(bakim.decode(_utf16("abc") + b"\x00"), "abc")  # yarım kalan son bayt

    def test_percent_takes_last_and_ignores_garbage(self):
        self.assertEqual(bakim.yuzde("Verification 12% complete.\rVerification 45% complete."), 45)
        self.assertEqual(bakim.yuzde("Doğrulama %7 tamamlandı"), 7)
        self.assertEqual(bakim.yuzde("[==========  21.0%  ]"), 21)
        self.assertIsNone(bakim.yuzde("no numbers here"))
        self.assertIsNone(bakim.yuzde("Verification 250% complete."))

    def test_clean_collapses_progress_lines_and_limits_size(self):
        raw = "Starting.\r\nVerification 1% complete.\rVerification 2% complete.\rVerification 100% complete.\r\n\r\nDone."
        self.assertEqual(bakim.temizle(raw), "Starting.\nVerification 100% complete.\nDone.")
        self.assertLessEqual(len(bakim.temizle("x\n" * bakim.MAX_CIKTI)), bakim.MAX_CIKTI)

    def test_sfc_result_recognition(self):
        self.assertEqual(bakim.sfc_sonucu(SFC_TEMIZ), "temiz")
        self.assertEqual(bakim.sfc_sonucu(SFC_TR_TEMIZ), "temiz")
        self.assertEqual(bakim.sfc_sonucu(SFC_ONARILDI), "onarildi")
        self.assertEqual(bakim.sfc_sonucu(SFC_ONARILAMADI), "onarilamadi")
        self.assertEqual(bakim.sfc_sonucu("Windows Resource Protection could not perform the requested operation."), "onarilamadi")
        self.assertEqual(bakim.sfc_sonucu("tanınmayan dil çıktısı"), "belirsiz")  # tahmin yok
        self.assertEqual(bakim.sfc_sonucu(""), "belirsiz")


class TestSistemOnar(NoRealProcess):
    def run_repair(self, replies, admin=True, cancel_first=False):
        fake = Fake(replies)
        cancel = threading.Event()
        if cancel_first:
            cancel.set()
        steps = []
        result = bakim.sistem_onar(cancel, lambda *a: steps.append(a), fake, lambda: admin)
        return result, fake, steps

    def test_runs_fixed_commands_in_order(self):
        result, fake, steps = self.run_repair([(0, _utf16(SFC_TEMIZ)), (0, b"The restore operation completed successfully.")])
        system = powershell.SYSTEM32
        self.assertEqual(fake.calls, [[os.path.join(system, "sfc.exe"), "/scannow"],
                                      [os.path.join(system, "Dism.exe"), "/Online", "/Cleanup-Image", "/RestoreHealth"]])
        self.assertEqual(result["sonuc"], "temiz")
        self.assertIn("did not find any integrity violations", result["cikti"])
        self.assertIn("completed successfully", result["cikti"])
        self.assertEqual([s[:2] for s in steps], [(1, 2), (2, 2)])

    def test_overall_results(self):
        ok = (0, b"ok")
        cases = [((0, _utf16(SFC_ONARILDI)), ok, "onarildi"),
                 ((1, _utf16(SFC_ONARILAMADI)), ok, "tekrar"),            # DISM bileşenleri onardı, sfc tekrar gerekli
                 ((0, _utf16(SFC_TEMIZ)), (87, b"Error: 87"), "onarilamadi"),  # DISM hatası dilden bağımsız (çıkış kodu)
                 ((1, _utf16(SFC_ONARILAMADI)), (1, b"x"), "onarilamadi"),
                 ((0, b"bilinmeyen"), ok, "belirsiz")]
        for sfc, dism, expected in cases:
            result, _fake, _steps = self.run_repair([sfc, dism])
            self.assertEqual(result["sonuc"], expected, (sfc, dism))

    def test_cancel_stops_before_dism(self):
        result, fake, _ = self.run_repair([(None, b"Verification 3% complete.")])
        self.assertEqual(result["sonuc"], "iptal")
        self.assertEqual(len(fake.calls), 1)  # DISM hiç başlamadı
        result, fake, _ = self.run_repair([], cancel_first=True)
        self.assertEqual((result["sonuc"], fake.calls), ("iptal", []))

    def test_not_admin_runs_nothing(self):
        result, fake, _ = self.run_repair([], admin=False)
        self.assertEqual((result["sonuc"], fake.calls), ("yetki", []))

    def test_start_failure_is_reported(self):
        result, _fake, _ = self.run_repair([FileNotFoundError("sfc.exe")])
        self.assertEqual(result["sonuc"], "baslatilamadi")
        self.assertIn("sfc", result["cikti"])


class TestOptimize(NoRealProcess):
    DRIVES = [{"harf": "C", "tur": "SSD"}, {"harf": "D", "tur": "HDD"}, {"harf": "E", "tur": "bilinmiyor"}]

    def run_opt(self, letters, replies, admin=True, drives=None):
        fake = Fake(replies)
        cancel = threading.Event()
        result = bakim.optimize(letters, cancel, None, fake, lambda: drives or self.DRIVES, lambda: admin)
        return result, fake

    @staticmethod
    def script(command):
        return command[-1]

    def test_ssd_gets_trim_hdd_gets_defrag_never_crossed(self):
        result, fake = self.run_opt(["C", "D"], [(0, b"ok"), (0, b"ok")])
        self.assertEqual(result["sonuc"], "tamam")
        self.assertEqual([(d["harf"], d["islem"]) for d in result["suruculer"]], [("C", "trim"), ("D", "birlestir")])
        self.assertIn("Optimize-Volume -DriveLetter C -ReTrim", self.script(fake.calls[0]))
        self.assertNotIn("-Defrag", self.script(fake.calls[0]))
        self.assertIn("Optimize-Volume -DriveLetter D -Defrag", self.script(fake.calls[1]))
        self.assertNotIn("-ReTrim", self.script(fake.calls[1]))
        self.assertTrue(fake.calls[0][0].lower().endswith("powershell.exe"))

    def test_only_listed_known_type_drives_run(self):
        # Liste dışı harf, komut enjeksiyonu denemesi ve türü bilinmeyen sürücü çalıştırılmaz.
        result, fake = self.run_opt(["Z", "C; calc", "E", "c", "C"], [(0, b"ok")])
        self.assertEqual(len(fake.calls), 1)  # küçük harf "c" ve "C" aynı sürücü: bir kez
        self.assertEqual([d["harf"] for d in result["suruculer"]], ["C"])
        for call in fake.calls:
            self.assertNotIn("calc", self.script(call))
        result, fake = self.run_opt(["Z", "E"], [])
        self.assertEqual((result["sonuc"], fake.calls), ("yok", []))

    def test_partial_failure_and_total_failure(self):
        result, _ = self.run_opt(["C", "D"], [(0, b"ok"), (1, b"hata")])
        self.assertEqual(result["sonuc"], "kismen")
        self.assertEqual([d["tamam"] for d in result["suruculer"]], [True, False])
        result, _ = self.run_opt(["C"], [OSError("yok")])
        self.assertEqual(result["sonuc"], "hata")

    def test_cancel_and_admin(self):
        result, fake = self.run_opt(["C", "D"], [(None, b"")])
        self.assertEqual(result["sonuc"], "iptal")
        self.assertEqual(len(fake.calls), 1)
        result, fake = self.run_opt(["C"], [], admin=False)
        self.assertEqual((result["sonuc"], fake.calls), ("yetki", []))

    def test_drive_list_parsing_and_media_mapping(self):
        rows = [{"harf": "d", "tur": "HDD"}, {"harf": "C", "tur": "4"}, {"harf": "F", "tur": "Unspecified"},
                {"harf": "1", "tur": "SSD"}, {"harf": "CD", "tur": "SSD"}, {"harf": None, "tur": "SSD"}]
        with mock.patch.object(bakim.powershell, "run_json", return_value=rows):
            self.assertEqual(bakim.suruculer(), [{"harf": "C", "tur": "SSD"}, {"harf": "D", "tur": "HDD"},
                                                 {"harf": "F", "tur": "bilinmiyor"}])


class TestSurecKatmani(unittest.TestCase):
    """Gerçek süreç katmanı zararsız bir Python alt süreciyle denenir (sfc/DISM/PowerShell DEĞİL)."""

    def test_collects_output_and_exit_code_with_progress(self):
        seen = []
        code, data = bakim.calistir([sys.executable, "-c", "print('Verification 40% complete.'); import sys; sys.exit(3)"],
                                    threading.Event(), seen.append)
        self.assertEqual(code, 3)
        self.assertIn("40%", bakim.decode(data))
        self.assertIn(40, seen)

    def test_cancel_terminates_process(self):
        cancel = threading.Event()
        threading.Timer(0.8, cancel.set).start()
        started = time.monotonic()
        code, _data = bakim.calistir([sys.executable, "-c", "import time; time.sleep(60)"], cancel)
        self.assertIsNone(code)
        self.assertLess(time.monotonic() - started, 20)


if __name__ == "__main__":
    unittest.main()
