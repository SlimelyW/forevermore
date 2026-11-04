# Kanıt incelemesi (BACKLOG A6, ayar bazlı)

## Yöntem
- Kapsam: data/tweaks_app.json içinde gerceklik.durum = durumsal, kısmen gerçek, tartışmalı olan 54 ayar (14 durumsal, 28 kısmen gerçek, 12 tartışmalı).
- 15 ayar için web araması yapıldı (konu başı gruplanmış; Microsoft Learn/devblogs, Blur Busters, randomascii, inceleme siteleri öncelikli). Kalan 39 ayar için bu turda ARAMA YAPILMADI: mevcut kayıtları Microsoft/üretici belgesine dayanıyor ve etiketleri (çoğu "placebo/uyumluluk için gerçek") zaten ihtiyatlı; "değişmez" yazılması "doğrulandı" demek değildir.
- Arama aracı çoğunlukla forum ve rehber sayfaları döndürdü; kontrollü ölçüm nadir. Forum tek başına kanıt sayılmadı, "yalnızca forum" diye işaretlendi. Kaynaklardan metin kopyalanmadı.
- Hiçbir veri/dil dosyası değiştirilmedi; bu belge yalnızca öneridir.

## Emin olunamayanlar
- Ölçüm bulunamadı, mevcut değer korunsun: PERF-009 (Win32PrioritySeparation), CPU-008 (C-state), CPU-007 (SMT; sonuç CPU'ya göre değişiyor), PERF-007 (bellek sıkıştırma), DISP-004 (FSO), NET-006 (Nagle), SYS-017 (Defender, oyun içi ölçüm yok), DISP-005 (MPO, 24H2 durumu forum kaynaklı).
- Ek arama yapılmayan 39 ayar: DISP-009, SYS-001, SYS-007, SYS-008, SYS-009, SYS-011, SYS-012, PERF-004, PERF-005, PERF-010, GPU-003, GPU-004, GPU-005, GPU-008, GPU-016, GPU-018, GPU-019, CPU-002, CPU-006, CPU-010, PWR-001, PWR-003, PWR-004, PWR-005, PWR-008, NET-002, NET-007, NET-008, INP-005, INP-006, INP-010, AUD-001, AUD-002, AUD-005, AUD-006, QOL-004, QOL-005, QOL-009, PLC-024.

## Önerilen değişiklikler (özet)
1. GPU-001 HAGS: tartışmalı/belirsiz yerine durumsal/durumsal; "DLSS Kare Üretimi kullanıyorsan açık kalmalı" notu.
2. CPU-001 çekirdek park etme: açıklamaya "tek CCD'de fark beklenmez, çift CCD X3D'de zararlı olabilir".
3. DISP-008: "gecikme kanıtı yok" yerine "monitörün ölçekleyicisine bağlı, ölçülmüş genel veri yok".
4. PERF-008: "odaktaki oyun zaten Yüksek QoS alır" notu (durum aynı).
5. DISP-005: 24H2'de OverlayTestMode'un tek başına etkisiz kalabileceği notu.

## Tablo
| id | ad | mevcut durum / etki | önerilen | gerekçe | kaynak |
|---|---|---|---|---|---|
| DISP-004 | Tam ekran optimizasyonlarını (FSO) devre dışı bırakma | tartışmalı / belirsiz | değişmez | Arama bağımsız FPS ölçümü bulamadı; Microsoft belgesi eşdeğerlik diyor, topluluk karışık. | https://devblogs.microsoft.com/directx/demystifying-full-screen-optimizations/ |
| DISP-005 | Multiplane Overlay (MPO) devre dışı bırakma | durumsal / durumsal | değişmez (açıklamaya "24H2'de OverlayTestMode tek başına çalışmayabilir" notu eklenebilir) | Geri alınabilir sorun giderme adımı; 2025 raporları anahtarın yeni Windows 11 derlemelerinde etkisiz kalabildiğini söylüyor (yalnızca forum). | https://forums.guru3d.com/goto/post?id=6305178 |
| DISP-008 | Ölçekleme modu: GPU ölçekleme mi monitör ölçekleme mi | kısmen gerçek / çok düşük | açıklama değişsin; durum/etki aynı | "Kanıt yok" yerine "monitörün ölçekleyicisine bağlı; bazı monitörlerde en çok bir yenileme süresi kadar fark, ölçülmüş genel veri yok" daha doğru. | https://forums.blurbusters.com/viewtopic.php?p=68614 |
| DISP-009 | Farklı yenileme hızlı çoklu monitör ve ikinci ekranda v | durumsal / durumsal | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://forums.blurbusters.com/ |
| SYS-001 | Yazdırma Biriktiricisi (Print Spooler) servisini devre  | kısmen gerçek / yok | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://msrc.microsoft.com/update-guide/vulnerability/CVE-2021-34527 |
| SYS-002 | SysMain (eski adıyla Superfetch) | tartışmalı / durumsal | değişmez | Intel SSD rehberi Win8+ için kapatmayı önermiyor; fayda yalnızca yüksek disk/CPU kullanımı sorununda; Microsoft kaynağı yok. | https://www.elevenforum.com/t/does-disabling-sysmain-superfetch-make-any-sense-with-an-nvme-system-drive.6625 |
| SYS-007 | Arka plan uygulamaları (Store/UWP uygulamaları) | kısmen gerçek / çok düşük | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://learn.microsoft.com/en-us/windows/client-management/mdm/policy-csp-privacy#letappsruninbackground |
| SYS-008 | Hızlı Başlatma (Fast Startup / Hiberboot) | kısmen gerçek / yok | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://learn.microsoft.com/en-us/windows-hardware/drivers/kernel/distinguishing-fast-startup-from-wake-from-hibernation |
| SYS-009 | Hazırda bekletmeyi kapatma (hiberfil.sys) | kısmen gerçek / yok | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/powercfg-command-line-options |
| SYS-011 | Widget'lar, Copilot ve Recall (Windows 11) | kısmen gerçek / çok düşük | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://learn.microsoft.com/en-us/windows/client-management/mdm/policy-csp-newsandinterests |
| SYS-012 | OneDrive eşitlemesini oyun sırasında duraklatma | durumsal / durumsal | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://support.microsoft.com/en-us/office/how-to-pause-and-resume-sync-in-onedrive-2152bfa4-a2a5-4d3a-ace8-92912fb4421e |
| SYS-017 | Windows Defender gerçek zamanlı korumasını kapatma | durumsal / durumsal | değişmez | Oyun içi etki raporları küçük; yeni oyun bazlı ölçüm bulunamadı; güvenlik maliyeti baskın. | https://learn.microsoft.com/en-us/defender-endpoint/prevent-changes-to-security-settings-with-tamper-protection |
| PERF-001 | Oyun Modu (Game Mode) | kısmen gerçek / düşük | değişmez | Bağımsız testlerde ortalama FPS kazancı küçük, asıl fark 1% düşüklerde; mevcut "düşük" etiketi uyuyor. | https://support.xbox.com/en-US/help/games-apps/game-setup-and-play/use-game-mode-gaming-on-pc |
| PERF-004 | Sanal Makine Platformu (VMP) / Hyper-V'yi kapatma | kısmen gerçek / düşük | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://support.microsoft.com/en-us/windows/options-to-optimize-gaming-performance-in-windows-11-a255f612-2949-4373-a566-ff6f3f474613 |
| PERF-005 | Görsel efektler: 'En iyi performans için ayarla' | kısmen gerçek / çok düşük | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://support.microsoft.com/en-us/windows/tips-to-improve-pc-performance-in-windows-b3b3ef5b-5953-fb6a-2528-4bbed82fba96 |
| PERF-007 | Bellek sıkıştırmayı kapatma (Memory Compression) | tartışmalı / belirsiz | değişmez | Kontrollü oyun ölçümü bulunamadı; 16 GB ve altında kapatmak risk, büyük RAM'de kazanç kanıtsız. | https://learn.microsoft.com/en-us/powershell/module/mmagent/disable-mmagent |
| PERF-008 | Güç azaltma (Power Throttling / EcoQoS) kapatma | durumsal / durumsal | durum değişmez; açıklamaya "odaktaki oyun zaten Yüksek QoS alır" eklenebilir | Microsoft EcoQoS'un ön plan işlerine uygulanmaması gerektiğini ve odaktaki pencerelere Yüksek QoS verildiğini yazıyor; oyunda fark beklenmez. | https://learn.microsoft.com/en-us/windows/win32/procthread/quality-of-service |
| PERF-009 | Win32PrioritySeparation (ön plan zaman dilimi önceliği) | tartışmalı / belirsiz | değişmez | 0x26/0x2A için ölçüm yok, öneriler tutarsız; kanıt bulunamadı, mevcut değer korunsun. | https://forums.blurbusters.com/viewtopic.php?p=95588 |
| PERF-010 | Oyun sürecine kalıcı 'Yüksek' CPU önceliği (IFEO PerfOp | durumsal / durumsal | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://learn.microsoft.com/en-us/windows/win32/procthread/scheduling-priorities |
| GPU-001 | Donanım hızlandırmalı GPU zamanlaması (HAGS) | tartışmalı / belirsiz | tartışmalı/belirsiz -> durumsal/durumsal | HAGS NVIDIA DLSS Kare Üretimi için gereklidir (açık kalmalı); aksi halde etki küçük ve oyuna bağlı, kontrollü gecikme ölçümü yok. | https://devblogs.microsoft.com/directx/hardware-accelerated-gpu-scheduling/ |
| GPU-003 | Güç yönetimi modu: Maksimum performansı tercih et | kısmen gerçek / düşük | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://www.nvidia.com/en-us/geforce/guides/system-latency-optimization-guide/ |
| GPU-004 | Doku filtreleme – Kalite: Yüksek performans | kısmen gerçek / çok düşük | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://www.nvidia.com/content/Control-Panel-Help/vLatest/en-us/mergedProjects/nv3d/Texture_Filtering_-_Quality.htm |
| GPU-005 | Gölgelendirici (Shader) önbellek boyutu | kısmen gerçek / düşük | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://www.nvidia.com/en-us/geforce/forums/game-ready-drivers/13/ |
| GPU-008 | İş parçacıklı optimizasyon (Threaded Optimization) | tartışmalı / belirsiz | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://www.nvidia.com/content/Control-Panel-Help/vLatest/en-us/mergedProjects/nv3d/Threaded_Optimization.htm |
| GPU-016 | ULPS (Ultra Low Power State) devre dışı bırakma | durumsal / yok | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://learn.microsoft.com/en-us/windows-hardware/drivers/install/system-defined-device-setup-classes-available-to-vendors |
| GPU-018 | MSI (Message Signaled Interrupts) modu | durumsal / belirsiz | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://learn.microsoft.com/en-us/windows-hardware/drivers/kernel/enabling-message-signaled-interrupts-in-the-registry |
| GPU-019 | Temiz sürücü kurulumu (DDU) ve güncel sürücü | kısmen gerçek / durumsal | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://www.wagnardsoft.com/display-driver-uninstaller-DDU- |
| CPU-001 | Çekirdek park etmeyi kapatma (Core Parking – CPMINCORES | tartışmalı / belirsiz | durum değişmez; açıklama güçlensin: "tek CCD'de fark beklenmez, çift CCD X3D'de zarar" | Windows 11 CCD/önbellek farkında zamanlama yapar; park etmeyi kapatmak bunu bozabilir (Blur Busters rehberi + AMD topluluğu, yalnızca forum). | https://forums.blurbusters.com/viewtopic.php?t=15161 |
| CPU-002 | Minimum işlemci durumu (PROCTHROTTLEMIN) | kısmen gerçek / çok düşük | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://learn.microsoft.com/en-us/windows-hardware/customize/power-settings/configure-processor-power-management-options |
| CPU-006 | Intel hibrit (P/E çekirdek) işlemcilerde Windows 11 ve  | durumsal / durumsal | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://learn.microsoft.com/en-us/windows/win32/procthread/quality-of-service |
| CPU-007 | SMT / Hyper-Threading kapatma | tartışmalı / belirsiz | değişmez | Zen 5 incelemesinde (TechPowerUp) SMT kapalı kazanç görüldü ama oyuna ve CPU'ya göre değişiyor; sonuç karışık kalıyor. | https://www.techspot.com/review/1882-ryzen-9-smt-on-vs-off/ |
| CPU-008 | C-State'leri kapatma (BIOS) | tartışmalı / belirsiz | değişmez | Blur Busters başlıklarında etki tekrar üretilemedi/karışık; ölçülmüş oyun kazancı yok. | https://forums.blurbusters.com/viewtopic.php?t=13726 |
| CPU-009 | Zamanlayıcı çözünürlüğü (timer resolution) araçları ve  | tartışmalı / belirsiz | değişmez | Windows 10 2004+ süreç başına davranış ve Windows 11'in GlobalTimerResolutionRequests ile eski davranışa dönüşü doğrulandı; değer yeniden başlatma ister, 0,5 ms bazı oyunlarda takılma yapabilir. | https://randomascii.wordpress.com/2020/10/04/windows-timer-resolution-the-great-rule-change/ |
| CPU-010 | Process Lasso / CPU affinity ile çekirdek atama | durumsal / durumsal | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://bitsum.com/apps/process-lasso/ |
| PWR-001 | Güç planı: Yüksek Performans / Nihai Performans | kısmen gerçek / düşük | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/powercfg-command-line-options |
| PWR-003 | USB seçici askıya alma (USB selective suspend) | kısmen gerçek / çok düşük | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://learn.microsoft.com/en-us/windows-hardware/drivers/usbcon/usb-selective-suspend |
| PWR-004 | PCI Express Bağlantı Durumu Güç Yönetimi (ASPM) | kısmen gerçek / çok düşük | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://learn.microsoft.com/en-us/windows-hardware/customize/power-settings/pci-express-settings-link-state-power-management |
| PWR-005 | Cihaz Yöneticisi: 'Güç tasarrufu için bilgisayarın bu c | kısmen gerçek / çok düşük | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://learn.microsoft.com/en-us/windows-hardware/drivers/kernel/introduction-to-power-management |
| PWR-008 | Sistem soğutma ilkesi: Etkin | durumsal / durumsal | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://learn.microsoft.com/en-us/windows-hardware/customize/power-settings/configure-processor-power-management-options |
| NET-002 | Wi-Fi bağdaştırıcısı güç tasarrufu: Maksimum performans | kısmen gerçek / durumsal | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/powercfg-command-line-options |
| NET-006 | Nagle algoritmasını kapatma (TcpAckFrequency / TCPNoDel | durumsal / durumsal | değişmez | Nagle/gecikmeli ACK yalnızca TCP'yi etkiler; UDP oyun trafiğinde etki beklenmez; kontrollü ölçüm bulunamadı. | https://learn.microsoft.com/en-us/troubleshoot/windows-server/networking/registry-entry-control-tcp-acknowledgment-behavior |
| NET-007 | Ağ kartı: Kesme denetimi (Interrupt Moderation) | kısmen gerçek / çok düşük | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://learn.microsoft.com/en-us/windows-server/networking/technologies/network-subsystem/net-sub-performance-tuning-nics |
| NET-008 | Enerji Verimli Ethernet (EEE / Green Ethernet) kapatma | kısmen gerçek / çok düşük | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://learn.microsoft.com/en-us/powershell/module/netadapter/set-netadapteradvancedproperty |
| INP-005 | MarkC Mouse Fix (eğri registry düzeltmesi) | durumsal / yok | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://donewmouseaccel.blogspot.com/2010/03/markc-windows-7-mouse-acceleration-fix.html |
| INP-006 | Klavye tekrar gecikmesi ve tekrar hızı | kısmen gerçek / yok | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-systemparametersinfoa |
| INP-010 | hidusbf ile USB polling 'overclock' | durumsal / durumsal | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://learn.microsoft.com/en-us/windows-hardware/drivers/install/the-testsigning-boot-configuration-option |
| AUD-001 | Ses geliştirmelerini (Audio Enhancements / sistem efekt | kısmen gerçek / çok düşük | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://learn.microsoft.com/en-us/windows/win32/coreaudio/pkey-audioendpoint-disable-sysfx |
| AUD-002 | Örnekleme hızı ve bit derinliği (Varsayılan biçim) | kısmen gerçek / yok | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://learn.microsoft.com/en-us/windows/win32/coreaudio/pkey-audioengine-deviceformat |
| AUD-005 | Uzamsal ses (Windows Sonic / Dolby Atmos for Headphones | tartışmalı / çok düşük | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://learn.microsoft.com/en-us/windows/win32/coreaudio/spatial-sound |
| AUD-006 | Kullanılmayan ses cihazlarını devre dışı bırakma (NVIDI | kısmen gerçek / yok | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://learn.microsoft.com/en-us/powershell/module/pnpdevice/disable-pnpdevice |
| QOL-004 | Şeffaflık efektlerini kapatma | kısmen gerçek / çok düşük | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://support.microsoft.com/en-us/windows/tips-to-improve-pc-performance-in-windows-b3b3ef5b-5953-fb6a-2528-4bbed82fba96 |
| QOL-005 | Animasyon efektleri ve menü gösterme gecikmesi (MenuSho | kısmen gerçek / yok | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-systemparametersinfoa |
| QOL-009 | Edge Başlangıç Artırması ve arka planda çalışma | kısmen gerçek / çok düşük | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://learn.microsoft.com/en-us/deployedge/microsoft-edge-policies#startupboostenabled |
| PLC-024 | Tek tıkla 'oyun hızlandırıcı' / FPS booster uygulamalar | tartışmalı / belirsiz | değişmez | Bu turda ek arama yapılmadı; mevcut açıklama ve kaynak (Microsoft/üretici belgesi) korunur. | https://hone.gg/ |


## Tur 2 (29 Ekim 2026): kalan 39 ayar, 5 alt ajan taraması

**Durum:** 'belgeli/ölçümlü' düzeyindeki 13 ayar için açıklama notu UYGULANDI (29 Ekim, Kubilay onayıyla; yalnızca `gerceklik.aciklama` sonuna not, etiket/etki seviyesi DEĞİŞMEDİ): SYS-009, PERF-004, PWR-001, PWR-003, GPU-003, GPU-018, GPU-019, CPU-002, CPU-010, NET-007, NET-008, INP-006, AUD-005. Kalanlar (yalnızca forum / bulunamadı) UYGULANMADI, yalnızca öneri. Birincil kaynakla DOĞRULANAN notlar (29 Ekim): PERF-004 (Microsoft Learn WSL kurulum sayfası: WSL 2 için Virtual Machine Platform özelliği şart) ve PWR-001 (XDA makalesi: tek PC, 4 oyun; Fortnite 1% low 72,3→83,4 FPS, öbür üçünde fark yok ya da küçük düşüş; not buna göre düzeltildi). Kalan 11 not da birincil kaynaktan kontrol edildi (29 Ekim): doğru çıkanlar PWR-003 (Microsoft USB belgesi: çıkış gecikmesi onlarca ms), GPU-019 (DDU sayfası: yalnızca sürücü kaldırma aracı), NET-008 (Intel: I225-V hız düşüşü, gecikme yok), INP-006 ve AUD-005 (Microsoft belgeleri); düzeltilenler SYS-009, GPU-003 (FPS Review sonuç sayfası: tutarsız küçük farklar, boşta güç belirgin artar, varsayılan önerilir), GPU-018 (vadyaravadim: tek test sistemi), CPU-002 (Microsoft sunucu belgesi), CPU-010 (iki oyunda artış, birinde fark yok), NET-007 (tek kart, Win10 1909, kesme sayıları). Hepsi şimdi birincil kaynağa uygun. Tur 1'in 5 önerisi Kubilay onayıyla veriye işlendi (GPU-001 durumsal/durumsal; CPU-001, DISP-008, PERF-008, DISP-005 açıklama notları; TR + EN).
**Güvenilirlik uyarısı:** aşağıdakiler alt ajan özetleridir; kaynak sayfaları birincil olarak açıp DOĞRULANMADI. Çoğu kaynak forum, rehber ya da tek kişilik ölçüm; arama kotası bazı ayarlarda taramayı yarıda kesti. "bulunamadı" = kanıt bulunamadı, "etkisi yok" demek değildir. Hiçbir kaynaktan metin kopyalanmadı.

| id | kanıt düzeyi | öneri |
|---|---|---|
| SYS-001 Print Spooler | bulunamadı (FPS), yalnızca blog | açıklama: yazıcı yoksa güvenlik için kapatılabilir, FPS kazancı ölçülmedi |
| SYS-007 Arka plan uygulamaları | yalnızca forum | "ölçülmedi; düşük RAM'li sistemde fayda olabilir" |
| SYS-008 Hızlı Başlatma | bulunamadı | "oyun FPS'i için kanıt yok; açılış/kapanış süresi" |
| SYS-009 Hazırda bekletme | belgeli (komut/dosya), oyun etkisi belgesiz | "oyun etkisi yok; disk alanı kazancı" |
| SYS-011 Widget/Copilot/Recall | bulunamadı (ölçüm) | "ölçüm yok; Recall yalnızca Copilot+ PC'de" |
| SYS-012 OneDrive duraklatma | yalnızca forum | değişmez; "geçici duraklatma" notu |
| QOL-004 Şeffaflık | bulunamadı | "ölçüm yok; düşük GPU'da küçük fark olabilir" |
| QOL-005 MenuShowDelay | bulunamadı | "sistem performansına etkisi yok; menü gecikmesi hissi" |
| QOL-009 Edge Startup Boost | yalnızca forum (tek ölçüm, hata raporu) | "Edge kullanılıyorsa boşta RAM/CPU; vakaya bağlı" |
| PERF-004 VMP/Hyper-V | ölçümlü (VBS/HVCI için, VMP tek başına değil) | "VBS/Hyper-V" ile VMP karışmasın; VMP kapanınca WSL2/Sandbox bozulur |
| PERF-005 Görsel efektler | yalnızca forum | "çok düşük" yerine "ihmal edilebilir, düşük donanımda anlamlı" |
| PERF-010 IFEO Yüksek öncelik | yalnızca forum | değişmez (durumsal); "kanıtlı kazanç yok" notu |
| PWR-001 Güç planı | ölçümlü (tek PC, 4 oyun; yalnızca bir oyunda 1% low farkı) | değişmez; "bazı oyunlarda 1% low" notu |
| PWR-003 USB seçici askıya alma | belgeli (mekanizma) | değişmez; "boşta iken uyanma gecikmesi" olarak anlat |
| PWR-004 ASPM | bulunamadı | etki "bilinmiyor" (çok düşük iddiası kanıtsız) |
| PWR-005 Cihaz güç tasarrufu | yalnızca forum | etki "bilinmiyor" |
| PWR-008 Soğutma ilkesi | yalnızca forum | değişmez (durumsal); "üretici eşiklerine bağlı" |
| DISP-009 Karışık Hz çoklu monitör | yalnızca forum | değişmez; "karışık yenileme hızında GPU saati boşta takılabilir" |
| GPU-003 Maks. performans modu | ölçümlü (FPS Review) | değişmez; tutarlı kazanç yok, boşta güç artar, oyuna özel dene |
| GPU-004 Doku filtreleme | ölçümlü (tek test, ~%2) | değişmez |
| GPU-005 Shader önbelleği | bulunamadı (FPS) | "düşük" yerine "yalnızca takılma, ortalama FPS değil" |
| GPU-008 Threaded Optimization | yalnızca forum | değişmez (belirsiz); Auto bırak |
| GPU-016 ULPS | bulunamadı (performans) | "tek GPU'da yok; eski çoklu GPU'ya özel" |
| GPU-018 MSI modu | ölçümlü (topluluk aracı) | "FPS yok; eski kartta gecikme olabilir, modern sürücüde zaten açık" |
| GPU-019 DDU | belgeli (kullanım amacı) | "performans değil, sürücü sorunu temizliği" |
| CPU-002 Min. işlemci durumu | belgeli (mekanizma, sunucu bağlamı) | "kısmen gerçek / düşük (ölçülmedi)" |
| CPU-006 Intel hibrit | ölçümlü (sentetik) | değişmez (durumsal) |
| CPU-010 Process Lasso | ölçümlü (tek test, X3D) | değişmez; "oyuna ve donanıma özgü" notu |
| NET-002 Wi-Fi güç tasarrufu | belgeli (modlar) | değişmez; dizüstü/Wi-Fi'ye özgü |
| NET-007 Kesme denetimi | ölçümlü (tek kartta) | "kapatma değil orta/adaptif önerilir" (kapalı DPC gecikmesini artırabilir) |
| NET-008 EEE | belgeli (yalnızca link hızı sorunu) | "kısmen gerçek" yerine "belirsiz (gecikme ölçülmedi)" |
| INP-005 MarkC | yalnızca forum | "performans değil, tutarlılık" |
| INP-006 Klavye tekrar | belgeli (tanım) | "performans yok, kullanım tercihi" |
| INP-010 hidusbf | yalnızca forum | "kalıcı değil" uyarısı |
| AUD-001 Ses geliştirmeleri | bulunamadı | "gecikme kanıtı yok; ses tutarlılığı için" |
| AUD-002 Örnekleme hızı | bulunamadı | "performans yok; ses kalitesi/uyumluluk" |
| AUD-005 Uzamsal ses | belgeli (seçenekler), gecikme bulunamadı | "tartışmalı" yerine "kullanım tercihi" |
| AUD-006 Kullanılmayan ses aygıtı | yalnızca forum | "performans yok; yalnızca aygıt karışıklığı" |
| PLC-024 FPS booster'lar | ölçümlü ama zayıf (bloglar) | "çoğu PC'de düşük (%1-3); bazı araçlar 1-2 FPS düşürdü" |

Notlar: HP'nin "%5-15 FPS" iddiası ölçüm yöntemi vermediği için kanıt sayılmadı. Blur Busters/Hardware Unboxed taraması yapılamadı (kota). Etiket değişikliklerinden önce kaynakların birincil okunması ve Kubilay onayı gerekir; yalnızca forum düzeyindeki öneriler zayıf dayanak sayılmalı.
