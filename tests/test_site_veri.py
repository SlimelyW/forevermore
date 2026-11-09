"""Sitedeki sayılar/metinler katalogla eşleşir mi? (tools/site_veri.py çıktısı güncel olmalı.)

Eski sayı yakalanırsa: py -3.12 tools\\site_veri.py çalıştırıp çıktıyı commit'le.
    py -3.12 -m unittest tests.test_site_veri -v
"""

import base64
import hashlib
import importlib.util
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"


def _site_veri():
    spec = importlib.util.spec_from_file_location("site_veri", ROOT / "tools" / "site_veri.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _text(path):
    return Path(path).read_text(encoding="utf-8").replace("\r\n", "\n")


@unittest.skipUnless(SITE.is_dir(), "site/ yalnızca private depoda (public eşitlemede yok)")
class TestSiteVeri(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _site_veri()
        cls.data = cls.mod.build()

    def test_veri_js_guncel(self):
        beklenen = ("/* tools/site_veri.py üretir; elle değiştirmeyin. */\nwindow.FM_VERI = "
                    + json.dumps(self.data, ensure_ascii=False, indent=1) + ";\n")
        self.assertEqual(_text(SITE / "veri.js"), beklenen,
                         "site/veri.js eski: py -3.12 tools\\site_veri.py çalıştır")

    def test_sayfa_sayaclari_guncel(self):
        for kod, sayfa in (("tr", "index.html"), ("en", "en.html")):
            with self.subTest(sayfa=sayfa), tempfile.TemporaryDirectory() as tmp:
                kopya = Path(tmp) / sayfa
                shutil.copyfile(SITE / sayfa, kopya)
                self.mod.patch(kopya, self.data[kod])
                self.assertEqual(_text(kopya), _text(SITE / sayfa),
                                 f"site/{sayfa} sayıları eski: py -3.12 tools\\site_veri.py çalıştır")

    def test_toplam_katalogla_ayni(self):
        katalog = json.loads((ROOT / "data" / "tweaks_app.json").read_text(encoding="utf-8"))["ayarlar"]
        self.assertEqual(self.data["tr"]["n"]["toplam"], len(katalog))


@unittest.skipUnless(SITE.is_dir(), "site/ yalnızca private depoda (public eşitlemede yok)")
class TestSiteYayinDosyalari(unittest.TestCase):
    """Cloudflare Pages dosyaları ve sayfa donanımı (C11/C12/C20/C21)."""

    PAGES = ("index.html", "en.html", "gizlilik.html", "erisilebilirlik.html", "kosullar.html")

    def test_csp_inline_betik_karmalari(self):
        headers = _text(SITE / "_headers")
        for page in self.PAGES:
            for m in re.finditer(r"<script>(.*?)</script>", _text(SITE / page), re.S):
                karma = "'sha256-" + base64.b64encode(hashlib.sha256(m.group(1).encode("utf-8")).digest()).decode() + "'"
                self.assertIn(karma, headers, f"{page}: satır içi betik değişti, site/_headers CSP karması eski: {karma}")

    def test_csp_dis_kaynak_yok(self):
        csp = re.search(r"Content-Security-Policy: (.*)", _text(SITE / "_headers")).group(1)
        self.assertIn("connect-src 'none'", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertNotIn("unsafe-eval", csp)

    def test_robots_sitemap_404(self):
        self.assertIn("Sitemap: https://forevermore.pages.dev/sitemap.xml", _text(SITE / "robots.txt"))
        sitemap = _text(SITE / "sitemap.xml")
        for page in self.PAGES:
            adres = "https://forevermore.pages.dev/" + ("" if page == "index.html" else page)
            self.assertIn(f"<loc>{adres}</loc>", sitemap)
        self.assertIn('name="robots" content="noindex"', _text(SITE / "404.html"))

    def test_sayfa_donanimi(self):
        for page in self.PAGES:
            text = _text(SITE / page)
            with self.subTest(page=page):
                self.assertIn('rel="canonical"', text)
                self.assertIn('property="og:title"', text)
                self.assertIn('name="description"', text)
                self.assertIn('class="atla" href="#main"', text)
                self.assertRegex(text, r'<main[^>]* id="main"')
        for page in ("gizlilik.html", "erisilebilirlik.html"):
            self.assertIn('id="en" lang="en"', _text(SITE / page))
        self.assertNotIn('href="#en"', _text(SITE / "kosullar.html"))

    def test_logo_kucuk(self):
        self.assertLess((SITE / "img" / "logo.png").stat().st_size, 40_000)


if __name__ == "__main__":
    unittest.main()
