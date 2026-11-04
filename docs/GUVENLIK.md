# Ayar motoru ve güvenlik katmanı (ADIM 3)

## Bir ayar açılınca sırasıyla ne olur

1. **Kontroller**
   - Ayar bir SWITCH mi ve yasaklı beş ayardan (Defender kapatma, Windows Update kalıcı
     kapatma, sayfa dosyası kapatma, Realtime öncelik, agresif debloat) biri değil mi?
     (Defender'ın yalnızca gerçek zamanlı koruması, kullanıcı isteğiyle Sistem menüsündeki ayrı bir
     karttan iki aşamalı uyarıyla kapatılabilir; Kurcalama korumasına uygulama dokunmaz.)
     Arayüzde bir hata olsa bile bu kural motorun içinde uygulanır.
   - Bu bilgisayara uygun mu? Windows sürümü, laptop/masaüstü, ekran kartı ve koşullar
     (HDD var mı vb.) kontrol edilir.
   - Uygulama yönetici olarak mı çalışıyor?
   - Onay: "dikkatli" ayar açılırken tek onay; "riskli" ayar açılırken **ve** kapatılırken
     iki ayrı ekran (1: ne yapar / açılırsa-kapatılırsa ne olur / dikkat / kimler dokunmamalı,
     2: "Ne yaptığınızdan emin olup ayarı uygulayın"). Motor da onaysız riskli değişikliği reddeder.
   - "Yalnızca kapatılabilir" ayarlar uygulama tarafından açılamaz.
2. **Geri yükleme noktası.** Oturumdaki ilk değişiklikten önce bir kez denenir.
   - Windows 24 saatte birden fazla nokta oluşturmaz; son 24 saatte bir nokta varsa o kullanılır
     ve tarihi gösterilir.
   - Nokta oluşturulamazsa (ör. Sistem Koruması kapalı) kullanıcı **açıkça kabul etmeden**
     hiçbir şey değiştirilmez.
3. **Yedek.** Dokunulacak her değerin o anki hâli, yazmadan **önce**
   `%ProgramData%\Forevermore\<SID>\backups\yedekler.json` dosyasına yazılır.
   - Klasöre yalnızca Yöneticiler/SYSTEM yazabilir, hesabın kendisi yalnızca okur (`app/core/guvenli_klasor.py`). Klasör
     ACL'siyle tek adımda oluşturulur; önceden açılmış, sahibi güvenilmeyen veya junction olan klasör kenara alınır.
     Eski `%LOCALAPPDATA%\Forevermore\backups` ilk yönetici açılışında bir kez kopyalanır ve `backups.tasindi` olur.
     Kaldırıcı yedekleri (`kaldirici_yedek`) de aynı yere taşınır.
   - Kaldırıcı: HKCU'daki kaldırma komutlarını her program yazabildiği için bunlar yönetici yetkisi almaz; normal kullanıcı
     olarak başlar, başlatılamazsa yönetici yetkisiyle denenmez (`admin.run_unelevated`).
   - Registry anahtarları ayrıca `.reg` dosyası olarak `backups\reg\` klasörüne aktarılır.
   - `yedekler.json` DPAPI anahtarıyla HMAC-SHA256 imzalıdır; imza tutmazsa dosya yüklenmez, `yedekler.bozuk.json`
     olarak saklanır ve üstte uyarı çıkar. Geri almadan önce adımların konumu şemadan geçirilir (docs/SECURITY.md).
4. **Uygulama.** Adımlar sırayla yazılır. Zaten istenen durumda olan adım atlanır.
   - Bir adım başarısız olursa o ana kadar yazılanlar **geri alınır**; ayar yarım kalmaz.
5. **Doğrulama.** Değer yeniden okunur; tutmuyorsa kullanıcıya "yeniden başlattıktan sonra
   kontrol edin" uyarısı gösterilir.
6. **Kayıt.** Her işlem `logs\forevermore.log` ve `backups\islem_gecmisi.jsonl` dosyalarına yazılır.

## Eski haline getirme

- Her ayar tek tıkla, uygulamanın **ilk dokunduğu andaki** hâline döner. Ayar birkaç kez
  açılıp kapatılsa bile ilk yedek korunur.
- "Tümünü eski haline getir", uygulamanın değiştirdiği her şeyi en yeniden eskiye geri alır.
- Geri alma, yalnızca bu ayarın değiştirdiği kısmı geri yazar:
  - DirectX ayar satırındaki diğer parçalara dokunmaz.
  - Erişilebilirlik bayraklarının diğer bitlerine dokunmaz.
  - Uygulamanın oluşturduğu boş registry anahtarlarını da siler.
- Geri alma, veri dosyası sonradan değişse bile çalışır; gereken her bilgi yedek dosyasındadır.
- Geri almak için geri yükleme noktası gerekmez.
- Riskli ayarı tek tek geri alırken de iki uyarı ekranı gösterilir (seviye, yedek alınırken
  kaydedilir). "Tümünü eski haline getir" tek, toplu onay alır.
- Tek seferlik eylemler (geçici dosya / Prefetch temizliği) **geri alınamaz**; açıkça sorulur
  ve yalnızca işlem geçmişine yazılır (Değişiklikler sayfasında ayrı listelenir).

## Özet sayfasındaki "Çöz" düğmesi

"Çöz" kullanıcıyı ayara yönlendirmez; ilgili ayarı uygulama kendisi değiştirir
(`app/engine/fixes.py`). Her çözüm normal ayar akışından geçer: onay seviyesi,
geri yükleme noktası, yedek, Değişiklikler kaydı ve tek tıkla geri alma. Tek istisna
geçici dosya temizliğidir; geri alınamaz olduğu ayrıca sorulur. Donanım/BIOS gerektiren
bulgularda (tek kanal RAM, HDD, XMP, disk sağlığı, olay kayıtları) "Çöz" yoktur.

## Yöneticiler (başlangıç, servisler, MSI, aygıt güç yönetimi)

Autoruns, MSI aracı veya benzeri program gömülmez (`app/engine/managers.py`). Her öğe ayrı
yedeklenir (`Engine.apply_custom`) ve Değişiklikler sayfasında kendi adıyla görünür:

- **Başlangıç uygulamaları:** Görev Yöneticisi ile aynı yöntem (StartupApproved değeri); program silinmez.
- **Zamanlanmış görevler:** yalnızca Microsoft dışı, oturum açılışında/önyüklemede çalışanlar.
- **Servisler:** başlangıç türü değişir; kritik Windows servisleri ve anti-cheat servisleri
  (vgc, vgk, BEService, EasyAntiCheat...) kilitlidir. Windows servisinde ek onay sorulur.
- **MSI modu:** riskli; açarken ve kapatırken iki onay ekranı, yeniden başlatma gerekir. Önce
  aygıt anahtarı `.reg` olarak `backups\reg` klasörüne aktarılır (Güvenli Mod'da elle geri yükleme için).
- **Aygıt güç yönetimi:** `MSPower_DeviceEnable` (Aygıt Yöneticisi > Güç Yönetimi kutucuğu).

Laptopta yalnızca güç planı değeri yazan ayarlar "Prizde" ve "Pilde" olarak iki ayrı düğmedir;
her biri ayrı yedeklenir (ör. `PWR-003@pil`).

## Oyunlar menüsü

- **Kalıcı ayarlar** (öncelik: IFEO PerfOptions, GPU tercihi: DirectX UserGpuPreferences, tam ekran
  optimizasyonları: AppCompatFlags\Layers) kaydedince yazılır, her biri ayrı yedeklenir ve
  Değişiklikler'den geri alınır. Uyumluluk bayraklarındaki diğer bayraklara dokunulmaz.
- **Oyun sırasında ayarları** yalnızca uygulama açıkken uygulanır; oyun kapanınca geri alınır.
  Önce `oyun_oturumu.json` günlüğüne yazılır; uygulama oyun sırasında kapanır/çökerse bir sonraki
  açılışta günlükteki her şey geri alınır. Yalnızca o anda çalışan servisler durdurulur ve sonra
  yeniden başlatılır.
- **Anti-cheat:** ayarlar yalnızca oyunun kendi sürecine uygulanır; anti-cheat ve başlatıcı süreçleri
  eklenemez ve hiç açılmaz. Erişim reddedilirse ayar atlanır ve söylenir. "Gerçek zamanlı" öncelik yok.
- İzleyici 2 saniyede bir süreç listesine bakar (yaklaşık 7 ms); yalnızca oyun sırasında ayarı olan
  oyun varsa çalışır.

## Ekstra ayarlar

- **Tepsi** (varsayılan kapalı): Qt'nin kendi tepsi bileşeni; pencere kapatılınca uygulama tepside
  çalışır, "Çıkış" ile tamamen kapanır. Ek kütüphane yok.
- **Windows'la başlatma** (varsayılan kapalı): oturum açılışında en yüksek yetkiyle çalışan bir
  zamanlanmış görev ("Forevermore - oturum acilisi"); uygulama `--tepside` ile pencere açmadan başlar.
  Kapatınca görev silinir. Kullanıcı adı uygulama tarafından okunmaz (`$env:USERNAME` PowerShell'de).
- **İçe/dışa aktarma:** yalnızca uygulama ayarları ve oyun profilleri; bilinmeyen anahtarlar ve
  anti-cheat/başlatıcı süreçleri alınmaz; kalıcı Windows ayarları içe aktarırken yazılmaz.
- **Bilgi:** iletişim ve bağlantılar `data/hakkinda.json` dosyasından gelir. Uygulama hiçbir yere
  kendiliğinden bağlanmaz; bağlantılar yalnızca kullanıcı tıklarsa varsayılan tarayıcıda açılır.

## Kaldırma

Ekstra ayarlar > "Kaldırmaya hazırla" veya `Forevermore.exe --kaldir`: "Windows'la başlat" görevini
siler, yarım kalan oyun oturumunu geri alır; istenirse tüm değişiklikleri eski haline getirir ve
uygulama verilerini siler. Geri alınmamış değişiklik varken veriler silinmez (yedekler kaybolmasın).

## Önce / Sonra ölçümü

- Sistem ölçümü salt okunurdur: olay günlüğü (açılış süresi), başlangıç öğeleri, servisler ve
  30–120 sn boyunca boştaki işlemci/bellek.
- Açılış süresi: yönetici izniyle Diagnostics-Performance olay 100 (Windows'un ölçtüğü süre);
  bulunamazsa çekirdek başlangıcı (Kernel-General 12) ile oturum açma (Winlogon 7001) arası.
  İkincisi şifre ekranında beklenen süreyi de içerir; ölçümler hep aynı şekilde (ör. yeniden
  başlat ve hemen giriş yap) alınmalıdır. Hızlı başlangıç açıkken "Kapat" tam açılış değildir.
- Oyun ölçümü: Intel PresentMon (MIT) ayrı bir program olarak çalıştırılır; oyuna enjekte olmaz,
  Windows'un ETW kayıtlarını okur. Kayıt bitince CSV dosyası okunur ve geçici klasörde kalır.
- Sonuçlar yalnızca `%LOCALAPPDATA%\Forevermore\olcumler.json` dosyasında; rapor isteğe bağlı olarak
  `reports` klasörüne düz metin yazılır.

## Canlı izleme

Özet sayfası açıkken saniyede bir Windows performans sayaçları (PDH, `pdh.dll`) ve
`GlobalMemoryStatusEx` okunur (`app/scan/live.py`); PowerShell veya ek kütüphane yoktur.
Sayfa gizlenince veya pencere küçültülünce durur. Değerler ve süreç adları yalnızca ekranda
gösterilir; dosyaya yazılmaz, hiçbir yere gönderilmez.

## Başlangıç onayı

İlk açılışta, sürüm veya onay metni değiştiğinde `lang/baslangic_onayi.tr.txt` gösterilir.
Kabul edilmezse uygulama açılmaz. Kabul tarihi, sürüm ve metnin özeti yalnızca bu
bilgisayarda `%LOCALAPPDATA%\Forevermore\onay.json` dosyasında tutulur.
**Satış öncesi metin ve akış bir avukata kontrol ettirilmelidir** (bkz. `app/core/consent.py`).

## Uygulama hiç açılmazsa (elle kurtarma)

1. **Sistem Geri Yükleme:** Başlat'a `rstrui` yaz → "Forevermore - degisiklik oncesi" noktasını seç.
2. **.reg yedekleri:** `%ProgramData%\Forevermore\<SID>\backups\reg\` klasöründeki ilgili dosyaya
   çift tıkla. Bu yöntem değerleri geri yazar ama uygulamanın oluşturduğu yeni değerleri silmez;
   tam geri dönüş için 1. yol daha iyidir.

## Hazır profiller (`data/profiller.json`)

| Profil | İçerik |
|---|---|
| Güvenli | Herkes için zararsız temel ayarlar (8 ayar) |
| Oyun | Güvenli + oyun gecikmesi ve akıcılığı (11 ayar daha; tartışmalı olanlar işaretsiz gelir) |
| Dikkatli kullanıcı | Oyun + "dikkatli" ayarlar (8 ayar). Hepsi **işaretsiz** gelir, her biri ayrı onayla açılır |

- Bilgisayara uymayan ayarlar profil ekranında hiç görünmez.
- "Dikkatli" bir ayarı profilde varsayılan seçili yapmaya çalışırsan kod bunu reddeder.

## Dürüst notlar: bilerek yapılmayanlar ve emin olmadıklarım

- **Hesap farkı.** Standart kullanıcı hesabında UAC penceresine **başka** bir yöneticinin
  şifresi girilirse uygulama o hesap adına çalışır. Bu durumda kullanıcıya ait (HKCU) ayarlar
  yanlış hesabı değiştireceği için gizlenir.
- **Ses geliştirmeleri.** Microsoft'un belgelediği API, bu bilgisayarda Windows'un kendi
  düğmesinin değerini göstermedi. Bu yüzden Windows'un kullandığı registry değeri yazılıyor ve
  ses servisi yeniden başlatılıyor. Test listesinde mutlaka denenmeli.
- **Güç planı varsayılanı.** Özel (kendi oluşturduğun) bir güç planında, yedeği olmayan bir
  güç ayarı "plan varsayılanına" döndürülemez. Bu durumda ayar değiştirilmez ve sebebi gösterilir.
- **Geri yükleme noktası.** Bu sınır kaldırılmaz, çünkü bu da bir sistem ayarını değiştirmek
  demektir.
  - Windows 24 saatte birden fazla nokta oluşturmaz.
  - Uygulama Sistem Korumasını kendiliğinden açmaz.
- **Test durumu.** Değişiklik yapan kodların hiçbiri gerçek Windows üzerinde **çalıştırılmadı**:
  - Mantıkları 24 testte, sahte bir Windows üzerinde denendi.
  - Bunlardan biri, veritabanındaki her switch'i açıp geri alınca sistemin birebir aynı kaldığını kontrol ediyor.
  - Gerçek bilgisayarda yalnızca okuma kısmı çalıştırıldı (`tests\durum_okuma.py`; yazma girişimi: yok).
