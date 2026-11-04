"""Oyun hazır ayarları: donanıma göre doldurma ve güvenlik sınırları."""

import unittest

from app.games import presets, profiles

PLAIN = {"hibrit": False, "vcache_l3": None}
X3D = {"hibrit": False, "vcache_l3": 1}
HYBRID = {"hibrit": True, "vcache_l3": None}


class TestPresets(unittest.TestCase):
    def test_only_known_profile_keys_and_valid_values(self):
        for preset in presets.PRESETS:
            fields = presets.build(preset, X3D, True)
            self.assertTrue(set(fields) <= set(profiles.DEFAULT_PROFILE), preset)
            self.assertIn(fields["oncelik"], ("Normal", "AboveNormal", "High"))  # Realtime hiçbir zaman
            self.assertIn(fields["gpu_tercihi"], profiles.GPU_PREF)

    def test_risky_or_situational_options_never_enabled(self):
        for preset in presets.PRESETS:
            fields = presets.build(preset, X3D, True)
            for key in ("servisleri_duraklat", "windows_search_durdur", "standby_temizle", "pencereyi_kucult"):
                self.assertFalse(fields[key], (preset, key))
            for key in ("fso_kapali", "otomatik", "cekirdekler"):  # hazır ayar bunlara dokunmaz
                self.assertNotIn(key, fields)

    def test_cores_follow_hardware(self):
        self.assertEqual(presets.build("performans", X3D, False)["cekirdek_secimi"], "vcache")
        self.assertEqual(presets.build("performans", HYBRID, False)["cekirdek_secimi"], "performans")
        self.assertEqual(presets.build("performans", PLAIN, False)["cekirdek_secimi"], "tum")
        self.assertEqual(presets.build("dengeli", HYBRID, False)["cekirdek_secimi"], "tum")  # dengeli yalnızca vcache
        self.assertEqual(presets.build("gorsel", X3D, False)["cekirdek_secimi"], "tum")

    def test_gpu_preference_only_with_two_gpus(self):
        self.assertEqual(presets.build("dengeli", PLAIN, True)["gpu_tercihi"], "yuksek_performans")
        self.assertEqual(presets.build("dengeli", PLAIN, False)["gpu_tercihi"], "varsayilan")

    def test_ordering_and_current(self):
        levels = {"Normal": 0, "AboveNormal": 1, "High": 2}
        values = [levels[presets.build(p, PLAIN, False)["oncelik"]] for p in presets.PRESETS]
        self.assertEqual(values, sorted(values))  # görsel <= dengeli <= performans
        draft = dict(profiles.DEFAULT_PROFILE, **presets.build("dengeli", HYBRID, True))
        self.assertEqual(presets.current(draft, HYBRID, True), "dengeli")
        draft["guc_plani"] = True
        self.assertIsNone(presets.current(draft, HYBRID, True))

    def test_unknown_preset(self):
        with self.assertRaises(ValueError):
            presets.build("kapali", PLAIN, False)


if __name__ == "__main__":
    unittest.main()
