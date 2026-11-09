# Dönüşüm raporu

Üretim: `tools/convert_tweaks.py` — 2026-11-10. Bu dosya her çalıştırmada yeniden yazılır.

## 1. Özet

Toplam 162 ayar: **SWITCH 93**, **REHBER 59**, **BİLGİ 10**.
SWITCH'lerin 21 tanesi 'dikkatli' (açarken tek onay): DISP-005, SYS-001, SYS-005, SYS-015, PERF-004, PERF-007, PERF-009, GPU-016, CPU-001, CPU-009, NET-003, PLC-003, PLC-004, PLC-005, PLC-006, PLC-007, PLC-015, PLC-016, PLC-017, PLC-025, PLC-030.
Riskli switch (2, açarken ve kapatırken iki aşamalı onay): PERF-003, CPU-004.
Placebo/zararlı switch (31): SYS-003, SYS-004, SYS-005, SYS-010, SYS-015, NET-009, PLC-003, PLC-004, PLC-005, PLC-006, PLC-007, PLC-009, PLC-010, PLC-011, PLC-012, PLC-013, PLC-014, PLC-015, PLC-016, PLC-017, PLC-019, PLC-023, PLC-025, PLC-027, PLC-029, PLC-030, PLC-031, PLC-032, PLC-033, PLC-034, PLC-035.
Yasaklı (hiçbir zaman switch olmaz): PLC-008, PLC-018, PLC-020, PLC-021, PLC-022.

| Kategori | SWITCH | REHBER | BİLGİ |
|---|---|---|---|
| Display | 5 | 3 | 0 |
| System | 14 | 8 | 0 |
| Performans | 8 | 3 | 0 |
| Ekran Kartı | 2 | 20 | 0 |
| İşlemci | 5 | 5 | 0 |
| Güç | 6 | 2 | 0 |
| İnternet/Ağ | 7 | 2 | 0 |
| Mouse ve Klavye | 4 | 5 | 1 |
| Ses | 0 | 5 | 0 |
| Görsel/QoL | 7 | 2 | 0 |
| Gezgin ve Başlat | 8 | 0 | 0 |
| Ses ve bildirim | 2 | 3 | 0 |
| Placebo | 25 | 1 | 9 |

## 2. Doğrulama hataları

Yok. Tüm ayarlar şema doğrulamasından geçti.

## 3. Otomatik dönüştürülemeyen veya belirsiz kalan ayarlar (SENİN ONAYIN GEREKİYOR)

Otomatik türde (registry/powercfg/servis/komut) olup switch yapılMAyanlar ve switch yapılan ama emin olmadığım noktası bulunanlar.

| ID | Ad | Tür | Risk | Karar | Neden / belirsizlik |
|---|---|---|---|---|---|
| DISP-002 | Değişken yenileme hızı (VRR) / G-SYNC / FreeSync | registry | güvenli | SWITCH | DirectXUserGlobalSettings değeri 'Ad=Değer;' biçiminde birden çok ayar içerir; motor diğer ayarlara dokunmadan yalnızca VRROptimizeEnable kısmını değiştirmelidir. VRR destekli monitör olup olmadığı Windows'tan güvenilir okunamaz. |
| DISP-003 | Pencereli oyunlar için optimizasyonlar (Windows 11) | registry | güvenli | SWITCH | Değer hiç yazılmamışsa bazı 24H2 sistemlerinde Windows bunu varsayılan olarak açık kabul ediyor olabilir; uygulama bu durumda 'kapalı' gösterir. Ayarlar > Ekran > Grafik ile karşılaştırarak doğrula. |
| SYS-006 | Başlangıç uygulamalarını azaltma | ayarlar_ui | güvenli | REHBER | Uygulamanın kendi başlangıç ve servis yöneticisinden tek tek yapılır. |
| SYS-011 | Widget'lar, Copilot ve Recall (Windows 11) | registry | güvenli | SWITCH | Kısmi otomasyon: yalnızca Widget ilkesi switch yapıldı. Recall (DISM özelliği, yalnızca Copilot+ PC) ve Copilot (uygulama kaldırma) rehber olarak kaldı. |
| SYS-013 | Defender dışlamaları ve Dev Drive (Defender'ı kapatmak yerine) | komut | dikkatli | REHBER | Dışlanacak oyun klasörünü kullanıcının seçmesi gerekir ('D:\Oyunlar' yalnızca örnek). Yanlış klasör dışlamak güvenlik açığı yaratır. v2'de klasör seçiciyle switch yapılabilir. |
| SYS-016 | Kullanıcı Hesabı Denetimi (UAC) seviyesi | registry | dikkatli | REHBER | Dört seviyeli seçim; Sistem menüsündeki UAC kartıyla yapılır. |
| SYS-017 | Windows Defender gerçek zamanlı korumasını kapatma | komut | riskli | REHBER | Kullanıcı isteğiyle; iki aşamalı uyarıyla Defender kartından yapılır, Kurcalama korumasını kullanıcı kendisi kapatır. |
| SYS-022 | XMP/EXPO profilini açma (BIOS) | bios | dikkatli | REHBER | BIOS ayarıdır; Windows içinden yapılamaz. |
| SYS-023 | Secure Boot'u kapatmama (anti-cheat için) | bios | güvenli | REHBER | BIOS ayarıdır; Windows içinden yapılamaz. |
| PERF-002 | Game DVR / arka plan kaydını kapatma (Game Bar'ı silmeden) | registry | güvenli | SWITCH | Veritabanındaki isteğe bağlı sistem çapı ilke (HKLM AllowGameDVR=0) switch'e dahil edilmedi; yalnızca kullanıcı ayarları değiştirilir. AppCaptureEnabled değeri hiç yazılmamışsa açık kabul edildi. |
| PERF-004 | Sanal Makine Platformu (VMP) / Hyper-V'yi kapatma | komut | dikkatli | SWITCH | Windows Home sürümünde Microsoft-Hyper-V-All yoktur; motor yalnızca sistemde bulunan özellikleri işlemelidir. Bellek Bütünlüğü (HVCI) açıksa hipervizör yine çalışır, kazanç daha da azalır. |
| PERF-006 | Uygulama başına GPU seçimi (hibrit grafikli laptoplar) | registry | güvenli | REHBER | Oyun başına yapılır: Oyunlar menüsüne taşındı. |
| PERF-010 | Oyun sürecine kalıcı 'Yüksek' CPU önceliği (IFEO PerfOptions) | registry | dikkatli | REHBER | Oyun başına yapılır: Oyunlar menüsüne taşındı. |
| GPU-001 | Donanım hızlandırmalı GPU zamanlaması (HAGS) | registry | güvenli | SWITCH | Ekran kartı veya sürücü HAGS'ı desteklemiyorsa değer yazılır ama etkisi olmaz. Değer hiç yoksa uygulama 'kapalı' gösterir; Ayarlar > Ekran > Grafik'teki durumla karşılaştır. |
| GPU-002 | Düşük Gecikme Modu (Low Latency Mode) | nvidia_cp | güvenli | REHBER | NVIDIA sürücü ayarı: NVAPI (DRS) ile uygulamadan seçilir. |
| GPU-003 | Güç yönetimi modu: Maksimum performansı tercih et | nvidia_cp | güvenli | REHBER | NVIDIA sürücü ayarı: NVAPI (DRS) ile uygulamadan seçilir. |
| GPU-004 | Doku filtreleme – Kalite: Yüksek performans | nvidia_cp | güvenli | REHBER | NVIDIA sürücü ayarı: NVAPI (DRS) ile uygulamadan seçilir. |
| GPU-005 | Gölgelendirici (Shader) önbellek boyutu | nvidia_cp | güvenli | REHBER | NVIDIA sürücü ayarı: NVAPI (DRS) ile uygulamadan seçilir. |
| GPU-006 | G-SYNC + V-Sync (sürücüde) + FPS sınırı kombinasyonu | nvidia_cp | güvenli | REHBER | NVIDIA sürücü ayarı: NVAPI (DRS) ile uygulamadan seçilir. |
| GPU-007 | Maksimum kare hızı (sürücü FPS sınırlayıcı) | nvidia_cp | güvenli | REHBER | NVIDIA sürücü ayarı: NVAPI (DRS) ile uygulamadan seçilir. |
| GPU-008 | İş parçacıklı optimizasyon (Threaded Optimization) | nvidia_cp | güvenli | REHBER | NVIDIA sürücü ayarı: NVAPI (DRS) ile uygulamadan seçilir. |
| GPU-009 | Tercih edilen yenileme hızı: Mevcut en yüksek | nvidia_cp | güvenli | REHBER | NVIDIA sürücü ayarı: NVAPI (DRS) ile uygulamadan seçilir. |
| GPU-013 | Radeon Anti-Lag / Anti-Lag 2 | amd_adrenalin | güvenli | REHBER | AMD sürücü ayarı: ADLX ile uygulamadan açılıp kapatılır. |
| GPU-014 | Radeon Chill | amd_adrenalin | güvenli | REHBER | AMD sürücü ayarı: ADLX ile uygulamadan açılıp kapatılır. |
| GPU-015 | Radeon Boost, Enhanced Sync ve AFMF (sürücü kare üretimi) | amd_adrenalin | güvenli | REHBER | AMD sürücü ayarı: ADLX ile uygulamadan açılıp kapatılır. |
| GPU-018 | MSI (Message Signaled Interrupts) modu | registry | riskli | REHBER | Aygıt bazında: PCI aygıt listesinden tek tek yapılır (riskli, iki aşamalı onay, yeniden başlatma). |
| GPU-019 | Temiz sürücü kurulumu (DDU) ve güncel sürücü | surucu | güvenli | REHBER | Araçlar tools klasöründen açılır; Güvenli Mod uygulamadan açılıp kapatılır. |
| GPU-020 | G-SYNC kapsamı: yalnızca tam ekran / tam ekran ve pencere | nvidia_cp | güvenli | REHBER | NVIDIA sürücü ayarı: NVAPI (DRS) ile uygulamadan seçilir. |
| GPU-021 | NVIDIA Görüntü Ölçekleme (NIS) kalite yükseltmesi | nvidia_cp | güvenli | REHBER | NVIDIA sürücü ayarı: NVAPI (DRS) ile uygulamadan seçilir. |
| GPU-022 | NVIDIA bindirmesinin (overlay) oyunlara eklenmesini engelle | nvidia_cp | güvenli | REHBER | NVIDIA sürücü ayarı: NVAPI (DRS) ile uygulamadan seçilir. |
| CPU-008 | C-State'leri kapatma (BIOS) | bios | dikkatli | REHBER | BIOS ayarıdır; Windows içinden yapılamaz. |
| CPU-009 | Zamanlayıcı çözünürlüğü (timer resolution) araçları ve GlobalTimerResolutionRequests | registry | dikkatli | SWITCH | Veritabanı 'genelde gerekmez' diyor ve etkisi 'belirsiz'. Yalnızca dikkatli kullanıcı için, onay penceresiyle sunulur. GlobalTimerResolutionRequests değeri yalnızca Windows 11'de anlamlıdır. |
| CPU-010 | Process Lasso / CPU affinity ile çekirdek atama | ucuncu_parti | dikkatli | REHBER | Oyun başına yapılır: Oyunlar menüsüne taşındı. |
| PWR-001 | Güç planı: Yüksek Performans / Nihai Performans | powercfg | güvenli | SWITCH | Nihai Performans planı (duplicatescheme ile yeni plan oluşturur) v1'e alınmadı; yalnızca hazır Yüksek Performans planı. Modern Bekleme (S0) destekli birçok laptopta Yüksek Performans planı bulunmaz; o zaman ayar gizlenir. |
| PWR-002 | Windows 11 Güç modu: En iyi performans (overlay) | powercfg | güvenli | SWITCH | PowerSetActiveOverlayScheme belgelenmemiş bir API'dir; laptopta pilde modu için değer kayıt defterine yazılır ve güç kaynağı değişince geçerli olması beklenir (doğrulanmadı). |
| PWR-005 | Cihaz Yöneticisi: 'Güç tasarrufu için bilgisayarın bu cihazı kapatmasına izin ver' | ayarlar_ui | güvenli | REHBER | Aygıt bazında: uygulamadaki aygıt listesinden (MSPower_DeviceEnable) tek tek yapılır. |
| NET-002 | Wi-Fi bağdaştırıcısı güç tasarrufu: Maksimum performans | powercfg | güvenli | SWITCH | Veritabanındaki ek bağdaştırıcı ayarları ('MIMO Power Save', 'Roaming Aggressiveness') sürücüye göre değiştiği için switch'e dahil edilmedi; rehber metninde kalır. |
| NET-006 | Nagle algoritmasını kapatma (TcpAckFrequency / TCPNoDelay) | registry | güvenli | SWITCH | Yalnızca tarama anında bağlı (Up) fiziksel ağ kartlarına uygulanır. Sonradan başka bir ağ kartı veya Wi-Fi'a geçilirse o kartta ayar yoktur; uygulamada yeniden tarama gerekir. |
| NET-008 | Enerji Verimli Ethernet (EEE / Green Ethernet) kapatma | komut | güvenli | SWITCH | Özellik adları üreticiye göre değişir. '*EEE' Microsoft'un standart anahtar kelimesidir; 'AdvancedEEE' ve 'EnableGreenEthernet' Realtek'e özgüdür (bu bilgisayarda görüldü). Intel ve diğer üreticilerin farklı adları kapsanmıyor. 0=kapalı varsayımı yalnızca sürücü 0 ve 1 değerlerini kabul ediyorsa uygulanır. |
| INP-005 | MarkC Mouse Fix (eğri registry düzeltmesi) | registry | güvenli | REHBER | Uygulanacak değerler MarkC'nin ayrı dağıtılan .reg dosyalarındadır ve ekran ölçeğine göre değişir; bu dosyaları uygulamaya gömmek lisans ve doğruluk sorunu yaratır. |
| INP-007 | Yapışkan/Filtre/Geçiş tuşları kısayollarını kapatma | registry | güvenli | SWITCH | Veritabanı tam değerler veriyor (506/122/58). Kullanıcı başka erişilebilirlik seçeneklerini değiştirdiyse bu değerler farklı olur; bu yüzden tüm değeri yazmak yerine yalnızca 'kısayol etkin' bitini (4) değiştiren bit işlemi tanımlandı. 510-506=126-122=62-58=4 olduğu için veritabanıyla aynı sonucu verir. |
| AUD-001 | Ses geliştirmelerini (Audio Enhancements / sistem efektleri) kapatma | registry | güvenli | SWITCH | ADIM 3'te değişti: Microsoft'un belgelediği Core Audio API (IPropertyStore) bu bilgisayarda değeri boş döndürdü; Windows'un kendi düğmesi ise değeri registry'de FxProperties altında tutuyor (bu bilgisayarda 'Headphone' cihazında 1 = kapalı olarak görüldü). Bu anahtara Yöneticiler'in yazma izni olduğu okunarak doğrulandı. Bu yüzden switch, yedeklenen bir registry değeri + Windows Ses servisinin yeniden başlatılması olarak tanımlandı. Emin olmadığım: bazı üretici yazılımları (Nahimic, Dolby, Realtek Console) kendi efektlerini yeniden açabilir. Test listesinde denenecek. |
| AUD-002 | Örnekleme hızı ve bit derinliği (Varsayılan biçim) | komut | güvenli | REHBER | Cihaz başına: desteklenen biçimler sürücüye sorulur, seçilen biçim uygulamadan yazılır. |
| AUD-006 | Kullanılmayan ses cihazlarını devre dışı bırakma (NVIDIA/AMD HDMI Audio vb.) | komut | güvenli | REHBER | Hangi ses cihazının 'kullanılmayan' olduğuna yalnızca kullanıcı karar verebilir (ör. monitör hoparlörü bazıları için gerekli). Yanlış cihazı kapatmak sesi tamamen kesebilir. v2'de cihaz listesinden seçmeli yapılabilir. |
| QOL-006 | Oyun sırasında bildirimleri susturma (Rahatsız Etmeyin) | ayarlar_ui | güvenli | REHBER | Oyun başına yapılır: Oyunlar menüsüne taşındı. |
| QOL-009 | Edge Başlangıç Artırması ve arka planda çalışma | registry | güvenli | SWITCH | Edge'deki 'kuruluşunuz tarafından yönetiliyor' mesajının çıkacağından büyük ölçüde eminim ama bu sürümde doğrulamadım; test listesinde kontrol edilecek. |
| PLC-026 | Üçlü arabelleklemeyi (Triple Buffering) DirectX oyunlar için açmak | nvidia_cp | güvenli | REHBER | NVIDIA sürücü ayarı: NVAPI (DRS) ile uygulamadan seçilir. |

## 4. Elle tanım ↔ metinden otomatik çıkarım karşılaştırması

Eşleşen: 43, farklı: 1, metinde komut yok: 87.

| ID | Adım | Durum | Ayrıntı |
|---|---|---|---|
| DISP-001 | yerlesik | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| DISP-002 | registry_bayrak | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| DISP-003 | registry_bayrak | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| DISP-004 | HKCU\...\GameDVR_FSEBehaviorMode | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| DISP-004 | HKCU\...\GameDVR_HonorUserFSEBehaviorMode | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| SYS-003 | servis WSearch | farkli | metin: Disabled/Automatic; tanım: Disabled/AutomaticDelayed |
| SYS-005 | servis XblAuthManager | metinde_yok | Set-Service komutu metinde yok |
| SYS-005 | servis XblGameSave | metinde_yok | Set-Service komutu metinde yok |
| SYS-005 | servis XboxNetApiSvc | metinde_yok | Set-Service komutu metinde yok |
| SYS-005 | servis XboxGipSvc | metinde_yok | Set-Service komutu metinde yok |
| SYS-009 | yerlesik | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| SYS-018 | HKLM\...\LongPathsEnabled | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| SYS-019 | HKLM\...\DisplayParameters | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| SYS-019 | HKLM\...\DisableEmoticon | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| SYS-020 | HKLM\...\PublishUserActivities | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| SYS-020 | HKLM\...\UploadUserActivities | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| SYS-021 | HKLM\...\PreventDeviceMetadataFromNetwork | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| PERF-004 | yerlesik | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| PERF-004 | yerlesik | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| PERF-005 | yerlesik | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| PERF-005 | yerlesik | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| PERF-005 | yerlesik | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| PERF-005 | yerlesik | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| PERF-005 | yerlesik | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| PERF-005 | yerlesik | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| PERF-005 | yerlesik | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| PERF-005 | yerlesik | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| PERF-005 | yerlesik | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| PERF-005 | yerlesik | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| PERF-005 | HKCU\...\TaskbarAnimations | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| PERF-005 | HKCU\...\ListviewAlphaSelect | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| PERF-005 | HKCU\...\ListviewShadow | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| PERF-005 | HKCU\...\EnableAeroPeek | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| PERF-005 | HKCU\...\VisualFXSetting | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| PERF-007 | yerlesik | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| CPU-004 | HKLM\...\FeatureSettingsOverride | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| CPU-004 | HKLM\...\FeatureSettingsOverrideMask | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| PWR-001 | guc_plani | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| PWR-002 | yerlesik | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| NET-003 | yerlesik | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| NET-005 | HKLM\...\DODownloadMode | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| NET-006 | HKLM\...\TCPNoDelay | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| NET-007 | yerlesik | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| NET-008 | yerlesik | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| NET-009 | yerlesik | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| INP-007 | registry_bit | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| INP-007 | registry_bit | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| INP-007 | registry_bit | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| AUD-001 | HKLM\...\{1da5d803-d492-4edd-8c23-e0c0ffee7f0e},5 | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| QOL-002 | registry_anahtar | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| QOL-008 | HKCU\...\SystemPaneSuggestionsEnabled | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| QOL-008 | HKCU\...\SoftLandingEnabled | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| QOL-008 | HKCU\...\SubscribedContent-338388Enabled | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| QOL-008 | HKCU\...\SubscribedContent-338389Enabled | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| QOL-009 | HKLM\...\StartupBoostEnabled | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| QOL-009 | HKLM\...\BackgroundModeEnabled | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| PLC-003 | yerlesik | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| PLC-004 | yerlesik | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| PLC-004 | yerlesik | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| PLC-004 | yerlesik | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| PLC-005 | yerlesik | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| PLC-005 | yerlesik | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| PLC-006 | HKLM\...\SvcHostSplitThresholdInKB | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| PLC-007 | HKLM\...\LargeSystemCache | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| PLC-007 | HKLM\...\DisablePagingExecutive | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| PLC-009 | yerlesik | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| PLC-010 | HKLM\...\SystemResponsiveness | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| PLC-011 | HKLM\...\NetworkThrottlingIndex | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| PLC-012 | HKLM\...\Priority | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| PLC-012 | HKLM\...\Scheduling Category | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| PLC-013 | HKLM\...\NonBestEffortLimit | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| PLC-015 | HKLM\...\DisabledComponents | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| PLC-016 | yerlesik | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| PLC-017 | HKLM\...\MouseDataQueueSize | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| PLC-017 | HKLM\...\KeyboardDataQueueSize | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| PLC-019 | HKLM\...\IRQ8Priority | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| PLC-019 | HKLM\...\IRQ16Priority | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| PLC-025 | servis NVDisplay.ContainerLocalSystem | metinde_yok | Set-Service komutu metinde yok |
| PLC-025 | servis NvContainerLocalSystem | metinde_yok | Set-Service komutu metinde yok |
| PLC-027 | yerlesik | metinde_yok | Bu adım türü otomatik karşılaştırılmıyor |
| PLC-029 | HKLM\...\ClearPageFileAtShutdown | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| PLC-030 | HKLM\...\NtfsDisable8dot3NameCreation | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| PLC-031 | HKLM\...\NtfsDisableLastAccessUpdate | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| PLC-032 | HKLM\...\IoPageLockLimit | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| PLC-033 | HKLM\...\SecondLevelDataCache | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| PLC-034 | HKLM\...\MaxUserPort | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| PLC-034 | HKLM\...\TcpTimedWaitDelay | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |
| PLC-035 | HKLM\...\DefaultTTL | metinde_yok | Komut metinde PowerShell biçiminde yok (yalnızca açıklama var) |

## 5. Yer tutucular

| ID | Sınıf | Metindeki yer tutucu | Nasıl çözülüyor |
|---|---|---|---|
| DISP-004 | SWITCH | `<C:\yol\oyun.exe>` | Switch işlemi yer tutucu gerektirmiyor (metindeki yer tutucu yalnızca açıklama/alternatif yol). |
| SYS-005 | SWITCH | `<servis>` | Switch işlemi yer tutucu gerektirmiyor (metindeki yer tutucu yalnızca açıklama/alternatif yol). |
| PERF-006 | REHBER | `<C:\yol\oyun.exe>` | Rehber metninde gösterilir; kullanıcı kendi değerini kullanır. |
| PERF-010 | REHBER | `<oyun.exe>` | Rehber metninde gösterilir; kullanıcı kendi değerini kullanır. |
| GPU-016 | SWITCH | `<0000>` | Çalışma anında 'amd_gpu_anahtarlari' çözümleyicisi bulur: ['amd_gpu_anahtari']. Bulunamazsa ayar gizlenir. |
| GPU-018 | REHBER | `<cihaz-id>, <örnek>` | Rehber metninde gösterilir; kullanıcı kendi değerini kullanır. |
| CPU-010 | REHBER | `<ad>` | Rehber metninde gösterilir; kullanıcı kendi değerini kullanır. |
| PWR-001 | SWITCH | `<GUID>` | Switch işlemi yer tutucu gerektirmiyor (metindeki yer tutucu yalnızca açıklama/alternatif yol). |
| PWR-005 | REHBER | `<cihaz>` | Rehber metninde gösterilir; kullanıcı kendi değerini kullanır. |
| NET-003 | SWITCH | `<Wi-Fi arabirim adı>` | Switch işlemi yer tutucu gerektirmiyor (metindeki yer tutucu yalnızca açıklama/alternatif yol). |
| NET-006 | SWITCH | `'...\, <InterfaceGuid>` | Çalışma anında 'ag_arabirimleri' çözümleyicisi bulur: ['ag_arabirim_guid']. Bulunamazsa ayar gizlenir. |
| NET-007 | SWITCH | `<Ethernet>` | Çalışma anında 'ag_ozellik_destekleyen' çözümleyicisi bulur: ['ag_bagdastirici', 'ag_ozellik']. Bulunamazsa ayar gizlenir. |
| NET-008 | SWITCH | `<Energy-Efficient Ethernet>, <Ethernet>` | Çalışma anında 'ag_ozellik_destekleyen' çözümleyicisi bulur: ['ag_bagdastirici', 'ag_ozellik']. Bulunamazsa ayar gizlenir. |
| NET-009 | SWITCH | `<Ethernet>` | Çalışma anında 'ag_ozellik_destekleyen' çözümleyicisi bulur: ['ag_bagdastirici', 'ag_ozellik']. Bulunamazsa ayar gizlenir. |
| AUD-001 | SWITCH | `<cihaz>, {endpoint-guid}` | Çalışma anında 'ses_cikis_cihazlari' çözümleyicisi bulur: ['ses_cihazi']. Bulunamazsa ayar gizlenir. |
| AUD-002 | REHBER | `<Hz>, <bit>, <cihaz adı>, {endpoint-guid}` | Rehber metninde gösterilir; kullanıcı kendi değerini kullanır. |
| AUD-005 | REHBER | `<cihaz>` | Rehber metninde gösterilir; kullanıcı kendi değerini kullanır. |
| AUD-006 | REHBER | `<InstanceId>` | Rehber metninde gösterilir; kullanıcı kendi değerini kullanır. |
| PLC-007 | SWITCH | `'...\` | Switch işlemi yer tutucu gerektirmiyor (metindeki yer tutucu yalnızca açıklama/alternatif yol). |
| PLC-014 | SWITCH | `<Ethernet>` | Çalışma anında 'ag_arabirimleri' çözümleyicisi bulur: ['ag_bagdastirici']. Bulunamazsa ayar gizlenir. |
| PLC-018 | BILGI | `<oyun>` | Bilgi kartı; uygulanmaz. |

## 6. Kurala takılıp switch olmaktan çıkarılanlar

Yok.

## 7. Yorumlanamayan donanım metinleri

Yok (yorumlanamayanların hepsi islemler.json'da elle tanımlandı).

## 8. Windows sürüm metinleri nasıl yorumlandı

| Metin | Sürümler | En düşük build |
|---|---|---|
| Windows 10, Windows 11 | 10, 11 | — |
| Windows 10 1903+ (Windows VRR anahtarı), Windows 11 | 10, 11 | W10≥18362 |
| Windows 11 22H2+ | 11 | W11≥22621 |
| Windows 10 1803+, Windows 11 | 10, 11 | W10≥17134 |
| Windows 10, Windows 11 (24H2'de etkinliği tartışmalı) | 10, 11 | — |
| Windows 11 (Auto HDR); HDR Windows 10'da da var | 10, 11 | — |
| Windows 11 | 11 | — |
| Windows 10, Windows 11 (AllowTelemetry=0 yalnızca Enterprise/Education'da tam etkili) | 10, 11 | — |
| Windows 11 (Recall yalnızca 24H2+ Copilot+ PC) | 11 | — |
| Windows 10, Windows 11 (Dev Drive: Windows 11 23H2+) | 10, 11 | — |
| Windows 10 (1607+), Windows 11 | 10, 11 | — |
| Windows 10 1703+, Windows 11 | 10, 11 | W10≥15063 |
| Windows 10 1709+, Windows 11 | 10, 11 | W10≥16299 |
| Windows 10 2004+, Windows 11 | 10, 11 | W10≥19041 |
| Windows 11 önerilir (Windows 10'da Thread Director yok) | 10, 11 | — |
| Windows 10 2004+ (süreç bazlı), Windows 11 (GlobalTimerResolutionRequests) | 11 | — |
| Windows 10 1803+ (Nihai Performans), Windows 11 | 10, 11 | W10≥17134 |
| Windows 10 1709+ (kaydırıcı), Windows 11 | 10, 11 | W10≥16299 |
| İşletim sisteminden bağımsız | 10, 11 | — |
| Windows 7 - Windows 11 | 10, 11 | — |
| Windows 10 (sorun daha olası), Windows 11 (iyileştirme var) | 10, 11 | — |
| Windows 10, Windows 11 (sürücü imzası gereksinimleri nedeniyle zor) | 10, 11 | — |
| Windows 10, Windows 11 (sürücü desteğine bağlı) | 10, 11 | — |
| Windows 10 (Odak Yardımı), Windows 11 | 10, 11 | — |
| Windows 11 23H2+ | 11 | W11≥22631 |
| Windows 10 1903+, Windows 11 | 10, 11 | W10≥18362 |

## 9. Doğrulanmamış 'Ayarı aç' bağlantıları (test listesinde denenecek)

- SYS-013: `windowsdefender://threatsettings`
- PERF-002: `ms-settings:gaming-gamedvr`
- AUD-009: `printers`
- QOL-005: `ms-settings:easeofaccess-visualeffects`
