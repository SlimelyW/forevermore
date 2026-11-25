"""Üçüncü parti araç doğrulaması (SECURITY.md F2 #1): sistemde hiçbir şey çalıştırmaz."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.engine import driver_tools, nvidia
from app.measure import presentmon


class ToolVerifyTest(unittest.TestCase):
    def test_npi_refuses_a_file_that_changed_after_approval(self):
        with tempfile.TemporaryDirectory() as folder:
            exe = Path(folder, "nvidiaProfileInspector.exe")
            exe.write_bytes(b"onaylanan")
            approved = driver_tools.sha256_file(exe)
            exe.write_bytes(b"degistirilmis")
            with mock.patch.object(nvidia, "npi_path", return_value=exe), \
                    mock.patch.object(nvidia.subprocess, "run", side_effect=AssertionError("çalıştırılmamalı")):
                with self.assertRaises(OSError):
                    nvidia.npi_import([(1, 1)], expected_sha256=approved)

    def test_npi_ice_aktarma_dosyasi_korumali_klasore_yazilir_ve_silinir(self):
        """Denetim A2 O7: yönetici olarak okunacak .nip kullanıcının yazabildiği %TEMP%'te durmaz, iş bitince silinir."""
        seen = {}
        with tempfile.TemporaryDirectory() as protected, tempfile.TemporaryDirectory() as folder:
            exe = Path(folder, "nvidiaProfileInspector.exe")
            exe.write_bytes(b"x")

            def fake_run(args, **_kw):
                seen["nip"] = args[-1]
                seen["var"] = Path(args[-1]).is_file()
                return mock.Mock(returncode=0)
            with mock.patch.object(nvidia, "npi_path", return_value=exe),                     mock.patch.object(nvidia.paths, "protected_work_dir", return_value=Path(protected)),                     mock.patch.object(nvidia.subprocess, "run", side_effect=fake_run):
                nvidia.npi_import([(1, 1)])
            self.assertTrue(seen["var"])
            self.assertTrue(Path(seen["nip"]).is_relative_to(protected))
            self.assertFalse(Path(seen["nip"]).parent.exists())  # klasör bırakılmadı

    def test_presentmon_refuses_a_file_that_changed_after_approval(self):
        with tempfile.TemporaryDirectory() as folder:
            exe = Path(folder, "PresentMon.exe")
            exe.write_bytes(b"onaylanan")
            approved = driver_tools.sha256_file(exe)
            exe.write_bytes(b"degistirilmis")
            with mock.patch.object(presentmon.subprocess, "run", side_effect=AssertionError("çalıştırılmamalı")):
                with self.assertRaises(OSError):
                    presentmon.capture("oyun.exe", 30, str(exe), approved)

    def test_tools_in_user_folder(self):
        home = Path.home()
        with mock.patch.object(driver_tools.paths, "tools_dir", return_value=home / "Downloads" / "Forevermore" / "tools"):
            self.assertTrue(driver_tools.tools_in_user_folder())
        with mock.patch.object(driver_tools.paths, "tools_dir", return_value=Path(r"C:\Program Files\Forevermore\tools")):
            self.assertFalse(driver_tools.tools_in_user_folder())


if __name__ == "__main__":
    unittest.main()
