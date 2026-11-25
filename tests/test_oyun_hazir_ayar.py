"""Oyun hazır ayarları: yalnızca kalıcı alanlar (öncelik, GPU tercihi) ve güvenlik sınırları."""

import unittest

from app.games import presets, profiles


class TestPresets(unittest.TestCase):
    def test_only_persistent_profile_keys_and_valid_values(self):
        for preset in presets.PRESETS:
            fields = presets.build(preset, True)
            self.assertEqual(set(fields), {"oncelik", "gpu_tercihi"}, preset)  # oyun sırasında alanı yok (izleyici kaldırıldı)
            self.assertIn(fields["oncelik"], ("Normal", "AboveNormal", "High"))  # Realtime hiçbir zaman
            self.assertIn(fields["gpu_tercihi"], profiles.GPU_PREF)

    def test_gpu_preference_only_with_two_gpus(self):
        self.assertEqual(presets.build("dengeli", True)["gpu_tercihi"], "yuksek_performans")
        self.assertEqual(presets.build("dengeli", False)["gpu_tercihi"], "varsayilan")

    def test_ordering_and_current(self):
        levels = {"Normal": 0, "AboveNormal": 1, "High": 2}
        values = [levels[presets.build(p, False)["oncelik"]] for p in presets.PRESETS]
        self.assertEqual(values, sorted(values))  # görsel <= dengeli <= performans
        draft = dict(profiles.DEFAULT_PROFILE, **presets.build("dengeli", True))
        self.assertEqual(presets.current(draft, True), "dengeli")
        draft["gpu_tercihi"] = "guc_tasarrufu"  # hiçbir hazır ayar bunu seçmez
        self.assertIsNone(presets.current(draft, True))

    def test_recommended_count_ignores_values_equal_to_default(self):
        none = dict(profiles.DEFAULT_PROFILE)
        self.assertEqual(presets.recommended_count(none, False), (0, 1))  # tek kart: yalnızca öncelik
        self.assertEqual(presets.recommended_count(none, True), (0, 2))   # iki kart: öncelik + GPU
        advised = dict(profiles.DEFAULT_PROFILE, **presets.build("dengeli", True))
        self.assertEqual(presets.recommended_count(advised, True), (2, 2))
        self.assertEqual(presets.recommended_count(dict(advised, oncelik="Normal"), True), (1, 2))

    def test_unknown_preset(self):
        with self.assertRaises(ValueError):
            presets.build("kapali", False)


if __name__ == "__main__":
    unittest.main()
