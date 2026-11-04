"""Uygulama kaldırıcı: sahte kayıt defteri ve geçici klasörlerle (gerçek sisteme dokunmaz)."""
import datetime
import json
import tempfile
import unittest
from pathlib import Path

from app.engine import uninstaller as u


class FakeReg:
    """{(kök, yol): {değer: veri}}; subkeys yalnızca doğrudan alt anahtarları verir."""

    def __init__(self, keys):
        self.keys = {(r, p.lower()): (p, v) for (r, p), v in keys.items()}

    def subkeys(self, root, path):
        prefix = path.lower() + "\\"
        out = set()
        for (r, low), (orig, _v) in self.keys.items():
            if r == root and low.startswith(prefix):
                out.add(orig[len(path) + 1:].split("\\")[0])
        return sorted(out)

    def read(self, root, path, name, default=None):
        return self.keys.get((root, path.lower()), (None, {}))[1].get(name, default)


class FakeOps:
    def __init__(self, fail_delete=()):
        self.exported, self.deleted, self.imported, self.fail_delete = [], [], [], set(fail_delete)

    def export(self, root, path, file):
        Path(file).write_text(f"{root}\\{path}", encoding="utf-8")
        self.exported.append(path)
        return True

    def delete(self, root, path):
        if path in self.fail_delete:
            return False
        self.deleted.append(path)
        return True

    def import_file(self, file):
        self.imported.append(Path(file).name)
        return True


UNINSTALL = u.UNINSTALL_KEYS[0][1]


def program(**extra):
    base = {"ad": "Foo Tool 1.2.3 (x64)", "surum": "1.2.3", "yayinci": "Foo Soft", "konum": "", "komut": '"C:\\x\\unins.exe" /S',
            "boyut_kb": 0, "kok": "HKLM", "anahtar": UNINSTALL + "\\Foo", "korumali": False}
    base.update(extra)
    return base


class TestList(unittest.TestCase):
    def test_lists_programs_and_skips_updates_and_system_components(self):
        reg = FakeReg({
            ("HKLM", UNINSTALL + "\\A"): {"DisplayName": "Alpha", "UninstallString": "a.exe", "DisplayVersion": "1"},
            ("HKLM", UNINSTALL + "\\B"): {"DisplayName": "Beta", "UninstallString": "b.exe", "SystemComponent": 1},
            ("HKLM", UNINSTALL + "\\C"): {"DisplayName": "Gamma update", "UninstallString": "c.exe", "ParentKeyName": "X"},
            ("HKLM", UNINSTALL + "\\D"): {"DisplayName": "Delta"},                                     # kaldırma komutu yok
            ("HKLM", UNINSTALL + "\\E"): {"DisplayName": "Microsoft Visual C++ 2015", "UninstallString": "e.exe"},
        })
        names = [p["ad"] for p in u.list_programs(reg)]
        self.assertEqual(names, ["Alpha", "Microsoft Visual C++ 2015"])
        self.assertTrue(u.list_programs(reg)[1]["korumali"])

    def test_split_command(self):
        self.assertEqual(u.split_command('"C:\\A B\\unins000.exe" /SILENT'), ("C:\\A B\\unins000.exe", "/SILENT"))
        self.assertEqual(u.split_command("MsiExec.exe /X{1234}"), ("MsiExec.exe", "/X{1234}"))
        self.assertEqual(u.split_command("C:\\Prog\\un.exe -x"), ("C:\\Prog\\un.exe", "-x"))

    def test_protected_program_is_not_started(self):
        calls = []
        self.assertFalse(u.start_uninstall(program(korumali=True), lambda e, a: calls.append((e, a)) or True))
        self.assertTrue(u.start_uninstall(program(), lambda e, a: calls.append((e, a)) or True))
        self.assertEqual(calls, [("C:\\x\\unins.exe", "/S")])


class TestLeftovers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for rel in ("PF/Foo Tool", "PF/Other App", "AD/foo-tool", "LA/FooTool/cache", "LA/Microsoft", "PD/Foo Soft"):
            (self.root / rel).mkdir(parents=True)
        (self.root / "LA/FooTool/cache/a.bin").write_bytes(b"x" * 100)
        self.env = {"ProgramFiles": str(self.root / "PF"), "APPDATA": str(self.root / "AD"), "LOCALAPPDATA": str(self.root / "LA"),
                    "ProgramData": str(self.root / "PD"), "SystemRoot": str(self.root / "Windows")}
        self.reg = FakeReg({("HKCU", "Software\\FooTool"): {}, ("HKCU", "Software\\Foo Soft\\Foo Tool"): {},
                            ("HKCU", "Software\\Foo Soft\\Other"): {}, ("HKLM", "SOFTWARE\\Microsoft"): {},
                            ("HKLM", "SOFTWARE\\OtherApp"): {}})

    def tearDown(self):
        self.tmp.cleanup()

    def test_only_exact_name_matches(self):
        found = u.find_leftovers(program(), self.env, self.reg)
        folders = sorted(Path(i["yol"]).name for i in found if i["tur"] == "klasor")
        keys = sorted(i["yol"] for i in found if i["tur"] == "kayit")
        self.assertEqual(folders, ["Foo Tool", "FooTool", "foo-tool"])        # yayıncı klasörü ("Foo Soft") ve başkaları değil
        self.assertEqual(keys, ["Software\\Foo Soft\\Foo Tool", "Software\\FooTool"])
        self.assertEqual(next(i for i in found if i["tur"] == "klasor" and i["yol"].endswith("FooTool"))["boyut"], 100)

    def test_generic_names_are_never_matched(self):
        self.assertEqual(u.find_leftovers(program(ad="Microsoft", konum=""), self.env, self.reg), [])
        self.assertEqual(u.find_leftovers(program(ad="Ab"), self.env, self.reg), [])      # çok kısa

    def test_install_location_that_is_a_root_is_ignored(self):
        found = u.find_leftovers(program(ad="Zeta Zeta", konum=self.env["ProgramFiles"]), self.env, self.reg)
        self.assertEqual(found, [])


class TestRemoveAndRestore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.folder = self.root / "LA" / "FooTool"
        (self.folder / "x").mkdir(parents=True)
        (self.folder / "x" / "a.txt").write_text("veri", encoding="utf-8")
        self.base = self.root / "yedek"
        self.now = datetime.datetime(2026, 10, 29, 12, 0, 0)

    def tearDown(self):
        self.tmp.cleanup()

    def test_remove_backs_up_and_restore_brings_back(self):
        ops = FakeOps()
        items = [{"tur": "klasor", "yol": str(self.folder)}, {"tur": "kayit", "kok": "HKCU", "yol": "Software\\FooTool"}]
        result = u.remove_leftovers("Foo Tool", items, self.base, ops, self.now)
        self.assertEqual((result["kaldirilan"], result["basarisiz"]), (2, []))
        self.assertFalse(self.folder.exists())
        self.assertEqual(ops.exported, ["Software\\FooTool"])
        sessions = u.list_sessions(self.base)
        self.assertEqual([(s["program"], s["adet"]) for s in sessions], [("Foo Tool", 2)])
        back = u.restore(result["oturum"], self.base, ops)
        self.assertEqual((back["geri_yuklenen"], back["basarisiz"]), (2, []))
        self.assertEqual((self.folder / "x" / "a.txt").read_text(encoding="utf-8"), "veri")
        self.assertEqual(len(ops.imported), 1)
        self.assertEqual(u.list_sessions(self.base), [])                      # başarıyla geri yüklenen oturum temizlenir

    def test_failed_registry_delete_is_reported_and_not_counted(self):
        ops = FakeOps(fail_delete={"SOFTWARE\\FooTool"})
        result = u.remove_leftovers("Foo Tool", [{"tur": "kayit", "kok": "HKLM", "yol": "SOFTWARE\\FooTool"}], self.base, ops, self.now)
        self.assertEqual(result["kaldirilan"], 0)
        self.assertEqual(result["basarisiz"][0]["yol"], "SOFTWARE\\FooTool")
        self.assertIsNone(result["oturum"])
        self.assertEqual(u.list_sessions(self.base), [])

    def test_restore_does_not_overwrite_existing_folder(self):
        result = u.remove_leftovers("Foo Tool", [{"tur": "klasor", "yol": str(self.folder)}], self.base, FakeOps(), self.now)
        self.folder.mkdir(parents=True)
        back = u.restore(result["oturum"], self.base, FakeOps())
        self.assertEqual(back["geri_yuklenen"], 0)
        self.assertEqual(len(back["basarisiz"]), 1)
        self.assertEqual(len(u.list_sessions(self.base)), 1)                  # yedek korunur

    def test_delete_session_rejects_paths(self):
        with self.assertRaises(ValueError):
            u.delete_session("..\\x", self.base)
        result = u.remove_leftovers("Foo Tool", [{"tur": "klasor", "yol": str(self.folder)}], self.base, FakeOps(), self.now)
        u.delete_session(result["oturum"], self.base)
        self.assertEqual(u.list_sessions(self.base), [])


if __name__ == "__main__":
    unittest.main()
