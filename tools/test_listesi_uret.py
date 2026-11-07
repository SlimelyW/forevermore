"""docs/TEST_KONTROL_LISTESI.md dosyasını üretir.

Genel bölümler bu dosyada yazılıdır; "her switch için" tablosu
data/tweaks_app.json'dan otomatik oluşturulur, böylece veri değişince
liste de güncel kalır.

Çalıştırma:  py -3.12 tools\\test_listesi_uret.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "data" / "tweaks_app.json").read_text(encoding="utf-8"))
OUT = ROOT / "docs" / "TEST_KONTROL_LISTESI.md"

RESTART_TEXT = {"yok": "—", "uygulama": "oyunu/uygulamayı yeniden aç", "oturum": "oturumu kapat-aç",
                "bilgisayar": "yeniden başlat", "gezgin": "Gezgin'i yeniden başlat",
                "ses_servisi": "ses birkaç sn kesilir", "durumsal": "gerekebilir"}

HEADER = """# Test kontrol listesi (sürüm 2.2.0 — Revizyon 2 ve 3 dahil)

> **Önemli:** Bu projedeki kod, ayar DEĞİŞTİREN hiçbir işlemde gerçek Windows üzerinde
> çalıştırılmadı. Aşağıdaki testleri **önce sanal makinede**, sonra kendi bilgisayarında
> **geri yükleme noktası alarak** yap. Her satırı işaretle (☐ → ☑). Bir şey ters giderse
> `%LOCALAPPDATA%\\Forevermore\\logs\\forevermore.log` ve kaydettiğin raporu bana gönder.

Bu dosya `tools/test_listesi_uret.py` ile üretilir; elle düzenleme, betiği güncelle.

## 0. Hazırlık

- ☐ **Sanal makine programı kur.** Ücretsiz seçenekler: VirtualBox veya VMware Workstation.
  Lisans koşulları değişebiliyor; indirirken sitesinden kontrol et. Hyper-V'yi bu bilgisayarda
  kapalı tuttuğun için Hyper-V yerine bunlardan biri daha uygun.
- ☐ **Windows 11 ve Windows 10 ISO'larını indir** (Microsoft'un resmi indirme sayfasından),
  ikisini ayrı sanal makineye kur.
  - Etkinleştirilmemiş Windows test için yeterli.
  - **Ama:** Etkinleştirilmemiş Windows'ta Ayarlar > Kişiselleştirme kilitlidir. Şeffaflık gibi
    ayarları Ayarlar penceresinden doğrulayamazsın; uygulamanın kendi durum göstergesine ve
    `regedit`'e bak.
- ☐ **Sanal makinede her testten önce "anlık görüntü" (snapshot) al.** Sorun olursa tek tıkla dönersin.
- ☐ **Sanal makinenin sınırlarını bil:** gerçek ekran kartı, pil ve Wi-Fi yoktur. NVIDIA/AMD,
  laptop ve Wi-Fi ayarları orada gizli görünür; bunları kendi laptopunda test et.
- ☐ **Kendi bilgisayarında test etmeden önce:** Başlat'a `rstrui` yaz → elle bir geri yükleme
  noktası oluştur (Sistem Koruması > Oluştur). Uygulama da kendisi oluşturur, ama ikisi bir arada
  daha güvenli.
- ☐ **.exe'yi derle:** proje klasöründe `derle.bat`. Sonda "Paket kontrolü" satırlarının hepsi
  OK olmalı.

## 1. Açılış ve yönetici izni

- ☐ `dist\\Forevermore.zip` dosyasını temiz sanal makineye kopyala, aç, içindeki `Forevermore.exe`'ye çift tıkla. İmzasız olduğu için SmartScreen uyarısı
  çıkması **normal**: "Ek bilgi" > "Yine de çalıştır". (Satış öncesi çözümü: `SATIS_NOTLARI.md`.)
- ☐ UAC penceresinde **Evet** → uygulama açılır, üstte uyarı şeridi yoktur.
- ☐ Kapat, tekrar aç, UAC'de **Hayır** → uygulama **salt okunur** açılır. Üstte turuncu şerit
  görünür, switch'ler gridir, tarama ve rehberler çalışır.
- ☐ Kısayol oluştur, hedefin sonuna ` --onizleme` ekle → önizleme modu açılır ve hiçbir ayar
  değiştirilemez.
- ☐ `%LOCALAPPDATA%\\Forevermore\\logs\\forevermore.log` dosyası oluştu mu?
- ☐ **Farklı hesap senaryosu:**
  - Sanal makinede **standart** bir kullanıcı hesabı aç ve uygulamayı o hesapla çalıştır.
  - UAC penceresine yönetici şifresini gir.
  - Kullanıcıya ait ayarlar (fare, klavye, Görsel/QoL) **gizlenmeli** ve nedeni "farklı hesap" olmalı.

## 2. Görsel kontrol (arayüzü ilk kez gözle görme)

- ☐ **Pencere ve menü**
  - ☐ Pencere hatasız açılıyor; sol menüde 15 giriş var (Özet, Hazır profiller, 11 kategori,
    Değişiklikler, Rapor).
  - ☐ Türkçe karakterler (ğ ü ş ı ö ç İ Ğ Ü Ş Ö Ç) her yerde doğru görünüyor.
- ☐ **Görünüm ayarları**
  - ☐ **Açık tema:** yazılar okunuyor. **Koyu tema:** yazılar okunuyor
    (Windows Ayarlar > Kişiselleştirme > Renkler > Mod).
  - ☐ Ekran ölçeği %100, %125, %150'de yazılar kesilmiyor, düğmeler taşmıyor
    (Ayarlar > Sistem > Ekran > Ölçek).
  - ☐ Pencereyi en küçük boyuta getir: içerik kayboluyor mu, kaydırma çubuğu çıkıyor mu?
- ☐ **Sayfa içerikleri**
  - ☐ Özet sayfası: kartlar iki sütun, bulgular renkli (kırmızı/turuncu/mavi/yeşil),
    "Ayara git" doğru menüye gidip ilgili satırı sarıyla vurguluyor.
  - ☐ Her kategori sayfasında "Etki" etiketi, (i) düğmesi ve switch aynı hizada.
  - ☐ (i) penceresi: tüm bölümler okunuyor, kaydırılabiliyor, "Kimler DOKUNMAMALI?" kutusu
    turuncu ve belirgin.
  - ☐ Dikkatli ayar onay penceresi: "Okudum, anladım" işaretlenmeden "Onayla ve aç" gri kalıyor.
  - ☐ Ses sayfasında 48 kHz üstü cihaz turuncu yazıyla görünüyor.
  - ☐ Mouse ve Klavye sayfasında polling rate açıklaması ve kaydırıcılar düzgün.
  - ☐ Placebo sayfasında 29 kart ve "Diğer menülerdeki" listesi var.
- ☐ **Pencereler ve geri bildirim**
  - ☐ Bekleme pencereleri (geri yükleme noktası, profil) ana pencerenin önünde açılıyor,
    arkada kalmıyor.
  - ☐ Alt durum çubuğunda başarı mesajları yeşil, hatalar kırmızı.
- ☐ Ekran görüntüsü al; garip görünen her şeyi not et.

## 3. Taramanın doğruluğu

- ☐ **Donanım:** Tarama 1 dakikadan kısa sürüyor. İşlemci, RAM (GB, hız), ekran kartı ve sürücü
  sürümü Görev Yöneticisi > Performans ile aynı.
- ☐ **Ekranlar:** Her monitörün çözünürlüğü ve Hz değeri Ayarlar > Ekran > Gelişmiş ekran ile aynı.
- ☐ **Diskler:** SSD/HDD türü ve boş alan Dosya Gezgini > Bu bilgisayar ile aynı.
- ☐ **RAM kanalı:** "çift kanal"/"tek kanal" bilgisi CPU-Z (Memory > Channel #) ile aynı.
- ☐ **XMP:** Bilgi, BIOS'taki durumla uyumlu. Masaüstünde dene; laptopta "uygulanmaz" yazmalı.
- ☐ **Ses:** Cihazların örnekleme hızı mmsys.cpl > cihaz > Özellikler > Gelişmiş ile aynı.
- ☐ **Arka plan:** Arka planda çalışan uygulamalar listesi Görev Yöneticisi ile tutarlı.
- ☐ **Bulgular:** Bulgular mantıklı; yanlış alarm varsa not et.
- ☐ **Yönetici farkı:** Yönetici olarak açıldığında disk sıcaklığı/aşınma ve bellek sıkıştırma
  durumu da görünüyor.

## 4. Gizlilik

- ☐ Rapor sayfasında "Raporu kaydet" → `.txt` ve `.json` dosyalarını Not Defteri'nde aç.
  Ctrl+F ile şunları ara; **hiçbiri bulunmamalı**:
  - ☐ Kullanıcı adın, bilgisayar adın (Ayarlar > Sistem > Hakkında).
  - ☐ IP adresin (`ipconfig`), MAC adresin (`getmac`).
  - ☐ Windows ürün anahtarı, disk seri numaraları (`wmic diskdrive get serialnumber`).
  - ☐ Bluetooth kulaklık/fare adında kendi adın varsa o da raporda olmamalı.
- ☐ Aynı aramayı `logs\\forevermore.log` dosyasında yap.
- ☐ Kaynak İzleyicisi (`resmon`) > Ağ sekmesi: uygulama çalışırken `Forevermore.exe`'nin ağ
  etkinliği **olmamalı**. İstisna: (i) penceresinde bir kaynak bağlantısına tıklarsan tarayıcı açılır.

## 5. Güvenlik katmanı

- ☐ **Geri yükleme noktası**
  - ☐ İlk ayarı açınca bekleme penceresi çıkıyor, sonra `rstrui`'de
    "Forevermore - degisiklik oncesi" noktası görünüyor.
  - ☐ Aynı oturumda ikinci ayar → yeni geri yükleme noktası denenmiyor (bekleme penceresi çıkmaz).
  - ☐ Uygulamayı kapat-aç, 24 saat dolmadan bir ayar aç → "son 24 saatte zaten var" mesajı.
  - ☐ **Sistem Korumasını kapat** (sanal makinede) → bir ayar aç → "oluşturulamadı" sorusu çıkıyor.
    "Vazgeç" deyince hiçbir şey değişmiyor, "Yine de devam et" deyince değişiyor.
- ☐ **Yedekler**
  - ☐ `%ProgramData%\\Forevermore\\<SID>\\backups\\yedekler.json` oluştu.
  - ☐ `backups\\reg\\` klasöründe `.reg` dosyaları var.
- ☐ **Geri alma**
  - ☐ Bir ayarı aç → "Eski haline getir" → değer tam olarak eskisine döndü (regedit ile bak).
  - ☐ Birkaç ayar aç → uygulamayı kapat → bilgisayarı yeniden başlat → uygulamayı aç →
    Değişiklikler sayfasında hepsi listeleniyor → **Tümünü eski haline getir** → hepsi eski hâlinde.
- ☐ **Profiller**
  - ☐ Güvenli profili uygula → sonuç penceresi kaç başarılı/başarısız olduğunu gösteriyor.
  - ☐ Dikkatli kullanıcı profili: dikkatli ayarlar işaretsiz geliyor; işaretlenince her biri için
    ayrı onay penceresi açılıyor.
- ☐ **Hata durumu:** Uygulama bir işlem sürerken kapatılmak istenince uyarı veriyor.

## 5b. Onay akışı, placebo menüsü, başlangıç onayı (Revizyon Faz 2)

- ☐ **Başlangıç onayı:** `%LOCALAPPDATA%\\Forevermore\\onay.json` dosyasını sil → uygulamayı aç →
  onay ekranı çıkıyor; kutu işaretlenmeden "Kabul ediyorum" pasif. "Kabul etmiyorum" → uygulama
  kapanıyor, hiçbir şey değişmiyor. Kabul et → bir daha sorulmuyor; `onay.json`'da tarih ve sürüm var.
- ☐ **Dikkatli ayar:** Açarken tek onay penceresi; kapatırken pencere yok.
- ☐ **Riskli ayar (PERF-003 HVCI, CPU-004 Spectre/Meltdown):** Açarken iki ayrı ekran (1. ekranda
  kutu işaretlenmeden "Devam" pasif). Herhangi birinde "Vazgeç" → hiçbir şey değişmiyor.
  Kapatırken ve "Eski haline getir"de de iki ekran çıkıyor.
- ☐ **Kısmen açık ayar:** (ör. NET-009'un yalnızca bir özelliğini Aygıt Yöneticisi'nden değiştir)
  switch'e tıkla → "Tamamen uygula / Tamamen kapat / Vazgeç" soruluyor.
- ☐ **Placebo menüsü:** En üstte "Bu bilgisayarda uygulanmış olanlar" bölümü bu bilgisayarın
  gerçek durumuyla uyuşuyor (ör. DiagTrack, WerSvc kapalıysa orada görünüyor). Bir placebo
  switch'ini aç → bölüme ekleniyor; kapat/eski haline getir → çıkıyor.
- ☐ **Yalnızca kapatılabilir ayarlar (PLC-005, PLC-017, PLC-019):** Kapalıyken switch pasif ve
  üzerine gelince açıklama çıkıyor.
- ☐ **Tek seferlik eylem (PLC-023):** "Geri alınamaz" sorusu çıkıyor; sonuçta silinen dosya sayısı
  ve MB görünüyor; Değişiklikler sayfasında "Geri alınamaz işlemler" altında listeleniyor,
  "Eski haline getir" listesine girmiyor.
- ☐ **DNS (PLC-014):** Mevcut DNS'in listedekilerden biri değilse (ör. kendi DNSCrypt/özel DNS'iniz)
  açılır listede "Özel (mevcut değer)" görünüyor ve **Uygula'ya basmadıkça hiçbir şey değişmiyor**.
  Cloudflare seç → uygula → `ipconfig /all`'da görünüyor → "Eski haline getir" → eski DNS geri geliyor.
- ☐ **Ekstra ayarlar > Ekstra ayar bilgileri:** Kapalıyken (i) penceresinde yalnızca ne yapar,
  artılar/eksiler, kimler dokunmamalı ve tahmini etki var. Açınca Windows sürümü, gerçeklik
  durumu ve kaynaklar da görünüyor. Uygulamayı kapat-aç → seçim hatırlanıyor.
- ☐ **Yasaklı beş ayar** (Defender kapatma, Windows Update kalıcı kapatma, sayfa dosyası kapatma,
  Realtime öncelik, agresif debloat) hiçbir yerde switch olarak görünmüyor; yalnızca bilgi kartı.

## 5c. Özet: canlı durum ve "Çöz" (Revizyon Faz 3)

- ☐ **Canlı değerler:** Özet sayfasındaki İşlemci, Bellek, Ekran kartı, Disk ve Ağ değerleri
  Görev Yöneticisi > Performans sekmesindekilerle aşağı yukarı aynı (birkaç puan fark olabilir).
  Bir oyun veya video açınca ekran kartı ve ağ grafikleri hareket ediyor.
- ☐ **Kaynak tüketimi:** Özet sayfası açıkken Görev Yöneticisi'nde Forevermore'un işlemci
  kullanımı %1'in altında kalıyor. Başka sayfaya geçince veya pencereyi küçültünce neredeyse 0'a düşüyor.
- ☐ **"Çöz" ve ayar:** Örneğin "Arka plan kaydı açık" bulgusunda "Çöz" → ayar uygulanıyor →
  kart "Çözüldü" oluyor → Değişiklikler sayfasında listeleniyor → kartta "Geri al" → eski hâline dönüyor.
- ☐ **Yenileme hızı (DISP-001):** Sanal makinede veya ikinci monitörde Hz'i düşür → Yeniden tara →
  "Çöz" → monitör en yüksek Hz'e geçiyor, çözünürlük değişmiyor. "Eski haline getir" → önceki Hz'e dönüyor.
  (Ekran 1-2 saniye kararabilir.)
- ☐ **Tespit edilen tweak:** "Daha önce uygulanmış sorunlu bir ayar" kartında "Çöz" → değer Windows
  varsayılanına dönüyor (regedit ile bak) → Değişiklikler'den geri alınabiliyor.
- ☐ **Geçici dosyalar:** "Çöz" → geri alınamaz sorusu → silinen dosya sayısı gösteriliyor.
- ☐ **Önizleme modu:** "Çöz" düğmeleri pasif.

## 5d. Rehberden uygulamaya taşınanlar (Revizyon Faz 4a)

- ☐ **Yenileme hızı listesi (Display):** Her monitör için ayrı liste; düşük bir Hz seç → Uygula → monitör o
  hıza geçiyor, çözünürlük değişmiyor → "Eski haline getir" → önceki Hz. Ekran 1-2 sn kararabilir.
- ☐ **FSO (DISP-004):** Aç → regedit `HKCU\\System\\GameConfigStore` içinde `GameDVR_FSEBehaviorMode=2` ve
  `GameDVR_HonorUserFSEBehaviorMode=1` → eski haline getir → önceki değerler.
- ☐ **Görsel efektler (PERF-005):** Aç → `SystemPropertiesPerformance.exe` penceresinde animasyon/gölge
  kutucukları boş, "Ekran yazı tiplerinin kenarlarını yumuşat" ve "Küçük resimleri göster" işaretli kalmış →
  oturumu kapat-aç → eski haline getir → kutucuklar eski hâlinde.
- ☐ **Güç modu (PWR-002):** Dengeli plandayken aç → Ayarlar > Sistem > Güç ve pil > Güç modu "En iyi performans".
  Kapat → önceki mod.
- ☐ **Laptop: Prizde / Pilde:** Güç sayfasında güç ayarlarında iki ayrı düğme var. "Pilde"yi değiştir →
  `powercfg /q` çıktısında yalnızca "DC" değeri değişiyor, "AC" aynı kalıyor. Masaüstünde tek düğme var.
- ☐ **Başlangıç uygulamaları:** Bir uygulamayı kapat → Görev Yöneticisi > Başlangıç uygulamaları'nda "Devre
  dışı" görünüyor → yeniden başlat → uygulama açılmıyor → "Eski haline getir" → yeniden "Etkin".
- ☐ **Zamanlanmış görevler:** Bir görevi kapat → Görev Zamanlayıcı'da "Devre dışı" → geri al.
- ☐ **Servisler:** Windows dışı bir servisi "Elle" yap → services.msc'de "El ile" → geri al. Windows servisinde
  ek onay soruluyor. Kritik ve anti-cheat servislerinde (vgc, BEService) liste ve Uygula kilitli.
- ☐ **MSI modu (yalnızca sanal makinede veya geri yükleme noktasıyla):** Bir aygıtta (ör. ağ kartı) MSI'ı
  değiştir → iki onay ekranı → yeniden başlat → aygıt çalışıyor mu? Geri al → yeniden başlat.
  Aygıt çalışmazsa Güvenli Mod'da uygulamayı açıp geri almayı da bir kez dene.
- ☐ **Aygıt güç yönetimi:** Bir USB kök hub'da düğmeyi aç → Aygıt Yöneticisi > aygıt > Güç Yönetimi
  sekmesinde kutucuk boş → geri al → işaretli.
- ☐ **Mouse ve Klavye:** "Polling rate neden gösterilmiyor" açıklaması yok; yalnızca bağlı cihazlar listesi var.

## 5e. Ekran kartı ve ses (Revizyon Faz 4b)

- ☐ **NVIDIA ayarları okunuyor:** Ekran Kartı sayfasındaki değerler NVIDIA Denetim Masası > 3D
  ayarlarını yönet > Genel ayarlar ile aynı (düşük gecikme, güç yönetimi, doku filtreleme,
  gölgelendirici önbelleği, dikey senkronizasyon, maksimum kare hızı, iş parçacıklı
  optimizasyon, tercih edilen yenileme hızı).
- ☐ **NVIDIA ayarı yazılıyor:** Birini değiştir → Uygula → Denetim Masası'nı kapatıp aç → yeni değer
  görünüyor → "Eski haline getir" → eski değer (veya "Uygulama ayarını kullan").
- ☐ **NVAPI yokken:** NVIDIA'sız sanal makinede kartlarda "NVIDIA sürücüsüne erişilemedi" yazıyor,
  uygulama çökmüyor. tools klasörüne nvidiaProfileInspector.exe konunca "NVIDIA Profile Inspector
  ile uygula" düğmesi çıkıyor (yalnızca sanal makinede dene; geri alınamaz).
- ☐ **Ses geliştirmeleri (cihaz başına):** Bir cihazda aç → Ayarlar > Ses > cihaz > Ses geliştirmeleri
  "Kapalı" → diğer cihazlar değişmemiş → geri al.
- ☐ **Örnekleme hızı:** Bir cihazda 48000 Hz / 24 bit seç → Uygula → mmsys.cpl > cihaz > Gelişmiş'te aynı
  biçim → "Eski haline getir" → eski biçim. Listede yalnızca cihazın desteklediği biçimler var.
- ☐ **Görsel/QoL:** Gece ışığı ve dijital canlılık kartında neden uygulamadan yapılamadığı yazıyor.

## 5f. Oyunlar menüsü (Revizyon Faz 5)

- ☐ **Oyun bulma:** Steam, Epic, GOG, Xbox, Riot, Battle.net, EA, Ubisoft oyunların listede. Eksik
  bir oyun varsa hangi başlatıcıdan olduğunu yaz. "Elle ekle" ile .exe seçilebiliyor.
- ☐ **Anti-cheat koruması:** `vgc.exe` veya `EasyAntiCheat.exe`'yi elle eklemeye çalış → "eklenemez" mesajı.
- ☐ **Kalıcı öncelik:** Bir oyuna "Normalin üstünde" → Kaydet → oyunu aç → Görev Yöneticisi > Ayrıntılar >
  oyun > Öncelik "Normalin üstünde" (uygulama kapalıyken de) → Değişiklikler'den geri al → Normal.
- ☐ **GPU tercihi (laptop):** "Yüksek performans" → Ayarlar > Sistem > Ekran > Grafik'te oyun için
  "Yüksek performans" görünüyor → geri al.
- ☐ **Tam ekran optimizasyonları:** İşaretle → oyun .exe > Özellikler > Uyumluluk'ta "Tam ekran
  iyileştirmelerini devre dışı bırak" işaretli → geri al.
- ☐ **Çekirdekler:** "Performans çekirdekleri" seç, kaydet, uygulama açıkken oyunu aç → Process Explorer
  veya Process Lasso'da oyunun CPU Set'leri yalnızca CPU 0–7 → oyunu kapat.
- ☐ **Oyun sırasında:** Servis duraklat + Windows Search + Yüksek Performans planı + bildirimleri sustur
  seç → oyunu aç → services.msc'de SysMain/WSearch durdu, güç planı Yüksek Performans → oyunu kapat →
  servisler yeniden çalışıyor, eski plan geri geldi, bildirimler açık.
- ☐ **Çökme kurtarması:** Oyun açıkken Forevermore'u Görev Yöneticisi'nden sonlandır → oyunu kapat →
  uygulamayı aç → "yarım kalan oyun ayarları geri alındı" mesajı, servisler ve plan eski hâlinde.
- ☐ **Anti-cheat'li oyunda (Valorant/LoL, mümkünse ikinci hesapla):** çekirdek seçimi açıkken oyunu
  aç → oyun açılıyor mu, uyarı/atılma var mı? Durum satırında "uygulanamayanlar" yazıyor mu?
- ☐ **Standby temizliği (durumsal):** Açıkken oyunu aç → RAMMap'te Standby küçüldü. Önce/sonra ölçümüyle
  gerçekten fark var mı bak.

## 5g. Ekstra ayarlar (Revizyon Faz 6)

- ☐ **Tepsi:** "Kapatınca tepside çalışmaya devam et"i aç → pencereyi kapat → saatin yanında simge var,
  uygulama çalışıyor → simgeye tıkla → pencere geri geliyor → sağ tık > Çıkış → uygulama tamamen kapanıyor.
- ☐ **Windows'la başlat:** Aç → Görev Zamanlayıcı'da "Forevermore - oturum acilisi" görevi var, "En yüksek
  ayrıcalıklarla çalıştır" işaretli → oturumu kapat-aç → UAC penceresi çıkmadan uygulama tepside başlıyor →
  kapat → görev silindi.
- ☐ **Durumu yeniden algıla:** Bir ayarı Windows Ayarları'ndan değiştir → düğmeye bas → uygulama yeni durumu gösteriyor.
- ☐ **Geri yükleme noktası oluştur:** `rstrui`'de nokta görünüyor (veya "son 24 saatte var" mesajı).
- ☐ **Dışa / içe aktar:** Dışa aktar → başka kullanıcıda/sanal makinede içe aktar → oyun profilleri geldi.
- ☐ **Bilgi:** Sürüm görünüyor; "Kopyala" panoya kopyalıyor; başka bağlantı yok;
  "Üçüncü taraf lisansları" listeyi açıyor. `data/hakkinda.json`'a bir satır ekleyince yeni bağlantı görünüyor.

## 5h. Önce / Sonra ölçümü (Revizyon Faz 7)

- ☐ **PresentMon:** GitHub'daki resmi sürüm sayfasından konsol sürümünü (`PresentMon-...-x64.exe`)
  indir, `tools` klasörüne koy → Önce/Sonra sayfasında "PresentMon bulunamadı" uyarısı kayboldu.
  `derle.bat` çalıştırınca exe programın yanına kopyalandı.
- ☐ **Sistem ölçümü:** Yeniden başlat, 2-3 dk bekle → "Önce" etiketiyle 30 sn ölçüm → değerler mantıklı
  (açılış süresi saniye cinsinden, başlangıç sayısı Görev Yöneticisi ile aynı) → birkaç başlangıç
  uygulamasını kapat → yeniden başlat → "Sonra" ölçümü → karşılaştırma tablosu otomatik açıldı, azalan
  değerler yeşil.
- ☐ **Açılış süresi kaynağı:** Uygulama yönetici olarak açıkken olay 100 bulunuyor mu (ayrıntıda
  kaynak "olay_100")? Bulunmuyorsa yedek yöntem (oturum açma) kullanılıyor.
- ☐ **Oyun ölçümü:** Oyunu aç, aynı sahneye gel → 60 sn ölçüm → ortalama FPS oyun içi sayaçla veya
  CapFrameX/PresentMon arayüzüyle aşağı yukarı aynı → aynı sahnede 3 kez ölç, sonuçların birbirine yakın
  olduğunu kontrol et.
- ☐ **Yanlış süreç adı:** Açık olmayan bir oyun adıyla ölç → "yeterli kare kaydedilmedi" mesajı.
- ☐ **Rapor:** "Raporu kaydet" → reports klasöründe metin dosyası; dürüstlük uyarısı içinde.

## 5i. Kaldırma ve anti-cheat uyarısı

- ☐ **Anti-cheat uyarısı:** Oyunlar'da Valorant/LoL "Anti-cheat: Riot Vanguard", Rainbow Six "BattlEye,
  EasyAntiCheat", PUBG/Destiny 2 "BattlEye" rozeti gösteriyor; oyunun ayarlarını açınca üstte uyarı var.
  CS2 gibi koruması klasörde görünmeyen oyunlarda "anti-cheat izi bulunamadı" notu çıkıyor.
- ☐ **Kaldırmaya hazırla:** Birkaç ayar uygula + "Windows'la başlat"ı aç → Ekstra ayarlar > Kaldırmaya
  hazırla → "tüm değişiklikleri geri al" işaretli → Temizle → Görev Zamanlayıcı'da görev yok,
  Değişiklikler boş, uygulama kapandı.
- ☐ **Veri silme:** Değişiklik varken "verileri sil" kutusu pasif; geri al işaretlenince aktif → işaretle →
  `%LOCALAPPDATA%\\Forevermore` klasörü silindi.
- ☐ **Komut satırı:** `Forevermore.exe --kaldir` → UAC → pencere açılmadan görev silindi.

## 5j. Yeni ad ve çok dil (Revizyon 2 Faz 1)

- ☐ **Yeni ad:** `derle.bat` → `dist\\Forevermore\\Forevermore.exe` oluştu; pencere başlığı, kenar menü,
  tepsi simgesi ipucu ve Görev Yöneticisi'nde "Forevermore" yazıyor. Dosya özelliklerinde sürüm 2.2.0.
- ☐ **Veri taşıma:** Eski sürümü kullandıysan `%LOCALAPPDATA%\\Forevermore` ilk açılışta oluştu ve içinde
  `eski_klasorden_tasindi.txt` var; `%LOCALAPPDATA%\\PCOptimizer` silinmedi. Değişiklikler sayfasında eski
  sürümde yaptığın değişiklikler görünüyor ve "Eski haline getir" çalışıyor.
- ☐ **Eski görev:** Eski sürümde "Windows'la başlat" açıktıysa, Ekstra ayarlar'da anahtar açık görünüyor.
  Kapat → Görev Zamanlayıcı'da ne "PC Optimizer - oturum acilisi" ne "Forevermore - oturum acilisi" kaldı.
  Aç → yalnızca "Forevermore - oturum acilisi" var.
- ☐ **İlk açılış dil seçimi:** `%LOCALAPPDATA%\\Forevermore\\uygulama_ayarlari.json` dosyasındaki `"dil"`
  satırını sil (veya dosyayı sil) → uygulamayı aç → önce dil seçme penceresi, SONRA başlangıç onayı çıkıyor.
  Windows dilin Türkçe ise Türkçe, değilse English önceden seçili.
- ☐ **Onay metni dili:** English seçince onay ekranı İngilizce ve sonunda "Turkish text prevails" notu var.
  Dil değiştirince onay bir kez daha soruluyor (beklenen davranış: metin değişti).
- ☐ **Ayarlardan dil değiştirme:** Ekstra ayarlar > Dil → Türkçe/English seç → "Şimdi yeniden aç" →
  uygulama UAC sormadan yeniden açıldı, yeni dilde. "Sonra" dersen bir sonraki açılışta geçerli.
- ☐ **İngilizce arayüz:** Tüm menüleri English'te gez. Arayüz metinleri, ayar adları, (i) penceresindeki
  açıklamalar, artı/eksiler, rehber adımları, kategori açıklamaları ve Placebo menüsü İngilizce (Faz 1b).
  Türkçe kalmış bir metin, kesilen veya taşan metin görürsen ekran görüntüsüyle bildir.
- ☐ **İngilizce çeviri kalitesi:** Çevirileri geliştirici yaptı; anlamı bozulmuş veya garip cümle görürsen
  not al (satıştan önce ana dili İngilizce bir uzman kontrol etmeli).
- ☐ **Dil değişince ayar durumları:** English'te bir ayarı aç, Türkçeye geç → Değişiklikler sayfasında aynı
  ayar görünüyor ve "Eski haline getir" çalışıyor (dil yalnızca metni değiştirir, kayıtları değil).
- ☐ **Sayı ve tarih biçimi:** Türkçede `4,2 GHz`, `%12`, tarih `23.10.2026 14:05`; English'te `4.2 GHz`,
  `12%`, `2026-10-23 14:05` (Özet, Değişiklikler, Önce/Sonra, rapor).
- ☐ **Ayar dosyası içe aktarma:** Eski sürümde dışa aktardığın `pcoptimizer_ayarlar.json` dosyası
  hâlâ içe aktarılabiliyor.

### Farklı dilde Windows kontrol listesi (sanal makinede)

Uygulama Windows'un diline bakmadan çalışacak şekilde yazıldı: servisler servis adıyla, güç ayarları
GUID ile, olaylar olay numarasıyla, ağ hızı sayısal değerle okunuyor. Yine de şunları **Türkçe, Almanca ve
Çince/Japonca Windows** kurulu bir sanal makinede dene (Ayarlar > Saat ve dil > Dil'den Windows görüntüleme
dilini değiştirip oturumu kapat-aç yeterli):

- ☐ Tarama hatasız bitiyor; Özet'teki Windows sürümü, işlemci, GPU, RAM doğru.
- ☐ İnternet/Ağ: kablolu bağlantı hızı doğru (ör. 1000 Mbps). (Bu bilgisayarda sayısal değerle doğrulandı.)
- ☐ Güç: etkin plan ve "Nihai Performans planı" durumu doğru; plan adı Windows dilinde görünüyor.
- ☐ Önyükleme ayarları (bcdedit kullananlar, ör. HPET/dinamik tick): durumları doğru okunuyor.
  **Doğrulanmadı:** bcdedit'in değerleri (Yes/No) Windows diline göre çevirip çevirmediği. Yanlış
  görünürse yönetici PowerShell'de `bcdedit /enum {current}` çıktısını bana gönder.
- ☐ Başlangıç ve servisler: listeler doluyor, başlangıç türleri doğru.
- ☐ Önce/Sonra: açılış süresi ölçülüyor (olay günlüğü).
- ☐ Çince/Japonca Windows'ta uygulama metinlerinde kutu (□) karakteri yok.

## 5k. Yeni tasarım, PC Detayları, ekran kartları, Bilgi (Revizyon 2 Faz 2)

- ☐ **Genel görünüm:** Koyu zemin, mor-mavi vurgu rengi; kenar menüde her bölümün simgesi kendi renginde.
  Ayar kartlarında solda renkli simge, başlık altında tek satırlık açıklama, sağda (i), geri al (↺) ve
  aç/kapa düğmesi. Açık Windows temasında da metinler okunuyor.
- ☐ **Geri al düğmesi:** Bir ayarı aç → kartın sağında ↺ düğmesi çıkıyor; üzerine gelince "Eski haline
  getir" yazıyor; tıklayınca ayar eski hâline dönüyor ve düğme kayboluyor.
- ☐ **Sade ana sayfa:** Özet'te yalnızca 4 sayı kartı, canlı durum (6 kutu) ve bulgular var. Donanım
  kartları ve "en çok işlemci kullananlar" artık burada DEĞİL.
- ☐ **PC Detayları:** Bilgisayar modeli, Windows sürümü, işlemci, bellek, ekran kartları, ekranlar,
  depolama/güç/anakart ve canlı "en çok işlemci kullananlar" listesi burada. Seri numarası, kullanıcı adı yok.
- ☐ **İki ekran kartı:** Bu laptopta iki kart da listeleniyor. NVIDIA "Yüksek performans" (oyunlarda
  kullanılan), AMD Radeon "Güç tasarrufu" rozetiyle; her kartın hangi ekranı sürdüğü yazıyor; birincil ekranı
  süren kartta "Birincil ekran" rozeti var. Windows Ayarlar > Sistem > Ekran > Grafik'teki "Yüksek
  performans" kartıyla aynı mı, kontrol et.
- ☐ **Ekranlar:** Her ekran için çözünürlük @ Hz, bu çözünürlükte en yüksek Hz ve onu süren kart. Windows
  monitöre özel ad vermiyorsa "Ekran 1/2" yazıyor (gerçek monitör adları Faz 3'te).
- ☐ **NVIDIA ayarları:** Ekran Kartı menüsündeki NVIDIA kartlarında "Bu ayar yalnızca NVIDIA … kartına
  uygulanır" satırı var.
- ☐ **Taşınan ayarlar:** Sistem menüsünde "Başlangıç uygulamalarını azaltma", Performans/İşlemci/Görsel
  menülerinde oyun başına yapılan ayarlar (öncelik, GPU seçimi, çekirdek atama, bildirim) artık YOK ve
  "taşındı" yazan kart da yok. Bunlar Başlangıç ve servisler / Oyunlar menülerinde.
- ☐ **Bilgi menüsü:** Kenar menüde Ekstra ayarlar'ın altında "Bilgi". En üstte büyük "Kubilay Paşa", altında
  Kopyala düğmesi; sürüm, gizlilik notu, üçüncü taraf lisansları. Bağış bölümü yok.
  Ekstra ayarlar'da artık bilgi bölümü yok.
- ☐ **Bilgi dosyası:** `data\\hakkinda.json` içinde `satirlar` listesine yeni bir satır ekle (ör.
  `{"etiket": "Not", "deger": "..."}`) → uygulamayı yeniden aç → Bilgi sayfasında görünüyor.
- ☐ **Rapor:** Kaydedilen raporda her ekran kartının altında "Windows rolü: Yüksek performans / Güç
  tasarrufu" ve her ekranın altında "süren kart" satırı var.

## 5l. Ekran ve fare/klavye (Revizyon 2 Faz 3)

- ☐ **Menü adı:** Türkçede kenar menüde "Ekran" yazıyor (önceden "Display").
- ☐ **Monitör adları:** Ekran > Monitörler kartında harici monitör EDID'deki adıyla ("ASUS VG27WQ1B"),
  dahili ekran "Dahili ekran (AU Optronics, AUO 56AD)" olarak görünüyor; bağlantı (HDMI/dahili) ve süren
  kart yazıyor. PC Detayları ve raporda da aynı adlar var.
- ☐ **Çözünürlük + Hz:** Bir monitörde çözünürlük ve Hz seç → Uygula → ekran değişti ve 15 saniyelik
  "Kalsın / Geri dön" penceresi çıktı. (a) Hiçbir şeye basma → 15 sn sonra eski moda döndü.
  (b) "Geri dön" → eski mod. (c) "Kalsın" → yeni mod kaldı, Değişiklikler sayfasında "Ekran modu: …" var
  ve "Eski haline getir" ile ilk hâle döndü. (Bu bilgisayarda yazma ve geri alma, uygulama arayüzü
  olmadan denendi ve çalıştı.)
- ☐ **Yeniden başlattıktan sonra geri alma:** Çözünürlüğü değiştir → "Kalsın" → bilgisayarı yeniden başlat
  → Değişiklikler'den eski haline getir → doğru monitöre uygulandı (ekran numarası değişse bile).
- ☐ **Ölçek:** %100 → %125 seç → Uygula → metinler hemen büyüdü; "Eski haline getir" → %100. Bazı açık
  programlar yeniden açılınca düzgün görünür (normal). Bu yöntem Windows'un belgelenmemiş arabirimidir;
  bu bilgisayarda denendi ve çalıştı.
- ☐ **Ölçekleme modu (GPU/monitör):** Uygulamada YOK. Windows'un arabirimiyle denendi, bu bilgisayarda modu
  değiştirmedi (docs/EKRAN.md); ekran kartı fazında sürücü üzerinden denenecek.
- ☐ **Fare ve klavyeler:** Mouse ve Klavye menüsünde "NuPhy Air75 HE" (VID:PID 19F5:6120) ve "SCYROX 8K
  Dongle" (3554:F5F7) gerçek adlarıyla; tek fiziksel cihaz tek satır (ör. "Fare + Klavye"). Kendi adını
  bildirmeyen cihazlarda "Windows'un genel adı" notu var.
- ☐ **Özel ad:** Bir cihazın kalem düğmesine bas → ad yaz → listede yeni ad, altında "Cihazın bildirdiği ad".
  Uygulamayı kapatıp aç → ad duruyor. Adı silip kaydet → cihazın kendi adına döndü. Kaydedilen rapora özel
  adlar GİRMİYOR.

## 5m. Sistem menüsü (Revizyon 2 Faz 4)

- ☐ **OneDrive rehberi:** OneDrive kurulu DEĞİLKEN Sistem menüsünde "OneDrive eşitlemesini duraklatma" kartı
  yok ("Uymayanları göster" ile "OneDrive bu bilgisayarda kurulu değil" gerekçesiyle görünür). OneDrive kurulu
  bir bilgisayarda kart görünüyor.
- ☐ **Defender dışlamaları / Dev Drive** rehberi duruyor.
- ☐ **Windows Update modları** (Sistem > Windows Update kartı): üç mod, şu anki modda "Şu an" rozeti.
  - Güvenlik (önerilen): tek onay → Uygula → `reg query HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\WindowsUpdate`
    içinde DeferFeatureUpdatesPeriodInDays=365, DeferQualityUpdatesPeriodInDays=4; Ayarlar > Windows
    Update'te "kuruluşunuz tarafından yönetiliyor" notu çıkabilir (normal).
  - 2100'e kadar duraklat: İKİ onay ekranı → Ayarlar > Windows Update'te "Güncellemeler duraklatıldı" ve
    bitiş tarihi 2100 görünüyor mu? **Denenmedi, belgelenmemiş yöntem** — sanal makinede dene.
  - Mod değiştirince önceki modun değerleri önce geri alınıyor; "Varsayılan" her şeyi uygulamadan önceki
    hâline döndürüyor; Değişiklikler sayfasında "Windows Update modu: …" var.
- ☐ **Servis süzgeçleri:** Başlangıç ve servisler > Servisler'de başlangıç türü seçimi (Otomatik / El ile /
  Devre dışı) listeyi süzüyor. "Yalnızca FPS'i etkileyebilecek servisler" işaretlenince Windows servisleri de
  görünüyor; her satırda gerçek/durumsal/placebo etiketi, kısa açıklama ve "Ayara git" (kaynaklar o ayarın
  (i) penceresinde) var.
- ☐ **Bilerek yapılmayanlar:** Defender'ı kapatan bir ayar yok (Placebo'daki bilgi kartı duruyor);
  HVCI ayarı önceki hâlinde (Performans menüsü).

## 5n. Elle yapılacaklar, zamanlayıcı, ses, güç (Revizyon 2 Faz 5)

- ☐ **Rehberler kategori sayfalarında yok:** Ekran, Sistem, Ekran Kartı, İşlemci, Güç, Ağ, Mouse/Klavye, Ses,
  Görsel menülerinde "Nasıl yapılır?" kartı kalmadı. Kenar menüde Placebo'nun altında **Elle yapılacaklar**:
  BIOS, ağ/yönlendirici, oyun içi, sürücü yazılımı, donanım, üretici uygulaması, Windows Ayarlar'ı, sizin
  kararınız, teşhis, üçüncü parti araç başlıkları altında, her kartta adımlar.
- ☐ **Bir bulgudan "Ayara git":** Elle yapılacak bir ayarı gösteren bulguda düğme Elle yapılacaklar sayfasını
  açıp kartı vurguluyor.
- ☐ **Zamanlayıcı çözünürlüğü (Performans):** "Etki: belirsiz" rozeti, şu anki değer satırı. 0,5 ms seç →
  Uygula → satırda "Uygulamanın isteği: 0,5 ms". Uygulamayı kapatıp aç → istek yeniden uygulanıyor
  (log'da "Zamanlayıcı çözünürlüğü istendi"). "Windows'a bırak" → istek kalkıyor. İşlemci > GlobalTimer-
  ResolutionRequests kapalıysa kartta "yalnızca bu uygulamayı etkiler" uyarısı ve "Ayara git" var.
- ☐ **Sleep(1) ölçümü:** Önce / Sonra > Sistem ölçümü sonunda "Sleep(1) süresi" satırı (ms) var.
  Zamanlayıcıyı 0,5 ms + GlobalTimerResolutionRequests açıkken ölçünce değer 1 ms'ye yaklaşıyor mu?
- ☐ **Ses — özel mod (Ses > Özel mod izinleri):** Her çıkış cihazında "Uygulamalar özel denetim alabilsin"
  anahtarı. Kapat → ses birkaç saniye kesilir; mmsys.cpl > cihaz > Gelişmiş'te iki kutu işaretsiz mi?
  (**Belgelenmemiş yerleşim, denenmedi — UAC gerekir, evde dene.**) Aç → eski hâline döndü.
- ☐ **Ses — kullanılmayan aygıtlar / Bluetooth Eller Serbest:** "Aygıtları göster" → listede hoparlör,
  kulaklık, mikrofonlar (ve Bluetooth kulaklık varsa Hands-Free). Bir aygıtın "Kullanılsın"ını kapat → onay
  → aygıt Ses ayarlarında devre dışı. Yeniden aç → geri geldi. (**UAC gerekir, denenmedi.**)
- ☐ **Güç — laptop ekran kartı modu:** Güç menüsünün üstünde "Şu an hibrit: dahili ekranı AMD Radeon 880M
  sürüyor" yazıyor; OMEN Gaming Hub'da MUX'u harici karta alıp yeniden başlatınca "yalnızca harici kart"
  yazıyor mu? Masaüstünde bu kart görünmüyor.
- ☐ **İşlemci kaynakları:** Elle yapılacaklar > BIOS > SMT kapatma (i) penceresinde (Ekstra ayar bilgileri
  açıkken) TechSpot / AnandTech / Notebookcheck kaynakları; C-State kartında Blur Busters forum kaynağı.

## 5o. Ekran kartı (Revizyon 2 Faz 6)

- ☐ **Yöntem rozetleri:** Ekran Kartı menüsündeki NVIDIA kartlarında "Yöntem: NVAPI", AMD kartlarında
  "Yöntem: ADLX" rozeti var. NVAPI'ye erişilemezse ve tools klasöründe NVIDIA Profile Inspector varsa
  "Yöntem: NVIDIA Profile Inspector (yedek)" görünüyor.
- ☐ **AMD Anti-Lag / Chill / Boost (laptop, Radeon 880M):** Kartlarda şu anki durum AMD Software ile aynı
  (bu bilgisayarda hepsi Kapalı). Anti-Lag'i aç → AMD Software > Oyun > Grafik'te Açık görünüyor mu?
  Anahtarı geri kapat → eski hâline döndü, "Değiştirildi" rozeti kalktı. Enhanced Sync satırı
  "Bu kartta desteklenmiyor" yazıyor. (**Yazma denenmedi.**)
- ☐ **G-SYNC kapsamı (yeni ayar):** "Tam ekran ve pencere" seç → Uygula → NVIDIA Denetim Masası > G-SYNC'i
  ayarla'da aynı seçenek işaretli mi? Eski haline getir → "Yalnızca tam ekran". (**Yazma denenmedi.**)
- ☐ **Ölçekleme (Ekran > Monitörler):** ASUS monitörde "Monitör: ölçekleme yok (ortala)" + "Yöntem: NVAPI";
  dahili ekranda "Monitör (GPU ölçekleme kapalı)" + "Yöntem: ADLX". "GPU: tam ekran" seç → Uygula →
  ekran bir an kararabilir, 15 saniyelik onay çıkıyor. "Geri dön" → eski değer. Onayla → NVIDIA Denetim
  Masası > Masaüstü boyutunu ve konumunu ayarla'da "GPU" seçili mi? Eski haline getir → monitöre döndü.
  (**Yazma denenmedi; ekran kararırsa 15 saniye bekleyin, kendiliğinden geri döner.**)
- ☐ **DDU / NVCleanstall:** tools\\DDU ve tools\\NVCleanstall klasörleri yokken kartta "Bulunamadı" ve
  "İndirme sayfasını aç" (resmi sayfa açılıyor). DDU'yu indirip tools\\DDU içine koy → kart
  "tools klasöründe: Display Driver Uninstaller.exe" ve "Aç" diyor; Aç → DDU açılıyor.
- ☐ **Güvenli Mod (UAC ve yeniden başlatma gerekir, evde):** "Güvenli Modda yeniden başlat" → iki ayrı uyarı.
  İkincide "Hayır" → hiçbir şey değişmiyor. İkisine "Evet" → 15 saniye sonra Güvenli Modda açılıyor;
  uygulama açılınca üstte "Şu an Güvenli Moddasınız" şeridi. "Normal başlatmaya dön" → yeniden
  başlatınca normal açılış. (Önce geri yükleme noktası alın.)

## 5p. Placebo ve Oyunlar (Revizyon 2 Faz 7)

- ☐ **Placebo – uygulanmış olanlar:** Placebo menüsünün en üstündeki "Bu bilgisayarda uygulanmış olanlar"
  bölümünde, bu bilgisayarda zaten açık olan placebo ayarlar var (ör. 8.3 kısa adlar, son erişim zamanı,
  MaxUserPort "kısmen açık"). Birini kapat → bölüm yenileniyor, ayar aşağıdaki listeye iniyor.
- ☐ **Placebo – yeni anahtarlar (PLC-030…035):** 8.3 adları, son erişim zamanı, IoPageLockLimit,
  SecondLevelDataCache, MaxUserPort/TcpTimedWaitDelay, DefaultTTL. Her biri aç → Değişiklikler sayfasında
  görünüyor; "Eski haline getir" → regedit'te eski değer (yoksa değer silinmiş). (**Yazma denenmedi.**)
- ☐ **Placebo servisler:** "Placebo servisler" bölümünde devre dışı olanlar "uygulanmış" rozetli ve listenin başında.
- ☐ **Oyunlar – düzen:** Pencereyi daralt → öncelik / çekirdek / ekran kartı düğmeleri alt satıra geçiyor,
  satırlar birbirine binmiyor, yatay kaydırma çubuğu çıkmıyor (TR ve EN).
- ☐ **Oyunlar – seçim ve kayıt:** Üstteki listeden bulunan bir oyunu seç → listeye ekleniyor ve sayfası açılıyor.
  Öncelik "Yüksek" + Kaydet → onay soruluyor. Görev Yöneticisi > Ayrıntılar'da oyun açılınca öncelik
  doğru mu? "Oyun açılınca otomatik uygula" kapalıyken kaydet → Windows varsayılanı yazılıyor.
- ☐ **Oyunlar – Gelişmiş ayarlar:** Varsayılan olarak kapalı; "Gelişmiş ayarları göster" ile açılıyor; (i)
  düğmeleri tek cümlelik açıklama gösteriyor. "Seçilebilen çekirdekler" → CPU kutuları ve hızlı düğmeler.

## 5q. UAC seviyesi ve Defender (Revizyon 2 ek istek)

- ☐ **UAC (Sistem menüsü, UAC gerekir, evde):** Kartta "Şu an" rozeti Windows'un Kullanıcı Hesabı Denetimi
  ayarları penceresindeki kaydırıcıyla aynı seviyede mi? "Her zaman bildir" → pencere kaydırıcıyı en üstte
  gösteriyor mu? "Hiçbir zaman bildirme" → iki ayrı uyarı; "Hayır" → değişmiyor. "Varsayılan" seviyesi →
  Değişiklikler sayfasında UAC kaydı kalmıyor ve kaydırıcı eski yerinde. (**Yazma denenmedi.**)
- ☐ **Defender – Kurcalama koruması açıkken:** Kartta koruma "Açık", Kurcalama "Açık"; kapatma düğmesi yok,
  Windows Güvenliği'ne yönlendiren metin var. "Windows Güvenliği'ni aç" doğru sayfayı açıyor.
- ☐ **Defender – kapatma (evde, geri yükleme noktası alıp):** Kurcalama korumasını Windows Güvenliği'nden
  kendin kapat → "Yeniden oku" → "Gerçek zamanlı korumayı kapat" → iki ayrı uyarı. Kabul et → Windows
  Güvenliği'nde gerçek zamanlı koruma Kapalı. "Korumayı geri aç" → tek tıkla (ek onay yok) Açık.
  Sonra Kurcalama korumasını geri aç. (**Yazma denenmedi.**)
- ☐ **Defender – Kurcalama açıkken yazma denemesi:** Hata metni "Windows, Defender ayarının değiştirilmesine
  izin vermedi..." ve Değişiklikler sayfasında kayıt kalmıyor.

## 5r. Derlenmiş paket (Revizyon 2 Faz 8)

- ☐ **Paket:** `derle.bat` → sonunda "Bitti", dosya boyutu ve SHA256 yazıyor; arada kırmızı hata yok.
- ☐ **Açılış:** dist\\Forevermore.zip'i başka bir klasöre aç → Forevermore.exe → yönetici izni sorulur;
  "Hayır" → salt okunur modda açılıyor. "Evet" → normal mod; Sistem menüsünde UAC ve Defender kartları var.
- ☐ **Lisans:** zip içinde THIRD-PARTY-NOTICES.txt ve PresentMon var; Bilgi menüsünde sürüm 2.2.0.

## 5s. Özet kutuları, Bilgi ve logo

- ☐ **Özet kutuları:** "bu bilgisayara uygun ayar" kutusuna tıkla → altında menülere göre liste açılıyor, sayı
  kutudakiyle aynı; "Ayara git" ayarın sayfasını açıyor. Aynı kutuya tekrar tıkla veya "Kapat" → liste kapanıyor.
  "zaten açık" ve "uygulama tarafından değiştirildi" kutuları da kendi listelerini açıyor ("Değişiklikler
  sayfasını aç" düğmesi var). "bulgu" kutusu sayfayı Bulgular bölümüne kaydırıyor.
- ☐ **Bilgi:** Üstte logo, uygulamanın amacı ve "Neden yaptım?" metni; en altta "Yapımcı" kartında ad ve Discord
  (Kopyala çalışıyor). Ad ve iletişim data\\hakkinda.json'dan değişiyor.
- ☐ **Logo:** Kenar menüde "F" yerine yaprak motifli sonsuzluk işareti; görev çubuğu ve pencere simgesi ile
  Forevermore.exe'nin dosya simgesi aynı logo.

## 5t. Lisans, imza ve dağıtım paketi

- ☐ **İlk açılış:** Başlangıç onayı metninde "MIT lisansıyla ücretsiz ve açık kaynak…" paragrafı var
  (metin değiştiği için bir kez yeniden sorulur).
- ☐ **Lisans:** Bilgi > "Lisans (MIT)" LICENSE metnini gösteriyor; zip içinde LICENSE, THIRD-PARTY-NOTICES.txt,
  OKUBENI.txt var. Forevermore.exe > Özellikler > Ayrıntılar: Telif "© 2026 Kubilay Paşa".
- ☐ **Anahtar yedeği:** %USERPROFILE%\\.forevermore-imza\\ozel_anahtar.txt dosyasını USB'ye/şifreli yere kopyaladın.

## 5v. Bilgi bağlantıları

- ☐ **Bilgi:** Web satırında "Aç" tarayıcıda doğru sayfayı açıyor.

## 5w. D4 elle test: Monitör yöneticisi (ekran yön/konum yazma)

Ekran düzenini değiştirir; yazma arayüzü gelince şu sırayla dene. **Önce:** `rstrui` ile elle geri yükleme noktası al.
- ☐ **Tek monitör:** Yön/konum düzenleme kapalı veya "tek ekran" uyarısı gösteriyor; hiçbir şey değişmiyor.
- ☐ **Çift monitör, okuma:** Şemadaki sıra, konum ve yönler Windows Ayarlar > Ekran ile aynı (birincil ekran işaretli).
- ☐ **Yön:** İkinci ekranı Dikey yap → 15 sn "Kalsın / Geri dön"; "Geri dön" ve hiç dokunmama (süre dolsun) ikisinde de
  eski yöne dönüyor. "Kalsın" → Ayarlar'da dikey; Değişiklikler'den geri al → yatay.
- ☐ **Konum:** İkinci ekranı sağdan sola taşı → fare geçişi yeni yerleşime uyuyor; geri alınca eski yere dönüyor.
- ☐ **Yeniden açma:** Uygulamayı kapatıp aç → yerleşim Windows'taki gerçek duruma göre okunuyor.

## 6. Her switch için test

Her satır için:

1. Ayarı aç.
2. "Nerede doğrula" sütunundaki yerde Windows'un da değişikliği gösterdiğini kontrol et.
3. Gerekiyorsa yeniden başlat.
4. Uygulamada switch'in açık göründüğünü kontrol et.
5. "Eski haline getir" de.
6. Windows'ta eski hâline döndüğünü kontrol et.

"dikkatli" ve "riskli" ayarları yalnızca sanal makinede veya geri yükleme noktasıyla dene.

| ☐ | ID | Ayar | Risk | Sonrasında | Nerede doğrula |
|---|---|---|---|---|---|
"""

UNCERTAIN = """
## 7. Emin olmadığım noktalar (özellikle dikkat et)

| Konu | Nasıl doğrulanır |
|---|---|
| AUD-001 ses geliştirmeleri registry yolu | Aç → Ayarlar > Ses > cihaz > Ses geliştirmeleri "Kapalı" görünmeli. Nahimic/Dolby/Realtek Console yüklü bilgisayarda, yeniden başlatınca açık hâle dönüyor mu? |
| QOL-009 Edge "kuruluşunuz tarafından yönetiliyor" yazısı | Aç → `edge://settings` sayfasının üstünde yazı çıkıyor mu? Kapatınca kayboluyor mu? |
| DISP-002/003 DirectX ayar satırı | Aç → Ayarlar > Ekran > Grafik > Varsayılan grafik ayarları'nda ilgili düğme açık görünmeli. Satırdaki diğer ayarlar korunmalı (regedit: `HKCU\\Software\\Microsoft\\DirectX\\UserGpuPreferences`). |
| DISP-003 24H2 varsayılanı | Hiç dokunulmamış 24H2+ sistemde uygulama "kapalı" gösterirken Ayarlar "açık" gösteriyor mu? |
| PWR-001 / CPU-* özel güç planı | Kendi oluşturduğun bir güç planındayken, yedeği olmayan bir güç ayarını kapatmaya çalış → "varsayılan değer bilinmiyor" mesajı çıkmalı, hiçbir şey değişmemeli. |
| PERF-004 Windows Home | Home sürümlü sanal makinede ayar görünüyor mu, açılınca yalnızca var olan özellik kapatılıyor mu? |
| NET-007/008 ağ kartı | Intel ağ kartlı bir bilgisayarda EEE ayarı görünüyor mu? Uygularken bağlantı birkaç saniye kopup geri geliyor mu? |
| INP-002/003/006 anında uygulama | Değişiklik oturum kapatmadan hemen hissediliyor mu? |
| Geri yükleme noktası 24 saat sınırı | 5. bölümdeki adımlar. |
| Doğrulanmamış "Ayarı aç" bağlantıları | SYS-013 (`windowsdefender://threatsettings`), PERF-002 (`ms-settings:gaming-gamedvr`), AUD-009 (`printers`), QOL-005 (`ms-settings:easeofaccess-visualeffects`): rehberdeki düğme doğru sayfayı açıyor mu? Windows 10'da da dene. |
| Windows 10 | Windows 10 sanal makinesinde 1, 3, 5. bölümleri tekrarla; yalnızca Windows 11 ayarları (Widget'lar, klasik sağ tık, Görevi sonlandır) gizli olmalı. |
| Laptop / masaüstü | Laptopta CPU-003 ve PWR-008 görünmeli, CPU-001/002 gizli olmalı. Bir masaüstü arkadaş bilgisayarında tersi. |
| PERF-004 Hyper-V / bcdedit | Kapat → yeniden başlat → `bcdedit /enum {current}` içinde `hypervisorlaunchtype Off`. Eski haline getir → `Auto`. **BitLocker açık bilgisayarda bcdedit değişikliği kurtarma anahtarı sorabilir (emin değilim)**; önce kurtarma anahtarını not al, ilk denemeyi sanal makinede yap. |
| PLC-004/005 bcdedit girdileri | Eski haline getirince ilgili satırlar `bcdedit /enum {current}`'ten kalkıyor mu? |
| PLC-016 TCP otomatik ayar | Okuma `Get-NetTCPSetting` (Internet şablonu), yazma `netsh` ile yapılıyor; ikisinin gösterdiği değer tutarlı mı? (Tutmazsa bana söyle.) |
| PERF-003 HVCI UEFI kilidi | Kuruluş ilkesi/UEFI kilidi olan bilgisayarda yeniden başlatınca ayar eski haline dönüyor mu? Uygulama bunu "doğrulanamadı" olarak gösteriyor mu? |
| PLC-027 Nihai Performans planı | Modern Standby'lı laptopta plan listede görünüyor mu, etkinleşiyor mu? Eski haline getirince önceki plana dönüp yalnızca uygulamanın oluşturduğu kopya siliniyor mu? |
| PLC-003 HPET | Aygıt Yöneticisi > Sistem aygıtları > "Yüksek duyarlıklı olay zamanlayıcısı" devre dışı / geri etkin oluyor mu? |
| AUD-001 eski yedek | Bu bilgisayarda önceki sürümden kalan AUD-001 yedeği var; Değişiklikler'de "Eski haline getir" ile temizlenebiliyor mu? |
| PWR-002 güç modu | Belgelenmemiş API (PowerSetActiveOverlayScheme) kullanılıyor; veritabanındaki `powercfg /overlaysetactive` bu Windows'ta çalışmadı. Laptopta prizdeyken "Pilde" modunu değiştirince değer kayıt defterine yazılıyor; fişi çekince gerçekten geçerli oluyor mu? |
| Servis kilit listesi | Kritik servis listesi elle hazırlandı; listede olmayan ama kapatılınca sorun çıkaran bir Windows servisi görürsen bana yaz. |
| MSI anahtarı | Aygıtta `Interrupt Management\\MessageSignaledInterruptProperties` anahtarı yoksa uygulama oluşturuyor; bazı aygıtlarda yönetici izni bile yetmeyebilir (erişim reddi mesajı çıkmalı). |
| Başlangıç klasörü | Başlangıç klasöründeki kısayolu kapatınca Görev Yöneticisi de "Devre dışı" gösteriyor mu? |
| NVIDIA yazma | Kullanıcının bilgisayarında (RTX 5070 Laptop) bir ayar yazıldı ve geri alındı: çalışıyor. Diğer ayarlar ve masaüstü kartlar denenmedi. |
| Ses biçimi yazma | Kullanıcının bilgisayarındaki Realtek "Speaker" çıkışında Windows yazmayı 0x80070491 ile reddetti (hiçbir şey değişmedi); uygulama mesaj + Ses ayarları düğmesi gösteriyor. Kayıt defteri yöntemi (değeri yazıp ses servislerini yeniden başlatmak) de etkisiz kaldı ve geri alındı. Bluetooth kulaklıkta ve USB DAC'ta dene. |
| Ses biçim listesi | Kullanımda olan cihaz (ör. çalan Bluetooth kulaklık) yalnızca şu anki biçimi destekliyor gibi görünebilir. |
| IFEO önceliği | `PerfOptions\\CpuPriorityClass` resmi olarak belgelenmemiş; değerler topluluk kaynağından. Vanguard/EAC'li oyunlarda uygulanıp uygulanmadığı bilinmiyor. |
| Bildirim susturma | `PushNotifications\\ToastEnabled=0` anında etkili oluyor mu, yoksa Gezgin yeniden başlatılmalı mı? |
| Oyun algılama (Canlı FPS, oyun kaydı) | Oyun başlatıcıdan açılınca (Steam/Riot) asıl oyun sürecini doğru yakalıyor mu? Aynı adlı başka exe'ler karışıyor mu? |
| Tepside başlatma | Windows'la başlatmada uygulama tepsi alanı hazır olmadan açılırsa simge görünmeyebilir (Qt bunu genelde bekler, doğrulanmadı). |
| PresentMon sürümü | `--v1_metrics` ile `MsBetweenPresents` sütunu okunuyor; PresentMon 2.x'in bu seçeneği desteklediği README'de yazıyor ama indirdiğin sürümle denenmedi. Ölçüm "yeterli kare yok" derse CSV'yi bana gönder. |
| Açılış süresi (olay 100) | Bu bilgisayarda yönetici olmadan Diagnostics-Performance günlüğünde kayıt bulunamadı; yönetici olarak var mı bilinmiyor. |
| DISP-001 yenileme hızı | Çoklu monitörde, G-SYNC/FreeSync açıkken ve HDMI ile bağlı TV'de yenileme hızı doğru değişiyor ve geri alınıyor mu? Sürücü bir modu listeleyip uygulamayı reddederse hata mesajı çıkmalı, ekran değişmemeli. |
| Canlı ağ değeri | Hyper-V/VPN sanal ağ kartları olan bilgisayarda indirme/yükleme iki kez sayılıyor mu (Görev Yöneticisi'ndekinin iki katı)? |
| Canlı sayaçlar okunamazsa | Performans sayaçları bozuk bir sistemde kartlarda "Canlı veriler okunamadı" yazmalı, uygulama çökmemeli. |
| PyInstaller ve Python 3.12 | `derle.bat` Python 3.12 ile sorunsuz derliyor mu? (Ben yalnızca 3.15 ile geçici bir derleme yaptım.) |

## 8. Antivirüs

- ☐ **Windows Defender taraması:** `dist\\Forevermore` klasörüne sağ tık > Microsoft Defender ile
  tara. Temiz çıkmalı.
- ☐ **İsteğe bağlı VirusTotal:** Dosyayı virustotal.com'a yükleyip kaç antivirüsün yanlış alarm
  verdiğini not et.
  - Dikkat: VirusTotal'e yüklenen dosya antivirüs şirketleriyle paylaşılır ve herkese açık hâle gelir.
- ☐ **Tek dosyayla karşılaştır:** `derle.bat -TekDosya` ile tek dosya hâlini de derle ve
  VirusTotal sonucunu karşılaştır.

## 9. Sorun bildirirken bana gönder

1. Uygulamanın kaydettiği rapor (`.txt`); kişisel bilgi içermez.
2. `logs\\forevermore.log`.
3. Hangi adımda ne beklediğini, ne olduğunu ve ekran görüntüsü.
"""


def where_to_verify(tweak):
    guide = tweak.get("rehber") or {}
    opener = guide.get("ac")
    if opener:
        return f"`{opener['hedef']}`"
    text = guide.get("kontrol") or ""
    return text[:90].replace("|", "/") + ("…" if len(text) > 90 else "")


def main():
    lines = [HEADER.rstrip("\n")]
    for tweak in DATA["ayarlar"]:
        if tweak["sinif"] != "SWITCH":
            continue
        risk = "**dikkatli**" if tweak["risk"] == "dikkatli" else tweak["risk"]
        lines.append(f"| ☐ | {tweak['id']} | {tweak['ad'].replace('|', '/')} | {risk} | "
                     f"{RESTART_TEXT.get(tweak['yeniden_baslatma_kodu'], '')} | {where_to_verify(tweak)} |")
    lines.append(UNCERTAIN)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Yazıldı: {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
