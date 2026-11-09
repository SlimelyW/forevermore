# Gömülü oyun kapakları — kaynaklar

Oyunlar sayfasındaki kapak sırası: **kullanıcının seçtiği resim → Steam yerel önbelleği → gömülü kapak (bu belge) → exe simgesi → harf kartı.**
Gömülü kapaklar `data/oyun_kapaklari/` altındadır (300x450 JPG, toplam ≈ 0,9 MB); hangi oyuna ait olduğu `data/oyun_kapaklari.json`'da
(exe adı, Steam appid, klasör/takma ad). Eşleştirme yalnızca oyun kaydındaki alanlara bakar; ağdan hiçbir şey indirilmez.

Her resim Steam'in herkese açık resim sunucusundan (`library_600x900.jpg`) alınmış, yayıncıya ait görseldir; telif yayıncınındır.
**Yayıncı isterse ilgili kapak kaldırılır** (aşağıdaki komut). Kaldırılan oyun exe simgesine / harf kartına döner, başka bir şey bozulmaz.

| Dosya | Oyun | Kaynak adresi |
|---|---|---|
| apex-legends.jpg | Apex Legends | https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/1172470/library_600x900.jpg |
| fall-guys.jpg | Fall Guys | https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/1097150/library_600x900.jpg |
| gta-v.jpg | Grand Theft Auto V | https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/271590/library_600x900.jpg |
| overwatch-2.jpg | Overwatch 2 | https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/2357570/library_600x900.jpg |
| call-of-duty.jpg | Call of Duty | https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/1938090/library_600x900.jpg |
| diablo-iv.jpg | Diablo IV | https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/2344520/library_600x900.jpg |
| rocket-league.jpg | Rocket League | https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/252950/library_600x900.jpg |
| pubg.jpg | PUBG: BATTLEGROUNDS | https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/578080/library_600x900.jpg |
| rust.jpg | Rust | https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/252490/library_600x900.jpg |
| warframe.jpg | Warframe | https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/230410/library_600x900.jpg |
| cs2.jpg | Counter-Strike 2 | https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/730/library_600x900.jpg |
| dota-2.jpg | Dota 2 | https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/570/library_600x900.jpg |
| helldivers-2.jpg | Helldivers 2 | https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/553850/library_600x900.jpg |
| path-of-exile.jpg | Path of Exile | https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/238960/library_600x900.jpg |
| lost-ark.jpg | Lost Ark | https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/1599340/library_600x900.jpg |

## Tek komutla kaldırma
`<dosya>` yerine tablodaki dosya adını yaz (ör. `rust.jpg`). Git Bash, proje klasöründe: resmi siler, JSON girdisini de çıkarır:
```
python tools/kapak_kaldir.py rust.jpg
```
Hepsini kaldırmak için `python tools/kapak_kaldir.py --hepsi`. Sonra testleri çalıştır ve commit at.

## Kapak bekleyenler
Resmi dikey (2:3) kapak bulunamadığı için kapak YOK; bu oyunlar exe simgesinde (yoksa harf kartında) kalır:
Valorant, League of Legends, Teamfight Tactics, Fortnite, Minecraft, Roblox, Genshin Impact, Honkai: Star Rail, World of Warcraft,
Wuthering Waves, Escape from Tarkov. (Steam'de olan bir kopya varsa yine de Steam önbelleğinden kapak alır.)

## Yeni kapak ekleme adımları
1. Resmi (dikey, tercihen 300x450, ≤ ~90 KB JPG) `kapak_gelen/<ad>.jpg` olarak koy; kaynak adresini `kapak_gelen/kaynaklar.txt`'ye yaz. `kapak_gelen/` depoya girmez.
2. Dosyayı `data/oyun_kapaklari/<ad>.jpg` altına kopyala.
3. `data/oyun_kapaklari.json`'a girdi ekle: `ad`, `dosya`, `exe` (küçük harf, `*` joker olur), `appid` (varsa), `klasor`, `takma`.
4. Bu belgedeki tabloya satır ekle (dosya, oyun, kaynak adresi) ve "kapak bekleyenler"den oyunu çıkar.
5. `python -m unittest tests.test_gomulu_kapak` ve `python -m app --kontrol` çalıştır (her girdinin dosyası var mı, sahipsiz dosya var mı denetler).
