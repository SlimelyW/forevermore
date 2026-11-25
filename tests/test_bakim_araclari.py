"""Bakım araçları (ağ sıfırlama, Windows Update onarma, disk taraması, bileşen deposu, ayrılmış depolama).
Gerçek süreç başlatılmaz, gerçek Windows klasörlerine dokunulmaz (geçici klasör + sahte çalıştırıcı).

Çalıştırma: py -3.12 -m unittest tests.test_bakim_araclari -v
"""

import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.engine import bakim, bakim_araclari as ba, schema  # noqa: E402
from tests.test_bakim import Fake, NoRealProcess  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def adlar(fake):
    return [os.path.basename(c[0]).lower() + " " + " ".join(c[1:]) for c in fake.calls]


class Ortam(NoRealProcess):
    def setUp(self):
        super().setUp()
        self.takili = {}
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.pd, self.win, self.yedek = root / "ProgramData", root / "Windows", root / "yedek"
        self.indirici = self.pd / "Microsoft" / "Network" / "Downloader"
        self.indirici.mkdir(parents=True)
        for yol in ("SoftwareDistribution/DataStore", "SoftwareDistribution/Download", "System32/catroot2"):
            (self.win / yol).mkdir(parents=True)
        for ad in ("qmgr0.dat", "qmgr1.dat", "baska.dat"):
            (self.indirici / ad).write_text("x")

    def calistir(self, arac, replies, admin=True, iptal=None, **kw):
        fake = Fake(replies)
        steps = []

        def durum(ad):  # son net komutu "stop" ise durmuş, değilse çalışıyor; takili[ad] bunu ezer
            if ad in self.takili:
                return self.takili[ad]
            son = [c[1] for c in fake.calls if len(c) > 2 and c[2] == ad]
            return bool(son) and son[-1] != "stop"
        result = ba.calistir_arac(arac, iptal or threading.Event(), lambda *a: steps.append(a), fake, lambda: admin,
                                  programdata=self.pd, windir=self.win, yedek=self.yedek, hizmet_calisiyor=durum, **kw)
        return result, fake, steps


class TestAgSifirla(Ortam):
    def test_tasinmamis_yedek_klasorune_yazilmaz(self):
        """Denetim YAYIN D2: yedekler korumalı klasöre taşınmadıysa ağ sıfırlama kullanıcının yazabildiği eski yere yazmaz."""
        fake = Fake([])
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(ba.paths, "protected_path", return_value=Path(tmp)):
            result = ba.calistir_arac("ag_sifirla", threading.Event(), None, fake, lambda: True)
        self.assertEqual(result["sonuc"], "yedeklenemedi")
        self.assertEqual(fake.calls, [])

    def test_once_yedek_sonra_sifirla(self):
        result, fake, _ = self.calistir("ag_sifirla", [(0, b"")] * 4)
        self.assertEqual(result["sonuc"], "tamam")
        self.assertTrue(result["yeniden_baslat"])
        kinds = adlar(fake)
        self.assertEqual([k.split()[0] + " " + k.split()[1] for k in kinds],
                         ["reg.exe export", "reg.exe export", "netsh.exe winsock", "netsh.exe int"])
        self.assertIn(r"services\tcpip\parameters", kinds[0].lower())
        self.assertIn(r"services\dhcp\parameters", kinds[1].lower())
        self.assertEqual(kinds[2].split()[1:], ["winsock", "reset"])
        self.assertEqual(kinds[3].split()[1:4], ["int", "ip", "reset"])
        self.assertEqual(result["yedek"], str(self.yedek))
        self.assertTrue(self.yedek.is_dir())

    def test_yedek_alinamazsa_hicbir_sey_sifirlanmaz(self):
        result, fake, _ = self.calistir("ag_sifirla", [(1, b"hata")])
        self.assertEqual(result["sonuc"], "yedeklenemedi")
        self.assertEqual(len(fake.calls), 1)  # winsock / ip hiç başlamadı
        self.assertFalse(result["yeniden_baslat"])

    def test_netsh_hatasi(self):
        result, _fake, _ = self.calistir("ag_sifirla", [(0, b""), (0, b""), (1, b"hata"), (1, b"hata")])
        self.assertEqual(result["sonuc"], "hata")
        self.assertFalse(result["yeniden_baslat"])  # hiçbir sıfırlama yapılmadı
        self.assertEqual(result["yedek"], str(self.yedek))  # ama yedek yeri yine söylenir

    def test_yarim_kalan_sifirlamada_yeniden_baslat_ve_yedek_yeri(self):
        """Denetim A2 B6: Winsock sıfırlandı (geri alınamaz), IP sıfırlama kod 1 döndü: 'kısmen', yeniden başlatma + yedek."""
        result, _fake, _ = self.calistir("ag_sifirla", [(0, b""), (0, b""), (0, b""), (1, b"Access is denied")])
        self.assertEqual(result["sonuc"], "kismen")
        self.assertTrue(result["yeniden_baslat"])
        self.assertEqual(result["yedek"], str(self.yedek))


class TestWindowsUpdate(Ortam):
    def test_basit_mod_microsoft_adimlari(self):
        result, fake, _ = self.calistir("wu_onar", [(0, b"")] * 6)
        self.assertEqual(result["sonuc"], "tamam")
        self.assertEqual(adlar(fake), ["net.exe stop bits /y", "net.exe stop wuauserv /y", "net.exe stop cryptsvc /y",
                                       "net.exe start bits", "net.exe start wuauserv", "net.exe start cryptsvc"])
        self.assertEqual(sorted(p.name for p in self.indirici.iterdir()), ["baska.dat"])  # yalnızca qmgr*.dat silindi
        for yol in ("SoftwareDistribution/DataStore", "System32/catroot2"):
            self.assertTrue((self.win / yol).is_dir())  # basit modda klasörlere dokunulmaz

    def test_sert_mod_klasorleri_bak_yapar(self):
        (self.win / "System32" / "catroot2.bak").mkdir()  # önceki .bak ezilmemeli
        result, _fake, _ = self.calistir("wu_onar_sert", [(0, b"")] * 6)
        self.assertEqual(result["sonuc"], "tamam")
        self.assertTrue((self.win / "SoftwareDistribution" / "DataStore.bak").is_dir())
        self.assertTrue((self.win / "SoftwareDistribution" / "Download.bak").is_dir())
        self.assertFalse((self.win / "System32" / "catroot2").exists())
        self.assertTrue((self.win / "System32" / "catroot2.bak").is_dir())
        self.assertEqual(len(list((self.win / "System32").glob("catroot2.bak.*"))), 1)

    def test_birakilan_bak_klasorleri_sonucta_listelenir(self):
        """Denetim A2 O4: ikinci deneme her çalışmada yeni .bak bırakır; ekran hangileri kaldığını ve silinebileceğini söyler."""
        (self.win / "System32" / "catroot2.bak").mkdir()
        result, _fake, _ = self.calistir("wu_onar_sert", [(0, b"")] * 6)
        kalan = sorted(os.path.basename(p) for p in result["birakilan"])
        self.assertEqual(len(kalan), 3)
        self.assertTrue(any(ad.startswith("catroot2.bak.") for ad in kalan))  # ezilmeyen eski .bak yanında yenisi
        self.assertTrue(all(os.path.isdir(p) for p in result["birakilan"]))
        basit, _f, _ = self.calistir("wu_onar", [(0, b"")] * 6)
        self.assertEqual(basit["birakilan"], [])

    def test_iptal_edilse_de_hizmetler_yeniden_baslar(self):
        iptal = threading.Event()
        fake_replies = [(0, b""), (None, b""), ]
        result, fake, _ = self.calistir("wu_onar", fake_replies + [(0, b"")] * 3, iptal=iptal)
        self.assertEqual(result["sonuc"], "iptal")
        self.assertEqual(adlar(fake)[2:], ["net.exe start bits", "net.exe start wuauserv", "net.exe start cryptsvc"])
        self.assertEqual(len(list(self.indirici.glob("qmgr*.dat"))), 2)  # iptal: dosya adımına geçilmedi

    def test_dosya_hatasinda_da_hizmetler_baslar(self):
        with mock.patch.object(ba.os, "remove", side_effect=PermissionError("kilitli")):
            result, fake, _ = self.calistir("wu_onar", [(0, b"")] * 6)
        self.assertEqual(result["sonuc"], "hata")
        self.assertEqual(adlar(fake)[-3:], ["net.exe start bits", "net.exe start wuauserv", "net.exe start cryptsvc"])

    def test_net_kodu_2_hizmet_durmadiysa_dosya_adimlarina_gecilmez(self):
        """Denetim A2 B5: net stop kod 2 'zaten durmuş' da 'durdurulamadı' da demek; hizmet durumuna bakılır."""
        self.takili["wuauserv"] = True  # durdurulamıyor
        result, fake, _ = self.calistir("wu_onar_sert", [(0, b""), (2, b""), (0, b"")] + [(0, b"")] * 3)
        self.assertEqual(result["sonuc"], "hata")
        self.assertIn("wuauserv", result["cikti"])
        self.assertEqual(len(list(self.indirici.glob("qmgr*.dat"))), 2)  # dosya adımlarına geçilmedi
        self.assertFalse((self.win / "SoftwareDistribution" / "DataStore.bak").exists())
        self.assertEqual(adlar(fake)[-3:], ["net.exe start bits", "net.exe start wuauserv", "net.exe start cryptsvc"])

    def test_net_kodu_2_hizmet_baslamadiysa_tamam_denmez(self):
        self.takili["wuauserv"] = False  # Devre dışı: başlamıyor
        result, _fake, _ = self.calistir("wu_onar", [(0, b"")] * 3 + [(0, b""), (2, b""), (0, b"")])
        self.assertEqual(result["sonuc"], "hata")
        self.assertIn("wuauserv", result["cikti"])

    def test_belgesiz_adimlar_yok(self):
        """WinUtil'in ilke anahtarı / güvenlik şablonu / GroupPolicy silmesi ve Microsoft'un 'son çare' sc sdset, regsvr32 adımları."""
        for arac in ("wu_onar", "wu_onar_sert"):
            text = " ".join(s["goster"] for s in ba.plan(arac, programdata=self.pd, windir=self.win)).lower()
            for yasak in ("policies", "secedit", "grouppolicy", "sdset", "regsvr32", "reg ", "rd /s"):
                self.assertNotIn(yasak, text, (arac, yasak))


class TestDiskTara(Ortam):
    LISTE = staticmethod(lambda: [{"harf": "C", "tur": "SSD", "fs": "NTFS"}, {"harf": "D", "tur": "HDD", "fs": "NTFS"},
                                  {"harf": "E", "tur": "SSD", "fs": "FAT32"}])

    def tara(self, harfler, replies):
        return self.calistir("disk_tara", replies, harfler=harfler, liste=self.LISTE)

    def test_yalniz_listedeki_ntfs_suruculer_ve_scan_bayragi(self):
        result, fake, _ = self.tara(["c", "E", "Z", "C"], [(0, b"")])
        self.assertEqual(adlar(fake), ["chkdsk.exe C: /scan"])  # FAT32, listede olmayan ve tekrar eden atlanır
        self.assertEqual((result["sonuc"], result["suruculer"]), ("temiz", ["C"]))

    def test_cikis_kodlari(self):
        for codes, expected in (([0], "temiz"), ([0, 2], "bilgi"), ([1], "bilgi"), ([0, 3], "sorun"), ([7], "hata")):
            result, _f, _ = self.tara(["C", "D"][:len(codes)], [(c, b"") for c in codes])
            self.assertEqual(result["sonuc"], expected, codes)

    def test_hic_ntfs_yoksa_calismaz(self):
        result, fake, _ = self.tara(["E"], [])
        self.assertEqual((result["sonuc"], fake.calls), ("yok", []))

    def test_scan_disinda_bayrak_yok(self):
        for step in ba.plan("disk_tara", ["C"]):
            self.assertEqual(step["komut"][1:], ["C:", "/scan"])  # /f /r /x /perf yok: tarar, düzeltmez


class TestDism(Ortam):
    def test_bilesen_temizligi_resetbase_yok(self):
        result, fake, _ = self.calistir("bilesen_temizle", [(0, b"")])
        self.assertEqual(adlar(fake), ["dism.exe /Online /Cleanup-Image /StartComponentCleanup".replace("dism", "dism")])
        self.assertNotIn("resetbase", " ".join(fake.calls[0]).lower())
        self.assertEqual(result["sonuc"], "tamam")
        self.assertFalse(result["yeniden_baslat"])
        result, _f, _ = self.calistir("bilesen_temizle", [(3010, b"")])
        self.assertEqual((result["sonuc"], result["yeniden_baslat"]), ("tamam", True))
        result, _f, _ = self.calistir("bilesen_temizle", [(87, b"")])
        self.assertEqual(result["sonuc"], "hata")

    def test_ayrilmis_depolama_kapat_ac(self):
        for arac, state in (("ayrilmis_kapat", "/State:Disabled"), ("ayrilmis_ac", "/State:Enabled")):
            _r, fake, _ = self.calistir(arac, [(0, b"")])
            self.assertEqual(fake.calls[0][1:], ["/Online", "/Set-ReservedStorageState", state])


class TestGenel(Ortam):
    def test_yonetici_degilse_hicbir_sey_calismaz(self):
        for arac in ba.ARACLAR:
            result, fake, _ = self.calistir(arac, [], admin=False, harfler=["C"])
            self.assertEqual((result["sonuc"], fake.calls), ("yetki", []), arac)
        self.assertTrue(self.indirici.joinpath("qmgr0.dat").exists())

    def test_baslatilamayan_komut_hata_olur(self):
        result, _f, _ = self.calistir("bilesen_temizle", [FileNotFoundError("Dism.exe")])
        self.assertEqual(result["sonuc"], "hata")
        self.assertIn("Dism", result["cikti"])

    def test_komutlar_system32_tam_yolla(self):
        for arac in ba.ARACLAR:
            for step in ba.plan(arac, ["C"], programdata=self.pd, windir=self.win, yedek=self.yedek):
                if "komut" in step:
                    self.assertTrue(step["komut"][0].startswith(bakim.powershell.SYSTEM32), step["komut"])

    def test_onizleme_gercek_komutlari_verir(self):
        self.assertEqual(ba.onizleme("bilesen_temizle")[0].split()[0], "Dism.exe")
        self.assertIn("net.exe stop bits /y", ba.onizleme("wu_onar"))

    def test_geri_alinamayanlar_isaretli(self):
        self.assertEqual({k for k, v in ba.ARACLAR.items() if v["geri_alinamaz"]}, {"ag_sifirla", "bilesen_temizle"})

    def test_paneller_beyaz_listede(self):
        for _ad, hedef in ba.PANELLER:
            self.assertIn(hedef, schema.ALLOWED_PROGRAMS)


class TestMetinler(unittest.TestCase):
    def test_kartlarin_tum_metinleri_tr_ve_en_dosyalarinda_var(self):
        from app.ui import bakim_kartlari as bk
        keys = {f"ui.bakim.arac_{c}" for c in ("hata", "iptal", "yetki", "yok", "basliyor")}
        keys |= {"ui.bakim.komutlar", "ui.bakim.geri_alinamaz", "ui.bakim.yeniden_baslat_not", "ui.bakim.yeniden_baslat_simdi",
                 "ui.bakim.ag_yedek", "ui.bakim.tara_yok", "ui.bakim.tara_surucu", "ui.bakim.bak_birakilan"}
        listed = {arac for araclar in bk._ARAC_KARTLARI.values() for arac in araclar}
        self.assertEqual(listed, set(ba.ARACLAR))  # her araç bir kartta
        for kart, araclar in bk._ARAC_KARTLARI.items():
            keys |= {f"ui.bakim.{kart}", f"ui.bakim.{kart}_not"}
            for arac in araclar:
                keys |= {f"ui.bakim.{arac}_dugme", f"ui.bakim.{arac}_onizleme"}
                keys |= {f"ui.bakim.{arac}_{code}" for code in bk._OZEL_SONUC[arac]}
                keys |= {"ui.bakim.adim_" + step["ad"] for step in ba.plan(arac, ["C"])}
        keys |= {f"ui.bakim.panel_{name}" for name, _target in ba.PANELLER} | {"ui.bakim.paneller", "ui.bakim.paneller_not"}
        for code in ("tr", "en"):
            lang = json.loads((ROOT / "lang" / f"{code}.json").read_text(encoding="utf-8"))
            self.assertEqual(sorted(k for k in keys if not lang.get(k)), [], code)


if __name__ == "__main__":
    unittest.main()
