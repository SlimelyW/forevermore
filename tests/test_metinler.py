"""Koddaki her metin anahtarının lang/tr.json'da bulunduğunu ve her dil dosyasının
Türkçeyle aynı anahtarlara ve yer tutuculara sahip olduğunu kontrol eder.

Çalıştırma (proje klasöründe):
    py -3.12 -m unittest tests.test_metinler -v
"""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LANGS = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (ROOT / "lang").glob("*.json")}
META_FIELDS = {"kod", "ad", "yerel_ad", "yon", "yerel", "ondalik", "binlik", "tarih", "saat", "yuzde", "yazi_tipi"}
TR = {k: v for k, v in LANGS["tr"].items() if k != "_meta"}
PLACEHOLDER = re.compile(r"\{(\w+)\}")
DATA = json.loads((ROOT / "data" / "tweaks_app.json").read_text(encoding="utf-8"))
LITERAL_KEY = re.compile(r"""\bt\(\s*"([a-z_]+(?:\.[^"{}]+)+)"\s*[,)]""")


class TestTexts(unittest.TestCase):
    def test_literal_keys_exist(self):
        missing = set()
        for path in (ROOT / "app").rglob("*.py"):
            for key in LITERAL_KEY.findall(path.read_text(encoding="utf-8")):
                if key not in TR:
                    missing.add(f"{path.name}: {key}")
        self.assertEqual(sorted(missing), [])

    def test_dynamic_key_families(self):
        expected = [f"kategori.{c['id']}" for c in DATA["kategoriler"]]
        expected += [f"ui.risk.{r}" for r in ("güvenli", "dikkatli", "riskli")]
        expected += [f"ui.mod_aciklama.{m}" for m in ("salt_okunur", "onizleme")]
        expected += [f"yeniden.{t['yeniden_baslatma_kodu']}" for t in DATA["ayarlar"]]
        expected += [f"profil.{p}.{f}" for p in ("guvenli", "oyun", "dikkatli") for f in ("ad", "aciklama")]
        expected += [f"rp.{s}" for s in ("olusturuldu", "mevcut_24s", "basarisiz")]
        expected += [f"onizleme.{a}" for a in ("hazirda_bekletme", "bellek_sikistirma", "windows_ozelligi",
                                                "ag_gelismis_ozellik", "bcdedit", "tcp_otomatik_ayar",
                                                "zamanlanmis_gorev", "pnp_cihaz", "nihai_performans_plani", "dns",
                                                "ekran_yenileme", "en_yuksek_hz", "ekran_modu", "ekran_olcek", "wlan_otomatik_yapilandirma")]
        expected += [f"onizleme.hesapla.{v}" for v in ("toplam_ram_kb",)]
        expected += [f"onizleme.{a}" for a in ("gorsel_efekt", "guc_modu")]
        expected += [f"ui.baslangic_sekme.{k}" for k in ("uygulamalar", "gorevler", "servisler")]
        expected += [f"ui.baslangic_konum.{k}" for k in ("kayit_kullanici", "kayit_tum", "kayit_32", "klasor_kullanici",
                                                          "klasor_tum")]
        expected += [f"ui.baslangic_turu.{k}" for k in ("Automatic", "AutomaticDelayed", "Manual", "Disabled")]
        expected += [f"ui.servis_kilit{s}.{k}" for s in ("", "_neden") for k in ("kritik", "anti_cheat")]
        expected += ["ui.msi_sutun", "ui.cihaz_guc_sutun"]
        expected += [f"ui.oncelik.{k}" for k in ("Normal", "AboveNormal", "High")]
        expected += [f"ui.gpu_tercihi.{k}" for k in ("varsayilan", "guc_tasarrufu", "yuksek_performans")]
        expected += [f"oyun.degisiklik.{k}" for k in ("oncelik", "gpu", "fso")]
        from app.measure import METRICS
        expected += [f"olcum.{kind}.{m}" for kind in ("metrik", "kisa") for m in METRICS]
        expected += [f"olcum.etiket.{k}" for k in ("once", "sonra", "diger")]
        expected += [f"olcum.tur.{k}" for k in ("sistem", "oyun")]
        expected += [f"deger.etki.{k}" for k in ("yüksek", "orta", "düşük", "çok düşük", "belirsiz", "durumsal", "yok")]
        expected += [f"deger.gerceklik.{k}" for k in ("gerçek", "kısmen gerçek", "durumsal", "tartışmalı", "placebo",
                                                       "zararlı")]
        expected += ["ui.oyun_kaynak.Klasör"]
        from app.ui.controller import MANUAL_REASONS
        expected += [f"ui.elle.{kind}.{r}" for kind in ("neden", "neden_aciklama") for r in MANUAL_REASONS]
        expected += [f"ui.mux.mod.{m}" for m in ("hibrit", "harici")]
        expected += [f"ui.zr.secenek.{k}" for k in ("windows", "1", "05")]
        from app.engine import amd, driver_tools
        from app.ui.managers_ui import MonitorsCard
        expected += [f"ui.olc.{d}.{n}" for d, values in MonitorsCard.SCALING_OPTIONS.items() for n in values]
        expected += [f"ui.amd.ozellik.{k}" for k in amd.FEATURES]
        expected += [f"ui.amd.durum.{k}" for k in ("acik", "kapali")]
        expected += [f"ui.surucu_arac.{k}" for k in driver_tools.TOOLS]
        services = json.loads((ROOT / "data" / "fps_servisleri.json").read_text(encoding="utf-8"))["servisler"]
        expected += [f"fps_servis.{s['servis']}" for s in services]
        expected += [f"ui.servis_filtre.{k}" for k in ("tumu", "otomatik", "el_ile", "devre_disi")]
        from app.engine.windows_update import MODES
        expected += [f"ui.wu.{kind}.{m}" for kind in ("mod", "aciklama") for m in MODES]
        expected += [f"ui.wu.{kind}.{m}" for kind in ("arti", "eksi", "dokunmamali", "dikkat")
                     for m in ("guvenlik", "duraklat")]
        from app.engine import uac
        expected += [f"ui.uac.{kind}.{lv}" for kind in ("seviye", "aciklama", "eksi") for lv in uac.LEVELS]
        expected += [f"ui.uac.durum.{k}" for k in ("kapali", "ozel")]
        expected += [f"ui.stat_liste{s}.{k}" for s in ("", "_aciklama") for k in ("uygun", "oyun", "degisen")]
        self.assertEqual([k for k in expected if k not in TR], [])

    def test_placeholders_match(self):
        """Aynı anahtarın metnindeki {yer tutucular} kodda verilmeli; burada yalnızca biçim kontrolü."""
        for key, text in TR.items():
            self.assertEqual(text.count("{"), text.count("}"), key)

    def test_every_language_matches_turkish(self):
        """Her dil dosyası: aynı anahtarlar, aynı sıra, aynı yer tutucular ve eksiksiz _meta."""
        for code, data in LANGS.items():
            with self.subTest(dil=code):
                self.assertEqual(set(data.get("_meta", {})), META_FIELDS)
                self.assertEqual(data["_meta"]["kod"], code)
                self.assertIn(data["_meta"]["yon"], ("ltr", "rtl"))
                texts = {k: v for k, v in data.items() if k != "_meta"}
                self.assertEqual(list(texts), list(TR))
                for key, text in texts.items():
                    self.assertIsInstance(text, str, key)
                    self.assertEqual(sorted(set(PLACEHOLDER.findall(text))), sorted(set(PLACEHOLDER.findall(TR[key]))),
                                     key)

    def test_consent_text_for_every_language(self):
        for code in LANGS:
            self.assertTrue((ROOT / "lang" / f"baslangic_onayi.{code}.txt").is_file(), code)


if __name__ == "__main__":
    unittest.main()
