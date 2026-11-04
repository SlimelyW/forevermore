# Ekran kartı ve ses ayarları: yöntem raporu (Revizyon Faz 4b)

## NVIDIA sürücü ayarları

**Yöntem:** NVIDIA'nın kendi NVAPI kütüphanesi (`nvapi64.dll`, sürücüyle gelir), ctypes ile
doğrudan çağrılıyor (`app/engine/nvidia.py`). Ayarlar NVIDIA Denetim Masası'ndaki
"Genel ayarlar"ın karşılığı olan geçerli genel profile yazılıyor.

**Kaynak ve lisans:** Fonksiyon kimlikleri (`nvapi_interface.h`), ayar kimlikleri ve
değerleri (`NvApiDriverSettings.h`) ve `NVDRS_SETTING` yapısı (`nvapi.h`) NVIDIA'nın
resmi deposundan alındı: <https://github.com/NVIDIA/nvapi> (MIT lisansı). Uygulamaya
NVIDIA dosyası gömülmüyor; kodda yalnızca sabit sayılar var.

**Bu bilgisayarda doğrulanan (yalnızca OKUMA):** NVAPI başlatıldı, yapı boyutu 12320 bayt
(sürüm 0x13020). Okunan genel ayarlar NVIDIA Denetim Masası'ndakilerle tutarlı:
düşük gecikme "Açık", dikey senkronizasyon "Kapalı", gölgelendirici önbelleği
"Sınırsız".

**Yazma testi (kullanıcının izniyle, 22.10.2026, önce geri yükleme noktası alındı):** "Doku
filtreleme - Kalite" genel ayarı Yüksek performans (20) olarak yazıldı, geri okununca 20 ve
"özelleştirilmiş" göründü; "Eski haline getir" ile yeniden sürücü varsayılanına (özelleştirilmemiş)
döndü. **NVIDIA yazma ve geri alma bu bilgisayarda çalışıyor.**

| Ayar | Kendi kodumuz (NVAPI) | Not |
|---|---|---|
| GPU-002 Düşük gecikme modu | ✔ Kapalı / Açık | "Ultra" değeri herkese açık NVAPI'de yok |
| GPU-003 Güç yönetimi modu | ✔ Optimum / Uyarlamalı / Maksimum | Oyun başına ayar Faz 5'te |
| GPU-004 Doku filtreleme kalitesi | ✔ 4 değer | |
| GPU-005 Gölgelendirici önbelleği | ✔ yalnızca Varsayılan / Sınırsız | Diğer boyutların birimi belgelenmemiş |
| GPU-006 Dikey senkronizasyon | ✔ Uygulama / Açık / Kapalı | G-SYNC açma: Denetim Masası (rehber) |
| GPU-007 Maksimum kare hızı | ✔ Kapalı / 60…237 FPS | |
| GPU-008 İş parçacıklı optimizasyon | ✔ Otomatik / Açık / Kapalı | |
| GPU-009 Tercih edilen yenileme hızı | ✔ Uygulama / Mevcut en yüksek | |
| Dijital canlılık | ✘ | Herkese açık NVAPI'de fonksiyonu yok (aşağıya bakın) |
| GPU-010 Reflex, GPU-011 Anlık Tekrar, GPU-012 DSR/NIS | ✘ | Oyun içi / NVIDIA App ayarı; rehber olarak kaldı |

**Yedek yöntem: NVIDIA Profile Inspector (NPI).** Lisansı MIT
(<https://github.com/Orbmu2k/nvidiaProfileInspector>). README'de `.nip` içe aktarma ve
`-silentImport` seçeneği belgelenmiş. Kaynak kodda (`App.xaml.cs`) doğruladığım önemli nokta:
**yalnızca `-silentImport` verilirse içe aktarma "Replace" modunda çalışıyor ve profili önce
sıfırlıyor.** Bu yüzden uygulama `-silentImport -mergeImport` kullanıyor. NPI uygulamaya
gömülmüyor; kullanıcı `tools\nvidiaProfileInspector.exe` olarak koyarsa ve NVAPI'ye
erişilemezse kartta "NVIDIA Profile Inspector ile uygula" düğmesi çıkıyor. Bu yol:
- önceki değeri okuyamadığı için **geri alınamaz** (yalnızca işlem geçmişine yazılır),
- doğrulanmadı: `.nip` dosyasında genel profil adı ("Base Profile") ve eski NPI
  sürümlerinin `-mergeImport` desteği.

## Ses

**Ses geliştirmeleri (AUD-001), cihaz başına:** Kayıt defterindeki `FxProperties` değeri
(Faz 2'de düzeltilen erişim izniyle) + Windows Ses servisinin yeniden başlatılması.

**Örnekleme hızı ve bit derinliği (AUD-002):** NirSoft svcl.exe kullanılmıyor (ticari lisans).
Kendi kodumuz, Windows'un Ses denetim masasının kullandığı COM arabirimleriyle
(`app/engine/audio.py`):
- Desteklenen biçimler: `IAudioClient::IsFormatSupported` (özel mod). Belgelenmiş API, yalnızca sorar.
- Şu anki biçim: `IPolicyConfig::GetDeviceFormat`. Bu bilgisayarda kayıt defterindeki biçimle
  aynı sonucu verdi (doğrulandı, salt okunur).
- Yazma: `IPolicyConfig::SetDeviceFormat`. **Belgelenmemiş** bir arabirim (Microsoft varsayılan
  biçimi değiştirmek için herkese açık bir API yayımlamıyor).
- **Yazma testi (kullanıcının izniyle, 22.10.2026):** Bu bilgisayardaki "Speaker" çıkışında
  48000 Hz / 16 bit → 24 bit denendi. Windows her biçim düzeni ve karıştırıcı biçimi kombinasyonunda
  `0x80070491` (ERROR_NO_MATCH) ile reddetti; **hiçbir şey değişmedi**. Nedenini kesin bilmiyorum.
  Uygulama artık bu durumda açık bir mesaj gösteriyor ve "Ses ayarlarını aç" (mmsys.cpl) düğmesi
  sunuyor. Başka cihazlarda (USB DAC, Bluetooth) sonuç farklı olabilir.
- **Kayıt defteri yöntemi de denendi (kullanıcının izniyle, aynı gün):** `PKEY_AudioEngine_DeviceFormat`
  değeri 48000 Hz / 24 bit olarak yazıldı (yazma izni vardı), Windows Ses servisi ve
  AudioEndpointBuilder yeniden başlatıldı; Windows cihazı yine 48000 Hz / 16 bit bildirdi, yani yeni
  değer kullanılmadı. Değer hemen eskisine geri yazıldı (bayt bayt aynı). Yeniden başlatmadan sonra
  geçerli olup olmayacağı denenmedi. Bu yöntem uygulamaya eklenmedi.

## Gece ışığı

Windows'un gece ışığını açıp kapatmak için belgelenmiş bir API'si yok. Durum,
kayıt defterinde biçimi belgelenmemiş bir ikili veride tutuluyor; onu elle değiştirmek
ayarı bozabilir. Bu yüzden rehber olarak kaldı ("Ayarı aç" Ayarlar > Gece ışığı'nı açıyor).

## Dijital canlılık

- **NVIDIA:** Herkese açık NVAPI'de dijital canlılık fonksiyonu yok. Topluluk projeleri,
  NVIDIA'nın yayımlamadığı fonksiyon kimlikleriyle bunu yapıyor. Bu kimlikleri doğrulayacak
  resmi bir kaynak olmadığı ve yanlış kimlik sürücüde başka bir fonksiyonu çağırabileceği için
  uygulanmadı.
- **AMD:** AMD'nin ADLX/ADL kütüphanesi gerekir; bu fazda eklenmedi.
- **Laptop notu:** Bu bilgisayar gibi hibrit grafikli laptoplarda dahili ekranı genellikle
  dahili GPU sürer; NVIDIA ayarları o ekranda etkisiz olabilir.

## AMD Radeon ayarları (GPU-013/014/015)

Radeon Anti-Lag, Chill, Boost vb. ayarlar AMD'nin ADLX kütüphanesi (C++) olmadan
programla yapılamıyor; rehber olarak kaldı.
