# Evde elle testler (kullanıcı onayıyla, yönetici olarak)

Tarih: 2026-10-28. Yöntem: önce geri yükleme noktası, her değişiklik motorun `apply_custom` yolundan (gerçek
`WindowsSystem`, geçici yedek deposu), yazdıktan sonra Windows'tan yeniden okunarak doğrulandı, hemen `engine.revert` ile
geri alındı. Tek UAC onayıyla yükseltilmiş bir betik çalıştı (betik depoda yok; scratchpad). Test bilgisayarı: 2 monitörlü
masaüstü (DISPLAY1 1920x1080 birincil, DISPLAY6 1440x2560 ikincil, dikey-ters, konum -1440,-700).

| Test | Sonuç | Kanıt |
|---|---|---|
| Geri yükleme noktası | **Oluşturuldu** (`olusturuldu`) | Motor `restore_point.ensure` → `Checkpoint-Computer`. Listesini yönetici olmayan kabuktan okuyamadım ("Access denied"); noktanın Windows'ta görünüp görünmediğini `rstrui` ile elle doğrulayın. |
| UAC seviyesi (SYS-016) | **Geçti** | Varsayılan → "Her zaman bildir": `ConsentPromptBehaviorAdmin` 5→2, `PromptOnSecureDesktop` 1; okunan seviye `her_zaman`. Geri alınca 5 ve 1, seviye `varsayilan`. "Hiç bildirme" DENENMEDİ. |
| Ekran konumu (ikincil ekran) | **Geçti** | y -700 → -699 yazıldı ve Windows'tan okundu; geri alınca -700. Boyut ve yön değişmedi. |
| Ekran yönü (ikincil ekran) | **Geçti** | dikey-ters → dikey yazıldı ve okundu (boyut 1440x2560 aynı kaldı, iki yön de dikey); geri alınca dikey-ters. |
| Ekran son durumu | **Aynı** | Başlangıç ve son yerleşim birebir eşit; ayrı bir kabukta yeniden okundu: DISPLAY1 (0,0) yatay, DISPLAY6 (-1440,-700) dikey-ters. |
| Defender | **Yalnızca okuma** | Gerçek zamanlı koruma açık, **Kurcalama koruması açık**, mod Normal. Kapatma yazması BİLEREK çalıştırılmadı (onayınız "yalnızca ret kontrolü" idi ve hiçbir şey değiştirmemek vaadi vardı); uygulamanın Kurcalama açıkken yazmayı denemeyip Windows Güvenliği'ne yönlendirdiği yol bu testte doğrulanmadı. |

## Yapılmayanlar / sınırlar
- **Arayüz denenmedi:** testler motor düzeyinde; 15 saniyelik "Kalsın / Geri dön" penceresi, şema tıklaması ve düğmeler
  elle bakılmadı (`docs/TEST_KONTROL_LISTESI.md` 5w'nin arayüz maddeleri hâlâ sizde).
- **Tek monitör senaryosu** ve **yer değiştiren/çakışan konum** gerçek ekranda denenmedi (çakışma reddi yalnızca birim testte).
- **Birincil ekran** değiştirilmedi (konumu zaten sabit).
- Ekranın karardığı süre veya titreme ölçülmedi.
- Defender kapatma ve geri açma (Kurcalama koruması kapalıyken) ile "Hiç bildirme" UAC seviyesi ve Windows Update,
  ses, MSI, HP BIOS MUX, HVCI, NVIDIA/AMD yazma, Güvenli Mod testleri (CLAUDE.md "evde denenecek" listesi) bu turda YOK.

---

# 2. tur (aynı gün, kullanıcı onayıyla; yönetici)

Aynı yöntem: motor üzerinden yaz → Windows'tan oku → hemen geri al → oku. Her geri almadan sonra değer başlangıçla
karşılaştırıldı ve ayrı bir kabukta yeniden okundu. Her turda motor bir geri yükleme noktası oluşturdu (bugün 3 nokta var).

| Test | Sonuç | Kanıt |
|---|---|---|
| Windows Update: "Yalnızca güvenlik" modu | **Geçti** | `varsayilan` → `guvenlik` okundu → geri alınca `varsayilan`. Güncelleme indirilmedi/kurulmadı. |
| Windows Update: "Duraklat" modu | **Geçti** | `varsayilan` → `duraklat` okundu → geri alınca `varsayilan`. |
| Ses biçimi (aygıt 1, 4 aygıttan) | **Geçti** | 48000/16 → 44100/16 yazıldı ve okundu → geri alınca 48000/16. Aygıt kapatma ve özel mod DENENMEDİ. |
| NVIDIA G-SYNC kapsamı (GPU-020, RTX 5070 Laptop) | **Geçti** | Sürücü profilinde 2 → 1 yazıldı ve okundu → geri alınca 2 (kullanıcı değeri olarak, `ozel`: true korundu). |
| AMD Anti-Lag (Radeon 880M, ADLX) | **Geçti** | kapalı → açık okundu → geri alınca kapalı. |
| UAC "Hiç bildirme" | **Geçti** | `varsayilan` → `hic` okundu → geri alınca `varsayilan` (birkaç saniye UAC sessizdi). |
| Son durum | **Hepsi başlangıçta** | Ayrı kabukta okundu: UAC `varsayilan`, WU `varsayilan`, G-SYNC 2, Anti-Lag kapalı, ses 48000/16. |

**Betik hatası notu:** İlk koşuda ses testi "aygıt bulunamadı" diye atlandı; sebep ürün değil, benim betiğimin
aygıt listesini yanlış kaynaktan (`list_audio_pnp_devices`) almasıydı. Düzeltilip tek başına yeniden çalıştırıldı (yukarıdaki satır).

**Hâlâ yapılmayanlar:** Güvenli Mod aç/kapat, Bellek bütünlüğü (HVCI), MSI modu, HP BIOS MUX okuma (yeniden başlatma
veya aygıt işi; onay cevabınız net olmadığı için bu turda çalıştırılmadı), NVIDIA/AMD'nin diğer ayarları, Defender kapatma
(Kurcalama kapalıyken), AMD Chill/Boost, arayüz (15 sn onay penceresi, düğmeler), ses aygıtı kapatma.

# Derleme (aynı gün)

`tools/derle.ps1` çalıştırıldı: veritabanı yeniden üretildi (154 ayar), 263 test geçti, PyInstaller derlemesi tamam,
paket imzalandı: **214 dosya, denetim: orijinal, parmak izi 5FE5-D786-0B89-A56E**, paket öz denetimi OK.
`dist\Forevermore.zip` 37,8 MB, SHA256 `06B34A61212F95ADC37DB61A46DADBFCE7698C1C887946BE7CE59E3057E07916`
(`dist\` depoya girmez). Pakette bulunan `.exe` açılıp arayüzü elle denenmedi.
Derleme günlüğünde testler sırasında bir uyarı izi var (`page_boost.py` → "libshiboken: Internal C++ object … already deleted",
yalnızca test ortamında, sayfa hızlı kapanırken); testler geçiyor, ürün davranışını etkilediği gözlenmedi, ayrıca incelenmedi.

---

# 3. tur: yeniden başlatma gerektiren testler (kullanıcı uygular, Claude yalnızca okur)

Kural: ayarı Kubilay uygulamadan kendisi değiştirdi; Claude salt okudu (kayıt defteri + `Win32_DeviceGuard`), yazma yapmadı.
Ayrıntılı günlük: `docs/RESTART_DURUM.md`. Test öncesi geri yükleme noktaları doğrulandı (son nokta #31, bugün 04:17).

| Test | Sonuç | Kanıt (salt okunur) |
|---|---|---|
| HVCI (PERF-003) açma | **Geçti** | Taban `Enabled=0`, Running `[0]`, VBS `1` → yeniden başlatma sonrası `Enabled=1`, Running `[2]`, VBS `2`. |
| HVCI geri alma | **Geçti** | Yeniden başlatma sonrası `Enabled=0`, Running `[0]`, VBS `1`: tabanla birebir aynı. |

**Kullanıcı gözlemleri (ölçülmedi, bağlantı doğrulanmadı):** ikinci yeniden başlatmada siyah ekran uzun sürdü; Başlat menüsü
uygulamaları kayboldu ve görünüm değiştirilip geri alınca geldi. HVCI açılıp kapanırken VBS yeniden yapılandırıldığı için açılışın
uzaması makul bir beklentidir ama bu testte ölçülmedi; Başlat menüsü sorununun HVCI ile ilgisi bilinmiyor.
| MSI modu açma (`AMD Audio CoProcessor`) | **Geçti** | Taban `MSISupported=0` → yeniden başlatma sonrası `1`; PnP `OK`, Problem `0`, 5 ses uç noktası `OK`. |
| MSI modu geri alma | **Geçti** | Yeniden başlatma sonrası `MSISupported=0`, PnP `OK`: tabanla aynı. |
| HP BIOS MUX (yalnızca okuma) | **Karşılaştırılamadı** | `HP_BIOSEnumeration`'da Graphics/GPU/MUX/Hybrid/Discrete/Optimus eşleşen ayar yok (hata yok, çıktı boş); uygulama "hibrit" gösteriyor ama BIOS'tan doğrulanamadı. |

**Yapılmayanlar (3. tur):** Güvenli Mod aç/kapat: kullanıcı kararıyla ATLANDI, test edilmedi (uygulamadaki Güvenli Mod yolu hâlâ ev testinde doğrulanmış değil).

## 30 Ekim 2026: Önce/Sonra (PresentMon) ve arkadaş raporu düzeltmeleri, yönetici denemesi
Ayrıntı ve tablo: docs/ARKADAS_RAPORU_DUZELTMELERI.md ("Yönetici denemesi"). Geri yükleme noktası alındı; tek yazma NVIDIA 0x90DE9159 idi, hemen geri alındı ve geri okundu (varsayılan). Tam ekranda NVIDIA ve AMD ölçümü geçti; pencereli modda kareler yakalandı ama deneme penceresi öne getirilemediği için tam süreli ölçüm yapılmadı.
