# Ekran kartı ayarları: yöntem raporu (Revizyon 2 Faz 6)

Her ayar kartında kullanılan yöntem bir rozetle yazar: **Yöntem: NVAPI**, **Yöntem: ADLX** veya
(yalnızca NVAPI'ye erişilemezse) **Yöntem: NVIDIA Profile Inspector (yedek)**.

## Özet tablo

| Ayar | Yöntem | Bu bilgisayarda |
|---|---|---|
| GPU-002…009 NVIDIA genel 3B ayarları | NVAPI DRS (kendi kodumuz) | Okuma ✔, yazma/geri alma ✔ (22.10.2026, izinle) |
| GPU-020 G-SYNC kapsamı (yeni) | NVAPI DRS `VRR_MODE` (0x1194F158) | Okuma ✔ (özelleştirilmemiş = sürücü varsayılanı); yazma denenmedi |
| GPU-013 Radeon Anti-Lag | ADLX `IADLX3DAntiLag` | Okuma ✔ (Kapalı); yazma denenmedi |
| GPU-014 Radeon Chill | ADLX `IADLX3DChill` (yalnızca aç/kapat) | Okuma ✔ (Kapalı); yazma denenmedi |
| GPU-015 Radeon Boost / Enhanced Sync | ADLX `IADLX3DBoost` / `IADLX3DEnhancedSync` | Boost okuma ✔; Enhanced Sync 880M'de "desteklenmiyor" |
| Ekran > Monitörler > Ölçekleme (NVIDIA ekran) | NVAPI `NvAPI_DISP_Get/SetDisplayConfig` | ASUS VG27WQ1B: okuma ✔ (7 = monitör, ölçekleme yok); yazma denenmedi |
| Ekran > Monitörler > Ölçekleme (AMD ekran) | ADLX `IADLXDisplayGPUScaling` + `IADLXDisplayScalingMode` | Dahili panel: okuma ✔ (GPU ölçekleme kapalı); yazma denenmedi |
| GPU-019 DDU / NVCleanstall | Aracı tools klasöründen açar (yoksa resmi indirme sayfası) | Araçlar bu bilgisayarda yok; indirme sayfası düğmesi |
| GPU-019 Güvenli Mod | `bcdedit /set {current} safeboot minimal` (yedekli) + `shutdown /r /t 15` | Denenmedi (UAC + yeniden başlatma gerekir) |
| GPU-018 MSI modu | Kayıt defteri (önceki fazdan) | Evde UAC ile denenecek |
| GPU-010 Reflex, GPU-011 Anlık Tekrar, GPU-012 DSR/NIS | Elle (oyun içi / NVIDIA App) | Herkese açık NVAPI'de karşılığı yok |

## NVIDIA (NVAPI)

`nvapi64.dll` NVIDIA sürücüsüyle gelir, uygulamaya gömülmez. Fonksiyon kimlikleri `nvapi_interface.h`,
ayar kimlikleri `NvApiDriverSettings.h`, yapılar `nvapi.h` (NVIDIA/nvapi, MIT).

- **G-SYNC kapsamı (GPU-020):** `VRR_MODE`: 0 kapalı, 1 yalnızca tam ekran (varsayılan), 2 tam ekran ve
  pencere. Monitörde G-SYNC'in kendisini açma (ekran başına ayar) herkese açık DRS ayarı değildir;
  NVIDIA Denetim Masası'nda kalır.
- **Ölçekleme:** `NV_DISPLAYCONFIG_PATH_ADVANCED_TARGET_INFO.scaling`. nvapi.h'ye göre "Balanced"
  değerlerinde (1, 6, 7) kart en yakın modu gönderir ve ölçeklemeyi monitör yapar (eski adı
  `NV_SCALING_MONITOR_SCALING`); "Force GPU" değerlerinde (2, 3, 5, 8) ölçeklemeyi ekran kartı yapar.
  Yazarken yapılandırmanın geri kalanı okunduğu gibi geri yazılır, yalnızca bu alan değişir
  (`NV_DISPLAYCONFIG_SAVE_TO_PERSISTENCE`). Değişiklikten sonra Windows'taki gibi 15 saniyelik
  "değişikliği koru" onayı sorulur; onaylanmazsa eski değere dönülür.
- Yapı boyutları (64 bit, pack 8): NV_TIMING 96, ADVANCED_TARGET_INFO_V1 128, PATH_INFO_V2 48 bayt;
  sürücü bu sürümleri kabul etti (okuma ✔). `tests/test_surucu.py` boyutları sabitler.
- Eklenmeyenler: FXAA, ortam perdeleme (AO), üçlü arabellek (OpenGL), anizotropik filtreleme. Hepsinin
  sürücü varsayılanı zaten "uygulama denetler / kapalı"; oyunlarda performansa olumlu etkileri yok,
  bu yüzden kart kalabalığı yapılmadı. Düşük gecikme "Ultra" ve dijital canlılık herkese açık NVAPI'de yok.

## AMD (ADLX)

`amdadlx64.dll` AMD Software sürücüsüyle gelir (bu bilgisayarda var), uygulamaya gömülmez. Arabirim
sıraları AMD'nin resmi deposundaki C başlıklarından alındı (GPUOpen-LibrariesAndSDKs/ADLX:
ISystem.h, I3DSettings.h, IDisplays.h, IDisplaySettings.h, ADLXDefines.h; MIT). Dışa aktarılan
fonksiyonlar (ADLXQueryFullVersion, ADLXInitialize, ADLXTerminate) bu bilgisayardaki DLL'de doğrulandı.

- Chill'in en düşük / en yüksek FPS değerleri, AFMF ve oyun başına profiller AMD Software'de kalır.
- Ölçekleme değeri: 0 = monitör (GPU ölçekleme kapalı), 1/2/3 = GPU ölçekler, sırasıyla en-boy oranını
  koru / tam panel / ortala (`ADLX_SCALE_MODE` + 1).
- ADLX ekranın Windows adını (DISPLAYn) vermediği için eşleştirme: önce EDID adı, o tutmazsa "AMD kartında
  tek ekran" durumu. Emin olunamazsa ölçekleme satırı gösterilmez (yanlış ekrana yazılmaz).

## DDU ve NVCleanstall

İkisi de ücretsiz ama programa **gömülmez**. Kullanıcı resmi sayfalarından indirip
`tools\DDU` ve `tools\NVCleanstall` klasörlerine koyar (klasör adı büyük/küçük harf duyarsız).
Klasörde yoksa kart resmi indirme sayfasını açar:

- DDU: <https://www.wagnardsoft.com/display-driver-uninstaller-DDU->
- NVCleanstall: <https://www.techpowerup.com/download/techpowerup-nvcleanstall/>

**Komut satırı araştırması:** DDU'nun eski sürümlerinde topluluk tarafından bildirilen `-silent`,
`-cleannvidia` gibi seçenekler var ama resmi, güncel ve kararlı bir belge bulunamadı; seçeneklerin
sürümler arasında değiştiği bildiriliyor. NVCleanstall'ın belgelenmiş bir komut satırı kullanımı yok.
Sürücüyü kaldıran bir aracı belgesiz seçeneklerle sessizce çalıştırmak riskli olduğu için uygulama
yalnızca aracın arayüzünü açar.

## Güvenli Mod (DDU için)

DDU sürücüyü Güvenli Modda kaldırmayı önerir. Kartta "Güvenli Modda yeniden başlat":

1. Birinci uyarı: bilgisayar 15 saniye sonra yeniden başlar, açık programlar kapanır, Güvenli Modda
   internet ve ekran kartı sürücüsü çalışmaz.
2. İkinci uyarı (son onay): güvenli önyükleme siz kapatana kadar açık kalır; nasıl kapatılacağı
   (uygulamadan "Normal başlatmaya dön" veya Win+R > msconfig > Önyükleme).
3. İkisi onaylanırsa `safeboot minimal` yazılır (yedekli, Değişiklikler sayfasında görünür), sonra
   `shutdown /r /t 15`.

Geri alma: kartta "Normal başlatmaya dön" (veya Değişiklikler > Eski haline getir) `safeboot` değerini
siler. Güvenli önyükleme açık kaldıkça uygulamanın üstünde uyarı şeridi görünür; Güvenli Moddayken
(GetSystemMetrics SM_CLEANBOOT) ayrı bir şerit "şu an Güvenli Moddasınız" der.

## Evde denenecek (UAC ve kullanıcı onayıyla)

AMD Anti-Lag aç/kapat, NVIDIA ve AMD ölçekleme yazma (ekran kararabilir; 15 sn onayla geri döner),
G-SYNC kapsamı yazma, Güvenli Mod aç → yeniden başlat → Normal başlatmaya dön.

## NVIDIA ayarları: gerçek yazma denetimi (27 Ekim 2026)
RTX 5070 Laptop GPU, yönetici olmadan (UAC yok), uygulamanın `nvidia.set_setting` işleviyle, her ayar
için: oku → farklı değer yaz → geri oku → özgün değere dön → doğrula. Sonunda tüm değerler başlangıçla aynı.
Geri yükleme noktası alınamadı (yönetici gerekir); değişiklik yalnızca sürücü profilinde ve anında geri alındı.

| Ayar | Kimlik | Sonuç |
|---|---|---|
| GPU-002 Düşük Gecikme | 0x007BA09E | yazıldı, okundu, geri alındı |
| GPU-003 Güç yönetimi | 0x1057EB71 | aynı (1 = Maksimum performans) |
| GPU-004 Doku filtreleme | 0x00CE2691 | aynı |
| GPU-005 Shader önbelleği | 0x00AC8497 | aynı (varsayılana dön / sınırsız) |
| GPU-006 G-SYNC kombinasyonu | 0x00A879CF | aynı |
| GPU-007 FPS sınırı | 0x10835002 | aynı (60 FPS denendi) |
| GPU-008 İş parçacıklı opt. | 0x20C1221E | aynı |
| GPU-009 Yenileme hızı | 0x0064B541 | aynı |
| GPU-020 G-SYNC kapsamı | 0x1194F158 | aynı |
| PLC-026 Üçlü arabellek | 0x20FDD1F9 | aynı (yalnızca OpenGL) |

Denenmedi / uygulamadan yapılamaz: GPU-010 (Reflex oyun içi), GPU-011 (Anlık Tekrar, GeForce Experience),
GPU-012 (DLDSR/DSR/NIS) ve G-SYNC'in monitör için açılması. NVIDIA Profile Inspector gerekmedi; NPI'nin
Reference.xml dosyası bu kimlikleri içermiyor (NPI bunları sürücüden okuyor), bu yüzden değer listeleri
yazma-okuma testiyle doğrulandı. NPI yedek yöntemi kodda duruyor, dağıtılmıyor.
Sürücünün gerçekten kabul ettiği değer ile oyunda etkisi ayrı şeydir; oyun içi etki ölçülmedi.

### Eklenenler: NIS ve NVIDIA Uygulaması katmanı (GPU-021, GPU-022)
Kimlikler NVIDIA Profile Inspector'ın Reference.xml sözlüğünden (resmi başlıkta yok).
- **GPU-021 NIS (0x10444444):** yönetici olmadan yazıldı, okundu, geri alındı. Oyundaki etkisi ölçülmedi;
  oyunda çalışması için NVIDIA Uygulaması'nda da Görüntü Ölçekleme açık olmalı.
- **GPU-022 Overlay yasağı (0x90DE9159):** yönetici olmadan sürücü reddetti (NVAPI -137, yetki). Yönetici (UAC)
  ile yazıldı, geri okundu (1) ve başlangıç değerine geri alındı (Kullanıcı yönetici terminalinde çalıştırdı, 27 Ekim 2026).
  Katmanın gerçekten kalktığı (Alt+Z) ve FPS etkisi **ölçülmedi**.


## Bellek (VRAM): yalnızca OKUMA (6 Kasım 2026)

Hiçbir şey yazılmaz; güç sınırı DEĞİŞTİRİLMEZ (yazma ancak Kubilay onayıyla ayrı iş) ve artık OKUNMAZ da (aşağıda).

| Değer | Kaynak | Nerede görünür | Bu bilgisayarda (RTX 5070 Laptop + Radeon 880M) |
|---|---|---|---|
| Toplam ekran belleği | DXGI `DedicatedVideoMemory` | PC Detayları kart satırı (eskiden de vardı), Özet "Ekran kartı" kutusu | okundu: 7,7 GB (RTX), 0,5 GB (880M) |
| Kullanılan ekran belleği | Windows sayacı `GPU Adapter Memory > Dedicated Usage` (kart, LUID ile DXGI'ye eşlenir) | Özet > Canlı sistem durumu > Ekran kartı: "Ekran kartı belleği: 1,5 / 7,7 GB" | okundu (RTX'te 1,43 GB; nvidia-smi 1453 MiB ile uyuştu) |
| Güç sınırı | ÇIKARILDI (6 Kasım 2026): `nvidia-smi enforced.power.limit` | satır yok | aynı kartta 83 → 79 → 77 W okundu (pil/ısı/Dynamic Boost); gerçek sınır olmayabilir, yanlış bilgi vermemek için kaldırıldı |
| Güç kullanımı (anlık W) | uygulamada OKUNMUYOR | satır yok | nvidia-smi `power.draw` bu kartta çalışıyor (32 W) ama saniyede bir süreç açmak doğru değil; NVML (nvml.dll) ile okunabilir, kodlanmadı (karar bekler) |

**Okunamadı / kodlanmadı (satır gizlenir, uydurma yok):**
- **AMD Radeon 880M (ADLX, AMD Software 32.0.22042.1):** güç sınırı ve güç kullanımı OKUNMUYOR. Bu iş için ADLX'te performans izleme (IADLXGPUMetrics) ve elle ayar arabirimleri gerekir; bu fazda eklenmedi ve vtable sıraları doğrulanmadı. PC Detayları'nda AMD kartında güç satırı çıkmaz.
- **NVIDIA `power.limit`** (yazılabilir sınır) bu kartta `[N/A]`; uygulama hiçbir güç sınırı değeri okumuyor. Sürücü 621.01.
- **Tümleşik kartlar (Radeon 880M, 512 MB ayrılmış):** bellek paylaşımlıdır; kullanım ayrılmış miktarı aşabilir. Kullanılan > toplam ise Özet yalnızca kullanılanı yazar; toplamı 1 GB'tan küçük kartta "dolmak üzere" uyarısı HİÇ verilmez.
- **Intel / diğer kartlar:** denenmedi (bu bilgisayarda yok). Sayaç ve DXGI genel olduğu için çalışması beklenir ama doğrulanmadı.

**Oyun içi uyarı ("Ekran kartı belleği dolmak üzere (%NN)"):** Ayarlar'da tek anahtar "Ekran kartı belleği uyarısı",
varsayılan KAPALI. Yalnızca canlı FPS çalışırken (oyun sürüyor ve Canlı FPS açık) Oyunlar sayfasındaki canlı FPS
satırının altına tek satır eklenir; %90'ın ÜSTÜNDE (kart bellek kullanımı / ayrılmış bellek). Açılır pencere, ses,
bildirim, dosyaya yazma, ağ yok. Okuma yalnızca bu oturumda, tek sayaçla, saniyede bir; oturum bitince kapanır.
Gerçek oyunda DENENMEDİ (EL_TESTLERI "Ekran kartı belleği").
