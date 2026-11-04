"""Nihai Performans durumu: şablon doğrudan etkinse ya da kopya düz adla kayıtlıysa da "açık" okunmalı."""

import unittest

from app.engine import handlers
from tests.fake_system import FakeSystem

TEMPLATE = "e9a42b02-d5df-448d-aa00-03f14749eb61"
STEP = {"tur": "yerlesik", "eylem": "nihai_performans_plani", "parametreler": {}, "acik": "nihai",
        "kapali": "381b4222-f694-41f0-9685-ff5bb260df2e"}


class TestUltimateState(unittest.TestCase):
    def state(self, system):
        return handlers.state(STEP, handlers.snapshot(system, STEP))

    def test_balanced_is_off(self):
        self.assertEqual(self.state(FakeSystem()), "kapali")

    def test_template_active_directly_is_on(self):
        system = FakeSystem()
        system.active_scheme = TEMPLATE
        self.assertEqual(self.state(system), "acik")

    def test_created_copy_is_on(self):
        system = FakeSystem()
        system.active_scheme = system.create_ultimate_scheme()
        self.assertEqual(self.state(system), "acik")

    def test_other_plan_is_off(self):
        system = FakeSystem()
        system.active_scheme = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
        self.assertEqual(self.state(system), "kapali")


class TestUltimateNameCheck(unittest.TestCase):
    """WindowsSystem.is_ultimate_scheme: kayıt defteri adına göre (gerçek kayıt defteri yerine sahte okuma)."""

    def check(self, name):
        from unittest import mock
        from app.engine.system import WindowsSystem
        with mock.patch("app.engine.system.registry.read", return_value=name):
            return WindowsSystem.is_ultimate_scheme(WindowsSystem.__new__(WindowsSystem), "bbbbbbbb-0000-0000-0000-000000000001")

    def test_resource_and_plain_names(self):
        self.assertTrue(self.check("@%SystemRoot%\system32\powrprof.dll,-19,Ultimate Performance"))
        self.assertTrue(self.check("Ultimate Performance"))
        self.assertTrue(self.check("Nihai Performans"))

    def test_other_names(self):
        self.assertFalse(self.check("Dengeli"))
        self.assertFalse(self.check(None))


if __name__ == "__main__":
    unittest.main()
