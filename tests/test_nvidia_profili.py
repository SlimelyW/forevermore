"""NVIDIA için optimize et profili: plan, uygulama, geri alma (yalnızca sahte sistemde; gerçek sürücüye/ekrana dokunmaz).

Çalıştırma: py -3.12 -m unittest tests.test_nvidia_profili -v
"""

import json
import os
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.engine import nvidia_profili as np  # noqa: E402
from tests.test_motor import BY_ID, EngineTestBase  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LATENCY, REFRESH, VSYNC, LIMIT = 0x007BA09E, 0x0064B541, 0x00A879CF, 0x10835002


def drs(tweak_id):
    return int(BY_ID[tweak_id]["nvidia"]["ayar"], 16)


class TestProfil(EngineTestBase):
    def apply(self, gsync=False, only=None):
        profile = np.plan(self.sys, BY_ID, gsync)
        rows = [r for r in profile["satirlar"] if only is None or r["id"] in only]
        steps, values = np.uygulanacaklar(rows)
        result = self.engine.apply_custom(np.PROFIL_ID, "NVIDIA profil", steps, values, restart="uygulama",
                                          confirmed=True, related=np.PROFIL_ID)
        self.assertTrue(result.ok, result)
        return profile

    def test_seceneklerin_katalogda_karsiligi_var(self):
        """Profilin yazacağı değerler ayarların kendi seçenek listesinde olmalı (arayüz adını gösterebilsin)."""
        for tweak_id, value in (*np.HER_ZAMAN, ("GPU-006", np.VSYNC_ACIK)):
            self.assertIn(value, [o["deger"] for o in BY_ID[tweak_id]["nvidia"]["secenekler"]], tweak_id)

    def test_oyun_modu_degeri_yoksa_zaten_acik_sayilir(self):
        """Windows'ta Oyun Modu varsayılan açıktır (PERF-001 'yoksa' = 1): değer yokken yazılmaz."""
        row = next(r for r in np.plan(self.sys, BY_ID)["satirlar"] if r["id"] == "PERF-001")
        self.assertTrue(row["zaten"])

    def test_g_sync_yokken_yalniz_dort_kalem(self):
        self.sys.write_reg("HKCU", r"Software\Microsoft\GameBar", "AutoGameModeEnabled", 0, "REG_DWORD")  # kullanıcı kapatmış
        profile = np.plan(self.sys, BY_ID, gsync=False)
        self.assertEqual([r["id"] for r in profile["satirlar"]], ["GPU-002", "GPU-009", "DISP-001", "PERF-001"])
        self.assertIsNone(profile["sinir"])
        self.apply()
        self.assertEqual(self.sys.nvidia[LATENCY], 1)
        self.assertEqual(self.sys.nvidia[REFRESH], 1)
        self.assertEqual(self.sys.displays["TEST"]["hz"], 144)
        self.assertEqual(self.sys.read_reg("HKCU", r"Software\Microsoft\GameBar", "AutoGameModeEnabled"), (1, "REG_DWORD"))
        for forbidden in (VSYNC, LIMIT):  # V-Sync ve kare sınırı G-SYNC işaretlenmeden asla yazılmaz
            self.assertNotIn(forbidden, self.sys.nvidia)

    def test_g_sync_isaretliyse_vsync_ve_hz_eksi_3(self):
        profile = self.apply(gsync=True)
        self.assertEqual(profile["hz"], 144)
        self.assertEqual(profile["sinir"], 141)
        self.assertEqual(self.sys.nvidia[VSYNC], np.VSYNC_ACIK)
        self.assertEqual(self.sys.nvidia[LIMIT], 141)

    def test_kare_siniri_birincil_ekranin_hzine_gore(self):
        self.sys.monitors["ikinci"] = dict(self.sys.monitors["TEST"], ad="İkinci", birincil=False)
        self.sys.monitors["TEST"]["birincil"] = False
        self.sys.monitors["ikinci"]["birincil"] = True
        self.sys.displays["ikinci"] = {"hz": 60, "en_yuksek": 240, "hizlar": [60, 240]}
        self.assertEqual(np.plan(self.sys, BY_ID, True)["sinir"], 237)

    def test_geri_al_her_seyi_eski_haline_dondurur(self):
        self.sys.nvidia[LATENCY] = 0  # kullanıcının özelleştirdiği değer geri gelmeli
        self.sys.write_reg("HKCU", r"Software\Microsoft\GameBar", "AutoGameModeEnabled", 0, "REG_DWORD")
        self.apply(gsync=True)
        self.assertEqual(self.sys.read_reg("HKCU", r"Software\Microsoft\GameBar", "AutoGameModeEnabled"), (1, "REG_DWORD"))
        self.assertEqual([c for c in self.engine.changed_ids()], [np.PROFIL_ID])  # tek değişiklik, tek geri alma
        self.assertTrue(self.engine.revert(np.PROFIL_ID).ok)
        self.assertEqual(self.sys.nvidia, {LATENCY: 0})  # özelleştirilmemiş olanlar sürücü varsayılanına döndü
        self.assertEqual(self.sys.displays["TEST"]["hz"], 60)
        self.assertEqual(self.sys.read_reg("HKCU", r"Software\Microsoft\GameBar", "AutoGameModeEnabled"), (0, "REG_DWORD"))

    def test_zaten_istenen_durumdaki_satirlar_yazilmaz(self):
        self.apply()
        again = np.plan(self.sys, BY_ID, False)
        self.assertTrue(all(r["zaten"] for r in again["satirlar"]))
        self.assertEqual(np.uygulanacaklar(again["satirlar"]), ([], []))

    def test_ikinci_uygulamada_yeni_adimlar_da_yedege_girer(self):
        """Denetim A2 B1: önce kutusuz, sonra G-SYNC kutusuyla uygula; geri alma V-Sync ve kare sınırını da döndürmeli."""
        self.apply(gsync=False)
        self.apply(gsync=True)
        self.assertEqual(self.sys.nvidia[LIMIT], 141)
        self.assertTrue(self.engine.revert(np.PROFIL_ID).ok)
        self.assertNotIn(VSYNC, self.sys.nvidia)
        self.assertNotIn(LIMIT, self.sys.nvidia)
        self.assertNotIn(LATENCY, self.sys.nvidia)

    def test_kendi_kaydi_olan_ayar_profilde_ayri_sayilir(self):
        """Denetim A2 O1: GPU-002 kendi kartından değiştirilmişse profil onu yazmaz (iki kayıt birbirini bozmasın)."""
        plan = np.plan(self.sys, BY_ID, False, kayitli={"GPU-002"})
        row = next(r for r in plan["satirlar"] if r["id"] == "GPU-002")
        self.assertTrue(row["ayri"] and row["zaten"])
        steps, _values = np.uygulanacaklar(plan["satirlar"])
        self.assertNotIn(LATENCY, {int(s["parametreler"]["ayar"], 16) for s in steps if s["eylem"] == "nvidia_drs"})

    def test_profil_varken_ayni_ayar_ayri_kayitla_yazilmaz(self):
        """Denetim YAYIN N1: profil SONRA kartından değiştirilip ikisi de geri alınınca ayar kayıtsız kalıyordu: artık engellenir."""
        self.sys.write_reg("HKCU", r"Software\Microsoft\GameBar", "AutoGameModeEnabled", 0, "REG_DWORD")
        self.apply()
        step = {"tur": "yerlesik", "eylem": "nvidia_drs", "parametreler": {"ayar": BY_ID["GPU-002"]["nvidia"]["ayar"]}}
        result = self.engine.apply_custom("GPU-002", "kart", [step], [0], confirmed=True)
        self.assertEqual(result.key, "hata.nvprofil_once_geri_al")
        self.assertEqual(self.sys.nvidia[LATENCY], 1)               # yazılmadı
        self.assertFalse(self.engine.store.has("GPU-002"))           # profil değerini alan ayrı yedek yok
        monitor = self.sys.list_monitors()[0]                       # Ekran sayfasındaki Hz satırı: başka kimlik, aynı monitör
        hz_step = {"tur": "yerlesik", "eylem": "ekran_yenileme",
                   "parametreler": {"aygit": monitor["aygit"], "monitor": monitor.get("monitor_yolu") or ""}}
        self.assertEqual(self.engine.apply_custom("MON-hz", "hz", [hz_step], [60], confirmed=True).key, "hata.nvprofil_once_geri_al")
        self.assertEqual(self.engine.set_enabled(BY_ID["PERF-001"], False, confirmed=True).key, "hata.nvprofil_once_geri_al")
        self.assertTrue(self.engine.revert(np.PROFIL_ID).ok)
        self.assertTrue(self.engine.apply_custom("GPU-002", "kart", [step], [0], confirmed=True).ok)  # profil gidince serbest

    def test_geri_alma_ekran_numarasi_degisse_de_dogru_monitore_yazar(self):
        """Denetim A2 B2: ekran numaraları yer değiştirirse yenileme hızı yine kendi monitörüne döner."""
        self.sys.monitors["ikinci"] = dict(self.sys.monitors["TEST"], ad="İkinci", monitor_yolu="MON-2", birincil=False)
        self.sys.displays["ikinci"] = {"hz": 100, "en_yuksek": 165, "hizlar": [100, 165]}
        self.apply(only={"DISP-001"})
        self.assertEqual((self.sys.displays["TEST"]["hz"], self.sys.displays["ikinci"]["hz"]), (144, 165))
        for table in (self.sys.displays, self.sys.monitors):  # numaralar yer değiştirdi
            table["TEST"], table["ikinci"] = table["ikinci"], table["TEST"]
        self.assertTrue(self.engine.revert(np.PROFIL_ID).ok)
        self.assertEqual(self.sys.displays["ikinci"]["hz"], 60)   # MON-TEST artık ikinci numarada
        self.assertEqual(self.sys.displays["TEST"]["hz"], 100)    # MON-2 artık ilk numarada

    def test_nvidia_yoksa_plan_yok(self):
        self.sys.nvidia_ok = False
        self.assertIsNone(np.plan(self.sys, BY_ID))

    def test_disarida_kalanlara_dokunulmaz(self):
        steps = np.uygulanacaklar(np.plan(self.sys, BY_ID, True)["satirlar"])[0]
        touched = {int(s["parametreler"]["ayar"], 16) for s in steps if s["eylem"] == "nvidia_drs"}
        self.assertEqual(touched, {LATENCY, REFRESH, VSYNC, LIMIT})
        for tweak_id in np.DISARIDA:
            tweak = BY_ID[tweak_id]
            if "nvidia" in tweak:
                self.assertNotIn(drs(tweak_id), touched, tweak_id)


class TestDisaridaNotlari(unittest.TestCase):
    def test_her_dislanan_ayarin_info_notu_tr_ve_en(self):
        en = json.loads((ROOT / "data" / "ceviriler" / "en.json").read_text(encoding="utf-8"))["ayarlar"]
        for tweak_id in np.DISARIDA:
            with self.subTest(tweak_id):
                self.assertGreater(len(BY_ID[tweak_id].get("profil_notu", "")), 40)
                self.assertGreater(len(en[tweak_id].get("profil_notu", "")), 40)
                self.assertNotEqual(en[tweak_id]["profil_notu"], BY_ID[tweak_id]["profil_notu"])  # çevrilmiş


if __name__ == "__main__":
    unittest.main()
