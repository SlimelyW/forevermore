"""Oyun rehberi bağlantıları: veri dosyası ve ad eşleştirme."""

import json
import unittest

from app.core import paths
from app.games import guides

INSTALLED = ["ARC Raiders", "Counter-Strike 2", "Destiny 2", "League Of Legends", "Marvel Rivals", "Once Human",
             "Overwatch®", "PUBG: BATTLEGROUNDS", "Rocket League", "Teamfighttactics", "THE FINALS",
             "The First Descendant", "Tom Clancy's Rainbow Six Siege", "Valorant", "Warframe"]


class TestGuides(unittest.TestCase):
    def test_data_file_is_https_and_allowed_hosts_only(self):
        data = json.loads((paths.data_dir() / "oyun_rehberi.json").read_text(encoding="utf-8"))["oyunlar"]
        self.assertTrue(data)
        for entry in data:
            self.assertTrue(entry["kaynaklar"], entry["ad"])
            for source in entry["kaynaklar"]:
                self.assertTrue(guides._allowed(source["url"]), source["url"])
                self.assertTrue(source["icerik"] and source["site"])

    def test_installed_games_match_loosely_named_entries(self):
        for name in INSTALLED:
            self.assertTrue(guides.find(name), name)

    def test_unknown_and_empty_names_give_nothing(self):
        self.assertEqual(guides.find("Bilinmeyen Oyun 9000"), [])
        self.assertEqual(guides.find("®™"), [])

    def test_non_https_or_foreign_hosts_are_dropped(self):
        self.assertFalse(guides._allowed("http://prosettings.net/x/"))
        self.assertFalse(guides._allowed("https://evil.example.com/x/"))
        self.assertFalse(guides._allowed("https://prosettings.net.evil.com/x/"))


if __name__ == "__main__":
    unittest.main()
