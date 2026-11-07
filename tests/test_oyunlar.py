"""Oyunlar menüsü testleri (sahte sistem ve sahte süreç işlemleri; gerçek bilgisayara dokunulmaz).

Çalıştırma (proje klasöründe):
    py -3.12 -m unittest tests.test_oyunlar -v
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from app.games import discovery, profiles, runtime
from tests.fake_system import FakeSystem

class FakeOps:
    def __init__(self, processes=None):
        self.processes = processes or []
        self.paths = {}
        self.priorities = {}

    def list_processes(self):
        return list(self.processes)

    def process_path(self, pid):
        return self.paths.get(pid)

    def set_priority(self, pid, value):
        self.priorities[pid] = value


def make_game(**profile):
    game = {"id": "OYUN-1", "ad": "Oyun", "klasor": r"C:\Oyun", "kaynak": "Steam", "exe": r"C:\Oyun\oyun.exe",
            "profil": dict(profiles.DEFAULT_PROFILE, **profile)}
    return game


class TestDiscovery(unittest.TestCase):
    def test_vdf_parser(self):
        text = '"libraryfolders"\n{\n "0"\n {\n  "path"  "D:\\\\SteamLibrary"\n  "apps" { "730" "1" }\n }\n}'
        data = discovery._vdf(text)
        self.assertEqual(data["libraryfolders"]["0"]["path"], r"D:\SteamLibrary")

    def test_skip_patterns(self):
        for name in ("unins000.exe", "UnityCrashHandler64.exe", "vc_redist.x64.exe", "EasyAntiCheat_EOS_Setup.exe"):
            self.assertTrue(discovery.SKIP_EXE.search(name), name)
        self.assertFalse(discovery.SKIP_EXE.search("cs2.exe"))

    def test_unreal_bootstrap_exe_points_to_shipping_exe(self):
        r"""2.7: UE oyununda kökteki exe başlatıcıdır; gerçek oyun süreci Binaries\Win64\*-Shipping.exe."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Binaries").mkdir()
            ship = root / "Oyun" / "Binaries" / "Win64"
            ship.mkdir(parents=True)
            (root / "Oyun.exe").write_bytes(b"x")
            (ship / "Oyun-Win64-Shipping.exe").write_bytes(b"x")
            self.assertEqual(discovery.real_game_exe(str(root / "Oyun.exe")), str(ship / "Oyun-Win64-Shipping.exe"))
            self.assertEqual(discovery.real_game_exe(str(ship / "Oyun-Win64-Shipping.exe")),
                             str(ship / "Oyun-Win64-Shipping.exe"))
            (root / "Ikinci" / "Binaries" / "Win64").mkdir(parents=True)
            (root / "Ikinci" / "Binaries" / "Win64" / "B-Win64-Shipping.exe").write_bytes(b"x")
            self.assertEqual(discovery.real_game_exe(str(root / "Oyun.exe")), str(root / "Oyun.exe"))  # belirsiz: dokunma

    def test_launcher_and_client_exes_are_not_picked(self):
        """A6: League istemcisi (LeagueClientUxRender.exe) en büyük dosya olsa da oyun exe'si önce gelir."""
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "League of Legends"
            (folder / "Game").mkdir(parents=True)
            for name, size in (("LeagueClientUxRender.exe", 9000), ("LeagueClient.exe", 8000),
                               (r"Game\League of Legends.exe", 3000)):
                (folder / name).write_bytes(b"0" * size)
            found = [os.path.basename(p) for p in discovery.exe_candidates(str(folder))]
            self.assertEqual(found[0], "League of Legends.exe")
            client = str(folder / "LeagueClientUxRender.exe")
            self.assertEqual(discovery.real_game_exe(client), str(folder / "Game" / "League of Legends.exe"))
            store = profiles.GameStore(Path(tmp) / "oyunlar.json")
            game = store.add("League Of Legends", str(folder), "Riot", client)
            self.assertTrue(game["exe"].endswith("League of Legends.exe"))
            # eski kayıt istemciyle yapılmışsa açılışta düzeltilir
            store.games[0]["exe"] = client
            store.save()
            self.assertTrue(profiles.GameStore(Path(tmp) / "oyunlar.json").games[0]["exe"].endswith(
                "League of Legends.exe"))

    def test_scan_cache_and_source_errors(self):
        """A3: tarama sonucu kalıcı; bir kaynağın hatası kaydedilir, diğerleri devam eder."""
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(discovery, "cache_path",
                                                                     lambda: Path(tmp) / "c.json"):
            def broken():
                raise PermissionError("erişim reddedildi")
            sources = [("Bozuk", broken), ("İyi", lambda: [discovery._game("Oyun", tmp, "İyi")])]
            errors = {}
            with mock.patch.object(discovery, "SOURCES", sources):
                found = discovery.discover(errors)
            self.assertEqual([g["ad"] for g in found], ["Oyun"])
            self.assertEqual(errors, {"Bozuk": "erişim reddedildi"})
            discovery.save_cache(found, errors)
            cached = discovery.load_cache()  # yeniden başlatma sonrası: önceki liste hemen hazır
            self.assertEqual(cached["oyunlar"], found)
            self.assertEqual(cached["hatalar"], errors)


class TestStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = profiles.GameStore(Path(self.tmp.name) / "oyunlar.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_anti_cheat_cannot_be_added(self):
        with self.assertRaises(ValueError):
            self.store.add("Vanguard", r"C:\Riot", "Elle", r"C:\Program Files\Riot Vanguard\vgc.exe")

    def test_profile_persistence_and_old_in_game_fields_ignored(self):
        game = self.store.add("Oyun", r"C:\Oyun", "Steam", r"C:\Oyun\oyun.exe")
        self.assertNotIn("guc_plani", game["profil"])  # oyun sırasında ayarları kaldırıldı (izleyici yok)
        self.store.update_profile(game["id"], dict(game["profil"], oncelik="AboveNormal", guc_plani=True))
        again = profiles.GameStore(self.store.path).get(game["id"])["profil"]
        self.assertEqual(again["oncelik"], "AboveNormal")  # eski dosyadaki alan okunur ama hiçbir yerde kullanılmaz

    def test_anti_cheat_detection(self):
        import os
        folder = os.path.join(self.tmp.name, "Oyun")
        os.makedirs(os.path.join(folder, "Binaries", "Win64", "EasyAntiCheat"))
        game = self.store.add("Oyun", folder, "Steam", os.path.join(folder, "oyun.exe"))
        self.assertEqual(game["anti_cheat"], ["EasyAntiCheat"])
        riot = profiles.detect_anti_cheat({"kaynak": "Riot", "klasor": self.tmp.name + "/yok"})
        self.assertEqual(riot, ["Riot Vanguard"])
        self.assertEqual(profiles.detect_anti_cheat({"kaynak": "Steam", "klasor": self.tmp.name + "/yok"}), [])

    def test_blackcipher_is_detected_and_old_records_rescanned_once_without_losing(self):
        from unittest import mock
        """The First Descendant: EAC + Nexon BlackCipher (M1/Binaries/Win64/BlackCipher, 4. seviye)."""
        import os
        folder = os.path.join(self.tmp.name, "TFD")
        os.makedirs(os.path.join(folder, "EasyAntiCheat"))
        os.makedirs(os.path.join(folder, "M1", "Binaries", "Win64", "BlackCipher"))
        game = self.store.add("TFD", folder, "Steam", os.path.join(folder, "M1.exe"))
        self.assertEqual(game["anti_cheat"], ["EasyAntiCheat", "Nexon BlackCipher"])
        game["anti_cheat"] = ["EasyAntiCheat"]           # eski sürümün kaydı: BlackCipher tanınmıyordu
        del game["anti_cheat_surum"]
        gone = dict(game, id="OYUN-yok", klasor=os.path.join(self.tmp.name, "takili_degil"), anti_cheat=["BattlEye"])
        self.store.games.append(gone)
        self.store.ensure_anti_cheat()
        self.assertEqual(game["anti_cheat"], ["EasyAntiCheat", "Nexon BlackCipher"])
        self.assertEqual(gone["anti_cheat"], ["BattlEye"])  # klasör yok: bulunan koruma silinmez
        with mock.patch.object(profiles, "detect_anti_cheat") as again:
            self.store.ensure_anti_cheat()
        again.assert_not_called()                           # bir kez

    def test_persistent_changes_keep_other_compat_flags(self):
        game = make_game(oncelik="High", fso_kapali=True)
        registry = {("HKCU", profiles.LAYERS_KEY, game["exe"]): "~ RUNASADMIN"}
        changes = profiles.persistent_changes(game, game["profil"], lambda r, p, n: registry.get((r, p, n)))
        values = {cid.rsplit("-", 1)[1]: value for cid, _k, _s, value in changes}
        self.assertEqual(values["oncelik"], 3)
        self.assertEqual(values["fso"], "~ RUNASADMIN " + profiles.FSO_FLAG)
        self.assertNotIn("gpu", values)  # zaten varsayılan: değişiklik yok

    def test_read_persistent_trusts_system(self):
        game = make_game()
        registry = {("HKCU", profiles.GPU_KEY, game["exe"]): "GpuPreference=2;"}
        state = profiles.read_persistent(game, lambda r, p, n: registry.get((r, p, n)))
        self.assertEqual(state["gpu_tercihi"], "yuksek_performans")
        self.assertEqual(state["oncelik"], "Normal")


class TestStoreAfterHardReset(unittest.TestCase):
    """2.4: bilgisayar zorla kapatılınca oyunlar.json NUL dolu kalabilir; liste sessizce boşalıp ezilmemeli."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "oyunlar.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_damaged_file_restores_previous_copy(self):
        store = profiles.GameStore(self.path)
        store.add("Bir", r"C:\Bir", "Elle", r"C:\Bir\bir.exe")
        store.add("Iki", r"C:\Iki", "Elle", r"C:\Iki\iki.exe")   # ilk kayıt .onceki'ye geçer
        self.path.write_bytes(bytes(400))                            # zorla kapatma sonrası
        reloaded = profiles.GameStore(self.path)
        self.assertEqual(reloaded.load_error, "yedekten")
        self.assertEqual([g["ad"] for g in reloaded.games], ["Bir"])
        self.assertTrue((Path(self.tmp.name) / "oyunlar.bozuk.json").is_file())

    def test_damaged_without_copy_is_reported_not_silent(self):
        self.path.write_bytes(bytes(400))
        store = profiles.GameStore(self.path)
        self.assertEqual((store.load_error, store.games), ("bozuk", []))
        self.assertTrue((Path(self.tmp.name) / "oyunlar.bozuk.json").is_file())


OLD_JOURNAL = {"oyun": "OYUN-1", "ad": "Oyun", "pid": 10, "servisler": ["SysMain", "WSearch"],
               "guc_plani": "381b4222-f694-41f0-9685-ff5bb260df2e", "bildirim": {"var": False, "deger": None},
               "steam": [[20, 0x20]]}


class TestOldSessionRecovery(unittest.TestCase):
    """Eski sürümün (oyun izleyici) yarım kalan oyun-sırası günlüğü açılışta/kaldırırken geri alınır; yeni ayar uygulanmaz."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sys = FakeSystem()
        self.sys.services.update({"SysMain": {"baslangic": "Automatic", "calisiyor": False},
                                  "WSearch": {"baslangic": "AutomaticDelayed", "calisiyor": False}})
        self.sys.active_scheme = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
        self.sys.write_reg("HKCU", runtime.TOAST_KEY, "ToastEnabled", 0, "REG_DWORD")
        self.ops = FakeOps(processes=[(10, "oyun.exe"), (20, "steamwebhelper.exe")])
        self.ops.priorities[20] = runtime.BELOW_NORMAL_PRIORITY_CLASS
        self.journal = Path(self.tmp.name) / "oyun_oturumu.json"
        self.journal.write_text(json.dumps(OLD_JOURNAL), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_session_can_no_longer_apply_settings(self):
        self.assertFalse(hasattr(runtime.GameSession, "start"))
        self.assertFalse(hasattr(runtime, "GameWatcher"))

    def test_recover_reverts_everything(self):
        self.assertTrue(runtime.GameSession(self.sys, self.ops, self.journal).recover())
        self.assertTrue(self.sys.services["SysMain"]["calisiyor"])
        self.assertTrue(self.sys.services["WSearch"]["calisiyor"])
        self.assertEqual(self.ops.priorities[20], runtime.NORMAL_PRIORITY_CLASS)
        self.assertEqual(self.sys.active_scheme, OLD_JOURNAL["guc_plani"])
        self.assertIsNone(self.sys.read_reg("HKCU", runtime.TOAST_KEY, "ToastEnabled"))
        self.assertFalse(self.journal.exists())

    def test_failed_restore_keeps_journal_for_retry(self):
        self.sys.fail_on.add("set_service")
        runtime.GameSession(self.sys, self.ops, self.journal).recover()
        self.assertTrue(self.journal.exists())
        self.sys.fail_on.clear()
        self.assertTrue(runtime.GameSession(self.sys, self.ops, self.journal).recover())
        self.assertTrue(self.sys.services["SysMain"]["calisiyor"])
        self.assertFalse(self.journal.exists())

    def test_no_journal_nothing_happens(self):
        self.journal.unlink()
        self.assertFalse(runtime.GameSession(self.sys, self.ops, self.journal).recover())
        self.assertNotIn("set_service", self.sys.calls)

    def test_foreign_journal_is_ignored(self):
        self.journal.write_text('{"servisler": ["BaskaServis"], "steam": []}', encoding="utf-8")
        self.assertFalse(runtime.GameSession(self.sys, self.ops, self.journal).recover())
        self.assertNotIn("set_service", self.sys.calls)
        self.assertFalse(self.journal.exists())


class TestDetector(unittest.TestCase):
    """"Oyun açık mı" algılayıcısı: yalnızca haber verir (canlı FPS / kayıt için), hiçbir ayar uygulamaz."""

    def setUp(self):
        self.ops = FakeOps()
        self.events = []
        self.game = make_game()
        self.detector = runtime.GameDetector(lambda: [self.game], self.ops,
                                             on_event=lambda kind, g: self.events.append((kind, g["id"])))

    def test_start_and_exit(self):
        self.ops.processes = [(5, "vgc.exe"), (10, "oyun.exe")]
        self.ops.paths[10] = r"C:\Oyun\oyun.exe"
        self.detector.tick()
        self.assertEqual(self.events, [("basladi", "OYUN-1")])
        self.assertEqual(self.ops.priorities, {})  # hiçbir sürece (anti-cheat 5 dahil) dokunulmadı
        self.ops.processes = [(5, "vgc.exe")]
        self.detector.tick()
        self.assertEqual(self.events, [("basladi", "OYUN-1"), ("bitti", "OYUN-1")])
        self.assertIsNone(self.detector.active)

    def test_same_name_in_other_folder_is_ignored(self):
        self.ops.processes = [(11, "oyun.exe")]
        self.ops.paths[11] = r"D:\Baska\oyun.exe"
        self.detector.tick()
        self.assertEqual(self.events, [])


if __name__ == "__main__":
    unittest.main()
