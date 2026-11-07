"""Oyun ayar dosyası sakla / geri yükle / sıfırla: geçici klasörlerde (gerçek oyun klasörüne dokunulmaz).

Çalıştırma: py -3.12 -m unittest tests.test_oyun_ayar -v
"""

import datetime
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from app.engine import uninstaller
from app.games import oyun_ayar as oa


class TestOyunAyar(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.env = {"LOCALAPPDATA": str(root / "Local"), "SYSTEMDRIVE": str(root / "C"), "DOCUMENTS": str(root / "Belgeler")}
        self.base, self.backup = root / "kopyalar", root / "yedek"
        self.closed = lambda: [(1, "explorer.exe")]
        self.valorant = root / "Local" / "VALORANT" / "Saved" / "Config"
        self.write(self.valorant / "abc" / "Windows" / "GameUserSettings.ini", "[ScalabilitySettings]\nsg.ShadowQuality=0\n")
        self.fortnite = root / "Local" / "FortniteGame" / "Saved" / "Config" / "WindowsClient" / "GameUserSettings.ini"
        self.write(self.fortnite, "benim ayarim")
        self.write(self.fortnite.parent / "Engine.ini", "dokunulmaz")
        siege = root / "Belgeler" / "My Games" / "Rainbow Six - Siege"
        self.r6 = [siege / "hesap1" / "GameSettings.ini", siege / "hesap2" / "GameSettings.ini"]
        for path in self.r6:
            self.write(path, path.parent.name)
        self.write(siege / "benchmark.txt", "dokunulmaz")
        self.root = root

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def write(path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def at(self, second):
        return datetime.datetime(2026, 11, 7, 12, 0, second)

    def test_find_matches_library_names(self):
        self.assertEqual(oa.find("VALORANT"), "valorant")
        self.assertEqual(oa.find("Tom Clancy's Rainbow Six® Siege X"), "r6")  # 2025 adı: önek eşleşmesi
        self.assertEqual(oa.find("Tom Clancy's Rainbow Six Siege"), "r6")
        self.assertEqual(oa.find("League of Legends"), "lol")
        self.assertEqual(oa.find("Fortnite"), "fortnite")
        self.assertIsNone(oa.find("Counter-Strike 2"))
        self.assertIsNone(oa.find(""))

    def test_status_is_read_only(self):
        before = self.fortnite.read_bytes()
        state = oa.status("fortnite", self.env, self.closed, self.base, self.backup)
        self.assertEqual(state, {"var": True, "calisiyor": False, "sifirla": False, "kopyalar": [], "geri_al": None})
        self.assertFalse(oa.status("lol", self.env, self.closed, self.base, self.backup)["var"])
        self.assertTrue(oa.status("valorant", self.env, lambda: [(1, "RiotClientServices.exe")], self.base, self.backup)["calisiyor"])
        self.assertEqual(self.fortnite.read_bytes(), before)
        self.assertFalse(self.base.exists())

    def test_save_reset_restore_roundtrip_is_byte_identical(self):
        original = {p: p.read_bytes() for p in self.valorant.rglob("*") if p.is_file()}
        name = oa.save("valorant", self.env, self.closed, self.base, self.at(0))
        session = oa.reset("valorant", self.env, self.closed, self.backup, self.at(1))
        self.assertFalse(self.valorant.exists())
        self.assertEqual(oa.status("valorant", self.env, self.closed, self.base, self.backup)["geri_al"], session)
        self.write(self.valorant / "yeni.ini", "oyun yeniden kurdu")
        oa.restore("valorant", name, self.env, self.closed, self.base, self.backup, self.at(2))
        self.assertEqual({p: p.read_bytes() for p in self.valorant.rglob("*") if p.is_file()}, original)
        self.assertEqual(len(oa.resets("valorant", self.backup)), 2)  # sıfırlanan ve geri yükleme öncesi olan: ikisi de geri alınabilir

    def test_undo_reset_brings_back_and_can_be_undone_again(self):
        session = oa.reset("r6", self.env, self.closed, self.backup, self.at(0))
        self.assertTrue(all(not p.exists() for p in self.r6))
        self.assertTrue((self.r6[0].parent.parent / "benchmark.txt").exists())
        self.write(self.r6[0], "oyunun yenisi")
        oa.undo("r6", session, self.env, self.closed, self.backup, self.at(1))
        self.assertEqual([p.read_text(encoding="utf-8") for p in self.r6], ["hesap1", "hesap2"])
        latest = oa.resets("r6", self.backup)[0]["oturum"]
        oa.undo("r6", latest, self.env, self.closed, self.backup, self.at(2))
        self.assertEqual(self.r6[0].read_text(encoding="utf-8"), "oyunun yenisi")
        self.assertFalse(self.r6[1].exists())

    def test_fortnite_has_no_reset_and_only_touches_its_file(self):
        with self.assertRaises(ValueError):
            oa.reset("fortnite", self.env, self.closed, self.backup)
        name = oa.save("fortnite", self.env, self.closed, self.base, self.at(0))
        self.fortnite.write_text("guncelleme sildi", encoding="utf-8")
        oa.restore("fortnite", name, self.env, self.closed, self.base, self.backup, self.at(1))
        self.assertEqual(self.fortnite.read_text(encoding="utf-8"), "benim ayarim")
        self.assertEqual((self.fortnite.parent / "Engine.ini").read_text(encoding="utf-8"), "dokunulmaz")

    def test_refuses_when_game_or_launcher_running(self):
        running = lambda: [(5, "EpicGamesLauncher.exe")]  # noqa: E731
        before = self.fortnite.read_bytes()
        for call in (lambda: oa.save("fortnite", self.env, running, self.base),
                     lambda: oa.restore("fortnite", "20261107-120000", self.env, running, self.base, self.backup)):
            with self.assertRaises(RuntimeError):
                call()
        with self.assertRaises(RuntimeError):
            oa.reset("valorant", self.env, lambda: [(5, "VALORANT-Win64-Shipping.exe")], self.backup)
        self.assertEqual(self.fortnite.read_bytes(), before)
        self.assertTrue(self.valorant.exists())
        self.assertFalse(self.base.exists())

    def test_keeps_only_latest_copies(self):
        for second in range(oa.KEEP + 2):
            oa.save("fortnite", self.env, self.closed, self.base, self.at(second))
        names = [s["ad"] for s in oa.snapshots("fortnite", self.base)]
        self.assertEqual(len(names), oa.KEEP)
        self.assertEqual(names[0], "20261107-120006")

    def test_tampered_manifest_outside_root_is_refused_before_touching(self):
        name = oa.save("fortnite", self.env, self.closed, self.base, self.at(0))
        manifest = self.base / name / "manifest.json"
        outside = self.root / "baska.txt"
        for bad in (str(outside), str(self.fortnite.parent / ".." / "GameUserSettings.ini"), str(self.fortnite.parent / "Engine.ini")):
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["ogeler"][0]["yol"] = bad
            manifest.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                oa.restore("fortnite", name, self.env, self.closed, self.base, self.backup)
        self.assertEqual(self.fortnite.read_text(encoding="utf-8"), "benim ayarim")
        self.assertFalse(outside.exists())
        with self.assertRaises(ValueError):
            oa.restore("fortnite", "..\\..\\x", self.env, self.closed, self.base, self.backup)
        with self.assertRaises(ValueError):
            oa.undo("fortnite", "20200101-000000", self.env, self.closed, self.backup)

    @unittest.skipUnless(os.name == "nt", "birleşim noktası yalnızca Windows'ta")
    def test_junction_inside_root_is_skipped(self):
        target = self.root / "baska_yer" / "hesap3"
        self.write(target / "GameSettings.ini", "baska")
        link = self.r6[0].parent.parent / "hesap3"
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True)
        oa.reset("r6", self.env, self.closed, self.backup, self.at(0))
        self.assertEqual((target / "GameSettings.ini").read_text(encoding="utf-8"), "baska")

    def test_same_second_moves_get_separate_sessions(self):
        first = uninstaller.remove_leftovers("A", [{"tur": "klasor", "yol": str(self.r6[0])}], self.backup, None, self.at(0))
        second = uninstaller.remove_leftovers("B", [{"tur": "klasor", "yol": str(self.r6[1])}], self.backup, None, self.at(0))
        self.assertNotEqual(first["oturum"], second["oturum"])
        self.assertEqual({s["program"] for s in uninstaller.list_sessions(self.backup)}, {"A", "B"})


if __name__ == "__main__":
    unittest.main()
