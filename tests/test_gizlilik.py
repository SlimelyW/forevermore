"""Gizlilik filtresi ve "internete bağlanma yok" kuralı kontrolleri.

Çalıştırma (proje klasöründe):
    py -3.12 -m unittest tests.test_gizlilik -v
"""

import os
import re
import unittest
from pathlib import Path
from unittest import mock

from app.core import privacy

ROOT = Path(__file__).resolve().parent.parent


class TestScrub(unittest.TestCase):
    def setUp(self):
        privacy._sensitive_words.cache_clear()
        self.env = mock.patch.dict(os.environ, {
            "USERNAME": "Kubil", "COMPUTERNAME": "MASAUSTU-ABC", "USERPROFILE": r"C:\Users\Kubil",
            "USERDOMAIN": "MASAUSTU-ABC",
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        privacy._sensitive_words.cache_clear()

    def check(self, text, expected):
        self.assertEqual(privacy.scrub_text(text), expected)

    def test_user_path(self):
        self.check(r"C:\Users\Kubil\AppData\Local", r"C:\Users\<KULLANICI>\AppData\Local")

    def test_username_and_computer_name(self):
        self.check("Kubil's AirPods", "<GIZLI>'s AirPods")
        self.check("MASAUSTU-ABC", "<GIZLI>")

    def test_word_boundary_keeps_normal_words(self):
        with mock.patch.dict(os.environ, {"USERNAME": "Ali"}):
            privacy._sensitive_words.cache_clear()
            self.assertEqual(privacy.scrub_text("Kalite ayarı"), "Kalite ayarı")

    def test_ip_mac(self):
        self.check("192.168.1.1", "<IP>")
        self.check("fe80::1c2b:3d4e%12", "<IP>")
        self.check("2001:db8:85a3:0:0:8a2e:370:7344", "<IP>")
        self.check("AA-BB-CC-DD-EE-FF", "<MAC>")

    def test_versions_and_times_untouched(self):
        for text in ("10.0.26300.1", "32.0.15.8157", "Durum: Up 12:34:56", "Saat 09:15"):
            self.check(text, text)

    def test_export_drops_local_only_fields(self):
        data = {"ad": "Kulaklık", "_yerel_ad": "Kubil's AirPods"}
        self.assertEqual(privacy.scrub(data), {"ad": "Kulaklık"})
        self.assertIn("_yerel_ad", privacy.scrub(data, export=False))

    def test_find_leaks(self):
        self.assertTrue(privacy.find_leaks({"x": "kubil"}))
        self.assertFalse(privacy.find_leaks(privacy.scrub({"x": "kubil 192.168.0.5"})))


class TestNoNetwork(unittest.TestCase):
    """Uygulama kodu internete bağlanmamalı. Tek istisna: uygulama güncellemesi (guncelleme.py; kullanıcı ilk soruda
    "evet" demedikçe bağlanmaz, veri göndermez)."""

    FORBIDDEN = re.compile(r"^\s*(?:import|from)\s+(socket|urllib|http|requests|ftplib|smtplib|httpx|aiohttp)\b", re.M)
    ALLOWED = {"app/core/guncelleme.py"}

    def test_no_network_imports(self):
        offenders = []
        for path in (ROOT / "app").rglob("*.py"):
            if self.FORBIDDEN.search(path.read_text(encoding="utf-8")) and \
                    path.relative_to(ROOT).as_posix() not in self.ALLOWED:
                offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])

    def test_update_client_talks_only_to_github_and_sends_nothing(self):
        text = (ROOT / "app" / "core" / "guncelleme.py").read_text(encoding="utf-8")
        self.assertEqual(text.count("urlopen("), 1)
        self.assertNotIn("data=", text)  # POST gövdesi yok: veri gönderilmez
        self.assertIn('API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"', text)
        self.assertEqual(set(re.findall(r"https?://([^/\s\"'{]+)", text)), {"api.github.com", "github.com"})

    def test_update_never_connects_before_the_user_chose(self):
        from app.core import settings
        self.assertIsNone(settings.DEFAULTS["guncelleme_denetle"])  # None = sorulmadı; yalnızca True bağlanır


if __name__ == "__main__":
    unittest.main()


class TestAntivirusTriggers(unittest.TestCase):
    """1.4: kötü amaçlı yazılımı andıran çağrı biçimleri uygulamada olmasın."""

    def test_no_bypass_or_encoded_powershell(self):
        root = Path(__file__).resolve().parent.parent / "app"
        found = [str(path.relative_to(root)) for path in root.rglob("*.py")
                 if re.search(r'"Bypass"|EncodedCommand|-enc|FromBase64String', path.read_text(encoding="utf-8"))]
        self.assertEqual(found, [])

    def test_powershell_command_line(self):
        from app.core import powershell
        with mock.patch("subprocess.run") as run:
            run.return_value = mock.Mock(returncode=0, stdout=b"", stderr=b"")
            powershell.run("Get-Date")
        args = run.call_args[0][0]
        self.assertNotIn("-ExecutionPolicy", args)
        self.assertEqual(args[:3], ["powershell.exe", "-NoProfile", "-NonInteractive"])

    def test_shared_cache_runs_once_under_threads(self):
        import threading
        import time
        from app.engine import resolvers
        calls = []

        @resolvers._shared_cache  # noqa: SLF001
        def slow():
            calls.append(1)
            time.sleep(0.05)
            return 1
        threads = [threading.Thread(target=slow) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(calls), 1)
