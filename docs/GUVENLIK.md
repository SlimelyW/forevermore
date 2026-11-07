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

## "Windows varsayılanına döndür" (`app/engine/varsayilan.py`, 7 Kasım 2026)

Başka bir programın daha önce uyguladığı zararlı/placebo ayar taramada bulunursa:
- Anahtarlı ayarlar (PLC-003/004/005/006/007/015/016/017): Özet'teki düğme ayarı kapatır; katalogdaki "kapalı" değerleri
  Windows varsayılanıdır. Uygulamanın kendi yedeği varsa yedeğe döner (düğme o zaman "Çöz" der).
- Yalnızca bilgi olanlarda düğme YALNIZCA varsayılanı kesin bilinen ayarda çıkar: PLC-018 (csrss.exe
  `IFEO\csrss.exe\PerfOptions`; temiz Windows'ta bu anahtar yoktur). Anahtarda belgeli üç değer
  (CpuPriorityClass, IoPriority, PagePriority) dışında değer, alt anahtar ya da DWORD/metin dışı tür varsa düğme çalışmaz
  (yedek hepsini geri getiremez); `csrss.exe` anahtarının kendisine dokunulmaz.
- Akış: tek satır önizleme + Vazgeç → `apply_custom` (yönetici şart, geri yükleme noktası, değerler yedeklenir,
  anahtar .reg olarak da dışa aktarılır) → Değişiklikler'de "Eski haline getir" değerleri geri yazar → yalnız bu madde yeniden okunur.
- PLC-021 (Kubilay onayıyla, 7 Kasım): yalnızca `wuauserv` "Devre dışı" ise başlangıç türü "El ile" (Windows varsayılanı)
  yazılır; servis başlatılmaz/durdurulmaz, Update ilkelerine, UsoSvc/WaaSMedicSvc'ye dokunulmaz. Servis yöneticisi ekranında
  wuauserv yine kilitli (orada kapatılamaz). Geri alma eski "Devre dışı"yı geri yazar.
- Düğme yok, tek satır elle yönerge: PLC-008 (sayfa dosyasını "sistem yönetsin" yapacak güvenilir yazma yolu yok),
  PLC-020 (Defender kartına "Ayara git").
- Toplu "hepsini düzelt" yoktur; Hone vb. listelerden madde alınmadı, yalnızca kendi kataloğumuz.

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
- **Oyun sırasında ayarları ve oyun izleyici KALDIRILDI (7 Kasım 2026):** çalışan oyunla otomatik uygulama/geri alma
  yok. Eski sürümün bıraktığı `oyun_oturumu.json` günlüğü hâlâ açılışta ve "Kaldırmaya hazırla"da geri alınır
  (`runtime.GameSession.recover`; servisler, Steam önceliği, güç planı, bildirimler).
- **Anti-cheat:** ayarlar yalnızca oyunun kendi exe'sine yazılır; anti-cheat ve başlatıcı süreçleri eklenemez ve hiç
  açılmaz. "Gerçek zamanlı" öncelik yok.
- **Oyun algılama** (`runtime.GameDetector`): yalnızca Canlı FPS veya oyun oturumu kaydı açıkken ve exe'si bilinen oyun
  varken 2 saniyede bir süreç listesine bakar (yaklaşık 7 ms); hiçbir ayar uygulamaz, yalnızca bu ikisini başlatıp bitirir.

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

## Kullanıcı presetleri ve içe aktarma (`app/engine/user_presets.py`)

Preset = ad + ayar kimlikleri. Değer, kayıt defteri yolu ya da komut taşımaz. Dışarıdan gelen bir dosya (kötü niyetli olsa bile)
yalnızca katalogdaki güvenli bir ayarın listede işaretlenmesini sağlayabilir; uygulama kullanıcının tıklamasıyla ve her zamanki
yoldan (onay pencereleri, geri yükleme noktası, yedek, geri alma) yapılır.

| Girdi | Savunma |
|---|---|
| Dosya boyutu / iç içe JSON | En çok 64 KB; aşırı iç içe yapı hata verir (çökmez) |
| Biçim | İşaret alanı "Forevermore preset" ve sürüm 1 şart; tür denetimi, en çok 100 kimlik |
| Kimlikler | `AAA-000` biçimi + katalogda var + SWITCH + yasaklı liste dışı + placebo/zararlı değil; olmayanlar atılır ve sayısı gösterilir |
| Ad | Denetim ve yön değiştiren karakterler ve `<` `>` silinir, 40 karakter, düz metin gösterilir; aynı ad varsa "(2)" eklenir (üzerine yazılmaz) |
| Preset kimliği | Dosyadan alınmaz, uygulama üretir |
| "Dikkatli" ayar | Preset'te bile hiçbir zaman işaretli gelmez ve ayrıca onay ister |
| Kendiliğinden uygulama | Yok: içe aktarma yalnızca listeye ekler |

- Sınırlar: en çok 20 preset. Preset dosyası kullanıcı klasöründedir (`kullanici_presetleri.json`); bozuksa boş liste açılır.
- Bilinen sınır: bir preset, ayar kimliklerini bir araya getirir; kimliklerin her biri tek başına zaten uygulamada bulunan güvenli bir ayardır.

## Temizleyiciler (`app/engine/cleaners.py`, Temizlik sayfası)

Hiçbir şey SİLİNMEZ: bilinen önbellek/döküm öğeleri korumalı yedek klasörüne taşınır ve Uygulama kaldırıcı > Yedekler'den geri
yüklenir (aynı mekanizma: `uninstaller.remove_leftovers/restore`). Arayüz yalnızca temizleyici KİMLİĞİ gönderir; taşınacak öğeler
her seferinde yeniden taranır, kullanıcıdan ya da dosyadan yol alınmaz.

| Temizleyici | Kök (kodda sabit) | Öğeler | Açıksa atlanır |
|---|---|---|---|
| discord | `%APPDATA%\discord` | `Cache`, `Code Cache`, `GPUCache` | discord.exe |
| steam | `%LOCALAPPDATA%\Steam` | `htmlcache` | steam.exe, steamwebhelper.exe |
| kucuk_resim | `%LOCALAPPDATA%\Microsoft\Windows\Explorer` | `thumbcache_*.db` | (Gezgin dosyaları kilitleyebilir: taşınamazsa raporlanır) |
| cokme_dokumu | `%LOCALAPPDATA%\CrashDumps` | `*.dmp` | |
| eski_log | `%LOCALAPPDATA%\Temp` | `*.log`, `*.etl` DOSYALARI, son değişikliği 14 günden eski | |
| son_belgeler | `%APPDATA%\Microsoft\Windows\Recent` | `*.lnk` kısayolları | |

- Öğe, kökün DOĞRUDAN çocuğudur (özyineleme yok); gerçek yolu kök içinde kalmalı; sembolik bağ ve birleşim noktası (junction) atlanır.
- eski_log: klasörlere inilmez (klasör olan eşleşme alınmaz), `Forevermore*` adlı dosyalar hiçbir temizleyiciye girmez; Windows günlükleri (`C:\Windows\Logs`, WER, Olay Günlüğü) kapsam dışı.
- son_belgeler: yalnızca `.lnk`; belgelerin kendisi ve `AutomaticDestinations`/`CustomDestinations` (görev çubuğu sabitleri) dokunulmaz. Bilinen sınır: yedek manifesti kısayol adlarını (belge adlarını) yedek klasöründe tutar; klasör yönetici ACL'li, kullanıcı Yedekler'den kalıcı silebilir.
- Yazı tipi önbelleği BİLEREK yok (Font Cache servisini durdurmak gerekir; Kubilay kararı 8 Kasım 2026).
- Haftalık boyut ölçümü (`app/core/temizlik_olcum.py`, varsayılan KAPALI): Görev Zamanlayıcı'da yönetici OLMAYAN (RunLevel Limited) haftalık görev `--temizlik-olc` çalıştırır; yalnızca `scan()` ile toplam boyut hesaplar, `temizlik_olcum.json`'a tarih/bayt/adet yazar (yol yok), hiçbir şey taşımaz/silmez, ağ yok, bildirim yok. Taşıma her zaman Temizlik sayfasından, onayla. Kaldırma temizliği (`--kaldir`) görevi de siler.
- "Hepsini temizle" ve "Seçilenleri taşı": önce her temizleyici adı + boyutuyla liste ve toplam gösterilir; onay yoksa işlem yok; çalışan programlı ve boş temizleyici atlanır.
- Hesap, oturum, ayar dosyaları (ör. `Local Storage`, `settings.json`, `login.vdf`, `iconcache_*`) kalıpların dışındadır, dokunulmaz.
- Çalışan programı Forevermore kapatmaz; "önce kapatın" der. Kilitli dosya zorlanmaz, hata olarak raporlanır.
- Yedek klasörü korumalıdır (yönetici ister): yönetici olmayan modda düğme kapalıdır.
- Bilinen sınır: kullanıcı profili ile yedek klasörü farklı sürücüdeyse taşıma kopyala+sil olur (kaldırıcıyla aynı); orada kilitli dosya yarım kopya bırakabilir.

## Oyunun ayar dosyası (`app/games/oyun_ayar.py`, Oyunlar > Gelişmiş > Oyun içi ayarlar, 7 Kasım 2026)

Sakla / geri yükle / sıfırla / geri al. Dosyanın İÇİ okunmaz, yorumlanmaz, hiçbir ayar anahtarı yazılmaz: dosya bütün olarak
kopyalanır ya da taşınır. Gerekçe ve kaynaklar: docs/OYUN_ICI_AYAR.md.

| Oyun | Kök (kodda sabit) | Hedef | Sıfırla | Açıksa reddedilir |
|---|---|---|---|---|
| valorant | `%LOCALAPPDATA%\VALORANT\Saved` | `Config` klasörü | var (Riot belgesi) | oyun + Riot Client |
| lol | `%SystemDrive%\Riot Games\League of Legends` | `Config` klasörü | var (Riot belgesi) | oyun, LeagueClient + Riot Client |
| fortnite | `%LOCALAPPDATA%\FortniteGame\Saved\Config\WindowsClient` | `GameUserSettings.ini` | YOK (Epic belgelemiyor) | oyun + Epic Games Launcher |
| r6 | Belgeler (`CSIDL_PERSONAL`, OneDrive'a yönlenmiş olabilir) `\My Games\Rainbow Six - Siege` | `*\GameSettings.ini` (hesap başına) | var (Ubisoft belgesi) | oyun + Ubisoft Connect |

- Motorun `apply_custom`'u KULLANILMAZ (yönetici + geri yükleme noktası + kayıt defteri adımı içindir); Temizleyicilerle aynı
  taşıma yolu kullanılır: mevcut dosya `uninstaller.remove_leftovers` ile korumalı yedek klasörüne TAŞINIR (silinmez). Kartta
  "Son değişikliği geri al" en son taşımayı yerine koyar; o an yerdeki dosya da önce taşındığı için geri almak da geri alınabilir.
  Taşımalar Uygulama kaldırıcı > Yedekler'de "Oyun ayarı: <oyun>" adıyla da görünür.
- Saklanan kopyalar korumalı klasörde (`oyun_ayarlari\<oyun>\<tarih>`), oyun başına en yeni 5 tanesi kalır; daha eskileri
  (yalnızca bizim kopyalarımız) silinir.
- Oyun VEYA başlatıcısı açıksa sakla dahil hiçbir işlem yapılmaz (açık oyun dosyayı yeniden yazar). Süreç adları yapımcı belgesi
  değildir, bilinen exe adlarıdır.
- Arayüz yalnızca oyun kimliği ve kopya adı (`YYYYAAGG-SSDDss`) gönderir. Geri yüklemede manifestteki her yol, dosyalara
  dokunmadan ÖNCE denetlenir: kökün içinde, `..` yok, katalog kalıbına uyuyor, üst klasör bağlantı değil; uymazsa hiçbir şey
  değişmez. Kök altında bağlantı/birleşim noktası (OneDrive yer tutucusu dahil) olan hedef atlanır.
- Yönetici olmayan modda düğmeler kapalıdır (yedek klasörü korumalı). Her işlemden önce tek satır önizleme + onay (sakla hariç:
  hiçbir şey değiştirmez).
- Ortak düzeltme: aynı saniyede iki taşıma aynı yedek oturumuna düşüp eski manifesti eziyordu; `remove_leftovers` artık boş
  bir saniye bulana kadar ilerler (Temizlik ve Kaldırıcı'yı da kapsar).
- Bilinen sınırlar: bulut eşitlemesi (Riot hesabı, Ubisoft, Epic) geri yüklenen dosyanın üstüne yazabilir, doğrulanmadı.
  LoL başka bir sürücüye/klasöre kurulduysa bulunamaz. Standart kullanıcı + ayrı yönetici hesabıyla açılırsa
  `%LOCALAPPDATA%` yönetici hesabının klasörünü gösterir (Temizleyicilerle aynı sınır). Gerçek oyunda DENENMEDİ.

## Oyun oturumu kaydı (`app/games/recorder.py`)

Kullanıcı Ayarlar > Genel'den açarsa (varsayılan KAPALI), oyun algılamanın (`runtime.GameDetector`) bulduğu bir oyun oturumu SÜRERKEN, 5 saniyede bir
kaynak kullanımı örneği alınır. Oyun yokken hiçbir iş parçacığı çalışmaz; Özet'teki canlı izleme ayrıdır ve değişmedi.

| Konu | Durum |
|---|---|
| Saklanan | Yalnızca özet: süre, örnek sayısı, işlemci/ekran kartı/bellek/disk için en düşük-ortalama-en yüksek, %90 üstünde geçen süre, arka planda en çok işlemci kullanan en çok 3 program adı ve ortalaması. Ham örnek tutulmaz |
| Nerede | Bellekte ve `oyun_oturum_gecmisi.json` (kullanıcı klasörü, son 10 oturum, atomik yazım). Ağa hiçbir şey gitmez; rapora/tanılamaya girmez |
| Kişisel veri | Oyun adı, tarih, sayılar ve program adları. Pencere başlığı, dosya yolu, hesap bilgisi yok |
| Uyarı | Açılır pencere/bildirim yok; yalnızca oturum raporunda sakin satırlar |
| Hata | Sayaç okunamazsa kayıt sessizce biter; oyun ve uygulama etkilenmez |
| Bilerek yok | GPU güç sınırı (güvenilir okunabilirlik denenmedi). (Canlı FPS, VRAM satırı ve oyun üstü FPS kutusu sonradan kararla EKLENDİ: aşağıdaki bölümler) |

- Sınır: yalnızca Oyunlar listesinde exe'si seçili oyunlarda çalışır.
- Sınır: oyun alt-tab ile arka plana alınsa da kayıt sürer; rapor toplam süreyi yazar, odakta geçen süreyi ayırmaz.

## Güncelleme denetimi (`app/core/guncelleme.py`, tek seferlik soru)
- Ağa bağlanan TEK kod. `guncelleme_denetle`: `None` (hiç seçilmedi) bağlanmaz; soru `guncelleme_soruldu` bayrağı yoksa değer ne olursa olsun
  (None/True/False) bir kez sorulur (onaydan sonra, pencere açılmadan), cevap bayrağı yazar; değer zaten `True` ise sorulmaz,
  yalnızca bayrak yazılır; `True` → açılışta ve günde en çok bir kez (`denetim_vakti`); `False` → kendiliğinden hiç bağlanmaz.
  Yalnızca açık `True` bağlanır: `None`, pencerenin kapatılması ve önizleme modu "bağlanma" sayılır.
- Eski sürümün yazdığı `false` "hiç seçmedi" ile "kapalı seçti"yi ayırt ettirmediğinden mevcut kullanıcılar da bayrak yoksa
  bir kez sorulur (6 Kasım 2026; önceki "sorulmaz" kararı geri alındı). "Hayır"/pencere kapatma = `false`, ağ çağrısı yok.
- Değişmeyenler: yalnızca GitHub (api.github.com, github.com/<depo>/releases/download), GET, veri/sürüm numarası gönderilmez,
  indirilen paket yapımcı imzasıyla ve sürüm yükselmesiyle doğrulanır. Yeni sürüm bulunursa yalnızca durum çubuğunda tek satır;
  açılır pencere yok, hata sessiz. Test: `tests/test_gizlilik.py`, `tests/test_guncelleme.py`.

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

## Canlı FPS (`app/measure/live_fps.py`, 6 Kasım 2026)

5 Kasım'daki "bilerek yok" kararı Kubilay tarafından geri alındı. Ayarlar > Genel > "Canlı FPS" (varsayılan KAPALI). Yalnızca
oyun algılamanın bulduğu oyun SÜRERKEN ve oyun ekrandayken çalışır; ağa hiçbir şey gitmez.

| Konu | Durum |
|---|---|
| Yöntem | Intel PresentMon (ölçüm sayfasındaki aynı program), tek ETW oturumu (`ForevermoreCanli`), `--process_name <oyun.exe> --output_stdout`. Oyuna enjekte olmaz, oyun sürecine tanıtıcı açmaz, bellek okumaz. CSV boru hattından okunur, DOSYAYA YAZILMAZ |
| Saklanan | Yalnızca özet: en düşük/ortalama/en yüksek saniyelik FPS ve düşüş kayıtları (en çok 20: dakika, süre, önceki/en düşük FPS). Ham kare listesi yok. Kayıt ayarı (`oyun_kaydi`) açıksa yerel geçmişe girer, kapalıysa yalnızca bellekte, "Son oturum" kartında kalır |
| Düşüş uyarısı | Mutlak eşik YOK (FPS sınırı koyanlara yanlış alarm verirdi). FPS, son 30 sn ortalamasının %60'ının altına 5 sn kesintisiz inerse Oyunlar sayfasında sakin tek satır. İlk 30 sn uyarı yok. Eşikler sabit, ayar yok. Açılır pencere/bildirim yok |
| Odak | Oyun ekranda değilken (3 sn tolerans) PresentMon DURDURULUR, dönünce yeniden başlar; arkada üretilen kareler sayılmaz |
| Anti-cheat | (7 Kas, Kubilay kararı) Anti-cheat'li (algılanan) oyunda canlı FPS HİÇ çalışmaz; oyun başına izin (`canli_fps_izinli`) KALDIRILDI, eski dosyalardaki izin listesi yok sayılır. Ayar açıksa oyun sayfasında tek satır neden. Eski not: Vanguard/EAC/BattlEye'nin ETW dinlemeye tepkisi hakkında resmi açıklama BULUNAMADI ve ban anekdotu da bulunamadı; "güvenli" denmez. 7 Kasım GERÇEK GÖZLEM: The First Descendant (EAC + Nexon BlackCipher) canlı FPS açıkken iki kez ~25-30 sn'de kapandı, kapalıyken açık kaldı (Kubilay denedi; docs/CANLI_FPS_COKME.md). BlackCipher artık algılanır (`ANTI_CHEAT_MARKERS`). docs/ANTI_CHEAT_ARASTIRMA.md yalnızca oyun sürecine çekirdek/öncelik ayarını kapsar, bununla çelişmez ama bunu kapsamaz |
| İzin | PresentMon README'sine göre yönetici ŞART DEĞİL, "Performance Log Users" üyeliği yeterli; olmazsa süreç hemen kapanır, satır "başlatılamadı" der ve tekrar denenmez. Uygulama grubu DEĞİŞTİRMEZ |
| Hata | (7 Kas, TEST_FAZI C1/C4) Başlamazsa, alt-tab dönüşünde başlamazsa, çıktı okunamazsa veya başlatma hata verirse: ayar KAPANIR, tek satır "başlatılamadı ve kapatıldı", ayrıntı log'da; uygulama durmaz. İnceleme: docs/CANLI_FPS_COKME.md |
| Dürüstlük | Kare gelmezse "ölçüm alınamıyor" yazar, 0 FPS DEMEZ (çok sayıda açık ETW oturumunda PresentMon sessizce olay vermeyebilir: PresentMon issue #423) |
| Yük | Sürekli ETW dinleme yükü gerçek oyunda ÖLÇÜLMEDİ (Intel 2.6.0 için yükü azalttığını söylüyor, bağımsız ölçüm bulunamadı). Oyun ekranda değilken çalışmaz |

## Oyun üstü FPS kutusu (`app/ui/fps_widget.py`, 7 Kasım 2026)

Ayarlar > Genel > "Oyun üstü FPS kutusu" (`fps_widget`, varsayılan KAPALI). Yalnızca canlı FPS sürerken ve oyun ekrandayken görünür; ağ, dosya, ses, bildirim, ekran görüntüsü yok.

| Konu | Durum |
|---|---|
| Yöntem | Kendi sürecimizde ayrı, üstte duran, tıklanamayan, odak almayan küçük pencere (`WS_EX_TRANSPARENT`, `WS_EX_NOACTIVATE`, `WS_EX_TOPMOST`). Oyuna DLL enjekte edilmez, oyun belleği okunmaz, oyun penceresine kanca takılmaz, oyuna tanıtıcı açılmaz |
| Veri | Yeni ölçüm kaynağı YOK: canlı FPS'in anlık durumu ve (`vram_uyari` açıksa) mevcut ekran kartı belleği okuyucusu. Hiçbir yere yazılmaz. Kare gelmiyorsa "— FPS", 0 FPS demez |
| Anti-cheat | Algılanan oyunda HİÇ görünmez (canlı FPS orada çalışmadığı için); oyun başına izin (`fps_widget_izinli`) 7 Kasım'da KALDIRILDI. Oyun sayfasında tek satır "Canlı FPS ve FPS kutusu bu oyunda kapalı…" |
| Anti-cheat tepkisi | **Belgesiz.** Vanguard, EAC, BattlEye gibi sistemlerin üstte duran ayrı pencerelere tepkisi için resmi açıklama aranmadı ve varsayılmadı; docs/ANTI_CHEAT_ARASTIRMA.md bu konuyu kapsamıyor. Ban kaydı da aranmadı. Bu yüzden "güvenli" denmez, varsayılan kapalıdır |
| Alt+H | `RegisterHotKey` yalnızca kutu o oyun için açıkken; kutu kapanınca bırakılır. Tuş dinleme kancası YOK. Başka program kullanıyorsa sessizce vazgeçilir, kutu çalışır. Kutu açıkken Alt+H oyuna gitmez |
| Sınır | Özel tam ekranda görünmez (yalnızca pencereli/kenarlıksız); bunu aşmak oyuna dokunmayı gerektirir, yapılmaz. Yalnızca ana ekranda çizilir. Canlı FPS gibi yalnızca Oyunlar listesindeki (exe'si seçili) oyunlarda çalışır |
| Doğrulama | Gerçek Windows penceresinde EKRANA ÇİZMEDEN denetlendi: pencere stilleri, katman opaklığı, kısayol kaydı, çakışma, kısayol iletisi, bırakma. Gerçek oyunda, tuşa basarak ve kutu görünürken DENENMEDİ (docs/EL_TESTLERI.md) |

## Canlı süreç listesi (`app/games/canli_surec.py`, 7 Kasım 2026)

Oyunlar sayfasında oyun sürerken "Uygulamalar" / "Arka plan" grupları: toplam CPU% ve en çok kullanan 5 program, 2 sn'de bir.
Ayrı bir ayar YOK: "Oyun oturumu kaydı" açıksa görünür, kapalıysa hiç çalışmaz. Salt okunur (`\Process(*)\% Processor Time` PDH sayacı +
`presentmon.Desktop` ile pencereli süreç adları); ağ yok, sistem ayarı yazma yok, DOSYAYA/GÜNLÜĞE YAZILMAZ (yalnızca bellekte son sonuç; durunca silinir).
Örnekleme yalnızca oyun sürerken VE Oyunlar sayfası görünürken VE pencere küçültülmemişken; koşul bozulunca iş parçacığı ve PDH sorgusu kapanır.
Oyun ve Forevermore (forevermore/python/pythonw) listeden çıkarılır; anti-cheat'li oyunda da çalışır (yalnızca kendi masaüstü sayaçlarını okur,
oyun sürecine dokunmaz), ama bu davranış gerçek anti-cheat'le denenmedi. Yük (Process(*) sorgusunun oyun üzerindeki etkisi) ÖLÇÜLMEDİ.

## Bakım araçları (`app/engine/bakim.py`, `app/ui/bakim_kartlari.py`, 9 Kasım 2026)
Temizlik sayfasının altında iki araç; ikisi de Windows'un KENDİ aracını çalıştırır, ayar yazmaz, araç indirmez/gömmez, ağ yok.
- **Sistem dosyalarını onar:** `System32\sfc.exe /scannow`, ardından `System32\Dism.exe /Online /Cleanup-Image /RestoreHealth`. Yönetici ister
  (yönetici değilse düğme kapalı, motor da çalıştırmaz), 10-30 dk sürebilir. Başlamadan önce süre uyarısı + mevcut geri yükleme noktası akışı
  (`ensure_prepared`; kullanıcı "atla" derse atlanır). İptal çalışan süreci sonlandırır; onarım yarım kalabilir, arayüz bunu söyler.
- **Sürücüyü optimize et:** `Optimize-Volume -ReTrim` (SSD) / `-Defrag` (HDD). Tür her seferinde `Get-PhysicalDisk` ile okunur; türü bilinmeyen
  (ör. sanal disk) sürücü ATLANIR, SSD'ye birleştirme hiç gönderilmez. Kartta "Windows bunu genellikle haftalık yapar, fark küçük olabilir" yazar.
- Komutlar kodda sabit, kabuk yok (liste olarak Popen, System32 tam yol, temiz PSModulePath). Arayüz yalnızca sürücü HARFİ gönderir; harf, her
  seferinde yeniden okunan sabit sürücü listesinde yoksa çalıştırılmaz. Değişiklikler geçmişine yalnızca sonuç kodu (`bakim` işlemi) yazılır.
- Ham çıktı yalnızca bellekte, "Ayrıntı" altında (dosyaya/günlüğe yazılmaz). sfc çıktısı borulandığında UTF-16'dır; çözülür.
- Sonuç tanıma metne dayanır (İngilizce ve Türkçe cümleler). Tanınmazsa "Sonuç anlaşılamadı" denir, tahmin edilmez. DISM sonucu çıkış koduyla
  (dilden bağımsız). Türkçe cümleler Windows'tan alınmadı, hatırlanan metinlerdir: gerçek Türkçe Windows'ta DENENMEDİ.
- Uzun iş `serial=False` havuzunda çalışır (Değişiklikler sırası 30 dk beklemez). Uygulama çalışırken kapatılırsa sfc/DISM alt süreci kendi
  başına bitebilir (Windows aracı; Forevermore durdurmaz).
- Yapılmayanlar: DISM `/StartComponentCleanup`/`/ResetBase` (geri alınamaz), `chkdsk`, otomatik zamanlama, sfc'yi DISM'den sonra yeniden çalıştırma
  (sonuç "tekrar çalıştır" olarak söylenir).
