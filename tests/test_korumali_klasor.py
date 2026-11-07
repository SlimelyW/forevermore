"""Korumalı yedek klasörü: gerçek ACL davranışı (geçici klasörde) ve eski yedeklerin taşınması. %ProgramData%'ya dokunmaz."""
import json
import logging
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.__main__ import _protect_backups
from app.core import admin, guvenli_klasor as g, paths, uninstall
from app.engine import uninstaller
from app.engine.backup import BackupStore
from app.ui import controller

ENTRY = [{"adim": {"tip": "kayit"}, "anlik": {"var": True}}]
SESSION = "20261104-120000"


def make_junction(link, target):
    subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True)


class GercekAcl(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.sid = g.current_sid()

    def test_program_data_comes_from_windows_not_environment(self):
        with mock.patch.dict(os.environ, {"ProgramData": str(self.root)}):
            self.assertNotEqual(g.common_appdata(), self.root)

    def test_sid_format(self):
        self.assertRegex(self.sid, r"^S-1-5-")

    def test_descriptor_contents(self):
        text = g.sddl("BU")
        self.assertTrue(text.startswith("O:BAD:PAI"))
        self.assertIn(f"(A;OICI;{g.READ_EXECUTE};;;OW)", text)
        self.assertNotIn("FA;;;BU", text)

    @unittest.skipIf(admin.is_admin(), "yükseltilmiş süreç zaten yazabilir")
    def test_normal_user_cannot_write_or_reopen_permissions(self):
        folder = self.root / "korumali"
        self.assertTrue(g._create(folder, g.sddl(self.sid, owner=None)))
        self.assertEqual(g.owner_of(folder), self.sid)   # sahip bile olsa: OW kaydı izin değiştirmeyi engellemeli
        with self.assertRaises(PermissionError):
            (folder / "a.txt").write_text("x", encoding="utf-8")
        done = subprocess.run(["icacls", str(folder), "/grant", f"*{self.sid}:F"], capture_output=True)
        self.assertNotEqual(done.returncode, 0)
        self.assertEqual(os.listdir(folder), [])         # okuma kalır (salt okunur mod)

    def test_create_returns_false_when_exists(self):
        self.assertFalse(g._create(self.root, g.sddl(None, owner=None)))

    def test_planted_folder_is_set_aside_unread(self):
        folder = self.root / "Forevermore"
        folder.mkdir()
        (folder / "sahte.json").write_text("{}", encoding="utf-8")
        self.assertEqual(g.ensure(folder, g.sddl(self.sid, owner=None)), folder)  # sahibi bu kullanıcı: güvenilmez
        self.assertEqual(os.listdir(folder), [])
        aside = [p for p in self.root.iterdir() if ".supheli_" in p.name]
        self.assertEqual(len(aside), 1)
        self.assertTrue((aside[0] / "sahte.json").is_file())  # silinmez

    def test_junction_is_never_trusted(self):
        target, link = self.root / "hedef", self.root / "baglanti"
        target.mkdir()
        (target / "a.txt").write_text("x", encoding="utf-8")
        make_junction(link, target)
        with mock.patch.object(g, "TRUSTED_OWNERS", {self.sid}):
            self.assertFalse(g.trusted(link))
            g.ensure(link, g.sddl(self.sid, owner=None))
        self.assertTrue((target / "a.txt").is_file())
        self.assertEqual(os.listdir(link), [])

    def test_planted_file_is_never_trusted(self):
        file = self.root / "dosya"
        file.write_text("x", encoding="utf-8")
        with mock.patch.object(g, "TRUSTED_OWNERS", {self.sid}):
            self.assertFalse(g.trusted(file))

    def test_trusted_owner_keeps_folder(self):
        folder = self.root / "iyi"
        folder.mkdir()
        (folder / "a.txt").write_text("x", encoding="utf-8")
        with mock.patch.object(g, "TRUSTED_OWNERS", {self.sid}):
            g.ensure(folder, g.sddl(None, owner=None))
        self.assertTrue((folder / "a.txt").is_file())

    def test_reset_acl_real_tree(self):
        (self.root / "k" / "alt").mkdir(parents=True)
        (self.root / "k" / "alt" / "a.txt").write_text("x", encoding="utf-8")
        self.assertTrue(g.reset_acl(self.root / "k"))


class SahteKlasor(unittest.TestCase):
    """ensure sahte: O:BA yükseltilmemiş süreçte kurulamaz; taşıma mantığı ACL'den bağımsız denenir."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.local = self.root / "LA"
        self.old = self.local / paths.APP_NAME
        self.secure_root = self.root / "PD" / paths.APP_NAME
        self.secure = self.secure_root / g.current_sid()

        def ensure(path, _text):
            Path(path).mkdir(parents=True, exist_ok=True)
            return Path(path)

        for patcher in (mock.patch.object(paths, "_local_appdata", return_value=self.local),
                        mock.patch.object(paths, "protected_root", return_value=self.secure_root),
                        mock.patch.object(g, "ensure", side_effect=ensure)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.reset = mock.patch.object(g, "reset_acl", return_value=True)
        self.reset_mock = self.reset.start()
        self.addCleanup(self.reset.stop)
        (self.old / "backups" / "reg").mkdir(parents=True)

    def _sign_old_backup(self):
        BackupStore(self.old / "backups").save_first("A", "Ayar", ENTRY)
        (self.old / "backups" / "reg" / "A_1.reg").write_text("reg", encoding="utf-8")

    def _old_session(self, name=SESSION):
        session = self.old / paths.UNINSTALL_BACKUPS / name
        (session / "k1").mkdir(parents=True)
        (session / "k1" / "a.txt").write_text("veri", encoding="utf-8")
        (session / "manifest.json").write_text(json.dumps({"program": "Foo", "tarih": "2026-11-04T12:00:00", "ogeler": []}),
                                               encoding="utf-8")


class Tasima(SahteKlasor):
    def test_signed_backups_move_and_old_copy_is_kept(self):
        self._sign_old_backup()
        self.assertTrue(paths.migrate_to_protected())
        self.assertEqual(paths.backups_dir(), self.secure / "backups")
        store = BackupStore()
        self.assertFalse(store.tampered)
        self.assertTrue(store.has("A"))
        self.assertTrue((self.secure / "backups" / "reg" / "A_1.reg").is_file())
        self.assertTrue((self.old / "backups.tasindi" / "yedekler.json").is_file())
        self.assertFalse((self.old / "backups").exists())

    def test_uninstall_sessions_move_and_acl_is_reset(self):
        self._old_session()
        paths.migrate_to_protected()
        base = self.secure / paths.UNINSTALL_BACKUPS
        self.assertEqual([s["oturum"] for s in uninstaller.list_sessions(uninstaller.backup_dir())], [SESSION])
        self.assertEqual(uninstaller.backup_dir(), base)
        self.assertTrue((base / SESSION / "k1" / "a.txt").is_file())
        self.assertFalse((self.old / paths.UNINSTALL_BACKUPS / SESSION).exists())
        self.assertEqual(self.reset_mock.call_count, 1)

    def test_junction_session_is_not_moved(self):
        target = self.root / "disarisi"
        target.mkdir()
        (self.old / paths.UNINSTALL_BACKUPS).mkdir()
        make_junction(self.old / paths.UNINSTALL_BACKUPS / SESSION, target)
        paths.migrate_to_protected()
        self.assertEqual(os.listdir(self.secure / paths.UNINSTALL_BACKUPS), [])

    def test_runs_once_and_never_rereads_user_folder(self):
        self._sign_old_backup()
        self.assertTrue(paths.migrate_to_protected())
        (self.old / "backups").mkdir()
        (self.old / "backups" / "yedekler.json").write_text('{"SAHTE": {}}', encoding="utf-8")
        self.assertFalse(paths.migrate_to_protected())
        self.assertFalse(BackupStore().has("SAHTE"))

    def test_fresh_install(self):
        shutil.rmtree(self.old)
        self.assertTrue(paths.migrate_to_protected())
        self.assertTrue((self.secure / "backups").is_dir())
        self.assertEqual(BackupStore().ids_newest_first(), [])

    def test_failed_copy_keeps_old_data_and_retries(self):
        self._sign_old_backup()
        with mock.patch.object(paths.shutil, "copytree", side_effect=OSError("disk dolu")):
            self.assertFalse(_protect_backups(logging.getLogger("test")))
        self.assertEqual(paths.backups_dir(), self.old / "backups")
        self.assertTrue(BackupStore(paths.backups_dir()).has("A"))
        self.assertTrue(paths.migrate_to_protected())
        self.assertTrue(BackupStore().has("A"))

    def test_incomplete_copy_is_rejected(self):
        self._sign_old_backup()
        real = paths._tree_sizes
        with mock.patch.object(paths, "_tree_sizes", side_effect=lambda root: {} if "tasiniyor" in root.name else real(root)):
            with self.assertRaises(OSError):
                paths.migrate_to_protected()
        self.assertFalse((self.secure / "backups").exists())
        self.assertTrue((self.old / "backups" / "yedekler.json").is_file())

    def test_interrupted_session_move_resumes(self):
        self._sign_old_backup()
        self._old_session("20261104-120000")
        self._old_session("20261104-130000")
        real = shutil.move
        calls = []

        def fail_second(source, target):
            calls.append(source)
            if len(calls) == 2:
                raise OSError("kilitli")
            return real(source, target)

        with mock.patch.object(paths.shutil, "move", side_effect=fail_second):
            with self.assertRaises(OSError):
                paths.migrate_to_protected()
        self.assertEqual(paths.backups_dir(), self.old / "backups")   # işaret yok: yarım taşıma kullanılmaz
        self.assertTrue(paths.migrate_to_protected())
        self.assertEqual(len(uninstaller.list_sessions()), 2)
        self.assertTrue(BackupStore().has("A"))

    def test_unsigned_old_file_needs_user_confirmation(self):
        (self.old / "backups" / "yedekler.json").write_text(
            json.dumps({"A": {"ad": "x", "zaman": "2026-01-01T00:00:00", "adimlar": []}}), encoding="utf-8")
        paths.migrate_to_protected()
        store = BackupStore()
        self.assertTrue(store.tampered)
        self.assertFalse(store.has("A"))
        self.assertEqual(store.recover(), 1)
        self.assertTrue(BackupStore().has("A"))

    def test_tampered_old_file_is_not_trusted_after_move(self):
        self._sign_old_backup()
        file = self.old / "backups" / "yedekler.json"
        document = json.loads(file.read_text(encoding="utf-8"))
        document["veri"]["A"]["ad"] = "degisti"
        file.write_text(json.dumps(document), encoding="utf-8")
        paths.migrate_to_protected()
        self.assertTrue(BackupStore().tampered)

    def test_not_migrated_uses_old_location(self):
        self.assertEqual(paths.backups_dir(), self.old / "backups")
        self.assertEqual(paths.uninstall_backups_dir(), self.old / paths.UNINSTALL_BACKUPS)


class Kaldirma(SahteKlasor):
    def test_delete_data_removes_protected_folder_and_empty_root(self):
        self._sign_old_backup()
        paths.migrate_to_protected()
        engine = mock.Mock(changed_ids=lambda: [], revert_all=lambda: [])
        session = mock.Mock(recover=lambda: False)
        with mock.patch.object(uninstall, "autostart"), mock.patch.object(logging, "shutdown"):
            self.assertTrue(uninstall.cleanup(engine, delete_data=True, session=session)["veri_silindi"])
        self.assertFalse(self.secure_root.exists())
        self.assertFalse((self.old / "backups.tasindi").exists())

    def test_other_accounts_backups_stay(self):
        paths.migrate_to_protected()
        other = self.secure_root / "S-1-5-21-baska"
        other.mkdir()
        engine = mock.Mock(changed_ids=lambda: [], revert_all=lambda: [])
        with mock.patch.object(uninstall, "autostart"), mock.patch.object(logging, "shutdown"):
            uninstall.cleanup(engine, delete_data=True, session=mock.Mock(recover=lambda: False))
        self.assertTrue(other.is_dir())
        self.assertFalse(self.secure.exists())


class KaldiriciIzin(unittest.TestCase):
    def test_acl_reset_after_backup_and_after_restore(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(g, "reset_acl", return_value=True) as reset:
            root = Path(tmp)
            folder = root / "Program"
            folder.mkdir()
            (folder / "a.txt").write_text("x", encoding="utf-8")
            result = uninstaller.remove_leftovers("Foo", [{"tur": "klasor", "yol": str(folder)}], root / "yedek", mock.Mock())
            self.assertEqual(reset.call_args[0][0].name, "k1")
            uninstaller.restore(result["oturum"], root / "yedek", mock.Mock())
            self.assertEqual(reset.call_args[0][0], str(folder))
            self.assertEqual(reset.call_count, 2)
            self.assertTrue((folder / "a.txt").is_file())

    def test_acl_failure_does_not_lose_the_item(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(g, "reset_acl", return_value=False):
            root = Path(tmp)
            folder = root / "Program"
            folder.mkdir()
            result = uninstaller.remove_leftovers("Foo", [{"tur": "klasor", "yol": str(folder)}], root / "yedek", mock.Mock())
            self.assertEqual(result["kaldirilan"], 1)


class SaltOkunurDepo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name) / "backups"

    def _files(self):
        return {p.name: p.read_bytes() for p in self.folder.iterdir()}

    def test_reads_without_touching_the_folder(self):
        BackupStore(self.folder).save_first("A", "Ayar", ENTRY)
        before = self._files()
        store = BackupStore(self.folder, readonly=True)
        self.assertTrue(store.has("A"))
        store.save_first("B", "Ayar", ENTRY)
        store.history("uygula", "A", True)
        self.assertEqual(self._files(), before)

    def test_missing_folder_is_not_created(self):
        store = BackupStore(self.folder, readonly=True)
        self.assertEqual(store.ids_newest_first(), [])
        self.assertFalse(self.folder.exists())

    def test_tampered_file_stays_in_place(self):
        BackupStore(self.folder).save_first("A", "Ayar", ENTRY)
        file = self.folder / "yedekler.json"
        file.write_text(file.read_text(encoding="utf-8").replace("Ayar", "Oyna"), encoding="utf-8")
        before = self._files()
        store = BackupStore(self.folder, readonly=True)
        self.assertTrue(store.tampered)
        self.assertEqual(self._files(), before)

    def test_unsigned_old_file_is_not_rewritten(self):
        self.folder.mkdir()
        (self.folder / "yedekler.json").write_text(
            json.dumps({"A": {"ad": "x", "zaman": "2026-01-01T00:00:00", "adimlar": []}}), encoding="utf-8")
        before = self._files()
        self.assertTrue(BackupStore(self.folder, readonly=True).has("A"))
        self.assertEqual(self._files(), before)


class Baslangic(unittest.TestCase):
    def test_store_is_read_only_unless_normal_mode(self):
        for mode, readonly in ((controller.MODE_READ_ONLY, True), (controller.MODE_BACKUPS_NOT_MOVED, True),
                               (controller.MODE_NORMAL, False)):
            with mock.patch.object(controller, "BackupStore") as store, mock.patch.object(controller, "WindowsSystem"), \
                    mock.patch.object(controller, "Engine"), tempfile.TemporaryDirectory() as tmp:
                controller.Controller(mode, cache_file=Path(tmp) / "onbellek.json")
                store.assert_called_once_with(readonly=readonly)

    def test_failed_move_blocks_normal_mode(self):
        with mock.patch.object(paths, "migrate_to_protected", side_effect=PermissionError("hayir")):
            self.assertFalse(_protect_backups(logging.getLogger("test")))
        with mock.patch.object(paths, "migrate_to_protected", return_value=False):
            self.assertTrue(_protect_backups(logging.getLogger("test")))


if __name__ == "__main__":
    unittest.main()
