# Forevermore GitHub release notları

GitHub'daki release açıklamasına sürümün iki bloğunu (TR, sonra EN) yapıştırın. SHA-256 değeri `site/ayarlar.js` ile aynı olmalı.

# 2.3.1 (5 Kasım 2026)

## Türkçe

**Sürüm: 2.3.1 (etiket v2.3.1).** SHA-256 (Forevermore.zip): `5A0E839CB27E5F64F21A0EA9A2658251D27FE7528E00A3A5C761AF136F7F71E7`
İmza parmak izi: `5FE5-D786-0B89-A56E`

> **Uygulama henüz kod imzalı değil.** Windows Defender veya SmartScreen uyarı verebilir. Zip'i açıp `Forevermore.exe`'yi çalıştır.
> SHA-256 değerini `Get-FileHash Forevermore.zip -Algorithm SHA256` ile karşılaştır.

### Yeni neler var
- `.exe` dosya özelliklerinde sürüm artık doğru görünüyor (2.3.1); 2.3.0'da 2.2.0 görünüyordu.
- Qt'nin LGPLv3 lisans metni (`LGPL-3.0.txt`) pakete eklendi.
- Başka işlev değişikliği yok.

## English

**Version: 2.3.1 (tag v2.3.1).** SHA-256 (Forevermore.zip): `5A0E839CB27E5F64F21A0EA9A2658251D27FE7528E00A3A5C761AF136F7F71E7`
Signature fingerprint: `5FE5-D786-0B89-A56E`

> **The app is not code-signed yet.** Windows Defender or SmartScreen may warn. Unzip and run `Forevermore.exe`.
> Compare the SHA-256 with `Get-FileHash Forevermore.zip -Algorithm SHA256`.

### What's new
- The version shown in the `.exe` file properties is now correct (2.3.1); 2.3.0 showed 2.2.0.
- The full LGPLv3 text for Qt (`LGPL-3.0.txt`) is now included in the package.
- No other functional changes.

# 2.3.0 (4 Kasım 2026)

## Türkçe

**Sürüm: 2.3.0 (etiket v2.3.0).** SHA-256 (Forevermore.zip): `C11F8BF3A658FABD2A944E7AF2399CF4129DDAFC61AE2CB94FA4DA8980AB0347`
İmza parmak izi: `5FE5-D786-0B89-A56E`

> **Uygulama henüz kod imzalı değil.** Windows Defender veya SmartScreen uyarı verebilir. Zip'i açıp `Forevermore.exe`'yi çalıştır.
> SHA-256 değerini `Get-FileHash Forevermore.zip -Algorithm SHA256` ile karşılaştır.

### Yeni neler var
- **Forevermore artık tamamen ücretsiz ve açık kaynak (MIT).** Pro, lisans kodu ve kilitli özellik kalktı; tüm ayarlar herkese açık.
- Gönüllü bağış: sol menünün altında sabit "Beğendiysen bağış yap" düğmesi ve sitede indirmenin altında Destek bölümü. Zorunlu değil, hiçbir yerde açılır pencere yok.
- İki tur güvenlik denetimi düzeltmeleri; oyun günlüğündeki kapanış hatası düzeltildi.

## English

**Version: 2.3.0 (tag v2.3.0).** SHA-256 (Forevermore.zip): `C11F8BF3A658FABD2A944E7AF2399CF4129DDAFC61AE2CB94FA4DA8980AB0347`
Signature fingerprint: `5FE5-D786-0B89-A56E`

> **The app is not code-signed yet.** Windows Defender or SmartScreen may warn. Unzip and run `Forevermore.exe`.
> Compare the SHA-256 with `Get-FileHash Forevermore.zip -Algorithm SHA256`.

### What's new
- **Forevermore is now fully free and open source (MIT).** Pro, license codes and locked features are gone; every setting is available to everyone.
- Voluntary donation: a pinned "Donate if you like it" button at the bottom of the sidebar and a Support section under Download on the site. Optional, no pop-ups anywhere.
- Two rounds of security-audit fixes; fixed a shutdown error in the game log.

# 2.2.0 (31 Ekim 2026)

> **Not:** Bu sürümlerde Pro vardı; 2.3.0'da kalktı (Forevermore artık ücretsiz ve açık kaynak, MIT).

## Türkçe

**Sürüm: 2.2.0 (etiket v2.2.0).** SHA-256 (Forevermore.zip): `8C74918C5738328CD5A9C4D6047BFEC13E143B26D04F99F8C53D3FA6B3860209`
İmza parmak izi (uygulamada Bilgi sayfasında "Orijinal kopya" yanında): `5FE5-D786-0B89-A56E`

> **Uygulama henüz kod imzalı değil.** Windows Defender veya SmartScreen uyarı verebilir. Tespit olursa dosyayı silme, bana haber ver.
> Zip'i açıp içindeki `Forevermore.exe`'yi çalıştır. İndirdikten sonra SHA-256 değerini yukarıdakiyle karşılaştır
> (`Get-FileHash Forevermore.zip -Algorithm SHA256`).

### Yeni neler var
**Güvenlik ve kararlılık (Faz 1)**
- Spectre/Meltdown (CPU-004) ayarı: zorunlu geri yükleme noktası, uzun uyarı ve Güvenli Mod'dan geri alma komutu.
- "Yanıt vermiyor" donmaları: ekran kartı sorgusu ve donanım tespiti arka plana alındı; arayüz 2 sn'den uzun takılırsa yerel günlüğe yazar.
- Ani kapanma/elektrik kesintisinden sonra "bu kopya değiştirilmiş" yanlış alarmı giderildi; yedekler tek tıkla kurtarılır.
- Açılışta çalışan PowerShell sayısı azaltıldı (35 → 18), `-ExecutionPolicy Bypass` kaldırıldı.
**Hata düzeltmeleri (Faz 2)**
- msconfig'den kalan işlemci/bellek sınırı bulgusunda "Çöz" artık tüm taramayı yeniden başlatmıyor; BCD yedeği alınıyor.
- "Gelişmiş ayarlar" sayfayı en üste fırlatmıyor; yeniden başlatma sonrası oyun listesi ve profiller korunuyor.
- NVIDIA bindirme, GPU–ekran eşleşmesi, oyun başlatıcısı yerine gerçek oyun süreci, Önce/Sonra "yeterli kare yok" teşhisi.
- Bulgular gruplu ve açık; "Pro'ya geç" uyarısı sakin şerit (modal pencere yok).
**Özellikler (Faz 3)**
- Sistem geri yükleme kapalıysa onayınla açılır (alan ayırıp doğrular).
- Ücretsiz planda Oyunlar sayfası 1 oyunla denenir.
- Microsoft Store ve Windows uygulamalarını geri yükleme; başlatılamayan AppX hizmeti önceden bildirilir.
- GPU'ya göre ayarlar; hibritte oyunu çizmeyen kartın ayarlarına not; sürücü ayarlarında "geri alınabilir" rozeti.
**Tasarım ve hız (Faz 4)**
- Sayfa geçişi çok daha hızlı (tekrar ziyaret ≈ 8–50 ms); menü üstüne gelince sayfa önceden hazırlanır.
- Ayar uygulanınca "Geri al" bildirimi; Alt+Sol, fare geri tuşu ve Esc önceki ekrana döner.
- Menü klavyeyle gezilir, tıklama alanları 40 px, odak kaybında canlı izleme durur, en küçük pencere 900×560.
- Lisans artık tamamen çevrimdışı (imzalı kod); eski sunucu kodu silindi.

### Bilinen sorunlar / denenmedi
- **Kod imzası yok** (yukarıdaki uyarı). Sertifika alınınca imzalı sürüm gelecek.
- Gerçek bilgisayarda (yönetici izniyle) denenmedi: Sistem korumasını açma, Store geri yükleme, msconfig "Çöz" ile gerçek bcdedit, Spectre/Meltdown ayarı ve Güvenli Mod'dan geri alma.
- Faz 4 arayüz değişiklikleri yalnızca testlerle ve ekran dışı çizimle doğrulandı; gerçek ekranda, %125 DPI'da ve en küçük pencerede elle bakılmadı.
- Intel'e özel sürücü ayarı yok (genel ayarlar çalışır). Çok uzun sayfalar (ör. Placebo) ilk açılışta ≈ 0.4 sn gecikebilir.
- SYS-017 (Defender gerçek zamanlı koruma anahtarı) bazı antivirüs motorlarında yanlış alarm tetikleyebilir; sorun görürsen haber ver.

## English

**Version: 2.2.0 (tag v2.2.0).** SHA-256 (Forevermore.zip): `8C74918C5738328CD5A9C4D6047BFEC13E143B26D04F99F8C53D3FA6B3860209`
Signature fingerprint: `5FE5-D786-0B89-A56E`

> **The app is not code-signed yet.** Windows Defender or SmartScreen may show a warning. If something is detected, do not delete the file; tell me.

**What's new:** safer Spectre/Meltdown setting, fixes for "not responding" freezes, crash-safe backups, fewer PowerShell calls at startup (35 → 18); fixes for msconfig leftovers, page jumping, game list after restart, Before/After diagnostics; System Restore can be enabled when off, free plan can try 1 game, Store/Windows app repair, per-GPU settings; much faster page switches, "Undo" notice after changes, Alt+Left / mouse-back / Esc to go back, keyboard-navigable menu, 40 px click targets, fully offline licensing.
**Known issues:** not code-signed; elevated real-PC tests (System Restore enable, Store repair, bcdedit, Safe Mode rollback) and the new UI on a real screen / 125% DPI are not hand-verified yet; no Intel-specific driver settings.

# 2.1.2 (30 Ekim 2026)

> **Not:** Bu sürümlerde Pro vardı; 2.3.0'da kalktı (Forevermore artık ücretsiz ve açık kaynak, MIT).

## Türkçe

**Sürüm: 2.1.2 (etiket v2.1.2).** SHA-256 (Forevermore.zip): `53F2075F758366A285729FD4CC6C541797618B8F93A92D96903154A45E6E454D`
İmza parmak izi (uygulamada Bilgi sayfasında "Orijinal kopya" yanında): `5FE5-D786-0B89-A56E`

### Arayüz: daha sade ve daha hızlı
- **Ayar sayfaları tek liste:** her ayar ayrı kart yerine tek kartta, satırlar ince çizgiyle ayrılmış. Değişiklikler ve Hazır profiller sayfaları da aynı düzende.
- **Özet sakinleşti:** "Sıradaki en iyi hamle" tek odak; dört büyük rakam tek sıra küçük özete dönüştü (tıklanınca listeleri açılır), canlı izleme kutuları alçaldı.
- **Kenar menü:** her satırdaki "3 / 15" sayıları kalktı; yalnızca önerilen ama açık olmayan ayar varsa küçük bir sayı görünür.
- **Anında tepki:** aç/kapa düğmesi tıkladığın anda yeni durumu gösterir ("uygulanıyor"), işlem bitince doğrulanır; vazgeçersen veya işlem olmazsa eski haline döner. Düğmeler basılınca hafifçe küçülür, klavyeyle gezerken odak halkası net görünür.
- **Hareket kısa ve tutarlı:** bütün animasyonlar 300 ms'nin altında, yalnızca saydamlıkla; "Gelişmiş ayarlar" artık anında açılır. Pencere küçültülünce veya arka plandayken animasyon çalışmaz; Windows'ta animasyon efektleri kapalıysa uygulama da hareketi azaltır.
- **Daha hızlı sayfalar:** sayfa geçişleri yaklaşık yarı yarıya hızlandı; uzun program listesi kaydırdıkça parça parça çizilir. İlk açılışta boş ekran yerine sayfanın iskeleti görünür.

### Bilmen gerekenler
- 2.1.1'deki düzeltmelerin hepsi bu sürümde de var. Yeni arayüz testlerle (422 test) doğrulandı; gerçek bilgisayarda elle henüz denenmedi.
- Windows SmartScreen "bilinmeyen yayımcı" uyarısı verebilir. Zip'in SHA-256 değerini yukarıdakiyle karşılaştırarak doğrulayabilirsin.
- Forevermore varsayılan olarak internete bağlanmaz, telemetri yoktur.

## English

**Version: 2.1.2 (tag v2.1.2).** SHA-256 (Forevermore.zip): `53F2075F758366A285729FD4CC6C541797618B8F93A92D96903154A45E6E454D`
Signature fingerprint (next to "Original copy" on the About page): `5FE5-D786-0B89-A56E`

### Interface: simpler and faster
- **Settings pages are one list:** instead of a separate card per setting, rows sit in one card separated by thin lines. The Changes and Profiles pages use the same layout.
- **A calmer Summary:** "Next best step" is the single focus; the four big numbers became one compact row (click to open their lists), and the live monitor tiles are shorter.
- **Sidebar:** the "3 / 15" counts on every row are gone; a small number appears only when a category has recommended settings that are not on yet.
- **Instant response:** switches show the new state the moment you click ("applying") and are confirmed when the change finishes; if you cancel or it fails, they go back. Buttons shrink slightly when pressed, and keyboard focus rings are clear.
- **Short, consistent motion:** every animation is under 300 ms and uses only opacity; "Advanced settings" now opens instantly. Nothing animates while the window is minimized or in the background, and the app reduces motion when Windows animation effects are off.
- **Faster pages:** page switches are about twice as fast; the long program list is drawn in parts as you scroll. On first start you see the page skeleton instead of an empty screen.

### Good to know
- All 2.1.1 fixes are included. The new interface is covered by tests (422 tests) but has not been tried by hand on a real PC yet.
- Windows SmartScreen may warn about an "unknown publisher". You can verify the zip by comparing its SHA-256 with the value above.
- Forevermore does not connect to the internet by default and has no telemetry.

---

# 2.1.1 (30 Ekim 2026)

> **Not:** Bu sürümlerde Pro vardı; 2.3.0'da kalktı (Forevermore artık ücretsiz ve açık kaynak, MIT).

## Türkçe

**Sürüm: 2.1.1 (etiket v2.1.1).** SHA-256 (Forevermore.zip): `E710845C4CB7121AEEBDEFA6CE45E6C133C83A47FC13F34C2D4A4783816AD742`
İmza parmak izi (uygulamada Bilgi sayfasında "Orijinal kopya" yanında): `5FE5-D786-0B89-A56E`

### Düzeltildi
- **Önce/Sonra FPS ölçümü artık çalışıyor.** Önceki sürümde her oyunda "yeterli kare yok" hatası veriyordu: PresentMon'un yazdığı sütun adı yanlış okunuyordu. Ölçüm artık 8 saniyelik geri sayımla başlar (oyuna dönmek için), uygulama küçülür ve yalnızca oyun ön plandayken geçen süre sayılır. Alt-tab yapınca sayaç durur, "Oyuna dönün" yazar.
- **Ölçüm ekranında süreç listesi** artık çalışan pencereli programları ve oyunlarını gösterir; arama, yenileme ve "ön plandaki pencereyi seç" önerisi var. Ölçüm olmazsa genel hata kutusu yerine sebebi (yakalama sorunu / yanlış süreç / oyun ön planda değil), yakalanan kare sayıları, çözüm adımları ve "Logu kopyala" gösterilir. NVIDIA sürücü FPS sınırı ölçüm ekranında yazar.
- **Fare tekerleği** artık ayarların değerini (açılır liste, kaydırıcı, sayı kutusu) değiştirmiyor; sayfa kayıyor.
- **Oyunlar:** "Gelişmiş ayarları göster" sayfayı en üste atmıyor. Oyun taraması kalıcı saklanıyor, her açılışta arka planda yenileniyor, hata olursa sebebi ve "Yeniden tara" düğmesi çıkıyor. Steam, uygulama başka bir yönetici hesabıyla açılsa da bulunuyor.
- **League of Legends** profili istemciyle (LeagueClientUxRender.exe) değil oyunun kendisiyle (League of Legends.exe) kaydedilir; eski kayıtlar açılışta düzeltilir. Başlatıcı/istemci exe'leri listede en sona gider.
- **Hibrit laptoplarda** raporda ekranı süren kart ile oyunları çizen kart artık çelişmiyor.
- **NVIDIA bindirmesi:** ayarın adı düzeltildi ("oyunlara eklenmesini engelle"). Bu sürücü ayarı NVIDIA Overlay süreçlerini kapatmaz; uygulama artık süreçlerin gerçek durumunu ve tamamen kapatmak için NVIDIA app'teki yolu yazıyor.
- **Daha az arka plan yükü:** tarama sırasında aynı anda en fazla 6 PowerShell (önce 15). Uygulama zaten açıkken tekrar çalıştırılırsa yeni kopya açılmaz, var olan pencere öne gelir.

### Yeni
- **Microsoft Store ve Windows uygulamalarını geri yükle** (Uygulama kaldırıcı sayfası): Store, App Installer, Xbox bileşenleri, Hesap Makinesi, Fotoğraflar vb. için durum ve tek tek geri yükleme. Geri yükleme noktası alınır, sonuç yeniden okunarak doğrulanır; dosyalar silinmişse "başarılı" denmez, onarım yolları gösterilir.
- **Ekran Kartı sayfası** hibritte iki kartın ayarlarını ayrı başlıklarla gösterir (oyunları çizen / ekranı süren). Kart algılanamazsa marka elle seçilebilir.
- Pencere küçültülünce veya arka plana geçince animasyonlar durur; Windows'ta "Animasyon efektleri" kapalıysa uygulama da hareketi azaltır.

### Bilmen gerekenler
- FPS ölçümü yönetici olarak hibrit bir laptopta (NVIDIA + AMD) tam ekran ve pencereli deneme pencereleriyle denendi; gerçek oyunlarla (özellikle anti-cheat'li oyunlarla) ve Windows 10'da henüz denenmedi. Store geri yüklemesi gerçek bir eksik Store ile denenmedi.
- Windows SmartScreen "bilinmeyen yayımcı" uyarısı verebilir. Zip'in SHA-256 değerini yukarıdakiyle karşılaştırarak doğrulayabilirsin.
- Forevermore varsayılan olarak internete bağlanmaz, telemetri yoktur.

## English

**Version: 2.1.1 (tag v2.1.1).** SHA-256 (Forevermore.zip): `E710845C4CB7121AEEBDEFA6CE45E6C133C83A47FC13F34C2D4A4783816AD742`
Signature fingerprint (next to "Original copy" on the About page): `5FE5-D786-0B89-A56E`

### Fixed
- **Before/After FPS measurement now works.** The previous version failed with "not enough frames" in every game because a column written by PresentMon was read under the wrong name. Measuring now starts after an 8-second countdown (so you can get back into the game), the app minimizes, and only time with the game in the foreground counts. Alt-tab pauses the timer and shows "Go back to the game".
- **The process list on the measurement page** now shows running windowed programs and your games, with search, refresh and a "use the window in the foreground" suggestion. When a measurement fails, instead of a generic error you see why (capture problem / wrong process / game not in the foreground), the frame counts, what to do, and "Copy log". The NVIDIA driver FPS limit is shown on the measurement page.
- **The mouse wheel** no longer changes setting values (dropdowns, sliders, number boxes); the page scrolls instead.
- **Games:** "Show advanced settings" no longer jumps to the top. The game scan is saved, refreshed in the background on every start, and a failure shows the reason and a "Scan again" button. Steam is found even when the app runs under a different administrator account.
- **League of Legends** profiles are saved with the game itself (League of Legends.exe), not the client (LeagueClientUxRender.exe); old entries are fixed on start. Launcher/client executables go to the end of the list.
- **On hybrid laptops** the report no longer contradicts itself about which card drives the display and which renders games.
- **NVIDIA overlay:** the setting is renamed ("block from attaching to games"). This driver setting does not close the NVIDIA Overlay processes; the app now shows their real state and where to turn them off completely in the NVIDIA app.
- **Less background load:** at most 6 PowerShell processes at once during a scan (was 15). Running the app again while it is open no longer starts a second copy; the existing window comes to the front.

### New
- **Restore Microsoft Store and Windows apps** (App uninstaller page): status and one-by-one restore for the Store, App Installer, Xbox components, Calculator, Photos and more. A restore point is created and the result is read back; if the files were deleted it does not claim success and shows repair options.
- **The Graphics Card page** shows each card's settings under its own heading on hybrid systems (renders games / drives the display). If no card is detected, the brand can be picked manually.
- Animations stop when the window is minimized or in the background; if "Animation effects" is off in Windows, the app reduces motion too.

### Good to know
- FPS measurement was tested as administrator on a hybrid laptop (NVIDIA + AMD) with full-screen and windowed test windows; it has not yet been tested with real games (especially games with anti-cheat) or on Windows 10. Store restore was not tested on a PC with the Store actually missing.
- Windows SmartScreen may warn about an "unknown publisher". You can verify the zip by comparing its SHA-256 with the value above.
- Forevermore does not connect to the internet by default and has no telemetry.

---

# 2.1.0 (30 Ekim 2026)

> **Not:** Bu sürümlerde Pro vardı; 2.3.0'da kalktı (Forevermore artık ücretsiz ve açık kaynak, MIT).

## Türkçe

**Sürüm: 2.1.0 (etiket v2.1.0).** SHA-256 (Forevermore.zip): `B0F6AC7FC962AE47EEA6ED8F82ECAD22AAC2C99270EE760D4192F16061720694`
İmza parmak izi (uygulamada Bilgi sayfasında "Orijinal kopya" yanında): `5FE5-D786-0B89-A56E`

### Yeni
- **Referans:** Ücretsiz sürümde aynı anda 10 değişiklik (önceden 15). Bir arkadaşını Discord'a getirirsen ikiniz de +10 değişiklik hakkı kazanırsınız (toplam 20). Kod bilgisayara bağlı ve süresizdir, Pro değildir.
- **Uygulama kaldırıcı:** Programın kendi kaldırıcısını açar, sonra adı birebir eşleşen kalıntı klasör ve kayıt anahtarlarını bulur. Kalıntılar silinmez: yedek klasörüne taşınır / .reg olarak dışa aktarılır ve geri yüklenebilir.
- **Tek tuş Boost:** Oyun Modu'nu açar, Game DVR arka plan kaydını kapatır ve listendeki programları onayınla kapatır. Ayarlar geri alınabilir. Bellek boşaltma, pano silme ve servis durdurma bilerek yok (ölçümlerde fayda göstermedi ya da risk taşıyor).
- **Ekran yerleşimi:** Çoklu monitörleri şemada sürükleyip bırakabilirsin; Windows'taki gibi kenara oturur, üst üste binmez. Değişiklik 15 saniyelik onayla yapılır, geri alınır.
- **Oyun içi ayarlar:** Oyunlar sayfasında her oyunda aranacak ayarlar (Reflex, FPS sınırı, V-Sync, yükseltme vb.) kanıt rozetiyle ve kaynağıyla. Oyuna özel sayı verilmez: doğrulanmış kaynak yok. Bilinen NVIDIA Reflex desteği gösterilir.
- **Bilgi sayfası:** Yapımcı ve iletişim tek kartta (destek e-postası dahil); faydalı bağlantılar Oyunlar sayfasına taşındı.

### Değişti
- **VRR / G-SYNC / FreeSync** artık "tartışmalı" etiketli: rekabetçi oyunlarda gecikmeye etkisi için kontrollü ölçüm yok. "Hazır profil: oyun" içinde otomatik seçilmez ve öneri listelerine girmez.

### Bilmen gerekenler
- Yukarıdaki yeni özellikler testlerle (396 test) doğrulandı, ancak gerçek bilgisayarda henüz elle denenmedi. Özellikle ekran sürükleme ve uygulama kaldırıcı sistemi değiştirir; ilk denemede dikkatli ol, hepsi geri alınabilir.
- Windows SmartScreen "bilinmeyen yayımcı" uyarısı verebilir (ücretli kod imzalama sertifikası yok). Zip'in SHA-256 değerini yukarıdakiyle karşılaştırarak doğrulayabilirsin.
- Forevermore varsayılan olarak internete bağlanmaz, telemetri yoktur.

---

## English

**Sürüm: 2.1.0 (etiket v2.1.0).** SHA-256 (Forevermore.zip): `B0F6AC7FC962AE47EEA6ED8F82ECAD22AAC2C99270EE760D4192F16061720694`
Signature fingerprint (next to "Original copy" on the About page): `5FE5-D786-0B89-A56E`

### New
- **Referral:** The free version now allows 10 changes at a time (was 15). Bring a friend to our Discord and you both get +10 (20 in total). The code is machine-bound, does not expire, and is not Pro.
- **App uninstaller:** Runs the program's own uninstaller, then finds leftover folders and registry keys whose name exactly matches. Leftovers are not deleted: folders are moved to a backup folder and keys exported as .reg, and everything can be restored.
- **One-click Boost:** Turns on Game Mode, turns off Game DVR background recording and closes the programs on your list with your approval. The settings can be undone. Memory freeing, clipboard clearing and stopping services are deliberately not included (no measured benefit, or risk).
- **Display layout:** Drag and drop multiple monitors in the diagram; they snap to edges like in Windows and cannot overlap. Changes use the 15-second confirmation and can be undone.
- **In-game settings:** The Games page lists the settings to look for in any game (Reflex, FPS limit, V-Sync, upscaling, etc.) with an evidence badge and source. No per-game numbers: there is no verified source. Known NVIDIA Reflex support is shown.
- **About page:** Maker and contact are in one card (including the support email); useful links moved to the Games page.

### Changed
- **VRR / G-SYNC / FreeSync** is now labeled "disputed": there is no controlled measurement of its effect on latency in competitive games. It is not pre-selected in the "game" profile and is not in recommendations.

### Good to know
- The new features are covered by tests (396), but have not been tried by hand on a real PC yet. Display dragging and the uninstaller change the system; be careful on first use, everything is undoable.
- Windows SmartScreen may show an "unknown publisher" warning (no paid code-signing certificate). You can verify the zip's SHA-256 against the value above.
- Forevermore does not connect to the internet by default and has no telemetry.
