# Forevermore web sitesi

Bu klasör GitHub Pages'te yayımlanan tanıtım sitesidir (uygulamanın kendisi için depo kökündeki [README](../README.md) dosyasına bakın).

## Site yapısı (30 Ekim 2026)
- `index.html` (TR) ve `en.html` (EN): aynı iskelet. Sayaçlar ve bazı metinler `<!--n:...-->`, `<!--v:...-->` işaretleriyle
  `py -3.12 tools\site_veri.py` tarafından uygulamanın kendi dosyalarından (data/tweaks_app.json, lang/*.json) doldurulur; elle değiştirmeyin.
  Katalog ya da çeviri değişince bu aracı yeniden çalıştırın (`veri.js` de buradan üretilir).
- `demo.js`: örnek tarama, ayar künyesi, geri alma, tahmin oyunu, oyun denetimi. `erisim.js`: Okuma modu düğmesi.
- `erisilebilirlik.html`: erişilebilirlik bildirgesi (TR + EN).
- Demo örnek veriyle çalışır ve ziyaretçinin bilgisayarını taramaz; bunu sayfada da yazıyor.
- Metin kuralları: docs/TASARIM_ESASLARI.md bölüm 11 (slogan ve tekrar yasağı). `img/*_tr.png` eski arayüz görüntüleridir, sayfada kullanılmıyor.
