"""Ekran kartı sürücüsü arabirimleri: yapı boyutları ve değer doğrulaması (sürücü gerekmez)."""

import ctypes
import unittest

from app.engine import amd, nvidia


class TestDriverLayouts(unittest.TestCase):
    def test_nvapi_display_config_sizes(self):
        # nvapi.h #pragma pack(8): NV_TIMING 96, ADVANCED_TARGET_INFO_V1 128, PATH_INFO_V2 48 bayt (64 bit)
        self.assertEqual(ctypes.sizeof(nvidia._Timing), 96)
        self.assertEqual(ctypes.sizeof(nvidia._Advanced), 128)
        self.assertEqual(ctypes.sizeof(nvidia._Path), 48)
        self.assertEqual(nvidia.PATH_VERSION, 48 | (2 << 16))

    def test_scaling_values_are_checked_before_driver_call(self):
        with self.assertRaises(ValueError):
            nvidia.set_scaling("DISPLAY1", 4)  # 4 NV_SCALING'de tanımsız
        with self.assertRaises(ValueError):
            amd.set_scaling("0", 7)

    def test_amd_feature_table(self):
        for key, (getter, supported, enabled, setter) in amd.FEATURES.items():
            self.assertIn(getter, (3, 4, 5, 7), key)
            self.assertEqual((supported, enabled), (3, 4), key)
            self.assertGreater(setter, enabled, key)


if __name__ == "__main__":
    unittest.main()
