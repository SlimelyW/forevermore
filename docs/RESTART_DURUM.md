# Yeniden başlatma testleri: durum dosyası (3. tur)

Kural: ayarı **Kubilay uygulamadan kendisi** uygular; Claude yalnızca OKUR ve bu dosyaya/`docs/EL_TESTLERI.md`'ye yazar.
Yeniden başlattıktan sonra Kubilay "devam" der; Claude bu dosyadan sürdürür. Beklenenden farklı bir şey olursa DUR.

## Taban (2026-10-28 13:20, salt okunur, yönetici betiğiyle)
- **Geri yükleme noktaları:** son 6 nokta mevcut; en yenisi #31 "Forevermore - degisiklik oncesi", 2026-10-28 04:17:33.
  Bugünkü ayar yazmaları geri alındı; o noktadan beri kalıcı değişiklik yok.
- **Cihaz:** HP OMEN Gaming Laptop 17-db1xxx; Windows 11 build 26300; RTX 5070 Laptop + Radeon 880M.
- **HVCI (PERF-003, Bellek bütünlüğü):** `HKLM\...\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity\Enabled = 0`
  (uygulamada anahtar "açık" = bellek bütünlüğü KAPALI). `Win32_DeviceGuard`: SecurityServicesConfigured `[0]`,
  SecurityServicesRunning `[0]` (HVCI çalışmıyor), VirtualizationBasedSecurityStatus `1`.
- **bcdedit {current}:** `safeboot` değeri YOK (normal açılış); `nx OptIn`, `bootmenupolicy Standard`.

## Test 1: HVCI (PERF-003), DEVAM EDİYOR
Adımlar (Kubilay yapar):
1. Uygulamayı yönetici olarak aç, PERF-003 "Bellek bütünlüğü (HVCI)" anahtarını **kapat** (bellek bütünlüğü AÇILIR). Çıkan
   uyarıları oku, onayla. Kayıt: `Enabled` 0 → 1.
2. Bilgisayarı yeniden başlat. Dön, Claude'a "devam" de.
Claude'un okuyacağı (yeniden başlatma sonrası): `Enabled` değeri **1**; `Win32_DeviceGuard.SecurityServicesRunning` içinde
**2** (HVCI); aynı zamanda önyükleme sorunsuz.
3. (Sonra) anahtarı geri **aç** (Enabled 1 → 0), yeniden başlat; "devam" de. Beklenen: `Enabled = 0`, `SecurityServicesRunning = [0]`,
   yani tabanla aynı.

Geri alma: önce uygulamadan anahtarı eski haline getir; olmazsa Windows Güvenliği > Cihaz güvenliği > Çekirdek yalıtımı >
Bellek bütünlüğü'nü elle kapat; son çare `rstrui` ile #31 noktası. Windows uyumsuz sürücü bulursa özelliği kendisi açmaz
(uyarı verir); bu durum "sorun" değil bulgu olarak kaydedilir.

## Sıradaki testler (henüz başlamadı)
2. **MSI modu:** aygıt Kubilay'la seçilecek (liste aşağıda). 3. **HP BIOS MUX:** yalnızca okuma. 4. **Güvenli Mod:** en son.

Aday MSI aygıtları (msi şu an KAPALI olanlar; GPU/NVMe/ağ gibi kritikler önerilmez): `High Definition Audio Controller` (3 adet),
`AMD Audio CoProcessor`. Diğerlerinde MSI zaten AÇIK.

## Test 1 sonuç günlüğü
- **Adım A (HVCI aç) GEÇTİ** (2026-10-28 13:30, yeniden başlatma sonrası, salt okunur): `Enabled = 1`;
  `Win32_DeviceGuard`: SecurityServicesConfigured `[2]`, SecurityServicesRunning `[2]` (HVCI çalışıyor),
  VirtualizationBasedSecurityStatus `2` (VBS çalışıyor). Son açılış 13:27. Önyükleme sorunsuz.
  Taban: `Enabled=0`, Running `[0]`, VBS `1`.
- **Adım B (HVCI geri al) GEÇTİ** (2026-10-28 13:35, yeniden başlatma sonrası, salt okunur): `Enabled = 0`,
  SecurityServicesConfigured `[0]`, SecurityServicesRunning `[0]`, VBS `1`. Son açılış 13:34. **Tabanla birebir aynı.**
- **Test 1 SONUÇ: GEÇTİ.** Sistem tabanda. Kubilay'ın gözlemi (yalnızca kullanıcı bildirimi, ölçülmedi): ikinci yeniden
  başlatmada ekran "biraz uzun" siyah kaldı; Başlat menüsündeki uygulamalar kayboldu, görünüm (grid) değiştirilip geri
  alınınca geldi. Önyükleme süresi olay günlüğünden okunamadı (kayıt yok). **HVCI ile bağlantısı doğrulanmadı;** Başlat menüsü
  sorununun bu ayarla ilgisi bilinmiyor (kök neden araştırılmadı). Tekrarlanırsa ayrı not düşülecek.

## Test 2: MSI modu, DEVAM EDİYOR
- **Aygıt (Kubilay seçti):** `AMD Audio CoProcessor`, `PCI\VEN_1022&DEV_15E2&SUBSYS_8E0F103C&REV_70\4&35FE04F8&0&0541`
  (uygulamadaki kimlik `MSI-b4a017e416`). Kritik aygıtlarda (GPU/NVMe/ağ/USB) deneme yapılmıyor.
- **Taban (okuma):** `...\Device Parameters\Interrupt Management\MessageSignaledInterruptProperties\MSISupported` = **0** (REG_DWORD)
  (`anahtar_var`: True).
- **Adımlar (Kubilay yapar):** uygulamada GPU-018 (MSI modu) kartında bu aygıtı **aç**, yeniden başlat, "devam" de. Beklenen:
  `MSISupported = 1`, ses ve diğer aygıtlar çalışıyor. Sonra aynı aygıtı **kapat** (geri al), yeniden başlat, "devam" de; beklenen:
  `MSISupported` taban değerine döner (anahtar yoksa silinmiş olur).
- **Geri alma:** uygulamadan aygıtı eski haline getir; ses sorunu olursa aynı; son çare `rstrui` (#31).

### Test 2 sonuç günlüğü
- **Adım A (MSI aç) GEÇTİ** (2026-10-28 13:46, yeniden başlatma sonrası, salt okunur): `MSISupported = 1` (taban 0);
  uygulamanın aygıt listesi `msi: True`; PnP durumu `OK`, Problem kodu `0`; 5 ses uç noktası `OK`. Son açılış 13:43.
- **Adım B (MSI geri al) GEÇTİ** (2026-10-28 13:52, yeniden başlatma sonrası, salt okunur): `MSISupported = 0`,
  uygulamanın aygıt listesi `msi: False`, PnP `OK`, Problem `0`. Son açılış 13:49. **Tabanla aynı.**
- **Test 2 SONUÇ: GEÇTİ.** Sistem tabanda.

## Test 3: HP BIOS MUX (yalnızca okuma)
- **Uygulamanın gösterdiği:** dahili ekran (DISPLAY1) Radeon 880M tarafından sürülüyor; harici monitör (DISPLAY6) RTX 5070'te. Uygulama
  bunu "hibrit" yorumlar ve zaten "MUX'un varlığı Windows'tan okunamıyor" diye açıkça yazar (`page_category._gpu_mode_section`).
- **HP BIOS WMI (yönetici, salt okunur, 13:53):** `root\HP\InstrumentedBIOS` / `HP_BIOSEnumeration` içinde adı
  `Graphics|GPU|MUX|Hybrid|Discrete|Optimus` ile eşleşen ayar BULUNAMADI (çıktı boş, hata yok). Yani BIOS'tan MUX/grafik modu
  okunamadı; uygulamanın "hibrit" yorumuyla karşılaştırma YAPILAMADI. Ayar adlarının tam listesini almak için ikinci bir yönetici
  okuması denendi ama çalışmadı (UAC onayı verilmemiş olabilir); sonuç dosyası oluşmadı. BIOS'a yazma yok.
- **Test 3 SONUÇ: karşılaştırılamadı** (okuma hatasız, eşleşen ayar yok). Geçti/kaldı diye işaretlenmez.

## Test 4: Güvenli Mod, ATLANDI (Kubilay kararı, 2026-10-28: "bunu yapmayalım"). DENENMEDİ; sonuç yok.
