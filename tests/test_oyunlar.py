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

    def get_priority(self, pid):
        return self.priorities.get(pid, 0x20)

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

    def test_classic_scan_skips_floppy_letters(self):
        """Denetim B O4: A: ve B: sürücüleri yoklanmaz (boşken yavaş yanıt verir)."""
        from unittest import mock
        asked = []
        with mock.patch.object(discovery.os.path, "isdir", lambda p: asked.append(p) or False):
            discovery._classic()
        self.assertNotIn("A:\\Games", asked)
        self.assertNotIn("B:\\Games", asked)
        self.assertIn("C:\\Games", asked)

    def test_generic_anticheat_installer_and_riot_path_are_detected(self):
        """Denetim B B1/O1: THE FINALS/ARC Raiders yalnızca AntiCheatInstaller.exe taşır; VMProtect anti-cheat sayılmaz;
        Valorant elle eklenirse yol "riot games" klasörü içerir."""
        import os
        finals = os.path.join(self.tmp.name, "THE FINALS")
        os.makedirs(finals)
        open(os.path.join(finals, "AntiCheatInstaller.exe"), "w").close()
        self.assertEqual(profiles.detect_anti_cheat({"kaynak": "Steam", "klasor": finals}), ["Anti-cheat"])
        rivals = os.path.join(self.tmp.name, "Rivals")
        os.makedirs(rivals)
        open(os.path.join(rivals, "VMProtectSDK64.dll"), "w").close()
        self.assertEqual(profiles.detect_anti_cheat({"kaynak": "Steam", "klasor": rivals}), [])
        self.assertEqual(profiles.detect_anti_cheat({"kaynak": "Elle", "klasor": r"D:\Riot Games\VALORANT\live"}), ["Riot Vanguard"])
        self.assertGreaterEqual(profiles.ANTI_CHEAT_VERSION, 3)

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

    def test_wrong_shaped_game_list_does_not_crash(self):
        """Denetim B B3: null / [] / öğesi sözlük olmayan liste açılışı çökertmez."""
        for text in ("null", "[]", '{"oyunlar": null}', '{"oyunlar": [1, "x"]}'):
            self.path.write_text(text, encoding="utf-8")
            profiles.GameStore(self.path)   # çökmemeli
        self.path.write_text('{"oyunlar": [1, {"id": "OYUN-a", "ad": "A"}]}', encoding="utf-8")
        self.assertEqual([g["id"] for g in profiles.GameStore(self.path).games], ["OYUN-a"])

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

    def test_recover_before_skips_newer_journal_but_reverts_older(self):
        mtime = self.journal.stat().st_mtime
        self.assertFalse(runtime.GameSession(self.sys, self.ops, self.journal).recover(before=mtime - 1))  # sonradan yazıldı
        self.assertTrue(self.journal.exists())
        self.assertNotIn("set_service", self.sys.calls)
        self.assertTrue(runtime.GameSession(self.sys, self.ops, self.journal).recover(before=mtime + 1))  # başlangıçtan önce kalan
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


class TestGameSessionOptions(unittest.TestCase):
    """Oyun-sırası seçenekleri (Rahatsız etme, güç planı, servisler, Steam yardımcı önceliği, Steam indirme uyarısı):
    yalnızca start() ile uygulanır, motordan geçer, stop()/recover() ile geri alınır. Sahte sistem; gerçek PC'ye dokunulmaz."""

    def setUp(self):
        from app.engine.backup import BackupStore
        from app.engine.engine import Engine
        from tests.fake_system import FakeResolver
        from tests.test_motor import DESKTOP
        self.tmp = tempfile.TemporaryDirectory()
        self.sys = FakeSystem()
        self.engine = Engine(system=self.sys, store=BackupStore(Path(self.tmp.name) / "yedek"), profile=DESKTOP,
                             resolver=FakeResolver(), is_admin=lambda: True)
        self.engine.prepare()
        self.ops = FakeOps(processes=[(20, "steamwebhelper.exe"), (21, "baska.exe")])
        self.ops.priorities[20] = 0x20
        self.journal = Path(self.tmp.name) / "oyun_oturumu.json"
        self.sys.services.update({"SysMain": {"baslangic": "Automatic", "calisiyor": True},
                                  "WSearch": {"baslangic": "AutomaticDelayed", "calisiyor": True},
                                  "WerSvc": {"baslangic": "Manual", "calisiyor": False}})
        self._downloading = discovery.steam_downloading
        discovery.steam_downloading = lambda *a, **k: False
        self.before = self.sys.state_copy()

    def tearDown(self):
        discovery.steam_downloading = self._downloading
        self.tmp.cleanup()

    def session(self):
        return runtime.GameSession(self.sys, self.ops, self.journal, engine=self.engine)

    def game(self, **extra):
        game = make_game(**extra)
        game.update(extra.pop("oyun", {}))
        return game

    ALL = {"hazirla_rahatsiz_etme": True, "hazirla_guc_plani": True, "hazirla_servisler": True,
           "hazirla_search": True, "hazirla_steam_oncelik": True, "hazirla_steam_uyari": True}

    def test_everything_off_by_default_and_nothing_written(self):
        self.assertFalse(any(profiles.DEFAULT_PROFILE[k] for k in profiles.RUNTIME_KEYS))
        session = self.session()
        self.assertEqual(session.start(self.game()), [])
        self.assertFalse(session.active)
        self.assertFalse(self.journal.exists())
        self.assertEqual(self.sys.state_copy(), self.before)

    def test_all_options_apply_through_engine_and_stop_reverts_everything(self):
        session = self.session()
        results = session.start(self.game(**self.ALL))
        self.assertTrue(all(ok for _k, ok, _d in results), results)
        self.assertEqual(self.sys.read_reg("HKCU", runtime.DND_KEY, runtime.DND_VALUE)[0], 0)
        self.assertEqual(self.sys.active_scheme, runtime.HIGH_PERFORMANCE_PLAN)
        self.assertFalse(self.sys.services["SysMain"]["calisiyor"])
        self.assertFalse(self.sys.services["WSearch"]["calisiyor"])
        self.assertEqual(self.ops.priorities[20], runtime.BELOW_NORMAL_PRIORITY_CLASS)
        self.assertNotIn(21, self.ops.priorities)  # başka sürece dokunulmadı
        for change_id in ("oyunsirasi-rahatsiz", "oyunsirasi-guc", "oyunsirasi-servis-SysMain"):
            self.assertTrue(self.engine.store.has(change_id), change_id)  # Değişiklikler'de görünür
        self.assertFalse(self.engine.store.has("oyunsirasi-servis-WerSvc"))  # zaten durmuştu
        self.assertTrue(session.active and self.journal.exists())
        session.stop()
        self.assertEqual(self.sys.state_copy(), self.before)
        self.assertEqual(self.ops.priorities[20], 0x20)
        self.assertFalse(self.journal.exists())
        self.assertEqual(self.engine.store.ids_newest_first(), [])

    def test_only_selected_options_apply(self):
        session = self.session()
        results = session.start(self.game(hazirla_rahatsiz_etme=True))
        self.assertEqual([(k, ok) for k, ok, _d in results], [("hazirla_rahatsiz_etme", True)])
        self.assertEqual(self.sys.active_scheme, "381b4222-f694-41f0-9685-ff5bb260df2e")
        self.assertTrue(self.sys.services["SysMain"]["calisiyor"])
        session.stop()

    def test_already_in_wanted_state_changes_nothing(self):
        self.sys.write_reg("HKCU", runtime.DND_KEY, runtime.DND_VALUE, 0, "REG_DWORD")
        self.sys.active_scheme = runtime.HIGH_PERFORMANCE_PLAN
        before = self.sys.state_copy()
        session = self.session()
        results = session.start(self.game(hazirla_rahatsiz_etme=True, hazirla_guc_plani=True))
        self.assertEqual([d for _k, _ok, d in results], ["zaten", "zaten"])
        self.assertFalse(session.active)
        self.assertEqual(self.sys.state_copy(), before)

    def test_anti_cheat_game_gets_only_safe_options(self):
        game = self.game(**self.ALL)
        game["anti_cheat"] = ["EasyAntiCheat"]
        self.assertEqual(profiles.runtime_options(game), profiles.RUNTIME_ANTI_CHEAT_OK)
        self.assertFalse({"hazirla_servisler", "hazirla_search", "hazirla_steam_oncelik"} & set(profiles.runtime_options(game)))
        session = self.session()
        results = session.start(game)  # kullanıcı dosyasında hepsi açık olsa bile uygulama katmanı süzer
        self.assertEqual({k for k, _ok, _d in results}, set(profiles.RUNTIME_ANTI_CHEAT_OK))
        self.assertTrue(self.sys.services["SysMain"]["calisiyor"])
        self.assertTrue(self.sys.services["WSearch"]["calisiyor"])
        self.assertEqual(self.ops.priorities, {20: 0x20})
        self.assertNotIn("set_service", self.sys.calls)
        session.stop()
        self.assertEqual(self.sys.state_copy(), self.before)

    def test_no_game_process_is_ever_touched(self):
        self.ops.processes.append((10, "oyun.exe"))
        session = self.session()
        session.start(self.game(**self.ALL))
        self.assertEqual(set(self.ops.priorities), {20})  # yalnızca steamwebhelper; oyun (10) ve diğerleri değil
        session.stop()

    def test_crash_recovery_on_next_start_reverts_everything(self):
        session = self.session()
        session.start(self.game(**self.ALL))
        self.assertTrue(self.journal.exists())
        # uygulama burada çöktü: stop() hiç çağrılmadı. Yeni açılışta yeni nesne günlüğü bulur.
        self.assertTrue(self.session().recover())
        self.assertEqual(self.sys.state_copy(), self.before)
        self.assertEqual(self.ops.priorities[20], 0x20)
        self.assertFalse(self.journal.exists())
        self.assertEqual(self.engine.store.ids_newest_first(), [])

    def test_recover_skips_pid_that_is_no_longer_steam_helper(self):
        """Denetim A B4: yeniden başlatmadan sonra günlükteki PID başka bir sürece ait olabilir."""
        session = self.session()
        session.start(self.game(hazirla_steam_oncelik=True))
        self.ops.processes = [(20, "baska.exe")]  # aynı PID artık ilgisiz bir süreç
        self.ops.priorities[20] = 0x4000
        self.assertTrue(self.session().recover())
        self.assertEqual(self.ops.priorities[20], 0x4000)  # dokunulmadı
        self.assertFalse(self.journal.exists())

    def test_crash_between_journal_and_write_is_safe(self):
        """Günlük her değişiklikten önce yazılır: yazma gerçekleşmediyse geri alma zararsızdır."""
        session = self.session()
        session.journal = {"oyun": "OYUN-1", "ad": "Oyun", "motor": ["oyunsirasi-guc"], "steam": []}
        session._save()
        self.assertTrue(self.session().recover())
        self.assertEqual(self.sys.state_copy(), self.before)
        self.assertFalse(self.journal.exists())

    def test_failed_revert_keeps_journal_and_retries(self):
        session = self.session()
        session.start(self.game(hazirla_servisler=True))
        self.sys.fail_on.add("set_service")
        session.stop()
        self.assertTrue(self.journal.exists())
        self.sys.fail_on.clear()
        self.assertTrue(self.session().recover())
        self.assertTrue(self.sys.services["SysMain"]["calisiyor"])
        self.assertFalse(self.journal.exists())

    def test_failed_apply_is_reported_and_leaves_no_trace(self):
        self.sys.fail_on.add("set_active_scheme")
        session = self.session()
        results = session.start(self.game(hazirla_guc_plani=True))
        self.assertFalse(results[0][1])
        self.assertFalse(session.active)
        self.assertEqual(self.sys.active_scheme, "381b4222-f694-41f0-9685-ff5bb260df2e")
        self.assertFalse(self.engine.store.has("oyunsirasi-guc"))

    def test_not_admin_applies_nothing(self):
        self.engine.is_admin = lambda: False
        session = self.session()
        results = session.start(self.game(**self.ALL))
        motor = ("hazirla_rahatsiz_etme", "hazirla_guc_plani", "hazirla_servisler", "hazirla_search")
        self.assertTrue(all(not ok for k, ok, _d in results if k in motor))  # motor yönetici ister
        self.assertEqual(self.sys.state_copy(), self.before)
        session.stop()  # Steam yardımcı önceliği (süreç işlemi, motorsuz) yine de geri alınır
        self.assertEqual(self.ops.priorities[20], 0x20)

    def test_steam_download_warning_never_touches_steam(self):
        discovery.steam_downloading = lambda *a, **k: True
        session = self.session()
        results = session.start(self.game(hazirla_steam_uyari=True))
        self.assertEqual(results, [("hazirla_steam_uyari", True, "indiriyor")])
        self.assertFalse(session.active)  # geri alınacak bir şey yok
        self.assertEqual(self.ops.priorities, {20: 0x20})
        self.assertEqual(self.sys.state_copy(), self.before)

    def test_steam_download_detection_uses_recent_files_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "steamapps" / "downloading" / "730"
            folder.mkdir(parents=True)
            discovery.steam_downloading = self._downloading
            original = discovery.steam_libraries
            discovery.steam_libraries = lambda: [tmp]
            try:
                self.assertFalse(discovery.steam_downloading())  # boş klasör
                (folder / "state.patch").write_bytes(b"x")
                self.assertTrue(discovery.steam_downloading())
                self.assertFalse(discovery.steam_downloading(now=os.stat(folder / "state.patch").st_mtime + 600))  # duraklatılmış
            finally:
                discovery.steam_libraries = original

    def test_journal_accepts_only_known_change_ids(self):
        self.assertTrue(runtime.journal_ok({"motor": ["oyunsirasi-rahatsiz", "oyunsirasi-servis-SysMain"], "steam": []}))
        self.assertFalse(runtime.journal_ok({"motor": ["baska-bir-degisiklik"], "steam": []}))
        self.assertFalse(runtime.journal_ok({"motor": "oyunsirasi-guc"}))

    def test_there_is_no_watcher_or_background_loop(self):
        self.assertFalse(hasattr(runtime, "GameWatcher"))
        import inspect
        self.assertNotIn("Thread", inspect.getsource(runtime.GameSession))


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
