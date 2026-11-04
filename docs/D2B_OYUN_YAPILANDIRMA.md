# D2-B: Oyun yapılandırma dosyası araştırması

Tarih: 2026-10-28. Yalnızca araştırma; hiçbir oyun dosyasına dokunulmadı, hiçbir şey denenmedi.
Kaynak kalitesi genel olarak ZAYIF: resmi belge yalnızca Minecraft (wiki) ve Fortnite (Epic yardım, yalnızca yol + salt-okunur) için bulundu.
Anahtar adları ve ban riski için çoğu yerde "topluluk kaynağı" var; uygulamaya yazmadan önce her oyunda gerçek dosya üzerinde doğrulanmalı.

## Özet tablo

| Oyun | Dosya | Biçim | Anti-cheat riski | Uygulanabilirlik |
|---|---|---|---|---|
| Minecraft Java | `%APPDATA%\.minecraft\options.txt` | `anahtar:değer` düz metin | Yok (istemci anti-cheat'i yok) | kolay |
| Fortnite | `%LOCALAPPDATA%\FortniteGame\Saved\Config\WindowsClient\GameUserSettings.ini` | UE INI | EAC + BattleEye; dosya düzenleme için resmi açıklama bulunamadı (bilinmiyor) | orta |
| CS2 | `Steam\userdata\<steamid>\730\local\cfg\cs2_*.vcfg/txt` (sürüme göre değişiyor) | Valve KeyValues | VAC; cfg düzenleme için resmi açıklama bulunamadı (bilinmiyor); cfg/autoexec yaygın kullanılır | orta (yol doğrulanmadan önerilmez) |
| Apex Legends | `%USERPROFILE%\Saved Games\Respawn\Apex\local\videoconfig.txt` | `"setting.x" "değer"` | EAC; resmi açıklama yok (bilinmiyor) | orta |
| Cyberpunk 2077 | `%LOCALAPPDATA%\CD Projekt Red\Cyberpunk 2077\UserSettings.json` | JSON | Çevrimiçi/anti-cheat yok (tek oyunculu); hız koşusu kurallarında yasak olabilir | orta (biçim resmi belgelenmemiş) |

## Minecraft Java Edition (en güvenilir)

1. Yol: `.minecraft` klasörü içinde `options.txt`. Varsayılan Windows başlatıcısında `%APPDATA%\.minecraft\` (bu tam yol wiki sayfasında yazmıyor, genel bilgi; özel başlatıcılar/profiller farklı game dizini kullanır: doğrulanmalı). Biçim: düz metin, `anahtar:değer`, her satır bir ayar. Kaynak: minecraft.wiki "Options.txt (Java Edition)".
2. Doğrulanmış anahtarlar (wiki):
   - `renderDistance` 2-32 (varsayılan 12)
   - `simulationDistance` 5-32 (12)
   - `maxFps` 10-260 (120; 260 = sınırsız)
   - `graphicsPreset` fast/fancy/fabulous/custom (1.21.11 ile geldi; eski sürümlerde `graphicsMode` 0-2 veya `fancyGraphics`: sürüme göre değişir, sürüm sezilmeli)
   - `enableVsync` true/false
   - `particles` 0-2 (0 hepsi, 2 en az)
   - `ao` true/false (yumuşak ışık)
   - `mipmapLevels` 0-4
   - `biomeBlendRadius` 0-7
   - `entityShadows` true/false
   - `entityDistanceScaling` 0.5-5.0
   - `cloudRange` 2-128
   - `fullscreen` true/false
   - `fov` 30-110 (derece)
3. Oyun açıkken: wiki'ye göre oyun dosyayı çıkışta yazar; açıkken yapılan düzenleme ezilir. Salt-okunur gerekmez, oyun kapalıyken düzenlemek yeterli. Güncellemede anahtar adı değişebilir (yukarıdaki graphicsPreset örneği); bilinmeyen anahtarlara dokunulmamalı, yalnızca var olan satırlar değiştirilmeli.
4. Anti-cheat: istemcide yok. Sunucu tarafı eklentiler (özel sunucular) kuralları kendi koyar; tek oyunculuda risk yok. Kaynak: resmi açıklama aranmadı; bilgi genel (düşük güven, "bilinmiyor" kabul edin ama pratikte risk çok düşük).
5. Kademeli öneri: kaynaklı öneri yok (wiki yalnızca değer aralığı ve varsayılanı veriyor).

## Fortnite

1. Yol: `%LOCALAPPDATA%\FortniteGame\Saved\Config\WindowsClient\GameUserSettings.ini`. Kaynak: Epic resmi yardım ("Fortnite ayarlarımı kaydetmiyor") yolu ve dosya adını doğruluyor. Biçim: Unreal INI.
2. Anahtarlar: resmi şema YOK. Topluluk (2017 tarihli örnek dosya): bölüm `[/Script/FortniteGame.FortGameUserSettings]` içinde `ResolutionSizeX`, `bUseVSync`, `FrameRateLimit`; ayrı `[ScalabilityGroups]` bölümünde `sg.AntiAliasingQuality`, `sg.ShadowQuality`, `sg.PostProcessQuality`, `sg.ResolutionQuality`, `sg.FoliageQuality`. Değer aralıkları (UE genel belgesinde sg.* için 0-4) Fortnite için DOĞRULANMADI. Epic: oyun içi üst FPS sınırı 360.
3. Oyun açıkken: kapanırken/açılırken dosyayı yeniden yazar. Epic kendi yardımında salt-okunur işaretini KALDIRMAYI öneriyor (ayar kaydolmuyor sorunu); topluluk ise düzenlemeden sonra salt-okunur yapmayı öneriyor (aksi halde açılışta ezilir). Salt-okunur yapınca oyun içi ayar değişikliği kaydolmaz: kullanıcıya uyarı gerekir. Güncellemede bozulursa Epic başlatıcı "Doğrula" ile yenilenir.
4. Anti-cheat: Easy Anti-Cheat ve BattleEye. INI düzenlemesinin ban riski için resmi açıklama BULUNAMADI: bilinmiyor. Epic'in duyuruları hile yazılımı/hesap satışına odaklı. Oyun içi seçeneklerin yalnızca dosyada karşılığı varsa düzenleme (dosyadaki yalnız oyun içinde bulunan seçenekler) görece güvenli sayılır, ama bu çıkarımdır, kaynak değil.
5. Kademeli öneri: kaynaklı resmi öneri yok (esportstales vb. topluluk/blog önerileri var, kaynak sayılmaz).

## Counter-Strike 2

1. Yol: video ayarları Steam `userdata\<SteamID>\730\local\cfg\` altında; kaynaklar çelişiyor: bir kaynak `cs2_video.txt` diyor, csdb.gg rehberi video/ses/donanım için `cs2_machine_convars.vcfg` diyor. Hangisinin güncel olduğu DOĞRULANMADI; gerçek makinede bakılmalı. Steam Cloud eski ayarı geri getirebilir (csdb.gg). Biçim: Valve KeyValues (`"anahtar" "değer"`).
2. Anahtar adları: kaynaklarda yalnızca `setting.fullscreen_min_on_focus_loss` örneği var; grafik/FPS anahtarları (vsync, gölge, `fps_max` konsol komutu dışında) doğrulanamadı. `fps_max` bir konsol komutu olarak belgeli (csdb.gg), autoexec.cfg ile verilebilir.
3. Oyun açıkken: dosya kilidi nedeniyle kapalıyken düzenlenmeli (topluluk); salt-okunur ayarın sıfırlanmasına yol açtığı bildirilmiş (ayarlar kaydolmuyor). Silinince oyun varsayılan üretir.
4. Anti-cheat: VAC. Valve'in cfg/autoexec için resmi "serbest" beyanı bulunamadı: bilinmiyor. cfg kullanımı (autoexec) oyunda yaygın ve oyun içi konsol komutu olarak desteklenir; ancak 2026 Ocak'ta VAC yanlış-pozitif dalgası oldu (Valve düzeltti). Güvenli yol: `autoexec.cfg`/konsol komutu; ham dosya yazma önerilmez.
5. Kaynaklı kademe önerisi yok.

## Apex Legends

1. Yol: `%USERPROFILE%\Saved Games\Respawn\Apex\local\videoconfig.txt` (EA forum moderatörü + esportstales; Steam ve EA App için aynı). Bir EA forum yanıtı `.cfg` diyor: DOĞRULANMADI. Biçim: `"setting.anahtar" "değer"`. Kaynaklar topluluk, resmi belge yok.
2. Anahtarlar (esportstales): `setting.cl_ragdoll_self_collision` (0), `setting.mat_depthfeather_enable` (0), `setting.r_lod_switch_scale` (1 yüksek, 0.8 orta, 0.6 düşük; 0.3-0.4 önerilmiş, oynanışta sorun çıkarabilir), `setting.csm_enabled` (0 = gölge kapalı). Diğerleri (vsync, fps_max, stream_memory) videoconfig'de doğrulanmadı; fps_max bir başlatma seçeneği (`+fps_max`).
3. Oyun açıkken: açılışta dosyayı ezer; topluluk salt-okunur önerir. Salt-okunur dosyada oyunun varsayılan çözünürlüğe düştüğü bildirildi (EA forumu). Çelişki var: risk. Dosya silinirse yeniden üretilir.
4. Anti-cheat: Easy Anti-Cheat. Resmi açıklama yok; bilinmiyor. `r_lod_switch_scale` / `csm_enabled` gibi değerler rekabet avantajı sağlar (gölge/LOD): riskli bölge, uygulama bunlara dokunmamalı.
5. Kaynaklı kademe: yalnızca lod değerlerinin oyun içi karşılıkları (yukarıda).

## Cyberpunk 2077

1. Yol: `%LOCALAPPDATA%\CD Projekt Red\Cyberpunk 2077\UserSettings.json` (Steam/GOG forum yazıları, tutarlı). Biçim: JSON; ayarlar grup yolu + `value` alanıyla (topluluk: ışın izleme yansımalarını `value`'yu true yaparak açma örneği). CDPR'nin resmi şema belgesi BULUNAMADI.
2. Anahtar adları ve değer aralıkları DOĞRULANMADI.
3. Bozulursa dosyayı silmek yaygın çözüm (oyun yeniden üretir); salt-okunur kullanımı için kaynak yok. Güncellemede yeniden yazılma riski bilinmiyor.
4. Anti-cheat: yok (tek oyunculu). Hız koşusu kurallarında düzenleme yasak olabilir (speedrun.com tartışması).
5. Kaynaklı kademe önerisi yok.

## Elenenler

- Valorant: Vanguard çekirdek sürücülü anti-cheat; ayarların büyük kısmı sunucu tarafı/hesapta; yerel `GameUserSettings.ini` (`%LOCALAPPDATA%\VALORANT\Saved\Config\<id>\Windows`) var ama düzenlemenin Vanguard açısından durumu bilinmiyor, risk/fayda kötü. ELENDİ (araştırılmadı, bilinen bilgi).
- League of Legends: Vanguard ve ayarlar sunucuda/`PersistedSettings.json` karışık; araştırılmadı, ELENDİ.
- Overwatch 2: ayarlar `Documents\Overwatch\Settings\Settings_v0.ini`; biçim INI ama sürüm belgesi/anti-cheat bilgisi doğrulanmadı, araştırılmadı, ELENDİ.
- 5 sınırı nedeniyle bu üçü eşit güvenle incelenmedi; "elendi" yerine "kapsam dışı bırakıldı" olarak okunmalı.

## Doğrulanmayanlar (uygulamadan önce makinede kontrol)

- CS2: video dosyasının adı ve yolu (`cs2_video.txt` mı `cs2_machine_convars.vcfg` mi), grafik anahtar adları.
- Fortnite: güncel `GameUserSettings.ini` anahtarları ve değer aralıkları (2017 örneği eski).
- Apex: `.txt` mi `.cfg` mi; vsync/fps_max anahtarları.
- Cyberpunk: JSON şeması ve anahtar adları.
- Minecraft: tam Windows yolu wiki'de yazmıyor; sürüme göre `graphicsPreset` / eski anahtarlar.
- Tüm anti-cheat: dosya düzenlemesi için resmi (EAC, VAC) "serbest/yasak" beyanı hiçbir oyunda bulunamadı.

## Öneri

1. Minecraft Java (düz metin, resmi wiki, anti-cheat yok): ilk uygulanacak. Kapalıyken yedekle, yalnızca var olan anahtarları değiştir.
2. Cyberpunk 2077 (tek oyunculu, JSON, anti-cheat yok) ya da Fortnite; ikincisi yolu Epic ile doğrulanmış ama EAC belirsiz. Anahtar adlarını gerçek dosyadan okuyarak (kendi dosyasındaki anahtarlar) çalışmak şart.
