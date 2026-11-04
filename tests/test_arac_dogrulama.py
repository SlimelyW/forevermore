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
