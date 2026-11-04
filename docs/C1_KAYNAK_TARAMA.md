# C1 — Kaynak tarama (ayar fikirleri)

Tarih: 2026-10-27. Yöntem: sayfalar WebFetch ile okundu (özetleyici küçük model üzerinden; ham dosya değil). Kod/açıklama kopyalanmadı; yalnızca ayar adı, kayıt defteri değer adı gibi gerçekler ve kendi cümlelerim var.
Bizim veri: data/tweaks_app.json, 150 ayar (SYS, PERF, GPU, CPU, PWR, NET, INP, AUD, QOL, DISP, PLC).

## Kaynak başına bulunan ayar ve erişim notları

| Kaynak | Bulunan | Erişim / güvenilirlik |
|---|---|---|
| CTT WinUtil `config/tweaks.json` (raw GitHub) | 68 giriş (39 temel/gelişmiş tweak, 25 tercih anahtarı, 4 düğme/açılır liste) | Tam erişildi. Dosya özetleyici modelden geçti; kayıt yolları kısaltılmış, uzun GUID'ler doğrulanmadı. Liste eksik kalmış olabilir. |
| HellzerG Optimizer | ~20 özellik (yalnızca README düzeyi) | github.com/hellzerg/optimizer arşivlenmiş, yerine optimizerNXT. Tek tek kayıt değeri okunmadı; kaynak koddaki gerçek ayar listesi (Options/JSON) taranmadı. |
| Nexus Optimizer (getnexus.cc/tool) | ~20 başlık | Yalnızca pazarlama sayfası; tek tek ayarın içeriği, değerleri, kanıtı YOK. Uygulama/lisans gerekir, indirilmedi. |
| Hone (hone.gg/tr) | 0 adlandırılmış ayar | Sayfa yalnızca kategori anlatıyor (Windows, GPU, oyun, ağ, arka plan). Ücretsiz 10 / Premium ayar listesi uygulama içinde; erişilemedi. Uydurulmadı. |

Genel not: Nexus/Hone/HellzerG için aşağıdaki maddeler "iddia" düzeyindedir (tek kaynak, mekanizma belirtilmemiş); etkisi kanıtlanmadan eklenmemeli.

## A) Bizde olmayan, eklemeye aday ayarlar

Risk: düşük/orta/yüksek. Öneri: ekle / araştır.
Kanıt URL'leri: CTT = https://github.com/ChrisTitusTech/winutil/blob/main/config/tweaks.json (yalnızca "bu kaynakta var" kanıtıdır, etkiyi kanıtlamaz); etki için Microsoft belgesi gerekçesi ayrıca yazıldı (belge adı; URL doğrulanmadı).

| Ad | Ne yapar | Risk | Kaynak | Kanıt / gerekçe | Öneri |
|---|---|---|---|---|---|
| Etkinlik Geçmişi (Activity Feed) kapat | Windows'un yaptığınız işlemleri kaydedip yayınlamasını durdurur (EnableActivityFeed, PublishUserActivities, UploadUserActivities ilkesi) | düşük | CTT | CTT tweaks.json; Microsoft Group Policy belgesi (System ilkeleri) | ekle |
| Konum hizmeti (lfsvc) kapat | Konum servisini ve konum izni anahtarını kapatır | düşük | CTT | CTT tweaks.json; laptopta Hava durumu/Bul aygıtımı etkilenir | ekle (gizlilik, performans değil) |
| Klasör türü otomatik algılamayı kapat (Shell\Bags temizle + AllFolders FolderType) | Explorer'ın büyük klasörleri içeriğe bakıp tür tahmin etmesini engeller; çok dosyalı klasörlerde açılış takılması azalır | düşük | CTT | CTT tweaks.json; etki yaygın forum bilgisi, ölçülmedi | ekle (ölçümle) |
| Depolama Algısı (Storage Sense) kapat | Otomatik disk temizliğini kapatır (StoragePolicy 01) | düşük | CTT | CTT tweaks.json | araştır (performans etkisi yok) |
| Ayrılmış depolama (Reserved Storage) kapat | DISM ile ~7 GB ayrılmış alanı geri verir | orta (güncelleme boş alan gerektirir) | CTT | CTT tweaks.json | araştır |
| Aygıt meta verisini ağdan indirme (PreventDeviceMetadataFromNetwork) | Aygıt için üretici uygulaması/simge indirmeyi keser | düşük | CTT | CTT tweaks.json | ekle (gizlilik/debloat) |
| WPBT yürütmeyi engelle (DisableWpbtExecution) | Üretici yazılımının Windows açılışında dosya enjekte etmesini kapatır | orta (bazı OEM araçları/ kurtarma bozulabilir) | CTT | CTT tweaks.json; Microsoft WPBT belgesi | araştır |
| Donanım saatini UTC yap (RealTimeIsUniversal) | Windows+Linux çift önyüklemede saat kaymasını giderir | orta (tek Windows'ta saat 3 saat kayar) | CTT, HellzerG | CTT tweaks.json; HellzerG README "UTC" | araştır (yalnızca çift önyükleme algılanırsa) |
| Uzun yol desteği (LongPathsEnabled) | 260 karakter yol sınırını kaldırır | düşük | CTT | CTT tweaks.json; Microsoft "Maximum Path Length" belgesi | ekle |
| Ayrıntılı BSoD (DisplayParameters) | Mavi ekranda hata parametrelerini gösterir | düşük | CTT | CTT tweaks.json | ekle (teşhis) |
| Ayrıntılı oturum açma iletileri (VerboseStatus) | Açılışta ne yapıldığını yazar | düşük | CTT | CTT tweaks.json | ekle (teşhis, düşük değer) |
| Gizli dosyaları göster (Hidden) | Explorer'da gizli dosyaları açar | düşük | CTT | CTT tweaks.json | ekle (QOL-001 ile aynı grupta) |
| Karanlık mod | Uygulama/sistem temasını koyu yapar | düşük | CTT | CTT tweaks.json | ekle (QOL) |
| Görev çubuğu: hizalama, arama simgesi, Görev Görünümü düğmesi, widget/sohbet düğmeleri | Görev çubuğu düzenini kısar | düşük | CTT | CTT tweaks.json | ekle (QOL, toplu) |
| Pil yüzdesi göster | Tepsi simgesinde yüzde | düşük | CTT | CTT tweaks.json | ekle (laptop) |
| Kilit ekranını atla (NoLockScreen) / oturum açma bulanıklığı kapat | Açılışta bir adım ve GPU efekti azalır | düşük | CTT | CTT tweaks.json | ekle (küçük) |
| Pencere yakalama (snapping) / Her zaman görünür kaydırma çubuğu / NumLock başlangıcı | Kullanım rahatlığı anahtarları | düşük | CTT | CTT tweaks.json | ekle (QOL) |
| Ana sayfa ve Galeri'yi Explorer'dan kaldır | Gezinti panelinde Home/Gallery gizlenir | düşük | CTT | CTT tweaks.json | araştır |
| Teredo kapat | Eski tünel protokolünü kapatır (DisabledComponents ve netsh) | düşük | CTT | CTT tweaks.json | araştır (oyun NAT'ında Xbox ağı etkilenebilir) |
| Standby ağ bağlantısı (S0 ağ) / S3 uyku (PlatformAoAcOverride) | Modern Standby davranışını değiştirir | orta-yüksek (uyku/uyanma sorunları) | CTT | CTT tweaks.json | ekleme |
| MMCSS dışı: Zamanlanmış görev ayarı (telemetri görevlerini kapat) | Telemetri/CEIP zamanlanmış görevlerini devre dışı bırakır | düşük-orta | Nexus, Hone (iddia) | getnexus.cc/tool başlığı; hangi görevler belirtilmemiş | araştır (görev listesi bizim derlememiz gerekir) |
| Office telemetrisi kapat | Office 2016+ tanılama anahtarları | düşük | HellzerG | HellzerG README | araştır (kayıt anahtarları kaynakta okunmadı) |
| Windows Update dışında: CscService / MapsBroker / StorSvc servisleri | Çevrimdışı dosyalar, harita ve depolama servisi başlangıç türünü Manuel/Kapalı yapar | orta | CTT | CTT tweaks.json | araştır (ölçülebilir fayda belirsiz) |
| Edge/Brave ilke temizliği | Edge/Brave telemetri ve öneri ilkeleri | düşük | CTT | CTT tweaks.json | araştır (QOL-009 kısmen kapsıyor) |
| Disk Temizleme çalıştır (cleanmgr + DISM bileşen temizliği) | Güncelleme artıklarını siler | düşük | CTT | CTT tweaks.json | araştır (PLC-023 ile çelişmesin) |
| Bildirim merkezini tamamen kapat | Bildirim + takvim açılır penceresini devre dışı | orta (uyarılar kaçar) | CTT | CTT tweaks.json | ekleme (QOL-006 Rahatsız Etme yeterli) |

Şu ayarlar zaten VAR sayıldı (aynı iş): Telemetri/DiagTrack (SYS-004), WerSvc (SYS-010), Hiber (SYS-009), Widget/Copilot/Recall (SYS-011), Arka plan uygulamaları (SYS-007), Teslim İyileştirme (NET-005), Oyun Modu (PERF-001), MPO (DISP-005), Fare ivmesi (INP-002), Yapışkan tuşlar (INP-007), Sağ tık (QOL-002), Uzantılar (QOL-001), Bing arama (QOL-003), Görevi sonlandır (QOL-007), Başlat önerileri (QOL-008), Görsel efektler (PERF-005), Ultimate plan (PWR-001), Tüketici özellikleri (QOL-008'e yakın; tam eşleşme doğrulanmadı), HPET/bcdedit (PLC-003/004), IPv6 (PLC-015), SvcHost bölme (PLC-006), debloat (PLC-022).

## B) Donanım/oyun ayarları: kaynak iddiası var, kanıt YOK (araştır)

| Ad | Ne yapar (iddia) | Risk | Kaynak | Not | Öneri |
|---|---|---|---|---|---|
| Otomatik kayıt (Autologger) kapatma | Tanılama olay izleme oturumlarını kapatır | orta (teşhis zorlaşır) | Nexus, Hone | Sadece başlık; hangi oturumlar belirtilmemiş | araştır |
| Kesme yönlendirme (Interrupt steering) / Aygıt benzeşimi (device affinity) | Aygıt kesmelerini belirli çekirdeklere atar | orta | Nexus | Bizde MSI var (GPU-018), affinity yok; fayda kanıtı yok | araştır |
| NVMe güç kısıtlaması | NVMe güç durumlarını ayarlar | orta | Nexus | Yalnızca başlık | araştır |
| Donanım boşta durumları (idle states) | İşlemci C-state kapatma (Windows tarafı) | orta (ısı) | Nexus | CPU-008 BIOS tarafını kapsıyor | araştır |
| Segment Heap ayarı | Heap yöneticisini oyun exe'si için değiştirir | orta | Nexus | Mekanizma belirtilmemiş | araştır |
| DSCP ağ işaretleme | Oyun paketlerini QoS ile işaretler | düşük | Nexus | Genelde yalnızca ev ağında/yönlendiricide anlamlı; ISS işaretleri siler (PLC tarafı: yaygın bilgi, tek kaynak değil ama doğrulanmadı) | araştır |
| Arena Modu: arka plan süreçlerini sonlandırma / bellek temizliği / çekirdek benzeşimi | Oyun sırasında süreç kapatır, RAM boşaltır | orta | Nexus, Hone | RAM temizliği zaten PLC-001 (placebo); süreç kapatma veri kaybı riski | araştır (yalnızca kullanıcı seçimli liste) |

## C) EKLEME ÖNERİLMEZ

| Ad | Neden | Kaynak |
|---|---|---|
| Snap Tap / null bind | Oyun ve anti-cheat tarafından hile sayılabilir, hesap yasağı riski; tweak değil oyun avantajı | Nexus |
| Edge'i zorla kaldır (RemoveEdge) | WebView2 ve birçok uygulama bozulabilir; güncellemede geri gelir | CTT |
| OneDrive'ı kaldır + klasöre erişim reddi (ACL) | Veri erişimi kaybı riski, geri alma zor | CTT |
| BitLocker'ı kapat | Güvenlik düşürür, şifre çözme saatlerce sürer | CTT |
| IPv6'yı kapat (DisabledComponents=255) | PLC-015'te zaten placebo/zararlı işaretli | CTT |
| Çoğu hosts engeli: Adobe sunucuları | Lisans/oturum doğrulamasını bozar; hosts dosyasına kalıcı yazma | CTT |
| Razer/Logi yükleyici engeli (ACL) | Sürücü/yazılım kurulumunu sessizce bozar | CTT |
| Mağaza arama veritabanı (store.db) ACL reddi | Dosya izinlerini bozar; güncellemede sorun | CTT |
| Güncellemeleri durdurma, Defender kapatma | PLC-020/021 ile aynı, zararlı | HellzerG |
| O&O ShutUp10++ indir/çalıştır | Üçüncü parti, lisans/güvenlik denetimi gerekir | CTT |
| Toplu "oyun hızlandırıcı/FPS booster" / RAM boşaltıcı | PLC-024/001 placebo | Nexus, Hone |
| Telemetri/gizlilik iddiası taşıyan "hepsi bir arada" gizlilik ayarları | Bizim ilkemiz: telemetri/kişisel veri yok; yalnızca tek tek, açık, geri alınabilir ayar olarak değerlendir | tümü |

## Doğrulanmamış noktalar
- CTT listesi özetleyici modelden geçti; kayıt anahtarı yollarını eklemeden önce ham dosyayı doğrudan oku.
- HellzerG yalnızca README düzeyinde; asıl ayar listesi optimizerNXT / arşiv kaynak kodunda.
- Nexus ve Hone ayrıntısı uygulamada; etkileri kanıtsız.
- "Tüketici özellikleri" ve "Aktivite geçmişi"nin bizde kısmen karşılığı olup olmadığı tweaks_app.json'daki `islem` alanlarına bakılarak doğrulanmadı (yalnızca ad/açıklama karşılaştırıldı).
