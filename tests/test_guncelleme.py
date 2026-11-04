"""Uygulama güncellemesi (app/core/guncelleme.py): sürüm denetimi, güvenli açma, imza/sürüm doğrulama.
Ağ yok: sahte `get`; paketler testte üretilen geçici anahtarla imzalanır."""

import json
import secrets
import tempfile
import unittest
import zipfile
from pathlib import Path

from app.core import ed25519, guncelleme, integrity

URL = guncelleme.DOWNLOAD_PREFIX + "2.1.0/Forevermore.zip"


def release(tag="2.1.0", url=URL, name="Forevermore.zip"):
    return json.dumps({"tag_name": tag, "assets": [{"name": name, "browser_download_url": url, "size": 5}]}).encode()


class TestKontrol(unittest.TestCase):
    def test_newer_version_found(self):
        info = guncelleme.kontrol(lambda url, *a: release(), current="2.0.0")
        self.assertEqual((info["surum"], info["url"]), ("2.1.0", URL))

    def test_same_or_older_is_none(self):
        self.assertIsNone(guncelleme.kontrol(lambda url, *a: release("2.0.0"), current="2.0.0"))
        self.assertIsNone(guncelleme.kontrol(lambda url, *a: release("v1.9.9"), current="2.0.0"))

    def test_version_compares_numerically(self):
        self.assertIsNotNone(guncelleme.kontrol(lambda url, *a: release("2.10.0"), current="2.9.0"))

    def test_prerelease_orders_below_its_release(self):
        self.assertIsNone(guncelleme.kontrol(lambda url, *a: release("2.2.0-beta.1"), current="2.2.0-beta.1"))
        self.assertIsNotNone(guncelleme.kontrol(lambda url, *a: release("2.2.0-beta.2"), current="2.2.0-beta.1"))
        self.assertIsNotNone(guncelleme.kontrol(lambda url, *a: release("2.2.0"), current="2.2.0-beta.1"))
        self.assertIsNone(guncelleme.kontrol(lambda url, *a: release("2.2.0-beta.1"), current="2.2.0"))
        self.assertIsNotNone(guncelleme.kontrol(lambda url, *a: release("2.2.0-beta.1"), current="2.1.2"))

    def test_foreign_download_host_rejected(self):
        with self.assertRaises(guncelleme.GuncellemeHatasi):
            guncelleme.kontrol(lambda url, *a: release(url="https://evil.example/Forevermore.zip"), current="2.0.0")

    def test_missing_asset_and_garbage(self):
        with self.assertRaises(guncelleme.GuncellemeHatasi):
            guncelleme.kontrol(lambda url, *a: release(name="baska.zip"), current="2.0.0")
        with self.assertRaises(guncelleme.GuncellemeHatasi):
            guncelleme.kontrol(lambda url, *a: b"not json", current="2.0.0")
        with self.assertRaises(guncelleme.GuncellemeHatasi):
            guncelleme.kontrol(lambda url, *a: release("sürüm"), current="2.0.0")

    def test_download_url_must_be_release_asset(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(guncelleme.GuncellemeHatasi):
            guncelleme.indir("https://evil.example/x.zip", Path(tmp) / "a.zip", lambda *a: b"x")


class TestHazirla(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.secret = secrets.token_bytes(32)
        self.public = ed25519.public_key(self.secret).hex()
        self.addCleanup(self.tmp.cleanup)

    def build_zip(self, version="2.1.0", secret=None, tamper=None, extra=None, exe=True):
        src = self.dir / "src" / "Forevermore"
        (src / "_internal").mkdir(parents=True, exist_ok=True)
        if exe:
            (src / "Forevermore.exe").write_bytes(b"exe")
        (src / "_internal" / "veri.txt").write_text("v", encoding="utf-8")
        manifest = integrity.build_manifest(src, version)
        sig = ed25519.sign(secret or self.secret, integrity.canonical(manifest))
        (src / integrity.BUNDLE / integrity.MANIFEST).write_text(
            json.dumps({"manifest": manifest, "imza": sig.hex()}), encoding="utf-8")
        if tamper:
            (src / "_internal" / "veri.txt").write_text("DEĞİŞTİ", encoding="utf-8")
        path = self.dir / "p.zip"
        with zipfile.ZipFile(path, "w") as archive:
            for file in src.rglob("*"):
                if file.is_file():
                    archive.write(file, "Forevermore/" + file.relative_to(src).as_posix())
            for name, data in (extra or {}).items():
                archive.writestr(name, data)
        return path

    def prepare(self, path, current="2.0.0"):
        return guncelleme.hazirla(path, self.dir / "yeni", self.public, current)

    def test_unsigned_tools_folder_is_rejected(self):
        with self.assertRaises(guncelleme.GuncellemeHatasi) as caught:
            self.prepare(self.build_zip(extra={"Forevermore/tools/DDU/ddu.exe": "x"}))
        self.assertEqual(caught.exception.kod, "paket")

    def assertRejected(self, code, path, **kw):
        with self.assertRaises(guncelleme.GuncellemeHatasi) as ctx:
            self.prepare(path, **kw)
        self.assertEqual(ctx.exception.kod, code, str(ctx.exception))
        self.assertFalse((self.dir / "yeni").exists())  # reddedilen paket diskte kalmaz

    def test_valid_package(self):
        folder = self.prepare(self.build_zip())
        self.assertTrue((folder / "Forevermore.exe").is_file())

    def test_signed_by_other_key_rejected(self):
        self.assertRejected("imza", self.build_zip(secret=secrets.token_bytes(32)))

    def test_tampered_file_rejected(self):
        self.assertRejected("imza", self.build_zip(tamper=True))

    def test_extra_unsigned_file_rejected(self):
        self.assertRejected("imza", self.build_zip(extra={"Forevermore/_internal/ekstra.dll": b"x"}))

    def test_not_newer_rejected(self):
        self.assertRejected("eski", self.build_zip(version="2.0.0"))
        self.assertRejected("eski", self.build_zip(version="1.0.0"))

    def test_path_traversal_rejected(self):
        self.assertRejected("paket", self.build_zip(extra={"../kacis.txt": b"x"}))
        self.assertRejected("paket", self.build_zip(extra={"C:/Windows/x.txt": b"x"}))

    def test_missing_exe_and_not_a_zip(self):
        self.assertRejected("paket", self.build_zip(exe=False))
        bad = self.dir / "bad.zip"
        bad.write_bytes(b"nope")
        self.assertRejected("paket", bad)


class TestDegisim(unittest.TestCase):
    def test_paths_are_arguments_not_script_text(self):
        cmd = guncelleme.degisim_komutu(r"C:\a b\yeni'; calc; '", 42, r"C:\Programlar\Forevermore", r"C:\t\degistir.ps1")
        self.assertEqual(cmd[cmd.index("-File") + 1], r"C:\t\degistir.ps1")
        self.assertIn(r"C:\a b\yeni'; calc; '", cmd)  # ayrı bir argüman olarak
        self.assertNotIn("-Command", cmd)
        self.assertNotIn("calc", guncelleme.SWAP_SCRIPT)
        self.assertNotIn("Bypass", cmd)   # antivirüs sezgiseli; yerel betik için RemoteSigned yeter (1.4)
        self.assertNotIn("Hidden", cmd)

    def test_moved_files_take_install_folder_permissions(self):
        """Denetim 5: %LOCALAPPDATA%'dan taşınan klasör kullanıcının yazabildiği izinleri taşırdı; Program Files'taki
        kurulum güncellemeden sonra yönetici olmayan programlarca değiştirilebilir olurdu."""
        script = guncelleme.SWAP_SCRIPT
        self.assertIn("icacls.exe $Install /reset /T", script)
        self.assertLess(script.index("Move-Item -LiteralPath $Staging"), script.index("icacls.exe"))

    def test_script_rolls_back(self):
        self.assertIn("Rename-Item -LiteralPath $old", guncelleme.SWAP_SCRIPT)
        self.assertIn(".eski", guncelleme.SWAP_SCRIPT)

    def test_source_run_refuses(self):
        with self.assertRaises(guncelleme.GuncellemeHatasi) as ctx:
            guncelleme.degisimi_baslat(Path("x"))
        self.assertEqual(ctx.exception.kod, "kaynak")


class TestSwapScriptReal(unittest.TestCase):
    """Betiği gerçekten (geçici klasörlerde) çalıştırır: değişim, kullanıcı klasörü ve geri alma."""

    def run_swap(self, base, staging):
        import subprocess
        script = base / "degistir.ps1"
        script.write_text(guncelleme.SWAP_SCRIPT, encoding="utf-8-sig")
        cmd = guncelleme.degisim_komutu(staging, 999999, base / "Forevermore", script)
        cmd[cmd.index("Forevermore.exe")] = "calistir.cmd"  # gerçek .exe yerine işaret dosyası yazan betik
        subprocess.run(cmd, timeout=90, check=False, creationflags=guncelleme.CREATE_NO_WINDOW)

    def make(self, base, label):
        folder = base / label
        folder.mkdir(parents=True)
        (folder / "calistir.cmd").write_text("@echo ok\r\n", encoding="ascii")  # Start-Process baslatacagi sahte program
        (folder / "surum.txt").write_text(label, encoding="utf-8")
        return folder

    def test_swap_keeps_tools_and_removes_old(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            install = self.make(base, "Forevermore")
            (install / "tools").mkdir()
            (install / "tools" / "ddu.txt").write_text("kullanici", encoding="utf-8")
            staging = self.make(base / "yeni", "yeni_paket")
            self.run_swap(base, staging)
            self.assertEqual((base / "Forevermore" / "surum.txt").read_text(encoding="utf-8"), "yeni_paket")
            self.assertEqual((base / "Forevermore" / "tools" / "ddu.txt").read_text(encoding="utf-8"), "kullanici")
            self.assertFalse((base / "Forevermore.eski").exists())

    def test_failed_move_rolls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self.make(base, "Forevermore")
            self.run_swap(base, base / "yok_boyle_bir_klasor")  # Move-Item hata verir
            self.assertEqual((base / "Forevermore" / "surum.txt").read_text(encoding="utf-8"), "Forevermore")
            self.assertFalse((base / "Forevermore.eski").exists())


if __name__ == "__main__":
    unittest.main()
