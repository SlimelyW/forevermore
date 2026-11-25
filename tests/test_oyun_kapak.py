import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.games import discovery


def _png(width, height):
    """Yalnızca başlığı geçerli sahte PNG (image_size başlığı okur, görüntüyü çözmez)."""
    return b"\x89PNG\r\n\x1a\n" + (13).to_bytes(4, "big") + b"IHDR" + width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00"


def _jpeg(width, height):
    """APP0 + SOF0 başlıklı sahte JPEG."""
    app0 = b"\xff\xe0" + (16).to_bytes(2, "big") + b"JFIF\x00" + bytes(9)
    sof = b"\xff\xc0" + (17).to_bytes(2, "big") + b"\x08" + height.to_bytes(2, "big") + width.to_bytes(2, "big") + b"\x03" + bytes(9)
    return b"\xff\xd8" + app0 + sof + b"\xff\xd9"


def _put(root, appid, relative, data):
    path = Path(root, "appcache", "librarycache", appid, *relative.split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return str(path)


MANIFEST = """"AppState"
{
	"appid"		"77"
	"installdir"		"Ornek Oyun"
}
"""


class YerelKapakTesti(unittest.TestCase):
    """Steam yerel önbelleği: TÜM görseller boyutuna göre değerlendirilir (ağdan indirme yok)."""

    def test_boyut_okuma(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(discovery.image_size(_put(root, "1", "a.png", _png(600, 900))), (600, 900))
            self.assertEqual(discovery.image_size(_put(root, "1", "b.jpg", _jpeg(460, 215))), (460, 215))
            self.assertIsNone(discovery.image_size(_put(root, "1", "c.jpg", b"x")))  # bozuk dosya
            self.assertIsNone(discovery.image_size(Path(root, "yok.jpg")))

    def test_dikey_kapak_en_cozunurluklu_olan_secilir(self):
        with tempfile.TemporaryDirectory() as root:
            _put(root, "10", "aa/library_capsule.jpg", _jpeg(374, 448))
            _put(root, "10", "bb/header.jpg", _jpeg(460, 215))
            self.assertTrue(discovery.steam_cover("10", root).endswith("library_capsule.jpg"))
            big = _put(root, "10", "cc/library_600x900.jpg", _jpeg(600, 900))
            self.assertEqual(discovery.steam_cover("10", root), big)  # dikey ve daha çözünürlüklü

    def test_dosya_adi_hash_olsa_da_boyuta_bakilir(self):
        with tempfile.TemporaryDirectory() as root:
            path = _put(root, "11", "ab12/24997e842758136564aba8ebdd07d9572b3a395e.jpg", _jpeg(600, 900))
            self.assertEqual(discovery.steam_cover("11", root), path)

    def test_eski_duzen_appid_alt_cizgi(self):
        with tempfile.TemporaryDirectory() as root:
            old = Path(root, "appcache", "librarycache", "12_library_600x900.jpg")
            old.parent.mkdir(parents=True)
            old.write_bytes(_jpeg(300, 450))
            self.assertEqual(discovery.steam_cover("12", root), str(old))

    def test_dikey_yoksa_en_yuksek_yatay_secilir(self):
        with tempfile.TemporaryDirectory() as root:
            hero = _put(root, "13", "x/library_hero.jpg", _jpeg(3840, 1240))
            _put(root, "13", "x/header.jpg", _jpeg(460, 215))
            _put(root, "13", "x/logo.png", _png(1280, 720))  # saydam logo kapak olmaz
            _put(root, "13", "x/library_hero_blur.jpg", _jpeg(1920, 620))
            self.assertEqual(discovery.steam_cover("13", root), hero)  # kırpılınca en az büyütülen (en yüksek) yatay

    def test_cok_alcak_yatay_gorsel_elenir(self):
        with tempfile.TemporaryDirectory() as root:
            _put(root, "15", "x/strip.jpg", _jpeg(800, 150))  # kutuyu doldurmak için 1,4x'ten fazla büyütmek gerekir
            self.assertIsNone(discovery.steam_cover("15", root))

    def test_appid_klasorden_bulunur_baslat_olmasa_da(self):
        with tempfile.TemporaryDirectory() as lib, tempfile.TemporaryDirectory() as root:
            steamapps = Path(lib, "steamapps")
            (steamapps / "common" / "Ornek Oyun" / "Bin").mkdir(parents=True)
            (steamapps / "appmanifest_77.acf").write_text(
                MANIFEST, encoding="utf-8")
            _put(root, "77", "x/library_600x900.jpg", _jpeg(600, 900))
            folder = str(steamapps / "common" / "Ornek Oyun")
            self.assertEqual(discovery.steam_appid(folder), "77")
            self.assertEqual(discovery.steam_appid(str(Path(folder, "Bin"))), "77")  # alt klasör de olur
            self.assertEqual(discovery.steam_appid(folder.upper()), "77")  # büyük/küçük harf
            self.assertIsNone(discovery.steam_appid(str(steamapps / "common" / "Baska")))
            self.assertIsNone(discovery.steam_appid(lib))  # steamapps\common altında değil
            self.assertIsNone(discovery.steam_appid(None))
            game = {"klasor": folder, "baslat": None}
            self.assertTrue(discovery.cover_path(game, root).endswith("library_600x900.jpg"))

    def test_kucuk_kare_simge_kapak_diye_sisirilmez(self):
        with tempfile.TemporaryDirectory() as root:
            _put(root, "14", "x/icon.jpg", _jpeg(184, 184))
            _put(root, "14", "x/small.jpg", _jpeg(200, 300))  # dikey ama 300 px'ten dar
            self.assertIsNone(discovery.steam_cover("14", root))
            self.assertIsNone(discovery.steam_cover("99", root))  # önbellekte hiç yok

    def test_appid_yalnizca_rakam_yol_karistirilamaz(self):
        with tempfile.TemporaryDirectory() as root:
            _put(root, "..", "x.jpg", _jpeg(600, 900))
            for bad in ("../../secret", "1/../../secret", "*", "", None):
                self.assertIsNone(discovery.steam_cover(bad, root), bad)

    def test_cover_path_yalnizca_steam_kisayolundan(self):
        with tempfile.TemporaryDirectory() as root:
            _put(root, "42", "x/library_600x900.jpg", _jpeg(600, 900))
            self.assertIsNotNone(discovery.cover_path({"baslat": "steam://rungameid/42"}, root))
            self.assertIsNone(discovery.cover_path({"baslat": "steam://rungameid/42/../x"}, root))
            self.assertIsNone(discovery.cover_path({"baslat": "com.epicgames.launcher://apps/x?action=launch"}, root))
            self.assertIsNone(discovery.cover_path({"baslat": None}, root))

    def test_kullanici_resmi_steam_onbelleginden_once_gelir(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as data:
            _put(root, "42", "x/library_600x900.jpg", _jpeg(600, 900))
            game = {"id": "OYUN-0123456789", "baslat": "steam://rungameid/42"}
            steam = discovery.cover_path(game, root)
            with mock.patch.object(discovery.paths, "user_data_path", return_value=Path(data)):
                self.assertEqual(discovery.cover_path(game, root), steam)  # kullanıcı resmi yok: Steam
                own = Path(data, "kapaklar", "OYUN-0123456789.jpg")
                own.parent.mkdir()
                own.write_bytes(_jpeg(624, 832))
                self.assertEqual(discovery.cover_path(game, root), str(own))  # seçilen resim önce
                discovery.remove_user_cover("OYUN-0123456789")
                self.assertFalse(own.exists())
                self.assertEqual(discovery.cover_path(game, root), steam)  # "Resmi kaldır": eski sıraya döner
                discovery.remove_user_cover("OYUN-0123456789")  # olmayanı silmek sessiz
                self.assertIsNone(discovery.user_cover("../../x"))  # kimlik biçimi dışı: yol karıştırılamaz


class KullaniciResmiTesti(unittest.TestCase):
    """'Resim seç': dosya yerel olarak kopyalanıp ölçeklenir; özgün dosyaya dokunulmaz; geçersiz dosya reddedilir."""

    @classmethod
    def setUpClass(cls):
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        cls.qt = QApplication.instance() or QApplication([])

    def _image(self, folder, name, width, height):
        from PySide6.QtGui import QColor, QImage
        image = QImage(width, height, QImage.Format.Format_RGB32)
        image.fill(QColor("#3355aa"))
        path = str(Path(folder, name))
        self.assertTrue(image.save(path))
        return path

    def test_kopyalanir_olceklenir_ve_kaldirilir(self):
        from PySide6.QtGui import QImage
        from app.ui.page_games import Cover
        with tempfile.TemporaryDirectory() as data, tempfile.TemporaryDirectory() as src:
            wide = self._image(src, "genis.png", 1920, 1080)
            before = Path(wide).read_bytes()
            with mock.patch.object(discovery.paths, "user_data_path", return_value=Path(data)):
                self.assertTrue(Cover.import_image("OYUN-0123456789", wide))
                saved = discovery.user_cover("OYUN-0123456789")
                self.assertEqual(Path(saved).parent, Path(data, "kapaklar"))
                size = QImage(saved).size()
                self.assertEqual((size.width(), size.height()), (Cover.W * 2, Cover.H * 2))  # kutuya göre kırpılıp ölçeklendi
                self.assertEqual(Path(wide).read_bytes(), before)  # özgün dosya aynen
                self.assertFalse(list(Path(data, "kapaklar").glob("*.tmp*")))  # geçici dosya kalmadı
                cover = Cover({"ad": "Oyun", "id": "OYUN-0123456789"}, saved)
                self.assertIsNotNone(cover.pixmap)
                discovery.remove_user_cover("OYUN-0123456789")
                self.assertIsNone(discovery.user_cover("OYUN-0123456789"))

    def test_gecersiz_dosya_ve_kimlik_reddedilir(self):
        from app.ui.page_games import Cover
        with tempfile.TemporaryDirectory() as data, tempfile.TemporaryDirectory() as src:
            junk = Path(src, "resim.png")
            junk.write_bytes(b"resim degil")
            good = self._image(src, "iyi.png", 100, 100)
            with mock.patch.object(discovery.paths, "user_data_path", return_value=Path(data)):
                self.assertFalse(Cover.import_image("OYUN-0123456789", str(junk)))
                self.assertFalse(Cover.import_image("../../x", good))  # kimlik biçimi dışı: yol karıştırılamaz
                self.assertFalse(Path(data, "kapaklar").exists() and any(Path(data, "kapaklar").iterdir()))

    def test_yatay_da_dikey_de_kutuyu_doldurur(self):
        from app.ui.page_games import Cover
        with tempfile.TemporaryDirectory() as src:
            wide = Cover({"ad": "A"}, self._image(src, "w.png", 1920, 620))
            tall = Cover({"ad": "B"}, self._image(src, "t.png", 600, 900))
            for cover in (wide, tall):  # kırpılarak: kutudan küçük kalıp şeritlenmez
                self.assertEqual((cover.pixmap.width(), cover.pixmap.height()), (Cover.W * 2, Cover.H * 2))
            self.assertIsNone(Cover({"ad": "C"}, str(Path(src, "yok.png"))).pixmap)  # dosya yoksa harf/simge

    def test_ayni_yola_yeni_resim_onbellekte_eskimez(self):
        from app.ui.page_games import Cover
        with tempfile.TemporaryDirectory() as src:
            path = self._image(src, "k.png", 600, 900)
            first = Cover({"ad": "A"}, path).pixmap
            import os
            self._image(src, "k.png", 900, 600)
            os.utime(path, ns=(1, 2))  # değişme zamanı farklı
            self.assertIsNot(Cover({"ad": "A"}, path).pixmap, first)  # önbellek yeni dosyayı çözdü
            self.assertIsNotNone(first)


def _contrast(a, b):
    def lum(color):
        r, g, bl = (int(color.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
        f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(bl)
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


class HarfKartiTesti(unittest.TestCase):
    """Kapaksız, exe simgesiz oyunun harf kartı: renk adından sabit türer, iki temada da AA karşıtlık."""

    def test_ayni_ad_ayni_renk_ve_palette_kalir(self):
        from app.ui import theme
        for dark, tones in ((True, theme.LETTER_TONES_DARK), (False, theme.LETTER_TONES_LIGHT)):
            card = theme.DARK["card"] if dark else theme.LIGHT["card"]
            first = theme.letter_style("Örnek Oyun", dark, card)
            self.assertEqual(first, theme.letter_style("  örnek oyun ", dark, card))  # büyük/küçük harf ve kenar boşluğu farkı yok
            self.assertIn(first[0], tones)
        used = {theme.letter_style(name, True, theme.DARK["card"])[0] for name in
                ("Doom", "Blender", "Cyberpunk", "Destiny", "Hades", "Portal", "Terraria", "Celeste", "Dota", "Factorio")}
        self.assertGreater(len(used), 3)  # tek renge yığılmaz

    def test_harf_ve_zemin_en_az_AA(self):
        from app.ui import theme
        for dark, tones in ((True, theme.LETTER_TONES_DARK), (False, theme.LETTER_TONES_LIGHT)):
            card = theme.DARK["card"] if dark else theme.LIGHT["card"]
            for tone in tones:
                ground = theme.mix(tone, card, theme.LETTER_WASH)
                self.assertGreaterEqual(_contrast(tone, ground), 4.5, (dark, tone))


if __name__ == "__main__":
    unittest.main()
