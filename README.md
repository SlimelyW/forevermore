<p align="center">
  <img src="img/logo.png" alt="Forevermore" width="160">
</p>

<h1 align="center">Forevermore</h1>

<p align="center">
  <b>Placebo değil, gerçekten işe yarayan Windows ayarları.</b><br>
  <i>No placebo. Windows settings that actually work.</i>
</p>

<p align="center">
  <a href="https://slimelyw.github.io/forevermore/">Web sitesi</a> ·
  <a href="https://github.com/SlimelyW/forevermore/releases/latest/download/Forevermore.zip">İndir (Windows)</a> ·
  <a href="https://buymeacoffee.com/forevermore">Buy Me a Coffee</a> ·
  <a href="#english">English</a>
</p>

---

## Forevermore nedir?

Forevermore, oyuncular için bir Windows 10 / 11 ayar uygulamasıdır. Bilgisayarınızı tarar, her ayarın ne yaptığını
artısı ve eksisiyle sade bir dille anlatır; internette dolaşan "FPS artırır", "ping düşürür" gibi placebo ve zararlı
ayarları ayrıca işaretler. Her değişiklik yedeklenir ve tek tıkla geri alınır.

Uzun zamandır bilgisayar ve optimizasyon işleriyle hobi olarak ilgileniyorum. İnternette çok fazla yanıltıcı ayar ve
asılsız optimizasyon olduğu için kendi testlerime, ölçümlerime ve deneyimlerime dayanan, basit bir uygulama yapmak
istedim. Forevermore bir üniversite öğrencisinin hobi projesidir.

![Sistem özeti](img/ozet_tr.png)

## Özellikler

- **Tarama ve açıklama:** donanımı ve mevcut ayarları salt okuyarak tarar; her ayarın ne yaptığını, kimlerin
  dokunmaması gerektiğini yazar.
- **Placebo ve zararlı ayarlar:** işe yaramayan ya da zarar veren yaygın ayarları ayrı gösterir, bilgisayarınızda
  uygulanmış olanları bulur.
- **Her şey geri alınabilir:** değişiklikten önce yedek ve geri yükleme noktası; Değişiklikler sayfasından tek tıkla geri alma.
- **Ekran kartı ayarları:** NVIDIA ve AMD sürücü ayarları (gecikme, ölçekleme, G-SYNC).
- **Oyun profilleri** *(Pro)*: oyun başına işlemci önceliği, çekirdek seçimi, bildirimleri susturma; oyun açılınca
  otomatik uygulanır, kapanınca geri alınır. Oyun içi ayarlar kartı: her oyunda aranacak ayarlar, kanıt rozetiyle.
- **Tek tuş Boost:** Oyun Modu'nu açar, Game DVR arka plan kaydını kapatır, listendeki programları onayınla kapatır; geri alınabilir.
  Bellek boşaltma, pano silme ve servis durdurma bilerek yok.
- **Uygulama kaldırıcı:** programın kendi kaldırıcısını açar, adı birebir eşleşen kalıntıları yedekleyerek kaldırır (geri yüklenebilir).
- **Ekran yerleşimi:** çoklu monitörleri sürükleyip bırakarak yerleştirme.
- **Önce / Sonra ölçümü**: FPS, gecikme ve zamanlayıcı ölçümüyle gerçek etkiyi görme.
- Türkçe ve İngilizce arayüz. Telemetri yok.

| | Ücretsiz | Forevermore Pro |
|---|---|---|
| Tarama, açıklamalar, rehberler, rapor | ✓ | ✓ |
| Ayar değişikliği | aynı anda 10 (referansla +10) | sınırsız |
| Önce / Sonra ölçümü | ✓ | ✓ |
| Hazır profiller, Oyunlar | — | ✓ |
| Geri alma | ✓ | ✓ |
| Fiyat | ücretsiz | 1 ay $2 (~₺100), 3 ay $5 (~₺250), 12 ay $16 (~₺800); süreli kod, yenilenmez, 1 bilgisayar |

## Kurulum

1. [Forevermore.zip](https://github.com/SlimelyW/forevermore/releases/latest/download/Forevermore.zip) dosyasını indirin.
2. Bir klasöre açın ve **Forevermore.exe**'yi çalıştırın. Ayar değiştirmek için yönetici izni ister; "Hayır" derseniz
   salt okunur modda açılır.
3. Pro için: uygulamada **Lisans** sayfasından bilgisayar kodunuzu kopyalayın, Discord'da ticket açıp kodunuzu alın ve aynı sayfaya girin
   (ayrıntı: web sitesi, "Kod nasıl alınır?").

Kaldırmak için: Ekstra ayarlar > "Kaldırmaya hazırla" ile değişiklikleri geri alın, sonra klasörü silin.

## Orijinal kopya mı?

Forevermore'u yalnızca bu depodan ya da web sitesinden indirin.

- Uygulamanın **Bilgi** sayfası "Orijinal kopya" yazmalı ve imza parmak izi şu olmalı: `5FE5-D786-0B89-A56E`
- Her sürümün zip SHA-256 değeri [Releases](https://github.com/SlimelyW/forevermore/releases) sayfasında yazar.

> **Antivirüs uyarısı hakkında:** Forevermore Python ile yazılıp PyInstaller ile paketlenir; bu yöntemle paketlenen
> programlar küçük antivirüslerde sık sık yanlış alarm verir. 2.1.0 paketini
> [VirusTotal](https://www.virustotal.com/gui/file/b0f6ac7fc962ae47eea6ed8f82ecad22aac2c99270ee760d4192f16061720694)'da
> taranan 66 motorun hiçbiri işaretlemedi (0/66, Ekim 2026); sonuç sürümler arasında değişebilir. SmartScreen'in
> "bilinmeyen yayımcı" uyarısı kod imzalama sertifikası olmamasından kaynaklanır. Yukarıdaki değerler tutuyorsa dosya
> yayımlandığı gibidir.

## Gizlilik

Telemetri, reklam, analiz yok. Tarama sonuçları bilgisayarınızdan çıkmaz. Forevermore varsayılan olarak internete hiç
bağlanmaz; Pro kodu bilgisayarda, internetsiz doğrulanır. Tek istisna, Ayarlar'dan sizin açtığınız güncelleme denetimidir:
yalnızca GitHub'ın herkese açık sürüm listesine bağlanır ve veri göndermez.
Ayrıntı: [Gizlilik](https://slimelyw.github.io/forevermore/gizlilik.html).

## Lisans

© 2026 Kubilay Paşa. Tüm hakları saklıdır. **Bu depo yalnızca web sitesini ve indirme dosyasını içerir; uygulamanın
kaynak kodu açık değildir.** Forevermore kişisel kullanım için sunulur; satılamaz, değiştirilip dağıtılamaz, başka bir
ad veya yapımcı adıyla sunulamaz. Tam metin: [Kullanım koşulları](https://slimelyw.github.io/forevermore/kosullar.html).

İletişim: Discord **smileyw** · e-posta **forevermore.destek@protonmail.com** · Destek olmak için: [buymeacoffee.com/forevermore](https://buymeacoffee.com/forevermore)

---

<a id="english"></a>

## English

Forevermore is a Windows 10 / 11 settings app for gamers. It scans your PC, explains what each setting does with its
pros and cons, and flags the placebo and harmful tweaks that circulate online ("more FPS", "lower ping"). Every change
is backed up and can be undone with one click. It is a university student's hobby project, based on my own tests,
measurements and experience.

- **Free:** scan, explanations, guides, report, Before / After measurement, 10 setting changes at a time (+10 with a referral), undo.
- **Pro (1 month $2, 3 months $5, 12 months $16; a time-limited code, does not renew, 1 computer):** unlimited changes, profiles, per-game settings.
- **Download:** [Forevermore.zip](https://github.com/SlimelyW/forevermore/releases/latest/download/Forevermore.zip) →
  extract → run **Forevermore.exe**.
- **Genuine copy:** the About page says "Original copy" and shows the signature fingerprint `5FE5-D786-0B89-A56E`.
- **Antivirus warnings:** PyInstaller-packaged apps often get false alarms from smaller engines; none of the 66 engines on
  [VirusTotal](https://www.virustotal.com/gui/file/b0f6ac7fc962ae47eea6ed8f82ecad22aac2c99270ee760d4192f16061720694)
  flagged the 2.1.0 package (0/66, October 2026); results can change between versions.
- **Privacy:** no telemetry; the app does not connect to the internet by default, and Pro codes are verified offline on your computer.
  [Privacy policy](https://slimelyw.github.io/forevermore/gizlilik.html#en)
- **License:** © 2026 Kubilay Paşa. All rights reserved. This repository contains only the website and the download;
  the source code is not public. [Terms](https://slimelyw.github.io/forevermore/kosullar.html#en)

Contact: Discord **smileyw** · email **forevermore.destek@protonmail.com** · Support the project: [buymeacoffee.com/forevermore](https://buymeacoffee.com/forevermore)

## Site yapısı (30 Ekim 2026)
- `index.html` (TR) ve `en.html` (EN): aynı iskelet. Sayaçlar ve bazı metinler `<!--n:...-->`, `<!--v:...-->` işaretleriyle
  `py -3.12 tools\site_veri.py` tarafından uygulamanın kendi dosyalarından (data/tweaks_app.json, lang/*.json) doldurulur; elle değiştirmeyin.
  Katalog ya da çeviri değişince bu aracı yeniden çalıştırın (`veri.js` de buradan üretilir).
- `demo.js`: örnek tarama, ayar künyesi, geri alma, tahmin oyunu, oyun denetimi, fiyat süresi. `erisim.js`: Okuma modu düğmesi.
- `erisilebilirlik.html`: erişilebilirlik bildirgesi (TR + EN).
- Demo örnek veriyle çalışır ve ziyaretçinin bilgisayarını taramaz; bunu sayfada da yazıyor.
- Metin kuralları: docs/TASARIM_ESASLARI.md bölüm 11 (slogan ve tekrar yasağı). `img/*_tr.png` eski arayüz görüntüleridir, sayfada kullanılmıyor.
