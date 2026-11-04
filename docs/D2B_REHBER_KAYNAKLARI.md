# D2-B rehber kaynakları (2026-10-28)

Oyun başına dış grafik-ayar rehberi bağlantıları: `data/oyun_rehberi.json` (25 oyun). Yalnızca bağlantı + kısa tanım; site değerleri kopyalanmadı.

## Siteler
| Site | Durum | Oyun sayısı |
|---|---|---|
| prosettings.net | erişilebilir; /games/<oyun>/ ve /guides/<oyun>-options/ | 14 oyun |
| prosettings.gg | curl 466 (bot engeli); WebFetch ile `www.prosettings.gg` erişildi | 3 (CS2, Valorant, LoL) |
| systemrequirementslab.com/cyri | erişilebilir; adres `/cyri/requirements/<slug>/<id>` (YANLIŞ slug da 200 döner, başlıkla doğrulandı) | 23 oyun |
| pcgamecheck.com | `/game-settings` tek sayfalık araç, oyuna özel adresi YOK; bunun yerine `/game/<slug>` (gereksinim/FPS) sayfaları kullanıldı | 19 oyun |
| smoothfps.com | ERİŞİLEMEDİ (bağlantı reddedildi, WebFetch de başarısız); adres üretilmedi | 0 |

## Notlar
- Kullanım koşulları: prosettings.net ve SRL için koşullar sayfası bulunamadı (404 tahmini adresler); pcgamecheck koşulları üçüncü taraf bağlantılarına izin verir. Bağlantı yasağı görülmedi, ama prosettings.net/SRL için teyit edilmedi.
- Bu bilgisayardaki 15 oyunun hepsinde en az 1 bağlantı var. R6 Siege için SRL/pcgamecheck bağlantıları "Siege X" sayfasıdır. Rocket League ve TFT yalnızca SRL (tek kaynak).
- prosettings.net'te Destiny 2, Once Human, Warframe, Rocket League, TFT, The First Descendant için sayfa yok (404).
