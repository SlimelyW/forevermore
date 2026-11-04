"""Oyunlar menüsü testleri (sahte sistem ve sahte süreç işlemleri; gerçek bilgisayara dokunulmaz).

Çalıştırma (proje klasöründe):
    py -3.12 -m unittest tests.test_oyunlar -v
"""

import os
import tempfile
import unittest
from pathlib import Path

from app.games import discovery, profiles, runtime
from tests.fake_system import FakeSystem

TOPOLOGY = {
    "cpular": [{"id": 256 + n, "no": n, "cekirdek": n // 2 * 2, "l3": 0 if n < 8 else 8, "sinif": 1 if n < 8 else 0,
                "p": n < 8, "ilk_is_parcacigi": n % 2 == 0, "l3_boyut": None} for n in range(20)],
    "hibrit": True, "smt": True, "vcache_l3": None,
    "l3_gruplari": [{"indeks": 0, "boyut_mb": 16, "cpular": list(range(8))},
                    {"indeks": 8, "boyut_mb": 8, "cpular": list(range(8, 20))}],
}


class FakeOps:
    def __init__(self, processes=None, deny=()):
        self.processes = processes or []
        self.paths = {}
        self.deny = set(deny)
        self.cpu_sets = {}
        self.exempt = set()
        self.priorities = {}
        self.purged = 0

    def list_processes(self):
        return list(self.processes)

    def process_path(self, pid):
        return self.paths.get(pid)

    def _check(self, name):
        if name in self.deny:
            raise PermissionError("erişim reddedildi")

    def set_cpu_sets(self, pid, ids):
        self._check("cpu")
        self.cpu_sets[pid] = list(ids)

    def exempt_power_throttling(self, pid):
        self._check("throttle")
        self.exempt.add(pid)

    def get_priority(self, pid):
        return self.priorities.get(pid, runtime.NORMAL_PRIORITY_CLASS)

    def set_priority(self, pid, value):
        self.priorities[pid] = value

    def purge_standby(self):
        self.purged += 1


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

    def test_runtime_games_and_persistence(self):
        game = self.store.add("Oyun", r"C:\Oyun", "Steam", r"C:\Oyun\oyun.exe")
        self.assertEqual(self.store.runtime_games(), [])
        self.store.update_profile(game["id"], dict(game["profil"], guc_plani=True))
        self.assertEqual(len(self.store.runtime_games()), 1)
        again = profiles.GameStore(self.store.path)
        self.assertTrue(again.get(game["id"])["profil"]["guc_plani"])

    def test_anti_cheat_detection(self):
        import os
        folder = os.path.join(self.tmp.name, "Oyun")
        os.makedirs(os.path.join(folder, "Binaries", "Win64", "EasyAntiCheat"))
        game = self.store.add("Oyun", folder, "Steam", os.path.join(folder, "oyun.exe"))
        self.assertEqual(game["anti_cheat"], ["EasyAntiCheat"])
        riot = profiles.detect_anti_cheat({"kaynak": "Riot", "klasor": self.tmp.name + "/yok"})
        self.assertEqual(riot, ["Riot Vanguard"])
        self.assertEqual(profiles.detect_anti_cheat({"kaynak": "Steam", "klasor": self.tmp.name + "/yok"}), [])

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


class TestSession(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sys = FakeSystem()
        self.sys.services.update({"SysMain": {"baslangic": "Automatic", "calisiyor": True},
                                  "WSearch": {"baslangic": "AutomaticDelayed", "calisiyor": True},
                                  "DiagTrack": {"baslangic": "Manual", "calisiyor": False}})
        self.ops = FakeOps(processes=[(10, "oyun.exe"), (20, "steamwebhelper.exe")])
        self.journal = Path(self.tmp.name) / "oyun_oturumu.json"
        self.session = runtime.GameSession(self.sys, self.ops, self.journal)

    def tearDown(self):
        self.tmp.cleanup()

    def test_apply_and_revert_everything(self):
        game = make_game(cekirdek_secimi="performans", guc_kismasi_muaf=True, servisleri_duraklat=True,
                         windows_search_durdur=True, steam_dusuk_oncelik=True, guc_plani=True,
                         bildirimleri_kapat=True, standby_temizle=True)
        before_plan = self.sys.active_scheme
        results = self.session.start(game, 10, TOPOLOGY)
        self.assertTrue(all(ok for _k, ok, _m in results), results)
        self.assertEqual(self.ops.cpu_sets[10], [256 + n for n in range(8)])
        self.assertIn(10, self.ops.exempt)
        self.assertFalse(self.sys.services["SysMain"]["calisiyor"])
        self.assertFalse(self.sys.services["WSearch"]["calisiyor"])
        self.assertEqual(self.ops.priorities[20], runtime.BELOW_NORMAL_PRIORITY_CLASS)
        self.assertEqual(self.sys.active_scheme, runtime.HIGH_PERFORMANCE_PLAN)
        self.assertEqual(self.sys.read_reg("HKCU", runtime.TOAST_KEY, "ToastEnabled")[0], 0)
        self.assertEqual(self.ops.purged, 1)
        self.assertTrue(self.journal.exists())
        self.session.stop()
        self.assertTrue(self.sys.services["SysMain"]["calisiyor"])
        self.assertEqual(self.sys.services["WSearch"]["baslangic"], "AutomaticDelayed")
        self.assertFalse(self.sys.services["DiagTrack"]["calisiyor"])  # zaten durmuştu: başlatılmaz
        self.assertEqual(self.ops.priorities[20], runtime.NORMAL_PRIORITY_CLASS)
        self.assertEqual(self.sys.active_scheme, before_plan)
        self.assertIsNone(self.sys.read_reg("HKCU", runtime.TOAST_KEY, "ToastEnabled"))
        self.assertFalse(self.journal.exists())

    def test_denied_setting_is_skipped_and_reported(self):
        self.ops.deny = {"cpu"}
        results = self.session.start(make_game(cekirdek_secimi="fiziksel", guc_kismasi_muaf=True), 10, TOPOLOGY)
        self.assertEqual({k: ok for k, ok, _ in results}, {"cekirdekler": False, "guc_kismasi_muaf": True})

    def test_boost_closes_listed_programs_gently_never_the_game_never_forced(self):
        from unittest import mock

        class CloserOps:
            def __init__(self):
                self.procs = [(10, "oyun.exe"), (30, "chrome.exe"), (31, "discord.exe"), (32, "explorer.exe")]
                self.asked, self.terminated = [], []

            def list_processes(self):
                return list(self.procs)

            def post_close(self, pids):
                self.asked += sorted(pids)
                self.procs = [p for p in self.procs if p[1] != "chrome.exe" or p[0] not in pids]  # discord kapanmıyor
                return len(pids)

            def terminate(self, pid):
                self.terminated.append(pid)

        closer_ops = CloserOps()
        session = runtime.GameSession(self.sys, self.ops, self.journal, closer_ops=closer_ops)
        game = make_game(boost=True)
        with mock.patch.object(runtime.settings, "get", return_value=["chrome", "discord", "oyun", "explorer"]):
            results = session.start(game, 10, TOPOLOGY)
        boost = next(r for r in results if r[0] == "boost")
        self.assertFalse(boost[1])  # discord kapanmadı: raporlanır
        self.assertIn("discord", boost[2])
        self.assertEqual(sorted(closer_ops.asked), [30, 31])  # oyun (10) ve korumalı explorer (32) istenmedi
        self.assertEqual(closer_ops.terminated, [])  # zorla sonlandırma yok
        self.assertEqual([p[1] for p in closer_ops.procs], ["oyun.exe", "discord.exe", "explorer.exe"])

    def test_boost_off_by_default_touches_nothing(self):
        results = self.session.start(make_game(), 10, TOPOLOGY)
        self.assertNotIn("boost", [r[0] for r in results])

    def test_recover_after_crash(self):
        self.session.start(make_game(servisleri_duraklat=True), 10, TOPOLOGY)
        fresh = runtime.GameSession(self.sys, self.ops, self.journal)  # uygulama yeniden açıldı
        self.assertTrue(fresh.recover())
        self.assertTrue(self.sys.services["SysMain"]["calisiyor"])
        self.assertFalse(self.journal.exists())

    def test_failed_restore_keeps_journal_for_retry(self):
        self.session.start(make_game(servisleri_duraklat=True), 10, TOPOLOGY)
        self.sys.fail_on.add("set_service")
        self.session.stop()
        self.assertTrue(self.journal.exists())
        self.sys.fail_on.clear()
        self.assertTrue(runtime.GameSession(self.sys, self.ops, self.journal).recover())
        self.assertTrue(self.sys.services["SysMain"]["calisiyor"])
        self.assertFalse(self.journal.exists())

    def test_new_session_retries_pending_journal(self):
        self.session.start(make_game(servisleri_duraklat=True), 10, TOPOLOGY)
        self.sys.fail_on.add("set_service")
        self.session.stop()
        self.sys.fail_on.clear()
        self.session.start(make_game(), 11, TOPOLOGY)
        self.assertTrue(self.sys.services["SysMain"]["calisiyor"])

    def test_foreign_journal_is_ignored(self):
        self.journal.write_text('{"servisler": ["BaskaServis"], "steam": []}', encoding="utf-8")
        self.assertFalse(runtime.GameSession(self.sys, self.ops, self.journal).recover())
        self.assertNotIn("set_service", self.sys.calls)
        self.assertFalse(self.journal.exists())


class TestWatcher(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = profiles.GameStore(Path(self.tmp.name) / "oyunlar.json")
        game = self.store.add("Oyun", r"C:\Oyun", "Steam", r"C:\Oyun\oyun.exe")
        self.store.update_profile(game["id"], dict(game["profil"], guc_kismasi_muaf=True))
        self.sys = FakeSystem()
        self.ops = FakeOps()
        self.events = []
        session = runtime.GameSession(self.sys, self.ops, Path(self.tmp.name) / "j.json")
        self.watcher = runtime.GameWatcher(self.store, self.sys, self.ops,
                                           on_event=lambda kind, g, r: self.events.append(kind), session=session)

    def tearDown(self):
        self.tmp.cleanup()

    def test_start_and_exit(self):
        self.ops.processes = [(5, "vgc.exe"), (10, "oyun.exe")]
        self.ops.paths[10] = r"C:\Oyun\oyun.exe"
        self.watcher.tick()
        self.assertEqual(self.events, ["basladi"])
        self.assertEqual(self.ops.exempt, {10})  # anti-cheat (5) hiç ellenmedi
        self.ops.processes = [(5, "vgc.exe")]
        self.watcher.tick()
        self.assertEqual(self.events, ["basladi", "bitti"])

    def test_same_name_in_other_folder_is_ignored(self):
        self.ops.processes = [(11, "oyun.exe")]
        self.ops.paths[11] = r"D:\Baska\oyun.exe"
        self.watcher.tick()
        self.assertEqual(self.events, [])


if __name__ == "__main__":
    unittest.main()
