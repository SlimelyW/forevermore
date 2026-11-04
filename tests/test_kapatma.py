"""Boost, adım 2: program kapatma kuralları (sahte süreç işlemleriyle; gerçek süreç kapatılmaz)."""

import unittest

from app.engine import closer


class FakeOps:
    def __init__(self, procs, closes_on_request=True):
        self.procs = list(procs)  # [(pid, exe)]
        self.closes_on_request = closes_on_request
        self.asked, self.terminated = [], []

    def list_processes(self):
        return list(self.procs)

    def post_close(self, pids):
        self.asked.append(sorted(pids))
        if self.closes_on_request:
            self.procs = [p for p in self.procs if p[0] not in pids]
        return len(pids)

    def terminate(self, pid):
        self.terminated.append(pid)
        self.procs = [p for p in self.procs if p[0] != pid]
        return True


class TestCloser(unittest.TestCase):
    def test_protected_names_are_never_touched(self):
        for name in ("explorer", "Explorer.EXE", "svchost", "MsMpEng.exe", "vgc.exe", "EasyAntiCheat", "steam.exe",
                     "python", "Forevermore"):
            self.assertTrue(closer.is_protected(name), name)
            ops = FakeOps([(1, name.lower() if name.lower().endswith(".exe") else name.lower() + ".exe")])
            self.assertEqual(closer.close_gently(name, ops), "korumali")
            self.assertEqual(closer.kill(name, ops), 0)
            self.assertEqual((ops.asked, ops.terminated), ([], []))
        self.assertFalse(closer.is_protected("chrome"))

    def test_gentle_close_all_processes_of_the_program(self):
        ops = FakeOps([(10, "chrome.exe"), (11, "chrome.exe"), (12, "notepad.exe")])
        self.assertEqual(closer.close_gently("Chrome", ops, timeout=1), "kapandi")
        self.assertEqual(ops.asked, [[10, 11]])
        self.assertEqual(ops.terminated, [])  # nazik kapatmada zorla sonlandırma yok
        self.assertEqual(ops.procs, [(12, "notepad.exe")])

    def test_program_that_does_not_close_is_reported_and_not_killed(self):
        ops = FakeOps([(10, "discord.exe")], closes_on_request=False)
        self.assertEqual(closer.close_gently("discord", ops, timeout=0.3, poll=0.05), "calisiyor")
        self.assertEqual(ops.terminated, [])
        self.assertEqual(closer.kill("discord", ops), 1)  # yalnızca açıkça çağrılınca
        self.assertEqual(ops.terminated, [10])

    def test_running_and_close_many_skip_protected_and_never_force(self):
        ops = FakeOps([(1, "chrome.exe"), (2, "discord.exe"), (3, "explorer.exe")], closes_on_request=False)
        self.assertEqual(closer.running(["chrome", "explorer", "yok", "discord"], ops), ["chrome", "discord"])
        result = closer.close_many(["chrome", "explorer"], ops, timeout=0.2)
        self.assertEqual(result, {"chrome": "calisiyor", "explorer": "korumali"})
        self.assertEqual(ops.terminated, [])  # toplu kapatma zorla sonlandırmaz

    def test_not_running(self):
        self.assertEqual(closer.close_gently("chrome", FakeOps([]), timeout=0.2), "yok")


if __name__ == "__main__":
    unittest.main()
