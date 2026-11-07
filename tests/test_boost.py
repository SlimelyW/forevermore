"""Tek tuş Boost'un mantığı (app/engine/boost.py): sahte süreç işlemleri ve sahte bellek ölçümüyle; gerçek süreç kapatılmaz."""

import unittest

from app.engine import boost
from tests.test_kapatma import FakeOps


def row(name, category, count=1, mb=100):
    return {"ad": name, "adet": count, "bellek_mb": mb, "kategori": category}


class FakeFree:
    """Sıradaki boş bellek ölçümlerini (MB) döner: ilki kapatmadan önce, sonuncusu sonra."""

    def __init__(self, *values):
        self.values = list(values)

    def __call__(self):
        return self.values.pop(0) if len(self.values) > 1 else self.values[0]


class TestTargets(unittest.TestCase):
    def test_only_default_categories_and_never_protected(self):
        rows = [row("Discord", "iletisim"), row("OneDrive", "bulut"), row("GoogleUpdate", "guncelleyici"),
                row("chrome", "tarayici"), row("OBS64", "kayit_overlay"), row("iCUE", "rgb"),
                row("EpicGamesLauncher", "baslatici"), row("steam", "baslatici"), row("explorer", "iletisim")]
        names = [r["ad"] for r in boost.targets(rows)]
        # iletişim (Discord), tarayıcı, kayıt, RGB, başlatıcı, korumalı YOK; Discord yalnızca kullanıcı listesinden girer
        self.assertEqual(names, ["GoogleUpdate", "OneDrive"])

    def test_user_list_adds_running_unprotected_programs_only(self):
        ops = FakeOps([(1, "notepad.exe"), (2, "notepad.exe"), (3, "explorer.exe"), (5, "discord.exe")])
        found = boost.targets([row("Discord", "iletisim", 3, 400)], ["notepad", "explorer", "yok", "discord"], ops)
        self.assertEqual([(r["ad"], r["adet"]) for r in found], [("Discord", 3), ("notepad", 2)])  # discord iki kez girmez

    def test_nothing_known_gives_empty_list(self):
        self.assertEqual(boost.targets([]), [])
        self.assertEqual(boost.targets(None, []), [])


class TestRun(unittest.TestCase):
    def make(self, procs, free, closes=True, names=("chrome", "discord")):
        ops = FakeOps(procs, closes_on_request=closes)
        return ops, boost.Run(list(names), ops, free, timeout=0.2)

    def test_measures_closed_programs_processes_and_freed_memory(self):
        ops, run = self.make([(1, "chrome.exe"), (2, "chrome.exe"), (3, "discord.exe"), (4, "notepad.exe")],
                             FakeFree(8000, 10150))
        self.assertEqual(run.close(), [])
        result = run.result(settle=0)
        self.assertEqual(result, {"kapanan": ["chrome", "discord"], "acik": [], "surec": 3, "bosalan_mb": 2150})
        self.assertEqual(ops.terminated, [])  # nazik kapatma zorla sonlandırmaz
        self.assertEqual(ops.procs, [(4, "notepad.exe")])

    def test_no_gain_or_loss_is_reported_as_none_not_a_made_up_number(self):
        for after in (8000, 7500):  # fark yok / başka programlar bellek almış
            _, run = self.make([(1, "chrome.exe")], FakeFree(8000, after))
            run.close()
            self.assertIsNone(run.result(settle=0)["bosalan_mb"], after)

    def test_program_that_was_not_running_is_not_counted_as_closed(self):
        _, run = self.make([(1, "chrome.exe")], FakeFree(100, 200))
        run.close()
        result = run.result(settle=0)
        self.assertEqual((result["kapanan"], result["surec"]), (["chrome"], 1))  # discord hiç çalışmıyordu

    def test_stuck_program_is_reported_open_and_killed_only_by_force(self):
        ops, run = self.make([(1, "chrome.exe"), (2, "discord.exe")], FakeFree(100, 300), closes=False)
        self.assertEqual(run.close(), ["chrome", "discord"])
        self.assertEqual(ops.terminated, [])
        result = run.result(settle=0)
        self.assertEqual((result["kapanan"], result["acik"], result["surec"]), ([], ["chrome", "discord"], 0))
        self.assertEqual(run.force(["discord"]), 1)
        result = run.result(settle=0)
        self.assertEqual((result["kapanan"], result["acik"], result["surec"]), (["discord"], ["chrome"], 1))
        self.assertEqual(ops.terminated, [2])

    def test_protected_names_are_dropped_even_if_passed_in(self):
        ops = FakeOps([(1, "explorer.exe"), (2, "chrome.exe")])
        run = boost.Run(["explorer", "chrome", "chrome"], ops, FakeFree(1), timeout=0.2)
        self.assertEqual(run.names, ["chrome"])
        run.close()
        self.assertEqual(run.force(["explorer"]), 0)
        self.assertEqual(ops.procs, [(1, "explorer.exe")])


if __name__ == "__main__":
    unittest.main()
