"""Temizleyici testleri: geçici klasörlerde (gerçek kullanıcı klasörüne dokunulmaz).

Çalıştırma: py -3.12 -m unittest tests.test_temizleyiciler -v
"""

import datetime
import os
import subprocess
import time
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.engine import cleaners, uninstaller


class FakeRegOps:
    pass


class TestCleaners(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.env = {"APPDATA": str(root / "Roaming"), "LOCALAPPDATA": str(root / "Local")}
        self.base = root / "yedek"
        self.now = datetime.datetime(2026, 11, 5, 12, 0, 0)

        def write(path, size):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"x" * size)

        discord = root / "Roaming" / "discord"
        for name, size in (("Cache", 100), ("Code Cache", 200), ("GPUCache", 300)):
            write(discord / name / "f.bin", size)
        write(discord / "Local Storage" / "oturum.db", 50)     # hesap/oturum verisi: dokunulmaz
        write(discord / "settings.json", 5)
        write(root / "Local" / "Steam" / "htmlcache" / "a", 1000)
        write(root / "Local" / "Steam" / "config" / "login.vdf", 7)
        explorer = root / "Local" / "Microsoft" / "Windows" / "Explorer"
        write(explorer / "thumbcache_32.db", 400)
        write(explorer / "iconcache_32.db", 9)                 # kalıp dışı: dokunulmaz
        write(root / "Local" / "CrashDumps" / "a.dmp", 600)
        write(root / "Local" / "CrashDumps" / "notlar.txt", 3)
        temp = root / "Local" / "Temp"
        old = time.time() - 30 * 86400
        for name, size, age in (("eski.log", 11, old), ("eski.etl", 12, old), ("yeni.log", 13, time.time()),
                                ("eski.txt", 14, old), ("Forevermore_eski.log", 15, old)):
            write(temp / name, size)
            os.utime(temp / name, (age, age))
        write(temp / "klasor.log" / "ic.log", 16)               # klasör: eski_log yalnızca DOSYA alır
        os.utime(temp / "klasor.log", (old, old))
        recent = root / "Roaming" / "Microsoft" / "Windows" / "Recent"
        write(recent / "rapor.docx.lnk", 21)
        write(recent / "foto.jpg.lnk", 22)
        write(recent / "AutomaticDestinations" / "abc.automaticDestinations-ms", 23)  # sabitler: dokunulmaz
        write(root / "Roaming" / "belge.docx", 24)                                   # belgenin kendisi
        self.root = root

    def tearDown(self):
        self.tmp.cleanup()

    def scan(self, running=()):
        return {c["id"]: c for c in cleaners.scan(self.env, lambda: [(1, exe) for exe in running])}

    def test_scan_sizes_only_known_items(self):
        found = self.scan()
        self.assertEqual({k: (v["boyut"], v["adet"]) for k, v in found.items()},
                         {"discord": (600, 3), "steam": (1000, 1), "kucuk_resim": (400, 1), "cokme_dokumu": (600, 1),
                          "eski_log": (23, 2), "son_belgeler": (43, 2)})
        # ortam değişkeni yok: hiçbir şey bulunmaz, ama her temizleyici 0 boyutla listelenir
        self.assertEqual({(c["boyut"], c["adet"]) for c in cleaners.scan({}, lambda: [])}, {(0, 0)})

    def test_old_logs_only_old_files_in_temp_root(self):
        result = cleaners.clean(["eski_log"], "T", self.env, lambda: [], self.base, now=self.now)
        self.assertEqual((result["kaldirilan"], result["boyut"]), (2, 23))
        temp = self.root / "Local" / "Temp"
        self.assertFalse((temp / "eski.log").exists() or (temp / "eski.etl").exists())
        for kept in ("yeni.log", "eski.txt", "Forevermore_eski.log", "klasor.log/ic.log"):
            self.assertTrue((temp / kept).is_file(), kept)

    def test_recent_moves_only_shortcuts_and_roundtrips(self):
        result = cleaners.clean(["son_belgeler"], "T", self.env, lambda: [], self.base, now=self.now)
        self.assertEqual((result["kaldirilan"], result["boyut"]), (2, 43))
        recent = self.root / "Roaming" / "Microsoft" / "Windows" / "Recent"
        self.assertFalse((recent / "rapor.docx.lnk").exists())
        self.assertTrue((recent / "AutomaticDestinations" / "abc.automaticDestinations-ms").is_file())
        self.assertTrue((self.root / "Roaming" / "belge.docx").is_file())  # belgeye dokunulmadı
        session = uninstaller.list_sessions(self.base)[0]["oturum"]
        self.assertEqual(uninstaller.restore(session, self.base, FakeRegOps())["basarisiz"], [])
        self.assertTrue((recent / "rapor.docx.lnk").is_file())

    def test_clean_moves_not_deletes_and_roundtrips(self):
        result = cleaners.clean(["discord", "cokme_dokumu"], "Temizlik", self.env, lambda: [], self.base, now=self.now)
        self.assertEqual((result["kaldirilan"], result["basarisiz"], result["atlanan"], result["boyut"]), (4, [], [], 1200))
        discord = self.root / "Roaming" / "discord"
        self.assertFalse((discord / "Cache").exists())
        self.assertTrue((discord / "Local Storage" / "oturum.db").is_file())   # oturum verisi yerinde
        self.assertTrue((discord / "settings.json").is_file())
        self.assertTrue((self.root / "Local" / "CrashDumps" / "notlar.txt").is_file())
        self.assertTrue((self.root / "Local" / "Steam" / "htmlcache" / "a").is_file())  # seçilmeyen temizleyici
        sessions = uninstaller.list_sessions(self.base)
        self.assertEqual((sessions[0]["program"], sessions[0]["adet"]), ("Temizlik", 4))
        self.assertEqual((sessions[0]["tur"], sessions[0]["boyut"]), ("temizlik", 1200))  # Temizlik sayfası "Son taşımalar" için
        back = uninstaller.restore(sessions[0]["oturum"], self.base, FakeRegOps())
        self.assertEqual((back["geri_yuklenen"], back["basarisiz"]), (4, []))
        self.assertTrue((discord / "GPUCache" / "f.bin").is_file())
        self.assertTrue((self.root / "Local" / "CrashDumps" / "a.dmp").is_file())

    def test_running_program_is_skipped_never_closed(self):
        self.assertTrue(self.scan(["steamwebhelper.exe"])["steam"]["calisiyor"])
        self.assertFalse(self.scan()["steam"]["calisiyor"])
        result = cleaners.clean(["discord", "steam"], "T", self.env, lambda: [(5, "discord.exe")], self.base, now=self.now)
        self.assertEqual(result["atlanan"], ["discord"])
        self.assertEqual(result["kaldirilan"], 1)
        self.assertTrue((self.root / "Roaming" / "discord" / "Cache").is_dir())

    def test_unknown_ids_and_paths_are_ignored(self):
        result = cleaners.clean(["../../Windows", "C:\\Windows", "", None, "yok"], "T", self.env, lambda: [], self.base)
        self.assertEqual((result["kaldirilan"], result["oturum"]), (0, None))
        self.assertFalse(self.base.exists() and any(self.base.iterdir()))

    def test_junction_is_never_followed_or_moved(self):
        target = self.root / "baska_yer"
        (target).mkdir()
        (target / "onemli.txt").write_text("sakla", encoding="utf-8")
        cache = self.root / "Roaming" / "discord" / "Cache"
        for item in cache.iterdir():
            item.unlink()
        cache.rmdir()
        done = subprocess.run(["cmd", "/c", "mklink", "/J", str(cache), str(target)], capture_output=True)
        if done.returncode != 0:
            self.skipTest("birleşim noktası oluşturulamadı")
        found = self.scan()["discord"]
        self.assertEqual(found["adet"], 2)  # bağlantı olan Cache sayılmaz
        cleaners.clean(["discord"], "T", self.env, lambda: [], self.base, now=self.now)
        self.assertEqual((target / "onemli.txt").read_text(encoding="utf-8"), "sakla")  # hedefe dokunulmadı
        subprocess.run(["cmd", "/c", "rmdir", str(cache)], capture_output=True)

    def test_locked_item_is_reported_and_not_counted(self):
        real_move = uninstaller.shutil.move

        def move(src, dst):
            if "GPUCache" in str(src):
                raise PermissionError("kilitli")
            return real_move(src, dst)

        with mock.patch.object(uninstaller.shutil, "move", move):
            result = cleaners.clean(["discord"], "T", self.env, lambda: [], self.base, now=self.now)
        self.assertEqual((result["kaldirilan"], len(result["basarisiz"]), result["boyut"]), (2, 1, 300))
        self.assertTrue((self.root / "Roaming" / "discord" / "GPUCache" / "f.bin").is_file())  # yerinde, zarar yok


if __name__ == "__main__":
    unittest.main()
