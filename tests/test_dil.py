"""Çok dil altyapısı: yedek dil, biçimler, ayar çeviri katmanı, eski addan veri taşıma.

Çalıştırma (proje klasöründe):
    py -3.12 -m unittest tests.test_dil -v
"""

import copy
import datetime
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.core import i18n, paths
from app.engine import catalog

ROOT = Path(__file__).resolve().parent.parent


class TestLanguageCore(unittest.TestCase):
    def tearDown(self):
        i18n.load("tr")

    def test_fallback_to_english_for_missing_language(self):
        i18n.load("xx")  # böyle bir dil dosyası yok
        self.assertEqual(i18n.current(), "en")
        self.assertEqual(i18n.t("ui.ayar.dil"), "Language")

    def test_missing_key_in_language_falls_back_to_english(self):
        with tempfile.TemporaryDirectory() as tmp:
            lang = Path(tmp)
            (lang / "en.json").write_text(json.dumps({"_meta": {"kod": "en"}, "a": "English A", "b": "English B"}),
                                          encoding="utf-8")
            (lang / "de.json").write_text(json.dumps({"_meta": {"kod": "de", "ondalik": ","}, "a": "Deutsch A"}),
                                          encoding="utf-8")
            with mock.patch.object(paths, "lang_dir", return_value=lang):
                i18n.load("de")
                self.assertEqual(i18n.t("a"), "Deutsch A")
                self.assertEqual(i18n.t("b"), "English B")
                self.assertEqual(i18n.t("c"), "c")
                self.assertEqual([item["kod"] for item in i18n.available()], ["de", "en"])

    def test_number_and_date_formats_follow_language(self):
        when = datetime.datetime(2026, 10, 23, 14, 5)
        i18n.load("tr")
        self.assertEqual(i18n.fmt_number(1234.5, 1), "1.234,5")
        self.assertEqual(i18n.fmt_percent(42), "%42")
        self.assertEqual(i18n.fmt_date(when), "23.10.2026 14:05")
        self.assertEqual(i18n.t("ui.canli.ghz", ghz=4.2), "4,2 GHz")
        i18n.load("en")
        self.assertEqual(i18n.fmt_number(1234.5, 1), "1,234.5")
        self.assertEqual(i18n.fmt_percent(42), "42%")
        self.assertEqual(i18n.fmt_date("2026-10-23T14:05:00"), "2026-10-23 14:05")
        self.assertEqual(i18n.t("ui.canli.ghz", ghz=4.2), "4.2 GHz")

    def test_value_labels_translate_internal_ids(self):
        i18n.load("en")
        self.assertEqual(i18n.value_label("deger.etki", "yüksek"), "high")
        self.assertEqual(i18n.value_label("deger.gerceklik", "kısmen gerçek"), "real in some cases")
        self.assertEqual(i18n.value_label("deger.etki", "bilinmeyen"), "bilinmeyen")

    def test_suggestion_uses_windows_language_only_if_available(self):
        with mock.patch.object(i18n, "windows_language", return_value="tr"):
            self.assertEqual(i18n.suggest(), "tr")
        with mock.patch.object(i18n, "windows_language", return_value="ja"):
            self.assertEqual(i18n.suggest(), "en")
        with mock.patch.object(i18n, "windows_language", return_value=None):
            self.assertEqual(i18n.suggest(), "en")


class TestTweakTranslationLayer(unittest.TestCase):
    def setUp(self):
        self.data = copy.deepcopy(json.loads((ROOT / "data" / "tweaks_app.json").read_text(encoding="utf-8")))
        self.tweak = next(t for t in self.data["ayarlar"] if t.get("nvidia"))

    def test_only_visible_texts_can_change(self):
        original = copy.deepcopy(self.tweak)
        layer = {"ayarlar": {self.tweak["id"]: {
            "ad": "Translated name",
            "artilar": ["Pro"] * len(self.tweak["artilar"]),
            "nvidia.secenekler.0.etiket": "Option 0",
            "risk": "güvenli",                     # kimlik/seviye: değişmemeli
            "nvidia.ayar": "0x0",                  # sürücü ayar kimliği: değişmemeli
            "performans_etkisi.seviye": "yüksek",  # iç değer: değişmemeli
            "olmayan.alan": "x",
        }}, "genel": {"meta.anti_cheat_uyarisi": "Anti-cheat warning", "meta.surum": "9"}}
        rejected = catalog.apply_translation(self.data, layer)
        self.assertEqual(rejected, 5)
        self.assertEqual(self.tweak["ad"], "Translated name")
        self.assertEqual(self.tweak["nvidia"]["secenekler"][0]["etiket"], "Option 0")
        self.assertEqual(self.tweak["risk"], original["risk"])
        self.assertEqual(self.tweak["nvidia"]["ayar"], original["nvidia"]["ayar"])
        self.assertEqual(self.tweak["performans_etkisi"]["seviye"], original["performans_etkisi"]["seviye"])
        self.assertEqual(self.data["meta"]["anti_cheat_uyarisi"], "Anti-cheat warning")

    def test_type_mismatch_is_rejected(self):
        rejected = catalog.apply_translation(self.data, {"ayarlar": {self.tweak["id"]: {"ad": ["liste"]}}})
        self.assertEqual(rejected, 1)

    def test_layer_order(self):
        self.assertEqual(catalog._layers("tr"), [])
        self.assertEqual(catalog._layers("en"), ["en"])
        self.assertEqual(catalog._layers("de"), ["en", "de"])


class TestTranslationFiles(unittest.TestCase):
    """data/ceviriler/*.json: eksiksiz, güncel ve tamamı uygulanabilir olmalı."""

    def setUp(self):
        self.data = json.loads((ROOT / "data" / "tweaks_app.json").read_text(encoding="utf-8"))
        self.layers = {p.stem: json.loads(p.read_text(encoding="utf-8"))
                       for p in (ROOT / "data" / "ceviriler").glob("*.json")}

    def test_english_layer_exists(self):
        self.assertIn("en", self.layers)

    def test_every_entry_applies(self):
        for code, layer in self.layers.items():
            with self.subTest(dil=code):
                self.assertEqual(catalog.apply_translation(copy.deepcopy(self.data), layer), 0)

    def test_complete_and_up_to_date(self):
        """Türkçe metin değişince bu test düşer: çeviriyi güncelleyip tools/ceviri_ozeti.py --yenile <dil>."""
        for code, layer in self.layers.items():
            for tweak in self.data["ayarlar"]:
                with self.subTest(dil=code, ayar=tweak["id"]):
                    fields = layer["ayarlar"].get(tweak["id"], {})
                    self.assertEqual(set(fields), set(catalog.source_texts(tweak)))
                    self.assertEqual(layer["_kaynak_ozeti"].get(tweak["id"]), catalog.source_digest(tweak))

    def test_catalog_uses_layer_for_selected_language(self):
        try:
            i18n.load("en")
            catalog.load.cache_clear()
            self.assertEqual(catalog.by_id()["SYS-001"]["ad"], "Disable the Print Spooler service")
            self.assertEqual(catalog.by_id()["SYS-001"]["risk"], "dikkatli")  # iç değer değişmez
        finally:
            i18n.load("tr")
            catalog.load.cache_clear()
        self.assertIn("Yazdırma", catalog.by_id()["SYS-001"]["ad"])


class TestLegacyDataMigration(unittest.TestCase):
    def test_old_folder_is_copied_once_and_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = Path(tmp) / "PCOptimizer"
            (old / "backups").mkdir(parents=True)
            (old / "backups" / "yedekler.json").write_text("{}", encoding="utf-8")
            (old / "onay.json").write_text("{}", encoding="utf-8")
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": tmp}):
                new = paths.user_data_dir()
                self.assertEqual(new.name, "Forevermore")
                self.assertTrue((new / "backups" / "yedekler.json").is_file())
                self.assertTrue((new / "onay.json").is_file())
                self.assertTrue(old.is_dir())  # eski klasör silinmez
                (new / "onay.json").unlink()
                paths.user_data_dir()  # ikinci kez kopyalanmaz
                self.assertFalse((new / "onay.json").exists())

    def test_no_old_folder(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"LOCALAPPDATA": tmp}):
            self.assertTrue(paths.user_data_dir().is_dir())
            self.assertFalse((Path(tmp) / "PCOptimizer").exists())


class TestLegacyNames(unittest.TestCase):
    def test_settings_exported_with_old_name_are_accepted(self):
        from app.ui.page_settings import EXPORT_MARKER, LEGACY_EXPORT_MARKERS
        self.assertEqual(EXPORT_MARKER, "Forevermore")
        self.assertIn("PC Optimizer", LEGACY_EXPORT_MARKERS)

    def test_autostart_handles_old_task_name(self):
        from app.core import autostart
        self.assertEqual(autostart.TASK_NAME, "Forevermore - oturum acilisi")
        self.assertIn("'PC Optimizer - oturum acilisi'", autostart._all_names())


if __name__ == "__main__":
    unittest.main()
