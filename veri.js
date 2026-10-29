/* tools/site_veri.py üretir; elle değiştirmeyin. */
window.FM_VERI = {
 "tr": {
  "n": {
   "toplam": 154,
   "gercek": 55,
   "kismen": 31,
   "durumsal": 16,
   "tartisma": 12,
   "placebo": 29,
   "zararli": 11
  },
  "etiket": {
   "gercek": "gerçek",
   "kismen": "bazı durumlarda gerçek",
   "durumsal": "donanıma bağlı",
   "tartisma": "tartışmalı",
   "placebo": "placebo",
   "zararli": "zararlı"
  },
  "tahmin": [
   {
    "id": "PLC-001",
    "ad": "RAM temizleyiciler / 'RAM boşaltıcı' uygulamalar",
    "durum": "zararli",
    "neden": "Windows bellek yöneticisi zaten optimize edilmiştir; RAM 'temizlemek' önbelleği yok eder."
   },
   {
    "id": "DISP-001",
    "ad": "Monitör yenileme hızını en yüksek desteklenen değere ayarla",
    "durum": "gercek",
    "neden": "Yenileme hızı ekran gecikmesini ve hareket netliğini doğrudan belirler."
   },
   {
    "id": "PLC-003",
    "ad": "HPET kapatma / bcdedit useplatformclock",
    "durum": "placebo",
    "neden": "2016-2018 döneminde YouTube'da yayıldı; varsayılan ayarlarda zaten optimize durumdadır. Yalnızca useplatformclock=yes zorlanmış sistemlerde kaldırmak gerçek fayda sağlar."
   },
   {
    "id": "SYS-006",
    "ad": "Başlangıç uygulamalarını azaltma",
    "durum": "gercek",
    "neden": "Arka planda çalışan programlar gerçek kaynak tüketir; en tutarlı tavsiyelerden biridir."
   },
   {
    "id": "SYS-004",
    "ad": "Telemetri: Bağlı Kullanıcı Deneyimleri ve Telemetri (DiagTrack)",
    "durum": "placebo",
    "neden": "Gizlilik için gerçek, FPS için placebo. 'Telemetriyi kapat FPS artar' iddiası kanıtsızdır."
   },
   {
    "id": "PLC-008",
    "ad": "Sayfa dosyasını (pagefile) kapatma",
    "durum": "zararli",
    "neden": "Microsoft sayfa dosyasının commit limiti ve döküm dosyaları için gerekli olduğunu açıklar."
   },
   {
    "id": "PERF-002",
    "ad": "Game DVR / arka plan kaydını kapatma (Game Bar'ı silmeden)",
    "durum": "gercek",
    "neden": "Sürekli kayıt gerçek kaynak tüketir. Ancak yalnızca GameDVR registry değerlerini değiştirmek, kayıt kapalıyken ek fayda sağlamaz."
   },
   {
    "id": "SYS-005",
    "ad": "Xbox servisleri (XblAuthManager, XblGameSave, XboxNetApiSvc, XboxGipSvc)",
    "durum": "placebo",
    "neden": "Debloat listelerinde yaygın; performans faydası yok, işlev kaybı var."
   }
  ],
  "tarama": {
   "bulgular": [
    {
     "baslik": "Ekran olabileceğinden düşük yenileme hızında çalışıyor",
     "aciklama": "Monitör 1 şu an 60 Hz'de, ama bu çözünürlükte 144 Hz destekleniyor. En yaygın hatalardan biri budur; 'Çöz' ile en yüksek değere alınabilir."
    },
    {
     "baslik": "RAM tek kanalda çalışıyor",
     "aciklama": "Tek bellek modülü veya tek kanal, özellikle dahili grafikte ve işlemci ağırlıklı oyunlarda performansı belirgin düşürebilir. Masaüstünde ikinci modülü anakart kılavuzundaki doğru yuvaya takmak çözümdür."
    },
    {
     "baslik": "Başlangıçta çok fazla uygulama açılıyor",
     "aciklama": "14 uygulama bilgisayar açılınca başlıyor. Gereksizleri kapatmak açılışı hızlandırır ve arka plan yükünü azaltır."
    },
    {
     "baslik": "XMP/EXPO kapalı olabilir",
     "aciklama": "RAM 2133 MT/s'de (taban hız) çalışıyor. Bu Windows'tan kesin okunamaz; BIOS'ta XMP (Intel) veya EXPO (AMD) profilinin açık olup olmadığını kontrol edin."
    }
   ],
   "okunur": "Tarama yalnızca okur; hiçbir ayarı değiştirmez ve internete hiçbir şey göndermez."
  },
  "degisiklik": [
   {
    "id": "DISP-001",
    "ad": "Monitör yenileme hızını en yüksek desteklenen değere ayarla"
   },
   {
    "id": "SYS-006",
    "ad": "Başlangıç uygulamalarını azaltma"
   },
   {
    "id": "PERF-002",
    "ad": "Game DVR / arka plan kaydını kapatma (Game Bar'ı silmeden)"
   }
  ],
  "kunye": [
   {
    "id": "DISP-001",
    "ad": "Monitör yenileme hızını en yüksek desteklenen değere ayarla",
    "durum": "gercek",
    "etki": "yüksek",
    "risk": "güvenli",
    "neden": "Yenileme hızı ekran gecikmesini ve hareket netliğini doğrudan belirler."
   },
   {
    "id": "SYS-007",
    "ad": "Arka plan uygulamaları (Store/UWP uygulamaları)",
    "durum": "kismen",
    "etki": "çok düşük",
    "risk": "güvenli",
    "neden": "Mekanizma gerçek ama oyunculara etkisi sınırlı; çoğu arka plan yükü masaüstü programlarından gelir."
   },
   {
    "id": "DISP-005",
    "ad": "Multiplane Overlay (MPO) devre dışı bırakma",
    "durum": "durumsal",
    "etki": "donanıma bağlı",
    "risk": "dikkatli",
    "neden": "Belirli bir hata sınıfı için resmi geçici çözümdür, genel performans ayarı değildir. Windows 11 24H2'de bu anahtar tek başına etkisiz kalabilir."
   },
   {
    "id": "DISP-004",
    "ad": "Tam ekran optimizasyonlarını (FSO) devre dışı bırakma",
    "durum": "tartisma",
    "etki": "belirsiz",
    "risk": "güvenli",
    "neden": "Mekanizma gerçektir; fayda oyuna ve sürücüye bağlıdır. Yaygın 'her oyunda kapat' tavsiyesi kanıtlanmamıştır."
   },
   {
    "id": "SYS-004",
    "ad": "Telemetri: Bağlı Kullanıcı Deneyimleri ve Telemetri (DiagTrack)",
    "durum": "placebo",
    "etki": "yok",
    "risk": "güvenli",
    "neden": "Gizlilik için gerçek, FPS için placebo. 'Telemetriyi kapat FPS artar' iddiası kanıtsızdır."
   },
   {
    "id": "PLC-002",
    "ad": "Registry temizleyiciler",
    "durum": "zararli",
    "etki": "yok",
    "risk": "riskli",
    "neden": "Microsoft'un resmi destek politikası registry temizleyicileri desteklemez ve risklerine dikkat çeker."
   }
  ],
  "oyunlar": [
   "ARC Raiders",
   "Counter-Strike 2",
   "Destiny 2",
   "Marvel Rivals",
   "Once Human",
   "Overwatch 2",
   "PUBG: BATTLEGROUNDS",
   "Rocket League",
   "THE FINALS",
   "The First Descendant",
   "Tom Clancy's Rainbow Six Siege",
   "Warframe",
   "League of Legends",
   "Valorant",
   "Teamfight Tactics",
   "Fortnite",
   "Apex Legends",
   "Minecraft",
   "Cyberpunk 2077",
   "Grand Theft Auto V",
   "Call of Duty: Warzone",
   "Dota 2",
   "Rust",
   "Elden Ring",
   "Deadlock"
  ],
  "olcum": {
   "aciklama": "Ayarları uygulamadan önce bir 'Önce', uyguladıktan (ve gerekiyorsa yeniden başlattıktan) sonra bir 'Sonra' ölçümü alın; uygulama ikisini karşılaştırır. Sonuçlar yalnızca bu bilgisayarda saklanır.",
   "durustluk": "Dürüst uyarı: Tek ölçüm kesin kanıt değildir. Sonuçlar arka plan işlemlerine, sıcaklığa ve sahneye göre değişir. Aynı koşullarda (aynı sahne, aynı süre, aynı açık programlar) her biri için en az 3 ölçüm alıp ortalamalarına bakın. Küçük farklar (%3'ün altı) çoğu zaman ölçüm gürültüsüdür."
  },
  "sinir": {
   "uac": "UAC'yi tamamen kapatmak (EnableLUA=0) bilerek sunulmaz: Microsoft Store uygulamalarını bozar ve tüm programlar yönetici olarak çalışır.",
   "wu": "Windows Update'i tamamen kapatmak (servisleri devre dışı bırakmak) bilerek sunulmaz: geri dönüşü zordur ve Windows bunu çoğu zaman kendisi geri açar.",
   "anticheat": "Rekabetçi oyunlarda anti-cheat sistemleri (Vanguard, EAC, BattlEye, FACEIT, VAC) sürücü imza zorlamasını kapatan, oyun DLL'ine enjekte eden veya oyun sürecini değiştiren araçları engelleyebilir ya da ban sebebi sayabilir."
  }
 },
 "en": {
  "n": {
   "toplam": 154,
   "gercek": 55,
   "kismen": 31,
   "durumsal": 16,
   "tartisma": 12,
   "placebo": 29,
   "zararli": 11
  },
  "etiket": {
   "gercek": "real",
   "kismen": "real in some cases",
   "durumsal": "hardware-dependent",
   "tartisma": "disputed",
   "placebo": "placebo",
   "zararli": "harmful"
  },
  "tahmin": [
   {
    "id": "PLC-001",
    "ad": "RAM cleaners / 'RAM freeing' apps",
    "durum": "zararli",
    "neden": "The Windows memory manager is already optimized; 'cleaning' RAM destroys the cache."
   },
   {
    "id": "DISP-001",
    "ad": "Set the monitor refresh rate to the highest supported value",
    "durum": "gercek",
    "neden": "The refresh rate directly determines display latency and motion clarity."
   },
   {
    "id": "PLC-003",
    "ad": "Disable HPET / bcdedit useplatformclock",
    "durum": "placebo",
    "neden": "Spread on YouTube in 2016-2018; the default settings are already optimized. Removing it gives a real benefit only on systems where useplatformclock=yes was forced."
   },
   {
    "id": "SYS-006",
    "ad": "Reduce startup apps",
    "durum": "gercek",
    "neden": "Programs running in the background consume real resources; one of the most consistent recommendations."
   },
   {
    "id": "SYS-004",
    "ad": "Telemetry: Connected User Experiences and Telemetry (DiagTrack)",
    "durum": "placebo",
    "neden": "Real for privacy, placebo for FPS. The claim 'disable telemetry and FPS goes up' has no evidence."
   },
   {
    "id": "PLC-008",
    "ad": "Turn off the page file (pagefile)",
    "durum": "zararli",
    "neden": "Microsoft explains that the page file is needed for the commit limit and for dump files."
   },
   {
    "id": "PERF-002",
    "ad": "Turn off Game DVR / background recording (without removing Game Bar)",
    "durum": "gercek",
    "neden": "Continuous recording consumes real resources. But only changing the GameDVR registry values gives no extra benefit when recording is already off."
   },
   {
    "id": "SYS-005",
    "ad": "Xbox services (XblAuthManager, XblGameSave, XboxNetApiSvc, XboxGipSvc)",
    "durum": "placebo",
    "neden": "Common in debloat lists; no performance benefit, but features are lost."
   }
  ],
  "tarama": {
   "bulgular": [
    {
     "baslik": "Display runs below its possible refresh rate",
     "aciklama": "Monitör 1 is at 60 Hz, but 144 Hz is supported at this resolution. This is one of the most common mistakes; 'Fix' sets the highest value."
    },
    {
     "baslik": "RAM runs in single channel",
     "aciklama": "A single memory module or single channel can noticeably lower performance, especially with integrated graphics and CPU-heavy games. On a desktop, the fix is to install a second module in the slot shown in the motherboard manual."
    },
    {
     "baslik": "Too many apps start with Windows",
     "aciklama": "14 apps start when the computer boots. Disabling unneeded ones speeds up startup and reduces background load."
    },
    {
     "baslik": "XMP/EXPO may be off",
     "aciklama": "RAM runs at 2133 MT/s (base speed). Windows cannot read this for certain; check in the BIOS whether the XMP (Intel) or EXPO (AMD) profile is enabled."
    }
   ],
   "okunur": "The scan only reads; it changes no settings and sends nothing over the internet."
  },
  "degisiklik": [
   {
    "id": "DISP-001",
    "ad": "Set the monitor refresh rate to the highest supported value"
   },
   {
    "id": "SYS-006",
    "ad": "Reduce startup apps"
   },
   {
    "id": "PERF-002",
    "ad": "Turn off Game DVR / background recording (without removing Game Bar)"
   }
  ],
  "kunye": [
   {
    "id": "DISP-001",
    "ad": "Set the monitor refresh rate to the highest supported value",
    "durum": "gercek",
    "etki": "high",
    "risk": "güvenli",
    "neden": "The refresh rate directly determines display latency and motion clarity."
   },
   {
    "id": "SYS-007",
    "ad": "Background apps (Store/UWP apps)",
    "durum": "kismen",
    "etki": "very low",
    "risk": "güvenli",
    "neden": "The mechanism is real but the effect for gamers is limited; most background load comes from desktop programs."
   },
   {
    "id": "DISP-005",
    "ad": "Disable Multiplane Overlay (MPO)",
    "durum": "durumsal",
    "etki": "hardware-dependent",
    "risk": "dikkatli",
    "neden": "An official workaround for a specific class of bugs, not a general performance setting. On Windows 11 24H2 this key alone may have no effect."
   },
   {
    "id": "DISP-004",
    "ad": "Disable fullscreen optimizations (FSO)",
    "durum": "tartisma",
    "etki": "uncertain",
    "risk": "güvenli",
    "neden": "The mechanism is real; the benefit depends on the game and driver. The common advice 'turn it off in every game' is not proven."
   },
   {
    "id": "SYS-004",
    "ad": "Telemetry: Connected User Experiences and Telemetry (DiagTrack)",
    "durum": "placebo",
    "etki": "none",
    "risk": "güvenli",
    "neden": "Real for privacy, placebo for FPS. The claim 'disable telemetry and FPS goes up' has no evidence."
   },
   {
    "id": "PLC-002",
    "ad": "Registry cleaners",
    "durum": "zararli",
    "etki": "none",
    "risk": "riskli",
    "neden": "Microsoft's official support policy does not support registry cleaners and points out their risks."
   }
  ],
  "oyunlar": [
   "ARC Raiders",
   "Counter-Strike 2",
   "Destiny 2",
   "Marvel Rivals",
   "Once Human",
   "Overwatch 2",
   "PUBG: BATTLEGROUNDS",
   "Rocket League",
   "THE FINALS",
   "The First Descendant",
   "Tom Clancy's Rainbow Six Siege",
   "Warframe",
   "League of Legends",
   "Valorant",
   "Teamfight Tactics",
   "Fortnite",
   "Apex Legends",
   "Minecraft",
   "Cyberpunk 2077",
   "Grand Theft Auto V",
   "Call of Duty: Warzone",
   "Dota 2",
   "Rust",
   "Elden Ring",
   "Deadlock"
  ],
  "olcum": {
   "aciklama": "Take a 'Before' measurement before applying settings and an 'After' measurement after applying them (and restarting if needed); the app compares the two. Results are stored on this computer only.",
   "durustluk": "Honest warning: a single measurement is not proof. Results vary with background activity, temperature and the scene. Under the same conditions (same scene, same duration, same open programs), take at least 3 measurements each and compare the averages. Small differences (below 3%) are often measurement noise."
  },
  "sinir": {
   "uac": "Turning UAC fully off (EnableLUA=0) is intentionally not offered: it breaks Microsoft Store apps and runs every program as administrator.",
   "wu": "Turning Windows Update off completely (disabling its services) is deliberately not offered: it is hard to undo and Windows often turns it back on by itself.",
   "anticheat": "In competitive games, anti-cheat systems (Vanguard, EAC, BattlEye, FACEIT, VAC) may block, or treat as grounds for a ban, tools that disable driver signature enforcement, inject into a game's DLLs or modify the game process."
  }
 }
};
