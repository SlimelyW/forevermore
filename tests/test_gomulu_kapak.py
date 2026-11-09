import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.core import paths
from app.games import discovery

DATA = paths.data_dir()
ENTRIES = json.loads((DATA / "oyun_kapaklari.json").read_text(encoding="utf-8"))["kapaklar"]


class GomuluKapakTesti(unittest.TestCase):
    """data/oyun_kapaklari: oyun kaydındaki alanlarla eşleşme (ağ yok, yeni tarama yok)."""

    def cover(self, **game):
        found = discovery.embedded_cover(game, game.pop("appid", None))
        return Path(found).name if found else None

    def test_her_girdinin_dosyasi_var_ve_kayit_tutarli(self):
        files = {p.name for p in (DATA / "oyun_kapaklari").glob("*.jpg")}
        self.assertEqual({e["dosya"] for e in ENTRIES}, files)  # sahipsiz dosya da yok
        for entry in ENTRIES:
            self.assertTrue((DATA / "oyun_kapaklari" / entry["dosya"]).is_file(), entry["dosya"])
            self.assertTrue(entry["exe"] or entry["appid"], entry["ad"])
        self.assertEqual(len({e["dosya"] for e in ENTRIES}), len(ENTRIES))

    def test_toplam_boyut_makul(self):
        total = sum(p.stat().st_size for p in (DATA / "oyun_kapaklari").glob("*.jpg"))
        self.assertLess(total, 3 * 1024 * 1024)

    def test_bilinen_exe_dogru_dosya(self):
        for exe, expect in [("r5apex.exe", "apex-legends.jpg"), ("FallGuys_client_game.exe", "fall-guys.jpg"),
                            (r"C:\Games\GTAV\GTA5.exe", "gta-v.jpg"), ("Overwatch.exe", "overwatch-2.jpg"),
                            ("cod.exe", "call-of-duty.jpg"), ("Diablo IV.exe", "diablo-iv.jpg"),
                            ("RocketLeague.exe", "rocket-league.jpg"), ("TslGame.exe", "pubg.jpg"),
                            ("RustClient.exe", "rust.jpg"), ("Warframe.x64.exe", "warframe.jpg"),
                            ("cs2.exe", "cs2.jpg"), ("dota2.exe", "dota-2.jpg"), ("helldivers2.exe", "helldivers-2.jpg"),
                            ("PathOfExileSteam.exe", "path-of-exile.jpg"), ("PathOfExile_x64.exe", "path-of-exile.jpg"),
                            ("LOSTARK.exe", "lost-ark.jpg")]:
            self.assertEqual(self.cover(exe=exe), expect, exe)

    def test_appid_klasor_ve_ad_ile_de_eslesir(self):
        self.assertEqual(self.cover(appid="730"), "cs2.jpg")
        self.assertEqual(self.cover(klasor=r"D:\Epic\rocketleague"), "rocket-league.jpg")
        self.assertEqual(self.cover(ad="GTA V"), "gta-v.jpg")
        self.assertEqual(self.cover(ad="Rust", exe=r"D:\x\game.exe"), "rust.jpg")

    def test_bilinmeyen_oyun_kapak_almaz_exe_simgesine_duser(self):
        self.assertIsNone(self.cover(ad="Bilinmeyen Oyun", exe=r"C:\x\xyz.exe", klasor=r"C:\Games\Xyz"))
        for name in ("Valorant", "League of Legends", "Fortnite", "Minecraft", "Roblox", "Escape from Tarkov"):
            self.assertIsNone(self.cover(ad=name), name)
        self.assertIsNone(self.cover(ad="Rust Belt Simulator"))  # kısmi ad eşleşmez
        self.assertIsNone(discovery.embedded_cover({}))

    def test_dosya_yoksa_ya_da_json_bozuksa_none(self):
        with tempfile.TemporaryDirectory() as data:
            with mock.patch.object(discovery.paths, "data_dir", return_value=Path(data)):
                self.assertIsNone(discovery.embedded_cover({"exe": "cs2.exe"}))  # JSON yok
                Path(data, "oyun_kapaklari.json").write_text(
                    json.dumps({"kapaklar": [{"ad": "X", "dosya": "yok.jpg", "exe": ["cs2.exe"]}]}), encoding="utf-8")
                self.assertIsNone(discovery.embedded_cover({"exe": "cs2.exe"}))  # resim yok
                Path(data, "oyun_kapaklari.json").write_text("{bozuk", encoding="utf-8")
                self.assertIsNone(discovery.embedded_cover({"exe": "cs2.exe"}))

    def test_dosya_adi_yol_kacirmaz(self):
        with tempfile.TemporaryDirectory() as data:
            Path(data, "gizli.jpg").write_bytes(b"x")
            Path(data, "oyun_kapaklari").mkdir()
            Path(data, "oyun_kapaklari.json").write_text(
                json.dumps({"kapaklar": [{"ad": "X", "dosya": "../gizli.jpg", "exe": ["a.exe"]}]}), encoding="utf-8")
            with mock.patch.object(discovery.paths, "data_dir", return_value=Path(data)):
                self.assertIsNone(discovery.embedded_cover({"exe": "a.exe"}))

    def test_sira_kullanici_steam_gomulu(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as user:
            game = {"id": "OYUN-0123456789", "exe": "cs2.exe"}
            with mock.patch.object(discovery.paths, "user_data_path", return_value=Path(user)):
                self.assertTrue(discovery.cover_path(game, root).endswith("cs2.jpg"))  # Steam önbelleği boş: gömülü
                steam = Path(root, "appcache", "librarycache", "730", "x", "library_600x900.jpg")
                steam.parent.mkdir(parents=True)
                steam.write_bytes(b"\xff\xd8" + b"\xff\xe0" + (16).to_bytes(2, "big") + b"JFIF\x00" + bytes(9)
                                  + b"\xff\xc0" + (17).to_bytes(2, "big") + b"\x08" + (900).to_bytes(2, "big")
                                  + (600).to_bytes(2, "big") + b"\x03" + bytes(9) + b"\xff\xd9")
                game["baslat"] = "steam://rungameid/730"
                self.assertEqual(discovery.cover_path(game, root), str(steam))  # Steam, gömülüden önce
                own = Path(user, "kapaklar", "OYUN-0123456789.jpg")
                own.parent.mkdir()
                own.write_bytes(b"x")
                self.assertEqual(discovery.cover_path(game, root), str(own))  # kullanıcı resmi hepsinden önce


if __name__ == "__main__":
    unittest.main()
