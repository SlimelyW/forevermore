# Ekran ayarları: yöntem ve test raporu (Revizyon 2 Faz 3)

## Monitör adları (EDID)

**Yöntem:** Windows'un belgelenmiş ekran yapılandırma arabirimi: `QueryDisplayConfig` +
`DisplayConfigGetDeviceInfo` (`DISPLAYCONFIG_TARGET_DEVICE_NAME`). Windows monitörün adını
EDID'den okuyup `monitorFriendlyDeviceName` alanında verir; aynı yapı EDID üretici ve ürün kodunu,
bağlantı türünü (HDMI, DisplayPort, dahili) de içerir (`app/scan/displays.py`).

**Ad yoksa uydurulmaz:** EDID'de ad tanımı olmayan ekranlar (çoğu dahili laptop paneli)
"Dahili ekran (üretici, kod)" veya "Ekran N (üretici, kod)" olarak gösterilir. Üretici adı yalnızca
bilinen EDID üretici kodları tablosundan gelir (ör. AUO → AU Optronics).

**Bu bilgisayarda (salt okunur):**

| Windows ekranı | Gösterilen ad | Bağlantı | Süren kart |
|---|---|---|---|
| DISPLAY1 | Dahili ekran (AU Optronics, AUO 56AD) | dahili | AMD Radeon 880M |
| DISPLAY6 | ASUS VG27WQ1B | HDMI | NVIDIA RTX 5070 Laptop GPU |

Ekran numaraları (DISPLAYn) yeniden başlatınca değişebilir. Bu yüzden her ekran değişikliği
kalıcı monitör yolunu da saklar; geri alırken önce o yoldan şu anki ekran bulunur.

## Çözünürlük + yenileme hızı

**Yöntem:** `EnumDisplaySettings` (desteklenen modlar) ve `ChangeDisplaySettingsEx` (önce
`CDS_TEST`, sonra `CDS_UPDATEREGISTRY`). Yalnızca sürücünün listelediği modlar seçilebilir. Ekran
modu değişince 15 saniyelik "Kalsın / Geri dön" penceresi çıkar; seçim yapılmazsa önceki moda dönülür.

**Yazma testi (kullanıcının izniyle, 23.10.2026):** ASUS VG27WQ1B 2560x1440 @ 144 Hz → 120 Hz →
okunan 120 Hz → geri 144 Hz. Ayrıca 1920x1080 @ 144 Hz'e geçip geri dönüldü. Son durum başlangıçla
aynı. **Çalışıyor.**

## Windows ölçeği (%)

**Yöntem:** `DisplayConfigGetDeviceInfo` / `DisplayConfigSetDeviceInfo` ile **belgelenmemiş** tür
(-3 okuma, -4 yazma). Windows'un Ayarlar uygulamasının ve açık kaynak araçların (ör. SetDPI, MIT)
kullandığı yoldur; değer önerilen ölçeğe göre basamak olarak gelir. Windows sürümüyle değişebilir.

**Yazma testi (aynı gün):** VG27WQ1B %100 → %125 → okunan %125 → geri %100. **Çalışıyor.**

## Ölçekleme modu (GPU mu, monitör mü)

**Denendi, çalışmadı; uygulamada YOK.** Windows'un belgelenmiş `SetDisplayConfig` yolu
(`DISPLAYCONFIG_PATH_TARGET_INFO.scaling`) hem yerel çözünürlükte hem 1920x1080'de hatasız döndü
ama mod her seferinde "kimlik" (monitör ölçekliyor) olarak kaldı. Bu ayar ekran kartı sürücüsünün
kendi ayarıdır (NVIDIA Denetim Masası "Ölçeklendirmeyi şurada gerçekleştir", AMD "GPU Ölçekleme");
Faz 6'da her kartın kendi kütüphanesiyle eklendi: NVIDIA ekranlarda NVAPI, AMD ekranlarda ADLX
(okuma bu bilgisayarda çalışıyor, yazma henüz denenmedi; ayrıntı: docs/EKRAN_KARTI.md).

## Geri yükleme noktası notu

Bu testlerde geri yükleme noktası alınamadı: nokta oluşturmak yönetici izni (UAC onayı) ister ve
kullanıcı uzaktaydı. Değiştirilen ayarlar yalnızca kullanıcı düzeyi ekran ayarlarıydı; her biri
aynı arabirimle hemen geri alındı ve son durum karşılaştırılarak doğrulandı.
