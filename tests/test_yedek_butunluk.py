"""Yedek dosyası imzası (HMAC) ve geri almadan önce adım denetimi (SECURITY.md F2 #2). Gerçek sisteme dokunmaz."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from app.engine.backup import BackupStore
from tests.test_motor import EngineTestBase

ENTRY = [{"adim": {"tur": "yerlesik", "eylem": "guc_modu", "parametreler": {"kaynak": "ac"}}, "anlik": {"deger": "x"}}]


class BackupSignatureTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _store_with_entry(self):
        store = BackupStore(self.folder)
        store.save_first("A", "Ayar A", ENTRY)
        return store

    def test_signed_file_reloads(self):
        self._store_with_entry()
        reloaded = BackupStore(self.folder)
        self.assertFalse(reloaded.tampered)
        self.assertTrue(reloaded.has("A"))

    def test_edited_value_is_rejected_and_kept_aside(self):
        self._store_with_entry()
        document = json.loads((self.folder / "yedekler.json").read_text(encoding="utf-8"))
        document["veri"]["A"]["adimlar"][0]["anlik"]["deger"] = "sahte"
        (self.folder / "yedekler.json").write_text(json.dumps(document), encoding="utf-8")
        reloaded = BackupStore(self.folder)
        self.assertTrue(reloaded.tampered)
        self.assertFalse(reloaded.has("A"))
        self.assertTrue((self.folder / "yedekler.bozuk.json").is_file())

    def test_stripping_the_signature_does_not_downgrade_to_legacy(self):
        self._store_with_entry()
        document = json.loads((self.folder / "yedekler.json").read_text(encoding="utf-8"))
        (self.folder / "yedekler.json").write_text(json.dumps(document["veri"]), encoding="utf-8")
        reloaded = BackupStore(self.folder)
        self.assertTrue(reloaded.tampered)
        self.assertFalse(reloaded.has("A"))

    def test_legacy_unsigned_file_is_accepted_once_and_signed(self):
        (self.folder / "yedekler.json").write_text(json.dumps({"A": {"ad": "x", "zaman": "2026-01-01T00:00:00",
                                                                     "adimlar": ENTRY}}), encoding="utf-8")
        store = BackupStore(self.folder)
        self.assertFalse(store.tampered)
        self.assertTrue(store.has("A"))
        self.assertEqual(json.loads((self.folder / "yedekler.json").read_text(encoding="utf-8"))["surum"], 2)
        self.assertTrue(BackupStore(self.folder).has("A"))


class CrashRecoveryTest(unittest.TestCase):
    """Ani kapanma: ilk değişiklikte yazılan imza anahtarı boş / NUL dolu / yarım kalırsa (1.2)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        BackupStore(self.folder).save_first("CPU-004", "Spectre", ENTRY)
        self.key = self.folder / "yedek_anahtar.dat"
        self.good = self.key.read_bytes()

    def tearDown(self):
        self.tmp.cleanup()

    def broken_stores(self):
        for data in (b"", b"\0" * len(self.good), self.good[: len(self.good) // 2]):
            shutil.rmtree(self.folder)
            self.folder.mkdir()
            BackupStore(self.folder).save_first("CPU-004", "Spectre", ENTRY)
            self.key.write_bytes(data)
            yield BackupStore(self.folder)

    def test_recover_brings_back_revert_records(self):
        for store in self.broken_stores():
            self.assertTrue(store.tampered)
            self.assertTrue(store.recoverable)
            self.assertEqual(store.recover(), 1)
            self.assertFalse(store.tampered)
            reloaded = BackupStore(self.folder)  # yeni anahtarla imzalandı: bir sonraki açılış temiz
            self.assertFalse(reloaded.tampered)
            self.assertTrue(reloaded.has("CPU-004"))

    def test_reset_and_continue_does_not_loop(self):
        for store in self.broken_stores():
            store.dismiss_broken()
            self.assertFalse(store.tampered)
            store.save_first("PERF-001", "Yeni", ENTRY)
            reloaded = BackupStore(self.folder)
            self.assertFalse(reloaded.tampered)   # eskiden bozuk anahtar kalıyor, her açılış yeniden "değiştirilmiş"
            self.assertTrue(reloaded.has("PERF-001"))
            self.assertTrue((self.folder / "yedekler.bozuk.json").is_file())

    def test_second_quarantine_keeps_the_first(self):
        for store in self.broken_stores():
            store.dismiss_broken()
            store.save_first("PERF-001", "Yeni", ENTRY)
            (self.folder / "yedekler.json").write_text("{bozuk", encoding="utf-8")
            BackupStore(self.folder)
            self.assertEqual(len(list(self.folder.glob("yedekler.bozuk*.json"))), 2)

    def test_recover_skips_malformed_entries(self):
        store = next(self.broken_stores())
        store.recoverable["KOTU"] = {"ad": "x"}
        self.assertEqual(store.recover(), 1)
        self.assertFalse(store.has("KOTU"))


class DiskWriteFailureTest(unittest.TestCase):
    """Denetim A B2: diske yazılamazsa bellekteki kayıt da değişmemeli (bellek = disk)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = BackupStore(Path(self.tmp.name))
        self.store.save_first("A", "Ayar A", ENTRY)  # anahtar ve dosya oluştu

    def failing_disk(self):
        from unittest import mock
        from app.engine import backup
        return mock.patch.object(backup.paths, "atomic_write", side_effect=PermissionError("Erişim engellendi"))

    def test_save_first_failure_leaves_no_ghost_record(self):
        with self.failing_disk(), self.assertRaises(PermissionError):
            self.store.save_first("B", "Ayar B", ENTRY)
        self.assertFalse(self.store.has("B"))

    def test_remove_failure_keeps_record_in_memory(self):
        with self.failing_disk(), self.assertRaises(PermissionError):
            self.store.remove("A")
        self.assertTrue(self.store.has("A"))
        self.assertTrue(BackupStore(Path(self.tmp.name)).has("A"))

    def test_stamp_rev_failure_does_not_change_memory(self):
        with self.failing_disk(), self.assertRaises(PermissionError):
            self.store.stamp_rev("A", 7)
        self.assertNotIn("rev", self.store.get("A"))


class ListingLockTest(unittest.TestCase):
    def test_ids_newest_first_waits_for_writer(self):
        """Denetim A O5: liste, işçi iş parçacığı yazarken gezilmemeli (dictionary changed size during iteration)."""
        import threading
        with tempfile.TemporaryDirectory() as tmp:
            store = BackupStore(Path(tmp))
            store.save_first("A", "Ayar A", ENTRY)
            out = []
            with store._lock:  # bir yazıcı kilidi tutuyor
                reader = threading.Thread(target=lambda: out.append(store.ids_newest_first()))
                reader.start()
                reader.join(0.2)
                self.assertTrue(reader.is_alive())
            reader.join(5)
            self.assertEqual(out, [["A"]])


class RevertValidationTest(EngineTestBase):
    def test_revert_skips_a_stored_registry_step_with_a_bad_root(self):
        step = {"tur": "registry", "kok": "HKEY_USERS", "yol": r"Software\Test", "ad": "Deger",
                "veri_turu": "REG_DWORD", "acik": 1, "kapali": None, "yoksa": None}
        self.engine.store.save_first("EVIL-1", "Sahte", [{"adim": step, "anlik": {"deger": 5, "tur": "REG_DWORD"}}])
        before = self.sys.state_copy()
        result = self.engine.revert("EVIL-1")
        self.assertFalse(result.ok)
        self.assertEqual(result.key, "hata.geri_alma_kismen")
        self.assertEqual(self.sys.state_copy(), before)  # hiçbir şey yazılmadı
        self.assertTrue(self.engine.store.has("EVIL-1"))


if __name__ == "__main__":
    unittest.main()
