# Siteyi yayımlama (GitHub Pages, ücretsiz)

Yayın bilgileri: depo https://github.com/SlimelyW/forevermore · site https://slimelyw.github.io/forevermore/ ·
ücretsiz ve açık kaynak (MIT).

`site/` klasörü hazır bir statik sitedir: ana sayfa (TR `index.html`, EN `en.html`), kullanım koşulları,
gizlilik ve iade sayfaları. Dış kaynak (yazı tipi, analiz, çerez) kullanmaz. Lemon Squeezy'ye verilecek adres
bu sitenin adresidir.

**Neden GitHub Pages:** ücretsiz, kendi alan adı gerekmez (`kullaniciadi.github.io/forevermore`), 38 MB'lık zip
aynı deponun "Releases" bölümünde barınır. (Cloudflare Pages'te dosya başına 25 MiB sınırı var; zip sığmaz.)

> **Önemli:** GitHub'a YALNIZCA `site/` klasörünün İÇİNDEKİLERİ yüklenir. Projenin kaynak kodu, `docs/`,
> `tools/`, `.forevermore-imza` ya da `ozel_anahtar.txt` ASLA yüklenmez. Site deposu herkese açıktır.

## Adımlar (bir kez)

1. github.com'da hesap aç (kullanıcı adı adreste görünecek, ör. `kubilaypasa`).
2. Sağ üstte **+ → New repository**: ad `forevermore`, **Public**, "Add a README" işaretsiz → Create.
3. Açılan sayfada **uploading an existing file** → bilgisayarda `site` klasörünü aç, içindeki her şeyi
   (`index.html`, `en.html`, `kosullar.html`, `gizlilik.html`, `iade.html`, `style.css`, `ayarlar.js`, `img`
   klasörü) sürükle → **Commit changes**.
4. **Settings → Pages** → *Source*: "Deploy from a branch", *Branch*: `main`, klasör `/ (root)` → Save.
   1–2 dakika sonra adres görünür: `https://KULLANICI.github.io/forevermore/`
5. **Releases → Create a new release** → *Tag*: `v2.1.2` → `dist\Forevermore.zip` dosyasını sürükle →
   açıklamaya SHA-256 değerini yaz (`dist\Forevermore.zip.sha256.txt`) → **Publish release**.
6. Bana kullanıcı adını yaz; `site/ayarlar.js` içindeki `indir` bağlantısını
   `https://github.com/KULLANICI/forevermore/releases/latest/download/Forevermore.zip` yapıp güncel dosyayı
   veririm (sen 3. adımdaki gibi yeniden yüklersin).
7. Lemon Squeezy'de *Website* alanına `https://KULLANICI.github.io/forevermore/` yaz.
8. Mağaza ve ürün hazır olunca `ayarlar.js` içindeki `satinal`, `portal` ve `fiyat` doldurulur.

## Yeni sürümde

`derle.bat` → yeni Release (aynı adla `Forevermore.zip`) → `ayarlar.js` içindeki `sha256` güncellenir.
"latest/download" bağlantısı kendiliğinden yeni sürümü indirir.

## Site dosyalarını güncellemek

- Ekran görüntüleri: `py -3.12 -m tests.site_gorselleri tr` ve `... en` (önizleme modu, ayar değiştirmez;
  Özet görüntüsü bilgisayara özel bulgular görünmesin diye kesilir).
- Kullanım koşulları ve logo: `py -3.12 tools\site_uret.py` (depo kökündeki `LICENSE` dosyasından üretir).
- Yerelde bakmak: `py -3.12 -m http.server 8765 --directory site` → http://127.0.0.1:8765

## Bilinmesi gerekenler

- Lemon Squeezy belgeleri site için ayrıntılı bir liste vermiyor; mağaza onayı bir anket + kimlik doğrulaması
  ile yapılıyor. Sitede ürün açıklaması, fiyat, iletişim, koşullar, gizlilik ve iade sayfası var; bunlar ödeme
  sağlayıcılarının genelde aradığı şeyler. İnceleme ek bilgi isterse buraya eklenir.
- İade koşulu: gerekçesiz iade yok; yalnızca çözülemeyen teknik sorun (14 gün içinde bildirilen) ve hatalı ödeme. Değiştirmek
  istersen `site/iade.html`.
